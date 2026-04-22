import os
import json
import logging
import asyncio
from typing import AsyncGenerator, List
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from pydantic import BaseModel
from jose import jwt, JWTError
from app.services.database import get_async_session, store_chat_conversation
from app.services.personality_loader import load_personality, apply_personality_rules
from sqlalchemy.future import select

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


# Create router
xai_router = APIRouter()

# XAI API configuration - used via lazy loading
_xai_config = None


def _clean_env_value(value, default=None):
    if value is None:
        return default
    cleaned = value.strip().replace('"', '').replace("'", "")
    return cleaned or default


def _build_xai_http_error(upstream_status: int, error_text: str, model_name: str) -> HTTPException:
    detail = (error_text or "Unknown XAI upstream error").strip()
    if upstream_status in {401, 403, 404, 429}:
        return HTTPException(
            status_code=503,
            detail=f"XAI model unavailable for `{model_name}`: {detail}",
        )
    return HTTPException(
        status_code=502,
        detail=f"XAI API error for `{model_name}` ({upstream_status}): {detail}",
    )

def get_xai_config():
    """Get XAI configuration with lazy loading to ensure env vars are loaded"""
    global _xai_config
    if _xai_config is None:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = _clean_env_value(os.getenv("XAI_API_KEY"))
        proxy_url = os.getenv("PROXY_URL")
        proxy_auth = os.getenv("PROXY_AUTH")
        image_model = _clean_env_value(os.getenv("XAI_IMAGE_MODEL"), "grok-2-image")
        
        _xai_config = {
            "api_key": api_key,
            "proxy_url": proxy_url,
            "proxy_auth": proxy_auth,
            "base_url": "https://api.x.ai/v1",
            "image_model": image_model,
        }
        
        if not _xai_config["api_key"]:
            logger.warning("XAI_API_KEY not found in environment variables")
            
    return _xai_config

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: str = None
    project_name: str = None
    personality_id: str = None  # Optional, for AI personality customization

async def get_xai_response(messages, model_name):
    """Get response from XAI API"""
    config = get_xai_config()
    XAI_API_KEY = config["api_key"]
    XAI_BASE_URL = config["base_url"]
    PROXY_URL = config["proxy_url"]
    PROXY_AUTH = config["proxy_auth"]

    if not XAI_API_KEY:
        raise HTTPException(status_code=503, detail="XAI_API_KEY is not configured")
    
    logger.info(f"Making XAI API request with {len(messages)} messages for model: {model_name}")
        
    try:
        # Configure proxy if available
        client_kwargs = {
            "timeout": httpx.Timeout(90.0, connect=10.0),
            "limits": httpx.Limits(max_keepalive_connections=5, max_connections=10),
            "verify": True,
            "follow_redirects": True
        }
        
        if PROXY_URL:
            # Parse proxy authentication if provided
            if PROXY_AUTH and ":" in PROXY_AUTH:
                username, password = PROXY_AUTH.split(":", 1)
                proxy_url_with_auth = PROXY_URL.replace("://", f"://{username}:{password}@")
            else:
                proxy_url_with_auth = PROXY_URL
            
            client_kwargs["proxy"] = proxy_url_with_auth
            logger.info(f"Using proxy for XAI API: {PROXY_URL}")
    
        max_retries = 3
        base_delay = 2

        # Convert messages to the format expected by XAI
        xai_messages = []
        for msg in messages:
            xai_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    logger.info(f"Sending request to XAI API... (attempt {attempt + 1}/{max_retries})")
                    response = await client.post(
                        f"{XAI_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {XAI_API_KEY}",
                            "Content-Type": "application/json",
                            "User-Agent": "PhatagiAI/1.0"
                        },
                        json={
                            "model": model_name,
                            "messages": xai_messages,
                            "stream": True,
                            "max_tokens": 1000
                        }
                    )

                logger.info(f"XAI API response status: {response.status_code}")

                if response.status_code == 200:
                    return response
                if response.status_code >= 500 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"XAI upstream error {response.status_code}, retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    continue

                error_text = response.text
                logger.error(f"XAI API error: {response.status_code} - {error_text}")
                raise _build_xai_http_error(response.status_code, error_text, model_name)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"XAI network error on attempt {attempt + 1}: {exc}; retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    continue
                raise
            
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        logger.error(f"XAI API connection error: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to connect to XAI API: {e}") from e
    except httpx.TimeoutException as e:
        logger.error(f"XAI API timeout error: {e}")
        raise HTTPException(status_code=503, detail=f"XAI API request timed out: {e}") from e
    except Exception as e:
        logger.error(f"XAI API error: {e}")
        raise HTTPException(status_code=502, detail=f"XAI API error: {e}") from e

def extract_object_from_direct_request(user_message):
    """Extract the object/subject from direct image generation requests"""
    try:
        # Common patterns for direct image generation requests
        patterns = [
            r"generate an image (?:for|of) (.+)",
            r"create an image (?:for|of) (.+)",
            r"draw an image (?:for|of) (.+)",
            r"show me an image (?:for|of) (.+)",
            r"make an image (?:for|of) (.+)",
            r"show me (.+)",
            r"generate (.+)",
            r"create (.+)",
            r"draw (.+)",
            r"show (.+)",
            r"make (.+)"
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                object_name = match.group(1).strip()
                # Clean up the object name
                object_name = re.sub(r'\s+', ' ', object_name)  # Remove extra spaces
                object_name = object_name.strip('.,!?')  # Remove trailing punctuation
                
                # Create a proper image generation prompt
                if any(word in object_name.lower() for word in ["image", "picture", "photo", "drawing"]):
                    # If the object already contains image-related words, use as-is
                    return object_name
                else:
                    # Create a descriptive prompt (avoid double articles)
                    if object_name.lower().startswith(('a ', 'an ', 'the ')):
                        return object_name
                    else:
                        return f"a {object_name}"
        
        # If no pattern matches, try to extract the last meaningful part
        words = user_message.split()
        if len(words) > 2:
            # Look for the object after common verbs
            for i, word in enumerate(words):
                if word.lower() in ["for", "of", "about"] and i + 1 < len(words):
                    object_part = " ".join(words[i+1:]).strip('.,!?')
                    # Avoid double articles
                    if object_part.lower().startswith(('a ', 'an ', 'the ')):
                        return object_part
                    else:
                        return f"a {object_part}"
        
        # Fallback: use the original message
        return user_message
        
    except Exception as e:
        logger.warning(f"Error extracting object from direct request: {e}")
        return user_message

def build_context_aware_prompt(messages):
    """Build a concise, image-generation-friendly prompt from conversation history with enhanced cross-model support"""
    try:
        # Get the last user message
        user_messages = [msg for msg in messages if msg.role == "user"]
        if not user_messages:
            raise ValueError("No user message found")
        
        last_user_message = user_messages[-1].content.strip()
        
        # If it's a single message, use it directly
        if len(messages) == 1:
            return last_user_message
        
        # NEW: Enhanced context building for cross-model conversations
        # Get all assistant messages (from any model)
        assistant_messages = [msg for msg in messages if msg.role == "assistant"]
        
        if not assistant_messages:
            return last_user_message
        
        # Find the most recent substantial assistant response (not image links)
        most_recent_context = None
        for msg in reversed(assistant_messages):
            content = msg.content
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            
            # Skip image responses (contain image URLs or markdown)
            if not any(indicator in content.lower() for indicator in [
                "![generated image]", "![image]", "generated image", "image url", "image generated", "https://"
            ]) and len(content.strip()) > 20:
                most_recent_context = content
                break
        
        # If we found context, combine it with the user's request
        if most_recent_context:
            # Clean and summarize the context
            context_summary = enhanced_summarize_for_image_generation(most_recent_context, last_user_message)
            if context_summary:
                # Combine context with user request
                if any(word in last_user_message.lower() for word in ["generate", "create", "draw", "show", "make", "image"]):
                    context_prompt = f"{context_summary}. {last_user_message}"
                else:
                    context_prompt = f"Generate an image of {context_summary} based on: {last_user_message}"
                
                # Ensure prompt is within XAI limits (1024 characters)
                if len(context_prompt) > 1024:
                    context_prompt = context_prompt[:1021] + "..."
                
                logger.info(f"Built enhanced context-aware image prompt: {context_prompt}")
                return context_prompt
        
        # Fallback to original message
        return last_user_message
        
    except Exception as e:
        logger.error(f"Error building context-aware prompt: {e}")
        # Fallback to last user message
        user_messages = [msg for msg in messages if msg.role == "user"]
        if user_messages:
            return user_messages[-1].content
        raise ValueError("No user message found")

# Old function removed to fix linting errors

# Removed duplicate function definition

def summarize_for_image_generation(text):
    """Extract key visual concepts from assistant response for image generation"""
    try:
        # Convert to lowercase for processing
        text_lower = text.lower()
        
        # Extract key terms that are good for image generation
        key_terms = []
        
        # Look for specific objects, concepts, or subjects
        if "pc" in text_lower or "personal computer" in text_lower:
            key_terms.append("a personal computer")
        if "desktop" in text_lower:
            key_terms.append("a desktop computer")
        if "laptop" in text_lower:
            key_terms.append("a laptop computer")
        if "monitor" in text_lower:
            key_terms.append("a computer monitor")
        if "keyboard" in text_lower:
            key_terms.append("a computer keyboard")
        if "mouse" in text_lower:
            key_terms.append("a computer mouse")
        
        # Look for other common objects
        if "car" in text_lower or "vehicle" in text_lower:
            key_terms.append("a car")
        if "electric" in text_lower and "car" in text_lower:
            key_terms.append("an electric car")
        if "house" in text_lower or "home" in text_lower:
            key_terms.append("a house")
        if "building" in text_lower:
            key_terms.append("a building")
        if "animal" in text_lower or "dog" in text_lower or "cat" in text_lower:
            if "dog" in text_lower:
                key_terms.append("a dog")
            elif "cat" in text_lower:
                key_terms.append("a cat")
            else:
                key_terms.append("an animal")
        
        # If we found specific terms, use them
        if key_terms:
            return " and ".join(key_terms[:3])  # Limit to 3 key terms
        
        # Fallback: extract first few words that might be descriptive
        words = text.split()[:10]  # Take first 10 words
        return " ".join(words)
        
    except Exception as e:
        logger.warning(f"Error summarizing text for image generation: {e}")
        return ""

def extract_main_subject_from_gpt_response(text):
    """Extract the main subject from GPT responses for accurate image generation"""
    try:
        import re
        
        # Clean the text
        text = text.strip()
        if not text:
            return None
        
        # Look for common patterns that indicate the main subject
        patterns = [
            # Pattern 1: "A [subject] is..." - most common GPT response pattern
            r"^A\s+([A-Za-z\s]+?)\s+is\s+",
            # Pattern 2: "[Subject] is a..." 
            r"^([A-Za-z\s]+?)\s+is\s+a\s+",
            # Pattern 3: "An [subject] is..."
            r"^An\s+([A-Za-z\s]+?)\s+is\s+",
            # Pattern 4: "The [subject] is..."
            r"^The\s+([A-Za-z\s]+?)\s+is\s+",
            # Pattern 5: "[Subject] refers to..."
            r"^([A-Za-z\s]+?)\s+refers\s+to\s+",
            # Pattern 6: "[Subject] can be..."
            r"^([A-Za-z\s]+?)\s+can\s+be\s+",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                subject = match.group(1).strip()
                # Clean up the subject
                subject = re.sub(r'\s+', ' ', subject)  # Remove extra spaces
                subject = subject.strip()
                
                # Filter out common words that aren't the main subject
                if (len(subject) > 1 and 
                    not subject.lower() in ['tool', 'object', 'item', 'thing', 'device', 'instrument', 'piece', 'unit'] and
                    not subject.lower().startswith(('type of', 'kind of', 'form of', 'sort of'))):
                    return subject
        
        # Fallback: Look for the first noun phrase in the first sentence
        first_sentence = text.split('.')[0]
        words = first_sentence.split()
        
        if len(words) >= 2:
            # Look for patterns like "A [noun]" or "[noun] is"
            for i, word in enumerate(words):
                if word.lower() in ['a', 'an', 'the'] and i + 1 < len(words):
                    # Found article, next word is likely the subject
                    subject = words[i + 1]
                    if len(subject) > 1:
                        return subject
                elif word.lower() == 'is' and i > 0:
                    # Found "is", previous word is likely the subject
                    subject = words[i - 1]
                    if len(subject) > 1:
                        return subject
        
        # Final fallback: return the first meaningful word
        words = text.split()
        for word in words:
            if len(word) > 2 and word.isalpha():
                return word
                
        return None
        
    except Exception as e:
        logger.warning(f"Error extracting main subject: {e}")
        return None

def enhanced_summarize_for_image_generation(text, user_request):
    """Enhanced context summarization for better cross-model image generation"""
    try:
        # Safely handle Unicode content
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')
        if isinstance(user_request, bytes):
            user_request = user_request.decode('utf-8', errors='replace')
            
        text_lower = text.lower()
        user_lower = user_request.lower()
        
        # NEW: Enhanced context extraction for cross-model conversations
        # First, try to extract the main subject from the text
        main_subject = extract_main_subject_from_gpt_response(text)
        if main_subject:
            return main_subject
        
        # If no main subject found, try to extract key visual concepts
        # Look for descriptive terms that would be good for image generation
        visual_keywords = []
        
        # Extract nouns and descriptive terms
        import re
        # Find capitalized words (likely proper nouns or important terms)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', text)
        if capitalized_words:
            visual_keywords.extend(capitalized_words[:3])  # Take first 3
        
        # Find descriptive adjectives
        descriptive_words = re.findall(r'\b(beautiful|colorful|bright|dark|large|small|tall|short|round|square|triangular|modern|ancient|futuristic|vintage|elegant|simple|complex|detailed|abstract|realistic|fantasy|sci-fi|medieval|renaissance|baroque|gothic|art-deco|minimalist|maximalist|surreal|realistic|cartoon|anime|photorealistic|sketch|painting|sculpture|digital|traditional|contemporary|classic|modern|postmodern|impressionist|expressionist|cubist|surrealist|abstract|realistic|fantasy|sci-fi|medieval|renaissance|baroque|gothic|art-deco|minimalist|maximalist|surreal|realistic|cartoon|anime|photorealistic|sketch|painting|sculpture|digital|traditional|contemporary|classic|modern|postmodern|impressionist|expressionist|cubist|surrealist)\b', text_lower)
        if descriptive_words:
            visual_keywords.extend(descriptive_words[:3])
        
        # If we found visual keywords, combine them
        if visual_keywords:
            return ' '.join(visual_keywords[:5])  # Limit to 5 keywords
        
        # Extract key terms based on the user's request and context
        key_terms = []
        
        # NEW: Prioritize the most recent and relevant content
        # If the text is short and direct, use it as-is
        if len(text.strip()) < 200 and not any(word in text_lower for word in ["the", "and", "or", "but", "however", "although"]):
            # This looks like a direct description, use it
            return text.strip()
        
        # Sports-related context detection
        if any(word in text_lower for word in ["sport", "football", "soccer", "basketball", "tennis", "baseball", "cricket", "hockey", "golf", "swimming", "running", "cycling", "volleyball", "badminton", "table tennis", "rugby", "boxing", "martial arts", "wrestling", "gymnastics", "athletics", "track", "field", "olympic", "world cup", "championship", "tournament", "league", "team", "player", "athlete", "game", "match", "competition"]):
            if "football" in text_lower or "soccer" in text_lower:
                key_terms.append("football/soccer")
            if "basketball" in text_lower:
                key_terms.append("basketball")
            if "tennis" in text_lower:
                key_terms.append("tennis")
            if "baseball" in text_lower:
                key_terms.append("baseball")
            if "cricket" in text_lower:
                key_terms.append("cricket")
            if "hockey" in text_lower:
                key_terms.append("hockey")
            if "golf" in text_lower:
                key_terms.append("golf")
            if "swimming" in text_lower:
                key_terms.append("swimming")
            if "running" in text_lower:
                key_terms.append("running")
            if "cycling" in text_lower:
                key_terms.append("cycling")
            if "volleyball" in text_lower:
                key_terms.append("volleyball")
            if "badminton" in text_lower:
                key_terms.append("badminton")
            if "table tennis" in text_lower or "ping pong" in text_lower:
                key_terms.append("table tennis")
            if "rugby" in text_lower:
                key_terms.append("rugby")
            if "boxing" in text_lower:
                key_terms.append("boxing")
            if "martial arts" in text_lower or "karate" in text_lower or "judo" in text_lower or "taekwondo" in text_lower:
                key_terms.append("martial arts")
            if "wrestling" in text_lower:
                key_terms.append("wrestling")
            if "gymnastics" in text_lower:
                key_terms.append("gymnastics")
            if "athletics" in text_lower or "track and field" in text_lower:
                key_terms.append("athletics")
            if "olympic" in text_lower:
                key_terms.append("Olympic sports")
            if "world cup" in text_lower:
                key_terms.append("World Cup")
            if "championship" in text_lower or "tournament" in text_lower:
                key_terms.append("championship")
            if "league" in text_lower:
                key_terms.append("sports league")
            if "team" in text_lower or "player" in text_lower or "athlete" in text_lower:
                key_terms.append("sports team/athletes")
            if "game" in text_lower or "match" in text_lower or "competition" in text_lower:
                key_terms.append("sports competition")
        
        # Technology-related context detection
        if any(word in text_lower for word in ["computer", "pc", "laptop", "desktop", "monitor", "keyboard", "mouse", "cpu", "gpu", "ram", "storage", "hardware", "software", "programming", "coding", "development", "tech", "technology", "digital", "electronic", "device", "gadget", "smartphone", "tablet", "phone", "mobile"]):
            if "computer" in text_lower or "pc" in text_lower:
                key_terms.append("computer")
            if "laptop" in text_lower:
                key_terms.append("laptop")
            if "desktop" in text_lower:
                key_terms.append("desktop computer")
            if "monitor" in text_lower:
                key_terms.append("computer monitor")
            if "keyboard" in text_lower:
                key_terms.append("computer keyboard")
            if "mouse" in text_lower:
                key_terms.append("computer mouse")
            if "smartphone" in text_lower or "phone" in text_lower or "mobile" in text_lower:
                key_terms.append("smartphone")
            if "tablet" in text_lower:
                key_terms.append("tablet")
            if "programming" in text_lower or "coding" in text_lower:
                key_terms.append("programming")
            if "development" in text_lower:
                key_terms.append("software development")
        
        # Animals-related context detection
        if any(word in text_lower for word in ["dog", "cat", "bird", "fish", "horse", "cow", "pig", "sheep", "goat", "chicken", "duck", "rabbit", "hamster", "guinea pig", "turtle", "snake", "lizard", "frog", "butterfly", "bee", "spider", "ant", "animal", "pet", "wildlife", "nature", "zoo", "farm", "forest", "jungle", "ocean", "sea", "river", "lake", "mountain", "desert", "grassland", "savanna", "tundra", "arctic", "tropical", "temperate"]):
            if "dog" in text_lower:
                key_terms.append("dog")
            if "cat" in text_lower:
                key_terms.append("cat")
            if "bird" in text_lower:
                key_terms.append("bird")
            if "fish" in text_lower:
                key_terms.append("fish")
            if "horse" in text_lower:
                key_terms.append("horse")
            if "cow" in text_lower:
                key_terms.append("cow")
            if "pig" in text_lower:
                key_terms.append("pig")
            if "sheep" in text_lower:
                key_terms.append("sheep")
            if "goat" in text_lower:
                key_terms.append("goat")
            if "chicken" in text_lower:
                key_terms.append("chicken")
            if "duck" in text_lower:
                key_terms.append("duck")
            if "rabbit" in text_lower:
                key_terms.append("rabbit")
            if "hamster" in text_lower:
                key_terms.append("hamster")
            if "guinea pig" in text_lower:
                key_terms.append("guinea pig")
            if "turtle" in text_lower:
                key_terms.append("turtle")
            if "snake" in text_lower:
                key_terms.append("snake")
            if "lizard" in text_lower:
                key_terms.append("lizard")
            if "frog" in text_lower:
                key_terms.append("frog")
            if "butterfly" in text_lower:
                key_terms.append("butterfly")
            if "bee" in text_lower:
                key_terms.append("bee")
            if "spider" in text_lower:
                key_terms.append("spider")
            if "ant" in text_lower:
                key_terms.append("ant")
            if "wildlife" in text_lower:
                key_terms.append("wildlife")
            if "nature" in text_lower:
                key_terms.append("nature")
            if "zoo" in text_lower:
                key_terms.append("zoo")
            if "farm" in text_lower:
                key_terms.append("farm")
            if "forest" in text_lower:
                key_terms.append("forest")
            if "jungle" in text_lower:
                key_terms.append("jungle")
            if "ocean" in text_lower or "sea" in text_lower:
                key_terms.append("ocean")
            if "river" in text_lower:
                key_terms.append("river")
            if "lake" in text_lower:
                key_terms.append("lake")
            if "mountain" in text_lower:
                key_terms.append("mountain")
            if "desert" in text_lower:
                key_terms.append("desert")
            if "grassland" in text_lower:
                key_terms.append("grassland")
            if "savanna" in text_lower:
                key_terms.append("savanna")
            if "tundra" in text_lower:
                key_terms.append("tundra")
            if "arctic" in text_lower:
                key_terms.append("arctic")
            if "tropical" in text_lower:
                key_terms.append("tropical")
            if "temperate" in text_lower:
                key_terms.append("temperate")
        
        # If we found specific terms, use them
        if key_terms:
            return " and ".join(key_terms[:3])  # Limit to 3 key terms
        
        # Fallback: extract first few words that might be descriptive
        words = text.split()[:10]  # Take first 10 words
        return " ".join(words)
        
    except Exception as e:
        logger.warning(f"Error in enhanced summarization: {e}")
        return ""

async def get_xai_image_response(prompt):
    """Get image generation response from XAI API"""
    config = get_xai_config()
    XAI_API_KEY = config["api_key"]
    XAI_BASE_URL = config["base_url"]
    PROXY_URL = config["proxy_url"]
    PROXY_AUTH = config["proxy_auth"]
    IMAGE_MODEL = config["image_model"]

    if not XAI_API_KEY:
        raise HTTPException(status_code=503, detail="XAI_API_KEY is not configured")
    
    logger.info(f"Making XAI image generation request for prompt: {prompt[:100]}...")
    
    try:
        # Configure proxy if available
        client_kwargs = {
            "timeout": httpx.Timeout(180.0, connect=15.0, read=180.0, write=30.0),  # Extended timeout for image generation
            "limits": httpx.Limits(max_keepalive_connections=5, max_connections=10),
            "verify": True,
            "follow_redirects": True
        }
        
        if PROXY_URL:
            # Parse proxy authentication if provided
            if PROXY_AUTH and ":" in PROXY_AUTH:
                username, password = PROXY_AUTH.split(":", 1)
                proxy_url_with_auth = PROXY_URL.replace("://", f"://{username}:{password}@")
            else:
                proxy_url_with_auth = PROXY_URL
            
            client_kwargs["proxy"] = proxy_url_with_auth
            logger.info(f"Using proxy for XAI image API: {PROXY_URL}")
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Create client with proper error handling
                async with httpx.AsyncClient(**client_kwargs) as client:
                    logger.info(f"Sending request to XAI image generation API... (attempt {attempt + 1}/{max_retries})")
                    
                    # Prepare request payload - only include supported parameters
                    payload = {
                        "model": IMAGE_MODEL,
                        "prompt": prompt
                    }
                    
                    logger.info(f"XAI image generation payload: {payload}")
                    
                    response = await client.post(
                        f"{XAI_BASE_URL}/images/generations",
                        headers={
                            "Authorization": f"Bearer {XAI_API_KEY}",
                            "Content-Type": "application/json",
                            "User-Agent": "PhatagiAI/1.0"
                        },
                        json=payload
                    )
                    
                    logger.info(f"XAI image API response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        return response
                    elif response.status_code == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"Rate limited, retrying in {delay} seconds...")
                            await asyncio.sleep(delay)
                            continue
                    elif response.status_code >= 500:  # Server error
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"Server error {response.status_code}, retrying in {delay} seconds...")
                            await asyncio.sleep(delay)
                            continue
                    
                    # Safely decode error text with UTF-8 encoding
                    try:
                        error_text = response.text
                        if isinstance(error_text, bytes):
                            error_text = error_text.decode('utf-8', errors='replace')
                    except UnicodeDecodeError:
                        error_text = response.content.decode('utf-8', errors='replace')
                    
                    logger.error(f"XAI image API error: {response.status_code} - {error_text}")
                    raise _build_xai_http_error(response.status_code, error_text, IMAGE_MODEL)
                    
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Network error: {e}, retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in XAI image API call: {e}")
                raise
            
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        logger.error(f"XAI image API connection error: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to connect to XAI image API: {e}") from e
    except httpx.TimeoutException as e:
        logger.error(f"XAI image API timeout error: {e}")
        raise HTTPException(status_code=503, detail=f"XAI image API request timed out: {e}") from e
    except Exception as e:
        logger.error(f"XAI image API error: {e}")
        raise HTTPException(status_code=502, detail=f"XAI image API error: {e}") from e

async def stream_xai_response(response) -> AsyncGenerator[str, None]:
    """Stream a validated XAI response."""
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data = line[6:]  # Remove "data: " prefix
            
            if data.strip() == "[DONE]":
                logger.info("XAI streaming completed")
                break
                
            try:
                chunk = json.loads(data)
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        content = delta["content"]
                        
                        # Debug: Log what we're getting
                        logger.debug(f"XAI content type: {type(content)}, value: {repr(content)}")
                        
                        # Ensure content is a string
                        if not isinstance(content, str):
                            content = str(content) if content is not None else ""
                        
                        logger.debug(f"XAI streaming chunk: {content}")
                        yield content
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse XAI chunk: {data}, error: {e}")
                continue
        elif line.strip():  # Handle non-data lines
            logger.debug(f"XAI non-data line: {line}")
            continue

def get_token_from_header(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1]

def decode_email_from_token(token: str):
    try:
        SECRET_KEY = os.getenv("SECRET_KEY")
        ALGORITHM = os.getenv("ALGORITHM")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"[DEBUG] Decoded JWT payload: {payload}")
        email = payload.get("sub")
        if email is None:
            logger.warning("[DEBUG] No 'sub' (email) found in token payload.")
            return None
        return email
    except Exception as e:
        logger.error(f"[DEBUG] Error decoding token: {e}")
        return None

async def get_user_id_from_email(email: str):
    """Get user_id from email with enhanced error handling"""
    try:
        from app.routers.auth import User
        
        # Use the enhanced session with proper connection handling
        async for session in get_async_session():
            try:
                result = await session.execute(select(User).where(User.email == email))
                db_user = result.scalar_one_or_none()
                if not db_user:
                    logger.warning(f"User not found for email: {email}")
                    return None
                logger.info(f"Found user_id: {db_user.user_id} for email: {email}")
                return str(db_user.user_id)
            except Exception as session_error:
                logger.error(f"Database session error in get_user_id_from_email: {session_error}")
                # Rollback the session if there's an error
                try:
                    await session.rollback()
                except:
                    pass
                raise session_error
                
    except Exception as e:
        logger.error(f"Error getting user_id from email: {e}")
        # Log the specific error type for debugging
        logger.error(f"Error type: {type(e).__name__}")
        return None

async def store_chat(user_id, chat_request, response_text, model):
    """Store chat with retry logic and connection handling"""
    if not user_id:
        logger.warning("No user_id provided, skipping chat storage.")
        return None
    
    logger.info(f"Attempting to store chat for user_id: {user_id}, model: {model}")
    
    # Retry logic for database operations
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Check connection health before attempting database operations
            from app.services.database import ensure_connection, get_connection_pool_status
            if not await ensure_connection():
                logger.warning(f"Database connection not available (attempt {attempt + 1})")
                # Log connection pool status for debugging
                pool_status = await get_connection_pool_status()
                if pool_status:
                    logger.info(f"Connection pool status: {pool_status}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error("Database connection unavailable after all retries")
                    return None
            
            # Use SQLAlchemy async session with proper connection handling
            async for session in get_async_session():
                try:
                    # Get or create conversation (handles both new and existing conversations)
                    title = chat_request.messages[0].content[:50] if chat_request.messages else "Chat"
                    
                    from app.services.database import get_or_create_conversation, store_request_response_pair
                    
                    # This will use existing conversation if conversation_id is provided, or create new one
                    conversation_id = await get_or_create_conversation(
                        session, 
                        user_id, 
                        title, 
                        conversation_id=chat_request.conversation_id
                    )
                    
                    # Get the last user message (the current request)
                    user_message = chat_request.messages[-1].content if chat_request.messages else ""
                    
                    # Store as a new bubble in the conversation (existing or new)
                    await store_request_response_pair(
                        session, 
                        user_id, 
                        conversation_id, 
                        user_message, 
                        response_text, 
                        model
                    )
                    
                    logger.info(f"Successfully stored chat in conversation: {conversation_id}")
                    return conversation_id
                    
                except Exception as session_error:
                    logger.error(f"Database session error (attempt {attempt + 1}): {session_error}")
                    # Rollback the session if there's an error
                    try:
                        await session.rollback()
                    except:
                        pass
                    raise session_error
                    
        except Exception as e:
            logger.error(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                import asyncio
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"All {max_retries} attempts failed. Chat storage failed.")
                return None
    
    return None

async def chat_and_store(request: Request, chat_request: ChatRequest, model_name: str):
    """Handle chat request with conversation storage for multi-turn support"""
    logger.info(f"Received chat request for model: {model_name}")
    
    # Extract user_id before streaming response, but make optional
    user_id = None
    try:
        token = get_token_from_header(request)
        if not token:
            logger.warning("Missing Authorization header")
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        
        email = decode_email_from_token(token)
        if not email:
            logger.warning("Invalid token - could not decode email")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = await get_user_id_from_email(email)
        if not user_id:
            logger.warning(f"User not found for email: {email}")
            raise HTTPException(status_code=401, detail="User not found")
        
        logger.info(f"Successfully authenticated user_id: {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to get user_id: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")
    
    # Get response from XAI API
    messages = [msg.dict() for msg in chat_request.messages]
    
    # Apply personality if personality_id is provided
    personality_data = None
    if chat_request.personality_id:
        try:
            async for db in get_async_session():
                personality_data = await load_personality(chat_request.personality_id, db)
                if personality_data:
                    logger.info(f"Applying personality: {personality_data['name']} ({personality_data.get('avatar_emoji', '')})")
                    
                    # Add personality system prompt to messages
                    system_prompt = personality_data.get('system_prompt', '')
                    if system_prompt:
                        # Check if there's already a system message
                        has_system = any(msg.get('role') == 'system' for msg in messages)
                        if has_system:
                            # Prepend to existing system message
                            for msg in messages:
                                if msg.get('role') == 'system':
                                    msg['content'] = f"{system_prompt}\n\n{msg['content']}"
                                    break
                        else:
                            # Add new system message at the beginning
                            messages.insert(0, {
                                'role': 'system',
                                'content': system_prompt
                            })
                else:
                    logger.warning(f"Personality {chat_request.personality_id} not found")
                break
        except Exception as e:
            logger.error(f"Error loading personality: {e}")
    
    response = await get_xai_response(messages, model_name)
    response_chunks = []
    
    async def event_stream():
        try:
            async for chunk in stream_xai_response(response):
                response_chunks.append(chunk)
                # Format chunk for frontend compatibility with UTF-8 safety
                try:
                    # Safely handle Unicode content in chunks
                    safe_chunk = chunk
                    if isinstance(chunk, bytes):
                        safe_chunk = chunk.decode('utf-8', errors='replace')
                    
                    # Create JSON with UTF-8 safety
                    json_data = json.dumps({'content': safe_chunk}, ensure_ascii=False)
                    formatted_chunk = f"data: {json_data}\n\n"
                    yield formatted_chunk
                except UnicodeEncodeError as e:
                    logger.warning(f"Unicode encoding error in chunk: {e}")
                    # Fallback to ASCII-safe JSON
                    json_data = json.dumps({'content': chunk}, ensure_ascii=True)
                    formatted_chunk = f"data: {json_data}\n\n"
                    yield formatted_chunk
            
            # Send conversation metadata at the end and persist this bubble
            conversation_id = None
            try:
                response_text = ''.join(response_chunks)
                # Always store the chat (handles both new and existing conversations)
                saved_conversation_id = await store_chat(
                    user_id, chat_request, response_text, model_name
                )
                # Prefer saved id, then provided id, then fallback
                conversation_id = (
                    saved_conversation_id
                    or chat_request.conversation_id
                    or "new_conversation"
                )
            except Exception as e:
                logger.error(f"Error persisting chat/conversation_id: {e}")
                conversation_id = chat_request.conversation_id or "new_conversation"
            
            # Send metadata as a special marker
            if conversation_id:
                metadata = f"\n\n<!--CONVERSATION_ID:{conversation_id}-->"
                yield metadata
                
        except Exception as e:
            logger.error(f"Error in API streaming: {e}")
            try:
                # Safely handle error messages with UTF-8
                error_message = f'Error: {str(e)}'
                if isinstance(error_message, bytes):
                    error_message = error_message.decode('utf-8', errors='replace')
                error_chunk = f"data: {json.dumps({'content': error_message}, ensure_ascii=False)}\n\n"
                yield error_chunk
            except UnicodeEncodeError:
                # Fallback to ASCII-safe error message
                error_chunk = f"data: {json.dumps({'content': f'Error: {str(e)}'}, ensure_ascii=True)}\n\n"
                yield error_chunk
    
    # Stream response to client
    streaming_response = StreamingResponse(event_stream(), media_type="text/plain")
    
    return streaming_response

@xai_router.post("/grok-4/chat")
async def grok_4_chat(request: Request, chat_request: ChatRequest):
    """Chat with Grok-4 model with multi-turn conversation support"""
    try:
        return await chat_and_store(request, chat_request, "grok-4-fast-reasoning")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grok-4 chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@xai_router.post("/grok-3/chat")
async def grok_3_chat(request: Request, chat_request: ChatRequest):
    """Chat with Grok-3 model with multi-turn conversation support"""
    try:
        return await chat_and_store(request, chat_request, "grok-3")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grok-3 chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@xai_router.post("/grok-2-image/chat")
async def grok_2_image_chat(request: Request, chat_request: ChatRequest):
    """Generate image with Grok-2-image model using conversation context"""
    try:
        token = get_token_from_header(request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        email = decode_email_from_token(token)
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = await get_user_id_from_email(email)
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")

        # Build context-aware prompt from entire conversation
        context_prompt = build_context_aware_prompt(chat_request.messages)
        logger.info(f"Full conversation context: {len(chat_request.messages)} messages")
        logger.info(f"Generating image with context-aware prompt: {context_prompt[:200]}...")
        
        # Debug: Log the conversation history
        for i, msg in enumerate(chat_request.messages):
            logger.info(f"Message {i}: {msg.role} - {msg.content[:100]}...")
        
        # Get image generation response with UTF-8 encoding safety
        response = await get_xai_image_response(context_prompt)
        
        # Safely decode the response with UTF-8 encoding
        try:
            # Ensure response content is properly decoded
            response_text = response.text
            if isinstance(response_text, bytes):
                response_text = response_text.decode('utf-8', errors='replace')
            
            # Parse JSON with UTF-8 safety
            image_data = response.json()
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error in image response: {e}")
            # Try to decode with error replacement
            response_text = response.content.decode('utf-8', errors='replace')
            image_data = json.loads(response_text)
        except Exception as e:
            logger.error(f"Error parsing image response: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to parse image response: {str(e)}")
        
        # Extract image URL from response with UTF-8 safety
        if "data" in image_data and len(image_data["data"]) > 0:
            image_url = image_data["data"][0]["url"]
            # Ensure image URL is properly encoded
            if isinstance(image_url, bytes):
                image_url = image_url.decode('utf-8', errors='replace')
            
            # Fix URL protocol if missing
            if not image_url.startswith(('http://', 'https://')):
                image_url = f"https://{image_url}"
            
            logger.info(f"Image generated successfully: {image_url}")
            
            logger.info(f"Storing image generation for user_id: {user_id}")
            
            # Store the image generation in conversation with UTF-8 safety
            if user_id:
                try:
                    # Safely encode the image URL for storage
                    safe_image_url = image_url.encode('utf-8', errors='replace').decode('utf-8')
                    image_response_text = f"![Generated Image]({safe_image_url})"
                    await store_chat(user_id, chat_request, image_response_text, "grok-2-image")
                    logger.info("Image generation stored in conversation")
                except UnicodeEncodeError as e:
                    logger.warning(f"Unicode encoding error in image storage: {e}")
                    # Fallback to ASCII-safe storage
                    fallback_url = image_url.encode('ascii', errors='replace').decode('ascii')
                    fallback_text = f"![Generated Image]({fallback_url})"
                    await store_chat(user_id, chat_request, fallback_text, "grok-2-image")
                    logger.info("Image generation stored in conversation (ASCII fallback)")
                except Exception as e:
                    logger.warning(f"Failed to store image generation: {e}")
            
            # Return the image URL as a streaming response with UTF-8 safety
            async def generate():
                try:
                    # Safely encode the image URL and content
                    safe_image_url = image_url.encode('utf-8', errors='replace').decode('utf-8')
                    safe_content = f"![Generated Image]({safe_image_url})"
                    
                    # Create JSON response with UTF-8 safety
                    response_data = {
                        'content': safe_content,
                        'type': 'image'
                    }
                    
                    # Ensure JSON is properly encoded with UTF-8
                    json_response = json.dumps(response_data, ensure_ascii=False)
                    # Ensure the JSON string is properly encoded
                    if isinstance(json_response, str):
                        json_response = json_response.encode('utf-8', errors='replace').decode('utf-8')
                    yield f"data: {json_response}\n\n"
                    yield "data: [DONE]\n\n"
                except UnicodeEncodeError as e:
                    logger.error(f"Unicode encoding error in image response: {e}")
                    # Fallback to ASCII-safe response
                    fallback_content = f"![Generated Image]({image_url.encode('ascii', errors='replace').decode('ascii')})"
                    fallback_data = {
                        'content': fallback_content,
                        'type': 'image'
                    }
                    yield f"data: {json.dumps(fallback_data, ensure_ascii=True)}\n\n"
                    yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            logger.error(f"No image data in response: {image_data}")
            raise HTTPException(status_code=500, detail="No image generated")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grok-2-image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

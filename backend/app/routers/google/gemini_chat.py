import os
import json
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import base64
import uuid
from typing import List, Optional
from app.routers.openai.openai_chat import get_token_from_header, decode_email_from_token, get_user_id_from_email, store_chat

logger = logging.getLogger(__name__)
router = APIRouter()

# Gemini API configuration - used via lazy loading
_gemini_config = None

def get_gemini_config():
    """Get Gemini configuration with lazy loading to ensure env vars are loaded"""
    global _gemini_config
    if _gemini_config is None:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            api_key = api_key.strip().replace('"', '').replace("'", "")
            
        _gemini_config = {
            "api_key": api_key
        }
        
        if not _gemini_config["api_key"]:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            
    return _gemini_config
# Comprehensive fallback list: Latest to oldest Gemini models
# The system tries each model in order until one works
GEMINI_MODEL_CANDIDATES = [
    # Latest 3.0 model (Dec 2024)
    "gemini-3-pro-preview",          # LATEST - Gemini 3 Pro
    # 2.5 models
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    # 2.0 models (confirmed working)
    "gemini-2.0-flash",              # Stable - CONFIRMED WORKING
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-exp",
    "gemini-2.0-pro-exp",
    "gemini-2.0-flash-thinking-exp-01-21",
    # Experimental models
    "gemini-exp-1206",
    "gemini-exp-1121",
    # 1.5 models (stable fallback)
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-001",
    "gemini-1.5-pro-002",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash-8b-latest",
    # Legacy 1.0 models (oldest fallback)
    "gemini-pro",
    "gemini-1.0-pro",
    "gemini-1.0-pro-latest",
    "gemini-1.0-pro-001",
]
GEMINI_MODEL = GEMINI_MODEL_CANDIDATES[0]  # Default to first candidate


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: str = None
    project_id: str = None
    personality_id: str = None


def build_gemini_contents(messages: List[Message]):
    contents = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg.content}]
        })
    return contents


@router.post("/gemini-3-pro/chat")
async def chat_gemini_3_pro(request: Request, chat_request: ChatRequest):
    token = get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    email = decode_email_from_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = await get_user_id_from_email(email)
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found")

    config = get_gemini_config()
    if not config["api_key"]:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    async def event_stream():
        try:
            contents = build_gemini_contents(chat_request.messages)
            body = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "top_p": 0.9
                    # No max_output_tokens limit - model will generate until complete or API limit
                }
            }
            
            # Try multiple model names in sequence until one works
            last_error = None
            tried_models = []
            total_models = len(GEMINI_MODEL_CANDIDATES)
            
            config = get_gemini_config()
            api_key = config["api_key"]
            
            if not api_key:
                yield f"data: {json.dumps({'content': 'Gemini API key not configured'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            for idx, model_name in enumerate(GEMINI_MODEL_CANDIDATES, 1):
                tried_models.append(model_name)
                try:
                    # Use alt=sse to get proper Server-Sent Events format
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
                    logger.info(f"Gemini [{idx}/{total_models}] trying model={model_name}")
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        async with client.stream("POST", url, json=body) as resp:
                            if resp.status_code == 200:
                                # Success! Use this model
                                logger.info(f"✅ Successfully using Gemini model: {model_name}")
                                has_content = False
                                async for line in resp.aiter_lines():
                                    if not line:
                                        continue
                                    # SSE format: "data: {...json...}"
                                    if line.startswith("data: "):
                                        json_str = line[6:]  # Remove "data: " prefix
                                        try:
                                            data = json.loads(json_str)
                                            # Check for errors in the response
                                            if "error" in data:
                                                error_info = data["error"]
                                                error_message = error_info.get("message", "Unknown error")
                                                logger.error(f"Gemini API error in stream: {error_message}")
                                                yield f"data: {json.dumps({'content': f'API Error: {error_message}'})}\n\n"
                                                yield "data: [DONE]\n\n"
                                                return
                                            if "candidates" in data and data["candidates"]:
                                                parts = data["candidates"][0].get("content", {}).get("parts", [])
                                                for part in parts:
                                                    text_part = part.get("text", "")
                                                    if text_part:
                                                        has_content = True
                                                        logger.debug(f"Gemini content: {text_part[:50]}...")
                                                        yield f"data: {json.dumps({'content': text_part})}\n\n"
                                        except json.JSONDecodeError as e:
                                            logger.warning(f"JSON decode error: {e}, line: {line[:100]}")
                                            continue
                                # done
                                if has_content:
                                    logger.info(f"✅ Gemini stream completed successfully")
                                else:
                                    logger.warning(f"⚠️ Gemini stream completed but no content received")
                                yield "data: [DONE]\n\n"
                                return
                            else:
                                # Model not found, try next one
                                error_text = await resp.aread()
                                error_detail = error_text.decode() if error_text else f"HTTP {resp.status_code}"
                                logger.warning(f"Model {model_name} failed: {error_detail[:200]}")
                                last_error = error_detail
                                continue
                except Exception as e:
                    logger.warning(f"Error trying model {model_name}: {e}")
                    last_error = str(e)
                    continue
            
            # All models failed
            logger.error(f"All {len(tried_models)} Gemini models failed. Tried: {tried_models[:5]}... Last error: {last_error}")
            error_message = f"Tried {len(tried_models)} Gemini models, all unavailable."
            if last_error:
                try:
                    error_json = json.loads(last_error)
                    if "error" in error_json:
                        api_error = error_json["error"].get("message", "")
                        status = error_json["error"].get("status", "")
                        if "location" in api_error.lower():
                            error_message = f"Geographic restriction: {api_error}"
                        elif status:
                            error_message = f"{status}: {api_error}"
                        else:
                            error_message = api_error
                except:
                    if "location" in str(last_error).lower():
                        error_message = f"Geographic restriction detected. Your region may not support Gemini API."
                    else:
                        error_message = f"API Error: {last_error[:150]}"
            yield f"data: {json.dumps({'content': f'Gemini Error: {error_message}'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Gemini stream error: {e}", exc_info=True)
            error_message = str(e)
            # Try to extract more meaningful error message
            if "status_code" in str(e) or "HTTP" in str(e):
                error_message = f"API Error: {error_message}"
            else:
                error_message = f"Error: {error_message}"
            yield f"data: {json.dumps({'content': error_message})}\n\n"
            yield "data: [DONE]\n\n"

    # store after stream aggregation
    async def aggregated():
        collected = []
        async for chunk in event_stream():
            if chunk.startswith("data: "):
                payload = chunk[6:].strip()
                if payload == "[DONE]":
                    yield chunk
                    break
                try:
                    parsed = json.loads(payload)
                    if "content" in parsed:
                        collected.append(parsed["content"])
                except Exception:
                    pass
            yield chunk
        # store
        if user_id:
            try:
                response_text = "".join(collected)
                await store_chat(user_id, chat_request, response_text, "Gemini-3-Pro")
            except Exception as e:
                logger.warning(f"Gemini store failed: {e}")

    return StreamingResponse(aggregated(), media_type="text/event-stream")


def build_context_aware_prompt(messages: List[Message]) -> str:
    """Build a context-aware prompt from conversation history"""
    prompt_parts = []
    for msg in messages:
        if msg.role == "user":
            prompt_parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            prompt_parts.append(f"Assistant: {msg.content}")
    return "\n".join(prompt_parts)


def save_base64_image(base64_data: str, mime_type: str = "image/png") -> str:
    """Save base64 image data to local uploads directory and return the URL"""
    try:
        # Create directories if they don't exist
        os.makedirs("uploads/images", exist_ok=True)
        
        # Strip metadata prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
            
        # Decode base64
        image_bytes = base64.b64decode(base64_data)
        
        # Generate unique filename
        ext = mime_type.split("/")[-1] if "/" in mime_type else "png"
        if ext == "jpeg": ext = "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join("uploads/images", filename)
        
        # Save to disk
        with open(filepath, "wb") as f:
            f.write(image_bytes)
            
        # Return the relative URL (will be served by FastAPI static mount)
        return f"/uploads/images/{filename}"
    except Exception as e:
        logger.error(f"Error saving base64 image: {e}")
        return None


@router.post("/gemini-3-pro-image/chat")
async def chat_gemini_3_pro_image(request: Request, chat_request: ChatRequest):
    """Generate image with Gemini-3-Pro-Image using conversation context"""
    config = get_gemini_config()
    if not config["api_key"]:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    try:
        # Authentication
        token = get_token_from_header(request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        email = decode_email_from_token(token)
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        try:
            user_id = await get_user_id_from_email(email)
            if not user_id:
                raise HTTPException(status_code=401, detail="User not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Failed to get user_id: {e}")
            raise HTTPException(status_code=500, detail="Authentication failed")
        
        # Build context-aware prompt from entire conversation
        context_prompt = build_context_aware_prompt(chat_request.messages)
        logger.info(f"Full conversation context: {len(chat_request.messages)} messages")
        logger.info(f"Generating image with context-aware prompt: {context_prompt[:200]}...")
        
        # Debug: Log the conversation history
        for i, msg in enumerate(chat_request.messages):
            logger.info(f"Message {i}: {msg.role} - {msg.content[:100]}...")
        
        # Use Gemini 3 Pro Image Preview for image generation
        IMAGE_MODEL = "gemini-3-pro-image-preview"
        config = get_gemini_config()
        api_key = config["api_key"]
        
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API key not configured")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}:generateContent?key={api_key}"
        
        # Build request body for image generation
        body = {
            "contents": [{
                "parts": [{"text": context_prompt}]
            }],
            "generationConfig": {
                "imageConfig": {
                    "aspectRatio": "16:9",
                    "imageSize": "4K"
                }
            }
        }
        
        # Get image generation response
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(f"Gemini image generation error: {response.status_code} - {error_text.decode()}")
                raise HTTPException(status_code=response.status_code, detail=f"Image generation failed: {error_text.decode()}")
            
            # Parse JSON response
            try:
                image_data = response.json()
            except Exception as e:
                logger.error(f"Error parsing image response: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to parse image response: {str(e)}")
            
            # Extract image from response
            # Gemini returns base64 encoded images in the response
            image_url = None
            has_text_response = False
            text_response = ""
            
            if "candidates" in image_data and image_data["candidates"]:
                candidate = image_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    for part in parts:
                        if "inlineData" in part:
                            # Base64 encoded image
                            mime_type = part["inlineData"].get("mimeType", "image/png")
                            image_data_base64 = part["inlineData"].get("data", "")
                            if image_data_base64:
                                image_url = f"data:{mime_type};base64,{image_data_base64}"
                                break
                        elif "url" in part:
                            # URL to image
                            image_url = part["url"]
                            break
                        elif "text" in part:
                            # Text response instead of image
                            has_text_response = True
                            text_response = part.get("text", "")
            
            if not image_url:
                logger.error("No image data in response")
                logger.error(f"Response structure: {json.dumps(image_data, indent=2)[:500]}")
                
                # If we got a text response, the model interpreted the prompt as a text question
                if has_text_response:
                    logger.warning(f"Gemini image model returned text instead of image: {text_response[:200]}")
                    raise HTTPException(
                        status_code=400, 
                        detail="The prompt does not appear to request image generation. Please include keywords like 'generate an image', 'create a picture', 'draw', etc."
                    )
                
                # Check if the prompt might not be requesting an image
                last_user_message = chat_request.messages[-1].content if chat_request.messages else ""
                if not any(keyword in last_user_message.lower() for keyword in ['image', 'picture', 'photo', 'generate', 'create', 'draw', 'show', 'visual']):
                    raise HTTPException(
                        status_code=400, 
                        detail="The prompt does not appear to request image generation. Please include keywords like 'generate an image', 'create a picture', 'draw', etc."
                    )
                raise HTTPException(status_code=500, detail="No image generated - the API response did not contain image data")
            
            logger.info(f"Generated image successfully (type: {'base64' if image_url.startswith('data:') else 'url'})")
            if image_url.startswith('data:image/'):
                # Log base64 image info (truncated for logging)
                base64_preview = image_url[:100] + '...' if len(image_url) > 100 else image_url
                logger.info(f"Base64 image preview: {base64_preview} (length: {len(image_url)} chars)")
            
            # Save the image locally and get the sustainable URL immediately
            # This avoids massive base64 strings in the DB and ensures consistent URLs
            local_url = None
            if image_url and image_url.startswith("data:"):
                try:
                    mime_type = "image/png"
                    if "data:" in image_url and ";" in image_url:
                        mime_type = image_url.split("data:")[1].split(";")[0]
                    local_url = save_base64_image(image_url, mime_type)
                except Exception as e:
                    logger.error(f"Error saving base64 image: {e}")

            # Return relative URL to allow frontend proxying to handle it
            # This fixes issues where the base_url might differ from what the frontend expects
            final_image_url = local_url if local_url else image_url
            
            safe_content = f"![Generated Image]({final_image_url})"

            # Store the conversation if user_id is available
            if user_id:
                try:
                    logger.info(f"Storing Gemini image generation with model: gemini-3-pro-image")
                    logger.info(f"Response text preview: {safe_content[:150]}... (length: {len(safe_content)} chars)")
                    # Use safe_content which has the relative URL (or original if save failed)
                    conversation_id = await store_chat(user_id, chat_request, safe_content, "gemini-3-pro-image")
                    if conversation_id:
                        logger.info(f"Successfully stored Gemini image generation in conversation: {conversation_id}")
                    else:
                        logger.warning("store_chat returned None for Gemini image generation")
                except Exception as e:
                    logger.warning(f"Failed to store Gemini image generation: {e}", exc_info=True)
            
            # Return the image as a streaming response
            async def generate():
                try:
                    # Provide the same content as stored in DB
                    response_data = {
                        'content': safe_content,
                        'type': 'chunk'  # Use 'chunk' so standard frontend logic displays it immediately
                    }
                    
                    yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error in image representation: {e}", exc_info=True)
                    error_data = {
                        'content': f"Error representing image: {str(e)}",
                        'type': 'error'
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=True)}\n\n"
                    yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini-3-Pro-Image chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


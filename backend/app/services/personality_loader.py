"""
Personality Loader Service
Loads and applies AI personalities to chat requests
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import logging
from functools import lru_cache

from app.models.personalities import Personality

logger = logging.getLogger(__name__)

# In-memory cache for frequently used personalities
_personality_cache: Dict[str, Dict[str, Any]] = {}


async def load_personality(
    personality_id: str,
    db: AsyncSession,
    use_cache: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Load a personality from database
    
    Args:
        personality_id: UUID of the personality
        db: Database session
        use_cache: Whether to use cached personality (default: True)
    
    Returns:
        Dictionary with personality data or None if not found
    """
    try:
        # Check cache first
        if use_cache and personality_id in _personality_cache:
            logger.debug(f"Loading personality from cache: {personality_id}")
            return _personality_cache[personality_id]
        
        # Validate UUID format
        try:
            uuid.UUID(personality_id)
        except ValueError:
            logger.error(f"Invalid personality UUID format: {personality_id}")
            return None
        
        # Load from database
        logger.info(f"Loading personality from database: {personality_id}")
        result = await db.execute(
            select(Personality).where(Personality.id == uuid.UUID(personality_id))
        )
        personality = result.scalar_one_or_none()
        
        if not personality:
            logger.warning(f"Personality not found: {personality_id}")
            return None
        
        if not personality.is_active:
            logger.warning(f"Personality is not active: {personality_id}")
            return None
        
        # Convert to dict and cache
        personality_dict = {
            "id": str(personality.id),
            "name": personality.name,
            "system_prompt": personality.system_prompt,
            "rules": personality.rules or {},
            "avatar_emoji": personality.avatar_emoji
        }
        
        # Cache for future use
        _personality_cache[personality_id] = personality_dict
        logger.debug(f"Cached personality: {personality_id}")
        
        return personality_dict
        
    except Exception as e:
        logger.error(f"Error loading personality {personality_id}: {e}")
        return None


async def get_personality_prompt(
    personality_id: Optional[str],
    db: AsyncSession,
    base_prompt: str = ""
) -> str:
    """
    Get the complete system prompt for a personality
    
    Args:
        personality_id: UUID of the personality (optional)
        db: Database session
        base_prompt: Base system prompt to prepend (optional)
    
    Returns:
        Complete system prompt with personality merged
    """
    try:
        # If no personality specified, return base prompt
        if not personality_id:
            logger.debug("No personality specified, using base prompt")
            return base_prompt
        
        # Load personality
        personality = await load_personality(personality_id, db)
        
        if not personality:
            logger.warning(f"Could not load personality {personality_id}, using base prompt")
            return base_prompt
        
        # Merge prompts
        personality_prompt = personality.get("system_prompt", "")
        
        if base_prompt:
            # Combine base prompt with personality prompt
            combined_prompt = f"{base_prompt}\n\n{personality_prompt}"
        else:
            combined_prompt = personality_prompt
        
        logger.debug(f"Using personality '{personality['name']}' prompt")
        return combined_prompt
        
    except Exception as e:
        logger.error(f"Error getting personality prompt: {e}")
        return base_prompt


def apply_personality_rules(
    personality_data: Optional[Dict[str, Any]],
    request_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply personality rules to LLM request parameters
    
    Args:
        personality_data: Personality dictionary with rules
        request_params: LLM request parameters to modify
    
    Returns:
        Modified request parameters with personality rules applied
    """
    try:
        if not personality_data or not personality_data.get("rules"):
            logger.debug("No personality rules to apply")
            return request_params
        
        rules = personality_data.get("rules", {})
        logger.debug(f"Applying personality rules: {rules}")
        
        # Apply length rules (affects max_tokens)
        length = rules.get("length")
        if length == "concise":
            request_params["max_tokens"] = min(request_params.get("max_tokens", 1000), 500)
        elif length == "detailed":
            request_params["max_tokens"] = max(request_params.get("max_tokens", 1000), 2000)
        elif length == "balanced":
            request_params["max_tokens"] = request_params.get("max_tokens", 1000)
        
        # Apply tone rules (affects temperature)
        tone = rules.get("tone")
        if tone == "formal":
            # Lower temperature for more consistent, formal responses
            request_params["temperature"] = min(request_params.get("temperature", 0.7), 0.5)
        elif tone == "creative":
            # Higher temperature for more varied, creative responses
            request_params["temperature"] = max(request_params.get("temperature", 0.7), 0.9)
        elif tone == "technical":
            # Lower temperature for precise technical responses
            request_params["temperature"] = min(request_params.get("temperature", 0.7), 0.4)
        elif tone == "casual":
            # Moderate temperature for natural conversation
            request_params["temperature"] = request_params.get("temperature", 0.7)
        
        # Apply response format rules (adds instructions to prompt)
        response_format = rules.get("response_format")
        if response_format == "bullet_points":
            # This would be handled in the prompt itself
            pass
        elif response_format == "code_focused":
            # This would be handled in the prompt itself
            pass
        
        logger.debug(f"Applied rules: max_tokens={request_params.get('max_tokens')}, temperature={request_params.get('temperature')}")
        
        return request_params
        
    except Exception as e:
        logger.error(f"Error applying personality rules: {e}")
        return request_params


async def get_personality_context(
    personality_id: Optional[str],
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Get full personality context for UI display
    
    Args:
        personality_id: UUID of the personality
        db: Database session
    
    Returns:
        Dictionary with personality info for UI
    """
    try:
        if not personality_id:
            return {
                "active": False,
                "name": "Default",
                "emoji": "🤖",
                "rules": {}
            }
        
        personality = await load_personality(personality_id, db)
        
        if not personality:
            return {
                "active": False,
                "name": "Unknown",
                "emoji": "❓",
                "rules": {}
            }
        
        return {
            "active": True,
            "id": personality["id"],
            "name": personality["name"],
            "emoji": personality.get("avatar_emoji", "🤖"),
            "rules": personality.get("rules", {})
        }
        
    except Exception as e:
        logger.error(f"Error getting personality context: {e}")
        return {
            "active": False,
            "name": "Error",
            "emoji": "❌",
            "rules": {}
        }


def clear_personality_cache():
    """Clear the personality cache (useful for updates)"""
    global _personality_cache
    _personality_cache = {}
    logger.info("Personality cache cleared")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring"""
    return {
        "cached_personalities": len(_personality_cache),
        "personality_ids": list(_personality_cache.keys())
    }


# Prompt enhancement functions

def enhance_prompt_with_rules(base_prompt: str, rules: Dict[str, Any]) -> str:
    """
    Enhance a prompt with additional instructions based on rules
    
    Args:
        base_prompt: Original system prompt
        rules: Personality rules dictionary
    
    Returns:
        Enhanced prompt with rule-based instructions
    """
    enhancements = []
    
    # Add length instructions
    length = rules.get("length")
    if length == "concise":
        enhancements.append("Keep your responses brief and to the point. Avoid unnecessary elaboration.")
    elif length == "detailed":
        enhancements.append("Provide comprehensive, detailed explanations with examples.")
    
    # Add emoji usage instructions
    emoji_usage = rules.get("emoji_usage")
    if emoji_usage is False:
        enhancements.append("Do not use emojis in your responses.")
    elif emoji_usage is True:
        enhancements.append("Feel free to use relevant emojis to enhance your responses.")
    
    # Add format instructions
    response_format = rules.get("response_format")
    if response_format == "bullet_points":
        enhancements.append("Structure your responses using bullet points and lists for clarity.")
    elif response_format == "structured":
        enhancements.append("Use clear headings and structured formatting in your responses.")
    elif response_format == "code_focused":
        enhancements.append("Focus on providing code examples with explanations. Use markdown code blocks.")
    elif response_format == "storytelling":
        enhancements.append("Present information in a narrative, engaging storytelling format.")
    
    # Add code preference instructions
    code_preference = rules.get("code_preference")
    if code_preference == "explained":
        enhancements.append("When providing code, always include explanations and comments.")
    elif code_preference == "minimal":
        enhancements.append("Provide minimal code examples without extensive explanation.")
    
    # Combine enhancements with base prompt
    if enhancements:
        enhanced = base_prompt + "\n\nAdditional guidelines:\n" + "\n".join(f"- {e}" for e in enhancements)
        return enhanced
    
    return base_prompt


async def prepare_llm_request(
    personality_id: Optional[str],
    user_message: str,
    db: AsyncSession,
    base_prompt: str = "",
    **request_params
) -> Dict[str, Any]:
    """
    Prepare a complete LLM request with personality applied
    
    Args:
        personality_id: UUID of the personality (optional)
        user_message: User's message
        db: Database session
        base_prompt: Base system prompt
        **request_params: Additional LLM request parameters
    
    Returns:
        Complete request dictionary ready for LLM API
    """
    try:
        # Load personality if specified
        personality = None
        if personality_id:
            personality = await load_personality(personality_id, db)
        
        # Get system prompt
        system_prompt = await get_personality_prompt(personality_id, db, base_prompt)
        
        # Enhance prompt with rules
        if personality and personality.get("rules"):
            system_prompt = enhance_prompt_with_rules(system_prompt, personality["rules"])
        
        # Apply personality rules to request parameters
        if personality:
            request_params = apply_personality_rules(personality, request_params)
        
        # Build complete request
        llm_request = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            **request_params
        }
        
        logger.info(f"Prepared LLM request with personality: {personality['name'] if personality else 'default'}")
        
        return llm_request
        
    except Exception as e:
        logger.error(f"Error preparing LLM request: {e}")
        # Return basic request without personality
        return {
            "messages": [
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": user_message}
            ],
            **request_params
        }


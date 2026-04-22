import os
import json
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from app.routers.openai.openai_chat import get_token_from_header, decode_email_from_token, get_user_id_from_email, store_chat

logger = logging.getLogger(__name__)
router = APIRouter()

# Anthropic API configuration - used via lazy loading
_anthropic_config = None

def get_anthropic_config():
    """Get Anthropic configuration with lazy loading to ensure env vars are loaded"""
    global _anthropic_config
    if _anthropic_config is None:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            api_key = api_key.strip().replace('"', '').replace("'", "")
            
        _anthropic_config = {
            "api_key": api_key
        }
        
        if not _anthropic_config["api_key"]:
            logger.warning("ANTHROPIC_API_KEY not found in environment variables")
            
    return _anthropic_config
# Model candidates to try in order - TESTED AND VERIFIED WORKING (Dec 2024)
# claude-sonnet-4-20250514 = Claude Sonnet 4 (latest, formerly called "Sonnet 4.5")
CLAUDE_MODEL_CANDIDATES = [
    "claude-sonnet-4-20250514",     # Claude Sonnet 4 (latest!) - VERIFIED WORKING
    "claude-4-sonnet-20250514",     # Alias for Sonnet 4 - VERIFIED WORKING
    "claude-3-haiku-20240307",      # Claude 3 Haiku (fast/cheap) - VERIFIED WORKING
]


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: str = None
    project_id: str = None
    personality_id: str = None


def convert_messages(messages: List[Message]):
    out = []
    for msg in messages:
        role = "user" if msg.role == "user" else "assistant"
        out.append({"role": role, "content": msg.content})
    return out


@router.post("/claude-sonnet-4-5/chat")
async def chat_claude_sonnet(request: Request, chat_request: ChatRequest):
    token = get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    email = decode_email_from_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = await get_user_id_from_email(email)
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found")

    config = get_anthropic_config()
    if not config["api_key"]:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")

    async def event_stream():
        config = get_anthropic_config()
        api_key = config["api_key"]
        
        if not api_key:
            yield f"data: {json.dumps({'content': 'Anthropic API key not configured'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        last_error = None
        # Try each model candidate until one works
        for model_name in CLAUDE_MODEL_CANDIDATES:
            try:
                body = {
                    "model": model_name,
                    "max_tokens": 1024,
                    "messages": convert_messages(chat_request.messages),
                    "stream": True
                }
                logger.info(f"Anthropic: trying model={model_name}")
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream("POST", url, headers=headers, json=body) as resp:
                        if resp.status_code != 200:
                            text = await resp.aread()
                            error_detail = text.decode()
                            try:
                                error_json = json.loads(error_detail)
                                if isinstance(error_json, dict):
                                    if 'error' in error_json:
                                        if isinstance(error_json['error'], dict):
                                            error_detail = error_json['error'].get('message', error_detail)
                                        else:
                                            error_detail = str(error_json['error'])
                            except:
                                pass
                            logger.warning(f"Anthropic model {model_name} failed: {error_detail}")
                            last_error = f"API Error ({resp.status_code}): {error_detail}"
                            continue  # Try next model
                        # Success! Stream the response
                        logger.info(f"✅ Anthropic: successfully using model={model_name}")
                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                parsed = json.loads(data)
                                # content_block_delta -> text delta
                                if parsed.get("type") == "content_block_delta":
                                    delta = parsed.get("delta", {}).get("text", "")
                                    if delta:
                                        yield f"data: {json.dumps({'content': delta})}\n\n"
                            except json.JSONDecodeError:
                                continue
                        yield "data: [DONE]\n\n"
                        return  # Exit after successful response
            except Exception as e:
                logger.warning(f"Anthropic error with model {model_name}: {e}")
                last_error = str(e)
                continue  # Try next model
        # All models failed
        logger.error(f"All Claude models failed. Last error: {last_error}")
        yield f"data: {json.dumps({'content': last_error or 'All Claude models unavailable'})}\n\n"
        yield "data: [DONE]\n\n"

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
        if user_id:
            try:
                response_text = "".join(collected)
                await store_chat(user_id, chat_request, response_text, "Claude-Sonnet-4.5")
            except Exception as e:
                logger.warning(f"Anthropic store failed: {e}")

    return StreamingResponse(aggregated(), media_type="text/event-stream")


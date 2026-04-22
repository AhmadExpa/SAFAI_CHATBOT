"""
Multi-Model Chat Router
Handles parallel requests to multiple AI models simultaneously
Similar to ChatHub.gg functionality
"""
import os
import json
import logging
import asyncio
import httpx
from typing import List, Dict, AsyncGenerator
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from jose import jwt, JWTError
from app.services.database import get_async_session
from app.services.personality_loader import load_personality, apply_personality_rules
from sqlalchemy.future import select

logger = logging.getLogger(__name__)
router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class MultiModelChatRequest(BaseModel):
    messages: List[Message]
    models: List[str]  # List of model names to use
    conversation_id: str = None
    project_id: str = None
    personality_id: str = None  # Optional, for AI personality customization

def get_token_from_header(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1]

def decode_email_from_token(token: str):
    try:
        SECRET_KEY = os.getenv("SECRET_KEY")
        ALGORITHM = os.getenv("ALGORITHM", "HS256")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            return None
        return email
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None

async def get_user_id_from_email(email: str):
    """Get user_id from email"""
    try:
        from app.routers.auth import User
        async for session in get_async_session():
            result = await session.execute(select(User).where(User.email == email))
            db_user = result.scalar_one_or_none()
            if not db_user:
                return None
            return str(db_user.user_id)
    except Exception as e:
        logger.error(f"Error getting user_id from email: {e}")
        return None

def get_model_endpoint(model_name: str, base_url: str) -> str:
    """Get API endpoint for a specific model"""
    model_map = {
        # OpenAI models
        'gpt-4.1': f'{base_url}/openai/gpt4-1/chat',
        'GPT-4.1': f'{base_url}/openai/gpt4-1/chat',
        'gpt-4': f'{base_url}/openai/gpt-4/chat',
        'GPT-4': f'{base_url}/openai/gpt-4/chat',
        'gpt-4o': f'{base_url}/openai/gpt-4o/chat',
        'GPT-4o': f'{base_url}/openai/gpt-4o/chat',
        'gpt-4.1-mini': f'{base_url}/openai/gpt-4-1-mini/chat',
        'GPT-4.1 mini': f'{base_url}/openai/gpt-4-1-mini/chat',
        'gpt-4.1-nano': f'{base_url}/openai/gpt-4-1-nano/chat',
        'GPT-4.1 nano': f'{base_url}/openai/gpt-4-1-nano/chat',
        'o4-mini': f'{base_url}/openai/o4-mini/chat',
        'O4-mini': f'{base_url}/openai/o4-mini/chat',
        'o3-mini': f'{base_url}/openai/o3-mini/chat',
        'O3-mini': f'{base_url}/openai/o3-mini/chat',
        'gpt-image-1': f'{base_url}/openai/gpt-image-1/chat',
        'GPT-image-1': f'{base_url}/openai/gpt-image-1/chat',
        'deepseek-v3': f'{base_url}/openai/deepseek-v3/chat',
        'DeepSeek V3': f'{base_url}/openai/deepseek-v3/chat',
        'deepseek-r1': f'{base_url}/openai/deepseek-r1/chat',
        'DeepSeek R1': f'{base_url}/openai/deepseek-r1/chat',
        # Grok models (XAI)
        'grok-2': f'{base_url}/xai/grok-3/chat',
        'grok-3': f'{base_url}/xai/grok-3/chat',
        'Grok-3': f'{base_url}/xai/grok-3/chat',
        'grok-4': f'{base_url}/xai/grok-4/chat',
        'Grok-4': f'{base_url}/xai/grok-4/chat',
        'Grok-2-Image': f'{base_url}/xai/grok-2-image/chat',
        # Qwen models
        'qwen-72b': f'{base_url}/qwen/qwen1/chat',
        'Qwen1': f'{base_url}/qwen/qwen1/chat',
        'qwen-max': f'{base_url}/qwen/qwen2/chat',
        'Qwen2': f'{base_url}/qwen/qwen2/chat',
        'Qwen3': f'{base_url}/qwen/qwen3/chat',
        # Moonshot models
        'k-1': f'{base_url}/moonshot/k1/chat',
        'K1': f'{base_url}/moonshot/k1/chat',
        'k-2': f'{base_url}/moonshot/k2/chat',
        'K2': f'{base_url}/moonshot/k2/chat',
        # New providers
        'Gemini-3-Pro': f'{base_url}/gemini/gemini-3-pro/chat',
        'Gemini-3-Pro-Image': f'{base_url}/gemini/gemini-3-pro-image/chat',
        'Perplexity': f'{base_url}/perplexity/perplexity/chat',
        'Claude-Sonnet-4.5': f'{base_url}/anthropic/claude-sonnet-4-5/chat',
    }
    return model_map.get(model_name, f'{base_url}/openai/gpt-4o/chat')

async def stream_single_model(model_name: str, messages: List[Message], token: str, base_url: str) -> AsyncGenerator[str, None]:
    """Stream response from a single model by calling its endpoint"""
    endpoint = get_model_endpoint(model_name, base_url)
    
    # Check if this is a Moonshot model (sends plain text, not SSE format)
    is_moonshot = model_name in ['K1', 'K2', 'k-1', 'k-2']
    
    try:
        # Prepare request body
        request_body = {
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages]
        }
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                try:
                    async with client.stream(
                        "POST",
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        },
                        json=request_body
                    ) as response:
                        if response.status_code != 200:
                            try:
                                error_text = await response.aread()
                                error_detail = error_text.decode('utf-8', errors='ignore') if error_text else f"HTTP {response.status_code}"
                                # Try to parse JSON error if possible
                                try:
                                    error_json = json.loads(error_detail)
                                    if isinstance(error_json, dict):
                                        # Extract error message from various formats
                                        if 'detail' in error_json:
                                            error_detail = error_json['detail']
                                        elif 'error' in error_json:
                                            if isinstance(error_json['error'], dict):
                                                error_detail = error_json['error'].get('message', str(error_json['error']))
                                            else:
                                                error_detail = str(error_json['error'])
                                        else:
                                            error_detail = json.dumps(error_json)
                                except:
                                    pass
                                yield f"data: {json.dumps({'model': model_name, 'error': f'HTTP {response.status_code}: {error_detail}', 'type': 'error'})}\n\n"
                            except Exception as read_error:
                                logger.error(f"Error reading error response from {model_name}: {read_error}")
                                yield f"data: {json.dumps({'model': model_name, 'error': f'HTTP {response.status_code}: Unable to read error details', 'type': 'error'})}\n\n"
                            return
                        
                        if is_moonshot:
                            # For Moonshot models, handle plain text chunks directly
                            # Moonshot sends plain text chunks, not SSE format
                            try:
                                async for chunk_bytes in response.aiter_bytes():
                                    if chunk_bytes:
                                        try:
                                            chunk = chunk_bytes.decode('utf-8', errors='ignore')
                                            
                                            # Skip conversation metadata
                                            if "<!--CONVERSATION_ID:" in chunk:
                                                # Extract content before metadata
                                                parts = chunk.split("<!--CONVERSATION_ID:")
                                                if parts[0].strip():
                                                    # Send content before metadata
                                                    yield f"data: {json.dumps({'model': model_name, 'content': parts[0], 'type': 'chunk'})}\n\n"
                                                # Skip the metadata part
                                                continue
                                            
                                            # Send each chunk as SSE format (chunks may be partial words/sentences)
                                            if chunk:
                                                yield f"data: {json.dumps({'model': model_name, 'content': chunk, 'type': 'chunk'})}\n\n"
                                        except Exception as decode_error:
                                            logger.warning(f"Error decoding chunk for {model_name}: {decode_error}")
                                            continue
                            except Exception as stream_error:
                                logger.error(f"Error streaming bytes from {model_name}: {stream_error}")
                                yield f"data: {json.dumps({'model': model_name, 'error': f'Streaming error: {str(stream_error)}', 'type': 'error'})}\n\n"
                        else:
                            # For other models, parse SSE format
                            line_count = 0
                            stream_completed = False
                            try:
                                async for line in response.aiter_lines():
                                    line_count += 1
                                    try:
                                        if line.startswith("data: "):
                                            data = line[6:].strip()
                                            if data == "[DONE]" or data == "":
                                                continue
                                            
                                            try:
                                                parsed = json.loads(data)
                                                # Overwrite/Add model name but preserve other fields (type, chunk, etc.)
                                                parsed['model'] = model_name
                                                
                                                # Ensure type is set if missing (default to chunk)
                                                if 'type' not in parsed:
                                                    parsed['type'] = 'chunk'
                                                    
                                                # Type safety for content if present
                                                if 'content' in parsed and not isinstance(parsed['content'], str):
                                                    parsed['content'] = str(parsed['content'])
                                                
                                                yield f"data: {json.dumps(parsed, ensure_ascii=False)}\n\n"
                                            except json.JSONDecodeError as je:
                                                logger.warning(f"JSON decode error in multi-model from {model_name}: {je}, data summary: {data[:100]}...")
                                                continue
                                    except Exception as line_error:
                                        logger.warning(f"Error processing line from {model_name}: {line_error}")
                                        continue
                                
                                stream_completed = True
                            except (HTTPException, Exception) as stream_error:
                                # Catch any exception during streaming, including HTTPExceptions from the endpoint
                                error_msg = str(stream_error)
                                # Try to extract more details from the error
                                # Handle FastAPI HTTPException specifically
                                if isinstance(stream_error, HTTPException):
                                    if hasattr(stream_error, 'detail'):
                                        error_msg = stream_error.detail
                                    elif hasattr(stream_error, 'status_code'):
                                        error_msg = f"HTTP {stream_error.status_code}: {error_msg}"
                                elif hasattr(stream_error, 'detail'):
                                    error_msg = stream_error.detail
                                elif hasattr(stream_error, 'args') and stream_error.args:
                                    error_msg = str(stream_error.args[0])
                                
                                # Try to parse error detail if it's JSON
                                try:
                                    if isinstance(error_msg, str):
                                        error_json = json.loads(error_msg)
                                        if isinstance(error_json, dict):
                                            if 'error' in error_json:
                                                if isinstance(error_json['error'], dict):
                                                    error_msg = error_json['error'].get('message', str(error_json['error']))
                                                else:
                                                    error_msg = str(error_json['error'])
                                            elif 'detail' in error_json:
                                                error_msg = error_json['detail']
                                except:
                                    pass
                                
                                logger.error(f"Error streaming lines from {model_name}: {stream_error}", exc_info=True)
                                yield f"data: {json.dumps({'model': model_name, 'error': f'Streaming error: {error_msg}', 'type': 'error'})}\n\n"
                            
                            # Signal completion if stream completed successfully or if we got at least one line
                            if stream_completed or line_count > 0:
                                yield f"data: {json.dumps({'model': model_name, 'type': 'done'})}\n\n"
                            else:
                                # If we didn't get any lines and stream didn't complete, signal error completion
                                yield f"data: {json.dumps({'model': model_name, 'type': 'done'})}\n\n"
                except (httpx.HTTPStatusError, httpx.RequestError, HTTPException, Exception) as http_error:
                    # Catch all exceptions that might occur during response handling or cleanup
                    error_detail = str(http_error)
                    try:
                        # Handle FastAPI HTTPException specifically
                        if isinstance(http_error, HTTPException):
                            if hasattr(http_error, 'detail'):
                                error_detail = http_error.detail
                            elif hasattr(http_error, 'status_code'):
                                error_detail = f"HTTP {http_error.status_code}: {error_detail}"
                        elif isinstance(http_error, httpx.HTTPStatusError):
                            if hasattr(http_error, 'response') and http_error.response:
                                try:
                                    error_text = await http_error.response.aread()
                                    if error_text:
                                        error_detail = error_text.decode('utf-8', errors='ignore')
                                        try:
                                            error_json = json.loads(error_detail)
                                            if isinstance(error_json, dict):
                                                if 'detail' in error_json:
                                                    error_detail = error_json['detail']
                                                elif 'error' in error_json:
                                                    if isinstance(error_json['error'], dict):
                                                        error_detail = error_json['error'].get('message', str(error_json['error']))
                                                    else:
                                                        error_detail = str(error_json['error'])
                                        except:
                                            pass
                                except Exception:
                                    error_detail = f"HTTP {http_error.response.status_code if hasattr(http_error, 'response') and http_error.response else 'Unknown'}"
                        elif hasattr(http_error, 'detail'):
                            error_detail = http_error.detail
                        elif hasattr(http_error, 'args') and http_error.args:
                            error_detail = str(http_error.args[0])
                        
                        # Try to parse error detail if it's JSON
                        try:
                            if isinstance(error_detail, str):
                                error_json = json.loads(error_detail)
                                if isinstance(error_json, dict):
                                    if 'error' in error_json:
                                        if isinstance(error_json['error'], dict):
                                            error_detail = error_json['error'].get('message', str(error_json['error']))
                                        else:
                                            error_detail = str(error_json['error'])
                                    elif 'detail' in error_json:
                                        error_detail = error_json['detail']
                        except:
                            pass
                    except Exception:
                        pass
                    logger.error(f"HTTP/Request error from {model_name}: {error_detail}")
                    yield f"data: {json.dumps({'model': model_name, 'error': f'HTTP Error: {error_detail}', 'type': 'error'})}\n\n"
                    # Signal completion after error
                    yield f"data: {json.dumps({'model': model_name, 'type': 'done'})}\n\n"
        except Exception as client_error:
            logger.error(f"Client error from {model_name}: {client_error}")
            yield f"data: {json.dumps({'model': model_name, 'error': f'Client error: {str(client_error)}', 'type': 'error'})}\n\n"
                
    except Exception as e:
        logger.error(f"Error streaming from {model_name}: {e}", exc_info=True)
        yield f"data: {json.dumps({'model': model_name, 'error': str(e), 'type': 'error'})}\n\n"

async def stream_multi_model_responses(models: List[str], messages: List[Message], token: str, base_url: str) -> AsyncGenerator[str, None]:
    """Stream responses from multiple models in parallel"""
    queue = asyncio.Queue()
    
    async def collect_from_model(model_name: str):
        try:
            async for chunk in stream_single_model(model_name, messages, token, base_url):
                await queue.put((model_name, chunk))
        except Exception as e:
            logger.error(f"Error collecting from {model_name}: {e}")
            await queue.put((model_name, f"data: {json.dumps({'model': model_name, 'error': str(e), 'type': 'error'})}\n\n"))
        finally:
            await queue.put((model_name, None))  # Signal completion
    
    # Start all collection tasks
    tasks = [asyncio.create_task(collect_from_model(model)) for model in models]
    
    # Track which models are done
    completed_models = set()
    
    # Stream chunks as they arrive
    while len(completed_models) < len(models):
        model_name, chunk = await queue.get()
        
        if chunk is None:
            completed_models.add(model_name)
            continue
        
        yield chunk
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Send final completion signal
    yield f"data: {json.dumps({'type': 'all_done'})}\n\n"

@router.post("/multi-model/chat")
async def multi_model_chat(request: Request, chat_request: MultiModelChatRequest):
    """Handle multi-model chat requests - all models respond in parallel"""
    try:
        # Authentication
        token = get_token_from_header(request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        email = decode_email_from_token(token)
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = await get_user_id_from_email(email)
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Validate models
        if not chat_request.models or len(chat_request.models) == 0:
            raise HTTPException(status_code=400, detail="At least one model must be specified")
        
        if len(chat_request.models) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 models allowed")
        
        # Validate messages
        if not chat_request.messages or len(chat_request.messages) == 0:
            raise HTTPException(status_code=400, detail="At least one message is required")
        
        # Apply personality if personality_id is provided
        messages = [msg.dict() for msg in chat_request.messages]
        personality_data = None
        if chat_request.personality_id:
            try:
                async for db in get_async_session():
                    personality_data = await load_personality(chat_request.personality_id, db)
                    if personality_data:
                        logger.info(f"Applying personality to multi-model chat: {personality_data['name']} ({personality_data.get('avatar_emoji', '')})")
                        
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
        
        # Convert messages back to Message objects
        messages_list = [Message(**msg) for msg in messages]
        
        # Get base URL from request - works in both dev and production
        # Handle reverse proxy headers (Railway, etc.)
        scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("X-Forwarded-Host", request.headers.get("Host", request.url.hostname))
        
        # Construct base URL
        if scheme and host:
            base_url = f"{scheme}://{host}".rstrip('/')
        else:
            base_url = str(request.base_url).rstrip('/')
        
        # Fallback to environment variable if needed
        if not base_url or base_url.startswith('http://127.0.0.1') or base_url.startswith('http://localhost'):
            base_url = os.getenv("API_BASE_URL", base_url or "http://127.0.0.1:8000")
        
        logger.info(f"Multi-model chat request: {len(chat_request.models)} models, {len(chat_request.messages)} messages, base_url: {base_url}")
        
        # Stream responses from all models
        async def generate():
            # Send initial metadata with personality info
            metadata = {'type': 'start', 'models': chat_request.models}
            if personality_data:
                metadata['personality'] = {
                    'id': str(personality_data['id']),
                    'name': personality_data['name'],
                    'avatar_emoji': personality_data.get('avatar_emoji', '🤖')
                }
            yield f"data: {json.dumps(metadata)}\n\n"
            
            # Stream responses from all models
            async for chunk in stream_multi_model_responses(chat_request.models, messages_list, token, base_url):
                yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in multi-model chat: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


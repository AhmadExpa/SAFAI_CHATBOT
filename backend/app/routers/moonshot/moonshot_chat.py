import os
import json
import logging
from typing import AsyncGenerator, List
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from pydantic import BaseModel
from jose import jwt, JWTError
from app.services.database import get_async_session, store_chat_conversation
from sqlalchemy.future import select

# Environment variables are loaded in main.py

# Configure logging
logger = logging.getLogger(__name__)

# Create router
moonshot_router = APIRouter()

# Moonshot API configuration - used via lazy loading
_moonshot_config = None

def get_moonshot_config():
    """Get Moonshot configuration with lazy loading to ensure env vars are loaded"""
    global _moonshot_config
    if _moonshot_config is None:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("MOONSHOT_API_KEY")
        if api_key:
            api_key = api_key.strip().replace('"', '').replace("'", "")
            
        _moonshot_config = {
            "api_key": api_key,
            "base_url": os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
        }
        
        if not _moonshot_config["api_key"]:
            logger.warning("MOONSHOT_API_KEY not found in environment variables")
            
    return _moonshot_config

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: str = None
    project_name: str = None

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

async def get_moonshot_response(messages, model_name, api_key, base_url, max_retries=3):
    """Get response from Moonshot API with retry logic and better error handling"""
    if not api_key:
        logger.error(f"Moonshot API key not found for {model_name}")
        raise Exception(f"Moonshot API key not found for {model_name}")
    
    logger.info(f"Making Moonshot API request with {len(messages)} messages for model: {model_name}")
    logger.info(f"Using API endpoint: {base_url}")
    
    # Convert messages to the format expected by Moonshot API
    moonshot_messages = []
    for msg in messages:
        moonshot_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} for Moonshot API request")
            
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                verify=True,
                follow_redirects=True
            ) as client:
                logger.info(f"Sending request to Moonshot API: {base_url}/chat/completions")
                
                # Use OpenAI-compatible format for Moonshot API
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "PhatagiAI/1.0"
                    },
                    json={
                        "model": model_name,
                        "messages": moonshot_messages,
                        "max_tokens": 1000,
                        "temperature": 0.7,
                        "stream": True
                    }
                )
                
                logger.info(f"Moonshot API response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info("Moonshot API request successful")
                    return response
                elif response.status_code == 401:
                    logger.error("Moonshot API authentication failed - check API key")
                    raise Exception("Moonshot API authentication failed - invalid API key")
                elif response.status_code == 429:
                    logger.warning("Moonshot API rate limit exceeded")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.info(f"Rate limited, waiting {wait_time} seconds before retry...")
                        import asyncio
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception("Moonshot API rate limit exceeded after all retries")
                else:
                    error_text = response.text
                    logger.error(f"Moonshot API error: {response.status_code} - {error_text}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"API error, waiting {wait_time} seconds before retry...")
                        import asyncio
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Moonshot API error: {response.status_code} - {error_text}")
                        
        except httpx.ConnectError as e:
            logger.error(f"Moonshot API connection error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Connection failed, waiting {wait_time} seconds before retry...")
                import asyncio
                await asyncio.sleep(wait_time)
                continue
            else:
                raise Exception(f"Failed to connect to Moonshot API after {max_retries} attempts: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Moonshot API timeout error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Timeout, waiting {wait_time} seconds before retry...")
                import asyncio
                await asyncio.sleep(wait_time)
                continue
            else:
                raise Exception(f"Moonshot API request timed out after {max_retries} attempts: {e}")
        except Exception as e:
            logger.error(f"Moonshot API error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Error occurred, waiting {wait_time} seconds before retry...")
                import asyncio
                await asyncio.sleep(wait_time)
                continue
            else:
                raise Exception(f"Moonshot API error after {max_retries} attempts: {e}")
    
    # This should never be reached, but just in case
    raise Exception(f"Moonshot API failed after {max_retries} attempts")

async def stream_moonshot_response(messages, model_name, api_key, base_url) -> AsyncGenerator[str, None]:
    """Stream response from Moonshot API with OpenAI-compatible format"""
    try:
        response = await get_moonshot_response(messages, model_name, api_key, base_url)
        
        logger.info("Starting to stream Moonshot response")
        
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix
                
                if data.strip() == "[DONE]":
                    logger.info("Moonshot streaming completed")
                    break
                    
                try:
                    chunk = json.loads(data)
                    logger.debug(f"Moonshot streaming chunk: {chunk}")
                    
                    # Handle OpenAI-compatible streaming format
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            content = delta["content"]
                            logger.debug(f"Moonshot streaming content: {content}")
                            yield content
                    # Handle error responses
                    elif "error" in chunk:
                        error_msg = chunk["error"].get("message", "Unknown error")
                        logger.error(f"Moonshot API error in stream: {error_msg}")
                        yield f"Error: {error_msg}"
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse Moonshot chunk: {data}, error: {e}")
                    continue
            elif line.strip():  # Handle non-data lines
                logger.debug(f"Moonshot non-data line: {line}")
                continue
                    
    except Exception as e:
        logger.error(f"Moonshot API streaming error: {e}")
        error_message = f"Moonshot API is currently unavailable. Please try again later or use a different model. Error: {str(e)}"
        yield error_message

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

async def chat_and_store(request: Request, chat_request: ChatRequest, model_name: str, api_key: str, base_url: str):
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
    
    # Get response from Moonshot API
    messages = [msg.dict() for msg in chat_request.messages]
    response_chunks = []
    
    async def event_stream():
        try:
            async for chunk in stream_moonshot_response(messages, model_name, api_key, base_url):
                response_chunks.append(chunk)
                yield chunk
            
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
            yield f"Error: {str(e)}"
    
    # Stream response to client
    streaming_response = StreamingResponse(event_stream(), media_type="text/plain")
    
    return streaming_response

@moonshot_router.post("/k1/chat")
async def k1_chat(request: Request, chat_request: ChatRequest):
    """Chat with Moonshot K1 model"""
    try:
        config = get_moonshot_config()
        return await chat_and_store(request, chat_request, "moonshot-v1-8k", config["api_key"], config["base_url"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Moonshot K1 chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@moonshot_router.post("/k2/chat")
async def k2_chat(request: Request, chat_request: ChatRequest):
    """Chat with Moonshot K2 model"""
    try:
        config = get_moonshot_config()
        return await chat_and_store(request, chat_request, "moonshot-v1-32k", config["api_key"], config["base_url"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Moonshot K2 chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import BaseModel
import openai
import os
from fastapi.responses import StreamingResponse
from app.utils.openai_stream import stream_openai_chat
from typing import List
from jose import jwt, JWTError
import json
from app.services.database import get_async_session
from app.services.personality_loader import load_personality, apply_personality_rules
from sqlalchemy.future import select
from app.models.project_files import ProjectFile
import logging
import httpx
import asyncio

# Set up logger early for use in safe_unicode_content
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Import the centralized logging configuration
from app.config.logging import get_logger
# Logger already initialized at the top of the file - reuse it
# logger = get_logger(__name__)

# Import load_dotenv to ensure env vars are loaded even if module is imported early
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

# Global variables for lazy initialization
_openai_client = None
_openai_api_key = None

def get_openai_client():
    """Get OpenAI client with lazy initialization to ensure env vars are loaded"""
    global _openai_client, _openai_api_key
    
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        # Cleanup key - remove any whitespace or quotes
        if api_key:
            api_key = api_key.strip().replace('"', '').replace("'", "")
            
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables.")
            return None, None
            
        if not api_key.startswith('sk-'):
            logger.error(f"OpenAI API key doesn't start with 'sk-': {api_key[:10]}...")
            return None, None
            
        _openai_api_key = api_key
        proxy_url = os.getenv("PROXY_URL")
        proxy_auth = os.getenv("PROXY_AUTH")
        
        try:
            # Configure proxy if available
            if proxy_url:
                if proxy_auth and ":" in proxy_auth:
                    username, password = proxy_auth.split(":", 1)
                    proxy_url_with_auth = proxy_url.replace("://", f"://{username}:{password}@")
                else:
                    proxy_url_with_auth = proxy_url
                
            # Create custom httpx client to avoid 'proxies' vs 'proxy' incompatibility in openai library
            # with httpx 0.28+ on Python 3.14
            client_kwargs = {"verify": True}
            if proxy_url:
                client_kwargs["proxy"] = proxy_url_with_auth
                
            http_client = httpx.Client(**client_kwargs)
            _openai_client = openai.OpenAI(api_key=_openai_api_key, http_client=http_client)
            logger.info("OpenAI client initialized successfully with custom http_client")
            
            # Optional: test connectivity (commented out for faster startup unless needed)
            # try:
            #     _openai_client.models.list()
            # except:
            #     pass
                
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return None, None
            
    return _openai_client, _openai_api_key

# JWT Configuration is imported from app.routers.auth in decode_email_from_token

async def get_openai_image_response(prompt: str):
    """Generate image using OpenAI DALL-E API"""
    client, api_key = get_openai_client()
    if not api_key:
        raise Exception("OpenAI API key not found")

    proxy_url = os.getenv("PROXY_URL")
    proxy_auth = os.getenv("PROXY_AUTH")
    
    logger.info(f"Making OpenAI DALL-E image generation request for prompt: {prompt[:100]}...")
    
    try:
        # Configure httpx client for image generation
        client_kwargs = {
            "timeout": httpx.Timeout(180.0, connect=15.0, read=180.0, write=30.0),
            "limits": httpx.Limits(max_keepalive_connections=5, max_connections=10),
            "verify": True,
            "follow_redirects": True
        }
        
        if proxy_url:
            # Parse proxy authentication if provided
            if proxy_auth and ":" in proxy_auth:
                username, password = proxy_auth.split(":", 1)
                proxy_url_with_auth = proxy_url.replace("://", f"://{username}:{password}@")
            else:
                proxy_url_with_auth = proxy_url
            
            client_kwargs["proxy"] = proxy_url_with_auth
            logger.info(f"Using proxy for OpenAI image API: {proxy_url}")
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(**client_kwargs) as http_client:
                    logger.info(f"Sending request to OpenAI DALL-E API... (attempt {attempt + 1}/{max_retries})")
                    
                    # Prepare request payload for DALL-E 3
                    payload = {
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": "standard"
                    }
                    
                    logger.info(f"OpenAI DALL-E payload: {payload}")
                    
                    response = await http_client.post(
                        "https://api.openai.com/v1/images/generations",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json=payload
                    )
                    
                    logger.info(f"OpenAI DALL-E API response status: {response.status_code}")
                    
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
                    
                    error_text = response.text
                    logger.error(f"OpenAI DALL-E API error: {response.status_code} - {error_text}")
                    raise Exception(f"OpenAI DALL-E API error: {response.status_code} - {error_text}")
                    
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
                logger.error(f"Unexpected error in OpenAI DALL-E API call: {e}")
                raise
            
    except httpx.ConnectError as e:
        logger.error(f"OpenAI DALL-E API connection error: {e}")
        raise Exception(f"Failed to connect to OpenAI DALL-E API: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"OpenAI DALL-E API timeout: {e}")
        raise Exception(f"OpenAI DALL-E API request timed out: {e}")
    except Exception as e:
        logger.error(f"OpenAI DALL-E API error: {e}")
        raise Exception(f"OpenAI DALL-E API error: {e}")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    project_name: str = None  # Optional, for project_name field
    conversation_id: str = None  # Optional, for continuing existing conversation
    project_id: str = None  # Optional, for including project context
    personality_id: str = None  # Optional, for AI personality customization

def build_context_aware_prompt(messages: List[Message]) -> str:
    """Build a context-aware prompt from conversation history"""
    # Get the last user message as the main prompt
    user_messages = [msg for msg in messages if msg.role == 'user']
    if not user_messages:
        return "A beautiful image"
    
    last_message = user_messages[-1].content
    
    # If there's conversation history, add context
    if len(messages) > 1:
        # Limit context to last 3 exchanges to avoid token limits
        recent_messages = messages[max(0, len(messages) - 6):]
        context_parts = []
        for msg in recent_messages[:-1]:  # Exclude the last message
            if msg.role == 'user':
                context_parts.append(f"User said: {msg.content[:100]}")
            elif msg.role == 'assistant':
                context_parts.append(f"Assistant said: {msg.content[:100]}")
        
        if context_parts:
            context = " ".join(context_parts)
            return f"{last_message} (Context: {context})"
    
    return last_message

def get_token_from_header(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1]

def decode_email_from_token(token: str):
    """Decode email from JWT token using standardized auth logic"""
    try:
        from app.routers.auth import SECRET_KEY, ALGORITHM
        from jose import jwt
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None

async def get_project_context(project_id: str, user_id: str) -> str:
    """Get project context including all file contents"""
    if not project_id:
        return ""
    
    try:
        async for session in get_async_session():
            # Get project files with content
            result = await session.execute(
                select(ProjectFile).where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.user_id == user_id
                ).order_by(ProjectFile.upload_order)
            )
            project_files = result.scalars().all()
            
            if not project_files:
                return ""
            
            context_parts = []
            for file in project_files:
                if file.file_content and not file.file_content.startswith("[Error"):
                    # Truncate very long content to avoid token limits
                    content = file.file_content
                    if len(content) > 100000:  # Increased from 10000 to 100000 characters
                        content = content[:100000] + "... [truncated]"
                    
                    context_parts.append(f"File: {file.original_filename}\nContent:\n{content}\n")
                elif file.file_content and file.file_content.startswith("[Error"):
                    logger.warning(f"Skipping file {file.original_filename} due to processing error: {file.file_content[:50]}...")
            
            if context_parts:
                full_context = "\n".join(context_parts)
                logger.info(f"Retrieved project context with {len(project_files)} files, total length: {len(full_context)}")
                return full_context
            else:
                logger.info(f"No file content found for project {project_id}")
                return ""
                
    except Exception as e:
        logger.error(f"Error getting project context: {e}")
        return ""

async def get_user_id_from_email(email: str):
    """Get user_id from email with enhanced error handling"""
    try:
        from app.routers.auth import User
        from app.services.database import get_async_session
        
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
                        project_id=chat_request.project_id,
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

async def get_deepseek_response(messages, model_name):
    """Get response from DeepSeek API with improved timeout handling and fallback"""
    import httpx
    import asyncio
    
    # Check if DeepSeek is disabled
    disable_deepseek = os.getenv("DISABLE_DEEPSEEK", "false").lower() == "true"
    disable_deepseek_temp = os.getenv("DISABLE_DEEPSEEK_TEMP", "false").lower() == "true"
    
    
    if disable_deepseek or disable_deepseek_temp:
        logger.info("DeepSeek is disabled via configuration")
        raise Exception("DeepSeek is disabled via configuration")
    
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        logger.warning("DeepSeek API key not found, falling back to OpenAI")
        raise Exception("DeepSeek API key not found")
    
    logger.info(f"Using DeepSeek API key: {deepseek_api_key[:10]}...")
    
    # Get timeout from configuration - increased for better reliability
    default_timeout = int(os.getenv("DEEPSEEK_TIMEOUT", "60"))  # Increased from 30 to 60
    
    logger.info(f"Making DeepSeek API request with {len(messages)} messages")
    
    # Try multiple endpoints with longer timeouts for DeepSeek API
    endpoints_to_try = [
        {
            "url": "https://api.deepseek.com/v1/chat/completions",
            "timeout": default_timeout,
            "connect_timeout": 20.0  # Increased from 15
        },
        {
            "url": "https://api.deepseek.ai/v1/chat/completions",
            "timeout": default_timeout,  # Use same timeout
            "connect_timeout": 20.0  # Increased from 12
        }
    ]
    
    logger.info(f"Trying {len(endpoints_to_try)} DeepSeek endpoints...")
    
    for endpoint_config in endpoints_to_try:
        endpoint = endpoint_config["url"]
        timeout = endpoint_config["timeout"]
        connect_timeout = endpoint_config["connect_timeout"]
        
        try:
            logger.info(f"Trying endpoint: {endpoint} (timeout: {timeout}s)")
            
            # Use asyncio.wait_for for better timeout control
            async def make_request():
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout, connect=connect_timeout),
                    limits=httpx.Limits(max_keepalive_connections=1, max_connections=2),
                    verify=True,
                    follow_redirects=True,
                    http2=False  # Disable HTTP/2 for better compatibility
                ) as client:
                    logger.info("Sending request to DeepSeek API...")
                    
                    response = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {deepseek_api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "PhatagiAI/1.0",
                            "Accept": "application/json"
                        },
                        json={
                            "model": "deepseek-chat",
                            "messages": messages,
                            "stream": True,
                            "max_tokens": 1000
                        }
                    )
                    return response
            
            # Use asyncio.wait_for to enforce timeout with streaming
            response = await asyncio.wait_for(make_request(), timeout=timeout)
            
            logger.info(f"DeepSeek API response status: {response.status_code}")
            
            if response.status_code == 200:
                logger.info(f"Successfully connected to {endpoint}")
                # Check if response is streaming
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    logger.info("Received streaming response from DeepSeek API")
                return response
            elif response.status_code == 502:
                logger.warning(f"Bad Gateway for {endpoint} - server may be down")
                continue
            elif response.status_code == 503:
                logger.warning(f"Service Unavailable for {endpoint} - server overloaded")
                continue
            elif response.status_code == 429:
                logger.warning(f"Rate limited for {endpoint} - too many requests")
                continue
            else:
                error_text = response.text
                logger.warning(f"DeepSeek API error on {endpoint}: {response.status_code} - {error_text}")
                continue
                
        except asyncio.TimeoutError as e:
            logger.warning(f"⏱️ Timeout for {endpoint} after {timeout}s: {str(e)}")
            continue
        except httpx.ConnectError as e:
            logger.warning(f"🔌 Connection failed for {endpoint}: {str(e)}")
            continue
        except httpx.TimeoutException as e:
            logger.warning(f"⏱️ HTTP Timeout for {endpoint}: {str(e)}")
            continue
        except httpx.HTTPStatusError as e:
            logger.warning(f"❌ HTTP error for {endpoint}: Status {e.response.status_code} - {e.response.text[:200]}")
            continue
        except Exception as e:
            logger.warning(f"⚠️ Unexpected error for {endpoint}: {type(e).__name__} - {str(e)}")
            continue
    
    # If all endpoints fail, provide a helpful error message and suggest alternatives
    logger.error("All DeepSeek API endpoints failed")
    logger.info("DeepSeek API is currently unreachable. This may be due to:")
    logger.info("1. Regional restrictions")
    logger.info("2. API maintenance")
    logger.info("3. Network connectivity issues")
    logger.info("4. Server overload or temporary outages")
    logger.info("Please try using OpenAI models (GPT-4o, GPT-4) instead.")
    
    # Check if we should temporarily disable DeepSeek
    disable_deepseek_temp = os.getenv("DISABLE_DEEPSEEK_TEMP", "false").lower() == "true"
    if disable_deepseek_temp:
        logger.info("DeepSeek temporarily disabled due to API issues")
    
    
    raise Exception("DeepSeek API is currently unreachable. This may be due to regional restrictions, API maintenance, or server issues. Please try using OpenAI models (GPT-4o, GPT-4) instead.")

async def chat_and_store(request: Request, chat_request: ChatRequest, model_name: str):
    logger.info(f"Received chat request for model: {model_name}")
    
    # Store original model name for reference
    original_model = model_name
    
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
    
    # Get project context if project_id is provided
    project_context = ""
    if chat_request.project_id and user_id:
        project_context = await get_project_context(chat_request.project_id, user_id)
        if project_context:
            logger.info(f"Including project context for project {chat_request.project_id}")
    
    # Get response from appropriate API
    messages = [msg.dict() for msg in chat_request.messages]
    
    # Add project context to the first user message if available
    if project_context and messages:
        # Find the last user message and add context
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get('role') == 'user':
                original_content = messages[i].get('content', '')
                messages[i]['content'] = f"{original_content}\n\nProject Context:\n{project_context}"
                break
    
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
    
    response_chunks = []
    
    async def event_stream():
        import json  # Ensure json is available in local scope
        try:
            
            # Check if it's a DeepSeek model
            if model_name.startswith('deepseek'):
                try:
                    response = await get_deepseek_response(messages, model_name)
                    
                    # Handle DeepSeek streaming response with Unicode safety
                    async for line in response.aiter_lines():
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            if data.strip() == '[DONE]':
                                break
                            try:
                                import json
                                chunk_data = json.loads(data)
                                if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        # Debug: Log what we're getting from DeepSeek
                                        logger.debug(f"DeepSeek content type: {type(content)}, value: {repr(content)}")
                                        
                                        # Ensure content is properly handled (convert to string if needed)
                                        if not isinstance(content, str):
                                            content = str(content) if content is not None else ""
                                        
                                        response_chunks.append(content)
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
                                
                except Exception as e:
                    logger.error(f"DeepSeek API error: {e}")
                    logger.info("Attempting fallback to OpenAI GPT-4o...")
                    
                    # Fallback to OpenAI GPT-4o
                    client, api_key = get_openai_client()
                    if client is not None:
                        try:
                            # Send fallback message in SSE format
                            fallback_msg = '⚠️ DeepSeek API unavailable. Switching to OpenAI GPT-4o...\n\n'
                            yield f"data: {json.dumps({'content': fallback_msg})}\n\n"
                            
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=messages,
                                stream=True
                            )
                            for chunk in response:
                                delta = chunk.choices[0].delta.content
                                if delta:
                                    # Debug logging
                                    logger.debug(f"Fallback delta type: {type(delta)}, value: {repr(delta)}")
                                    
                                    # Ensure delta is properly handled
                                    if delta is not None:
                                        if not isinstance(delta, str):
                                            delta = str(delta)
                                        
                                        response_chunks.append(delta)
                                        yield f"data: {json.dumps({'content': delta})}\n\n"
                        except Exception as openai_error:
                            logger.error(f"OpenAI fallback also failed: {openai_error}")
                            error_message = f"Both DeepSeek and OpenAI APIs are currently unavailable. DeepSeek error: {str(e)}. OpenAI error: {str(openai_error)}"
                            yield f"data: {json.dumps({'content': error_message})}\n\n"
                            return
                    else:
                        error_message = f"DeepSeek API is currently unavailable and OpenAI fallback is not configured. Please check your API keys. Error: {str(e)}"
                        yield f"data: {json.dumps({'content': error_message})}\n\n"
                        return
            else:
                # Use OpenAI client for other models
                client, api_key = get_openai_client()
                if client is None:
                    error_message = "OpenAI API key not configured. Please check your environment variables."
                    logger.error(error_message)
                    yield f"data: {json.dumps({'content': error_message})}\n\n"
                    return
                
                try:
                    logger.info(f"Making OpenAI API call with model: {model_name}")
                    # logger.info(f"API key being used: {client.api_key[:10]}...{client.api_key[-4:]} (length: {len(client.api_key)})")
                    
                    # Prepare API parameters
                    api_params = {
                        "model": model_name,
                        "messages": messages,
                        "stream": True,
                        "temperature": 0.7,
                    }

                    reasoning_models = {"o3-mini", "o4-mini"}
                    if model_name in reasoning_models:
                        api_params["max_completion_tokens"] = 1000
                    else:
                        api_params["max_tokens"] = 1000
                    
                    # Apply personality rules to parameters
                    if personality_data:
                        api_params = apply_personality_rules(personality_data, api_params)
                        if model_name in reasoning_models and "max_tokens" in api_params:
                            api_params["max_completion_tokens"] = api_params.pop("max_tokens")
                        max_tokens_value = api_params.get("max_completion_tokens", api_params.get("max_tokens"))
                        logger.info(f"Applied personality rules: temp={api_params.get('temperature')}, max_tokens={max_tokens_value}")

                    if model_name in reasoning_models:
                        api_params.pop("temperature", None)
                    
                    response = client.chat.completions.create(**api_params)
                    for chunk in response:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            # Debug: Log what we're actually getting
                            logger.debug(f"Delta type: {type(delta)}, value: {repr(delta)}")
                            
                            # Ensure delta is a string
                            if not isinstance(delta, str):
                                delta = str(delta) if delta is not None else ""
                            
                            response_chunks.append(delta)
                            yield f"data: {json.dumps({'content': delta})}\n\n"
                except openai.APIConnectionError as e:
                    logger.error(f"OpenAI API connection error: {e}")
                    error_message = f"Connection error: Unable to reach OpenAI API. This may be due to network issues, API maintenance, or regional restrictions. Please check your internet connection and try again. If the problem persists, try using a different model or contact support."
                    yield f"data: {json.dumps({'content': error_message})}\n\n"
                    return
                except openai.APIError as e:
                    logger.error(f"OpenAI API error: {e}")
                    error_message = f"OpenAI API error: {str(e)}. Please check your API key and try again."
                    yield f"data: {json.dumps({'content': error_message})}\n\n"
                    return
                except openai.RateLimitError as e:
                    logger.error(f"OpenAI rate limit error: {e}")
                    error_message = f"Rate limit exceeded: {str(e)}. Please wait a moment and try again."
                    yield f"data: {json.dumps({'content': error_message})}\n\n"
                    return
                except Exception as e:
                    logger.error(f"Unexpected OpenAI error: {e}")
                    error_message = f"Unexpected error: {str(e)}. Please try again or contact support."
                    yield f"data: {json.dumps({'content': error_message})}\n\n"
                    return
            
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
                yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
                
        except Exception as e:
            logger.error(f"Error in API streaming: {e}")
            yield f"data: {json.dumps({'content': f'Error: {str(e)}'})}\n\n"
    
    # Stream response to client as Server-Sent Events
    streaming_response = StreamingResponse(event_stream(), media_type="text/event-stream")
    
    return streaming_response

@router.post("/gpt4-1/chat")
async def chat_gpt4_1(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "gpt-4.1")

@router.post("/gpt-4/chat")
async def chat_gpt4(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "gpt-4")

@router.post("/gpt-4o/chat")
async def chat_gpt4o(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "gpt-4o")

@router.post("/gpt-image-1/chat")
async def chat_gpt_image_1(request: Request, chat_request: ChatRequest):
    """Generate image with GPT-image-1 (DALL-E) using conversation context"""
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
        
        # Get image generation response
        response = await get_openai_image_response(context_prompt)
        
        # Parse JSON response
        try:
            image_data = response.json()
        except Exception as e:
            logger.error(f"Error parsing image response: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to parse image response: {str(e)}")
        
        # Extract image URL from response
        if 'data' in image_data and len(image_data['data']) > 0:
            image_url = image_data['data'][0].get('url')
            if not image_url:
                logger.error("No image URL in response")
                raise HTTPException(status_code=500, detail="No image URL in response")
            
            logger.info(f"Generated image URL: {image_url}")
            logger.info(f"Image URL domain: {image_url.split('/')[2] if len(image_url.split('/')) > 2 else 'unknown'}")
            
            # Store the conversation if user_id is available
            # Use the same store_chat function that Grok uses for consistency
            if user_id:
                try:
                    response_text = f"![Generated Image]({image_url})"
                    logger.info(f"Storing GPT image generation with URL: {image_url[:100]}...")
                    logger.info(f"Storing with model: gpt-image-1")
                    conversation_id = await store_chat(user_id, chat_request, response_text, "gpt-image-1")
                    if conversation_id:
                        logger.info(f"Successfully stored GPT image generation in conversation: {conversation_id}")
                        logger.info(f"Stored image URL: {image_url}")
                        logger.info(f"Stored model_used: gpt-image-1")
                    else:
                        logger.warning("store_chat returned None for GPT image generation")
                except Exception as e:
                    logger.warning(f"Failed to store GPT image generation: {e}", exc_info=True)
            
            # Return the image URL as a streaming response
            async def generate():
                try:
                    safe_image_url = image_url
                    safe_content = f"![Generated Image]({safe_image_url})"
                    
                    # Create JSON response
                    response_data = {
                        'content': safe_content,
                        'type': 'image'
                    }
                    
                    json_response = json.dumps(response_data, ensure_ascii=False)
                    yield f"data: {json_response}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error in image response: {e}")
                    error_data = {
                        'content': f"Error generating image: {str(e)}",
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
        else:
            logger.error(f"Unexpected image API response format: {image_data}")
            raise HTTPException(status_code=500, detail="Unexpected image API response format")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GPT-image-1 chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint to diagnose API connectivity issues"""
    client, api_key = get_openai_client()
    health_status = {
        "status": "healthy",
        "openai_configured": client is not None,
        "api_key_present": bool(api_key),
        "proxy_configured": bool(os.getenv("PROXY_URL")),
        "timestamp": "2025-10-02T07:27:00Z"
    }
    
    if client is None:
        health_status["status"] = "unhealthy"
        health_status["error"] = "OpenAI client not initialized"
        return health_status
    
    # Test basic connectivity
    try:
        # Simple API test
        test_response = client.models.list()
        health_status["openai_connectivity"] = "success"
        health_status["models_available"] = len(test_response.data) if test_response.data else 0
    except openai.APIConnectionError as e:
        health_status["status"] = "unhealthy"
        health_status["openai_connectivity"] = "connection_error"
        health_status["error"] = f"Connection error: {str(e)}"
    except openai.APIError as e:
        health_status["status"] = "unhealthy"
        health_status["openai_connectivity"] = "api_error"
        health_status["error"] = f"API error: {str(e)}"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["openai_connectivity"] = "unknown_error"
        health_status["error"] = f"Unknown error: {str(e)}"
    
    return health_status

@router.post("/gpt-4-1-mini/chat")
async def chat_gpt4_1_mini(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "gpt-4.1-mini")

@router.post("/gpt-4-1-nano/chat")
async def chat_gpt4_1_nano(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "gpt-4.1-nano")

@router.post("/o4-mini/chat")
async def chat_o4_mini(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "o4-mini")

@router.post("/o3-mini/chat")
async def chat_o3_mini(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "o3-mini")

# DeepSeek endpoints
@router.post("/deepseek-v3/chat")
async def chat_deepseek_v3(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "deepseek-v3")

@router.post("/deepseek-r1/chat")
async def chat_deepseek_r1(request: Request, chat_request: ChatRequest):
    return await chat_and_store(request, chat_request, "deepseek-r1")

# Grok endpoints
@router.post("/grok-3/chat")
async def chat_grok_3(request: Request, chat_request: ChatRequest):
    from app.routers.xai.xai_chat import grok_3_chat as xai_grok_3_chat

    return await xai_grok_3_chat(request, chat_request)

@router.post("/grok-4/chat")
async def chat_grok_4(request: Request, chat_request: ChatRequest):
    from app.routers.xai.xai_chat import grok_4_chat as xai_grok_4_chat

    return await xai_grok_4_chat(request, chat_request)

# Grok image generation is handled by the XAI router
# @router.post("/grok-2-image/chat")
# async def chat_grok_2_image(request: Request, chat_request: ChatRequest):
#     return await chat_and_store(request, chat_request, "grok-2-image")

# Qwen endpoints
@router.post("/qwen1/chat")
async def chat_qwen1(request: Request, chat_request: ChatRequest):
    from app.routers.qwen.qwen_chat import qwen1_chat as qwen_1_chat

    return await qwen_1_chat(request, chat_request)

@router.post("/qwen2/chat")
async def chat_qwen2(request: Request, chat_request: ChatRequest):
    from app.routers.qwen.qwen_chat import qwen2_chat as qwen_2_chat

    return await qwen_2_chat(request, chat_request)





    

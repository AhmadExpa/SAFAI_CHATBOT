from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_async_session
from app.models.conversations import Conversation
from app.models.bubbles import Bubble
from app.models.messages import Message
from app.models.users import User
from jose import jwt, JWTError
import logging
from typing import List, Optional
from pydantic import BaseModel
import re
import httpx
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    model_used: Optional[str] = None

class MessageResponse(BaseModel):
    message_id: str
    content: str
    role: str
    model_used: Optional[str] = None
    created_at: Optional[str] = None

class BubbleResponse(BaseModel):
    bubble_id: str
    bubble_index: int
    created_at: Optional[str] = None
    messages: List[MessageResponse]

class ConversationDetailResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    bubbles: List[BubbleResponse]

class LibraryImageResponse(BaseModel):
    image_url: str
    model_used: Optional[str]
    conversation_id: str
    conversation_title: str
    created_at: str
    message_id: str

def decode_email_from_token(token: str) -> str:
    """Decode email from JWT token"""
    import os
    SECRET_KEY = os.getenv("SECRET_KEY", "KyleService")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    try:
        logger.debug(f"Decoding token: {token[:20]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Decoded payload: {payload}")
        email = payload.get("sub")
        if email is None:
            logger.warning(f"No email in payload: {payload}")
            raise HTTPException(status_code=401, detail="Invalid token")
        logger.debug(f"Decoded email: {email}")
        return email
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_user_id_from_email(email: str) -> str:
    """Get user_id from email with retry logic"""
    import asyncio
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            async for session in get_async_session():
                result = await session.execute(select(User).where(User.email == email))
                db_user = result.scalar_one_or_none()
                if not db_user:
                    logger.warning(f"User not found for email: {email}")
                    raise HTTPException(status_code=401, detail="User not found")
                logger.info(f"Found user_id: {db_user.user_id} for email: {email}")
                return str(db_user.user_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user_id from email (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Check if it's a network/DNS error
            if "getaddrinfo failed" in str(e) or "11002" in str(e):
                logger.warning(f"Network connectivity issue (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error("Network connectivity failed after all retries")
                    raise HTTPException(status_code=503, detail="Service temporarily unavailable - network connectivity issue")
            else:
                # For non-network errors, don't retry
                raise HTTPException(status_code=500, detail="Internal server error")
    
    raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(request: Request):
    """Get all conversations for the authenticated user"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Retry logic for database operations
        import asyncio
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async for session in get_async_session():
                    try:
                        result = await session.execute(
                            select(Conversation)
                            .where(Conversation.user_id == user_id)
                            .order_by(Conversation.updated_at.desc())
                        )
                        conversations = result.scalars().all()
                        
                        # Process conversations within the session context
                        conversation_list = []
                        seen_conversation_ids = set()
                        
                        for conv in conversations:
                            conv_id = str(conv.conversation_id)
                            
                            # Skip if we've already seen this conversation
                            if conv_id in seen_conversation_ids:
                                logger.warning(f"Duplicate conversation found: {conv_id}, skipping")
                                continue
                            
                            seen_conversation_ids.add(conv_id)
                            conversation_list.append(ConversationResponse(
                                conversation_id=conv_id,
                                title=conv.title,
                                created_at=conv.created_at.isoformat() if conv.created_at else None,
                                updated_at=conv.updated_at.isoformat() if conv.updated_at else None
                            ))
                        
                        logger.info(f"Found {len(conversation_list)} unique conversations for user {user_id}")
                        return conversation_list
                        
                    except Exception as e:
                        logger.error(f"Error fetching conversations (attempt {attempt + 1}/{max_retries}): {e}")
                        
                        # Check if it's a network/DNS error
                        if "getaddrinfo failed" in str(e) or "11002" in str(e):
                            logger.warning(f"Network connectivity issue (attempt {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                logger.error("Network connectivity failed after all retries")
                                raise HTTPException(status_code=503, detail="Service temporarily unavailable - network connectivity issue")
                        else:
                            # For non-network errors, don't retry
                            raise HTTPException(status_code=500, detail="Database error while fetching conversations")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Database session error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise HTTPException(status_code=500, detail="Database connection failed after all retries")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations/search")
async def search_conversations(request: Request, q: str):
    """Search conversations by title or content"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")

        async for session in get_async_session():
            # Search conversations by title
            result = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .where(Conversation.title.ilike(f"%{q}%"))
                .order_by(Conversation.updated_at.desc())
            )
            conversations = result.scalars().all()
            
            # Convert to response format with model_used
            conversation_list = []
            for conv in conversations:
                # Get the latest message to find model_used
                model_used = None
                bubble_result = await session.execute(
                    select(Bubble)
                    .where(Bubble.conversation_id == conv.conversation_id)
                    .order_by(Bubble.bubble_index.desc())
                    .limit(1)
                )
                latest_bubble = bubble_result.scalar_one_or_none()
                
                if latest_bubble:
                    msg_result = await session.execute(
                        select(Message)
                        .where(Message.bubble_id == latest_bubble.bubble_id)
                        .where(Message.role == 'assistant')
                        .order_by(Message.created_at.desc())
                        .limit(1)
                    )
                    latest_msg = msg_result.scalar_one_or_none()
                    if latest_msg and latest_msg.model_used:
                        model_used = latest_msg.model_used
                
                conversation_list.append(ConversationResponse(
                    conversation_id=str(conv.conversation_id),
                    title=conv.title,
                    created_at=conv.created_at.isoformat() if conv.created_at else None,
                    updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
                    model_used=model_used
                ))
            
            logger.info(f"Found {len(conversation_list)} conversations matching '{q}' for user {user_id}")
            return conversation_list
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, request: Request):
    """Get a specific conversation with its bubbles and messages"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Fetch conversation with bubbles and messages from database
        async for session in get_async_session():
            # Get conversation
            conv_result = await session.execute(
                select(Conversation)
                .where(Conversation.conversation_id == conversation_id)
                .where(Conversation.user_id == user_id)
            )
            conversation = conv_result.scalar_one_or_none()
            
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            # Get bubbles for this conversation
            bubbles_result = await session.execute(
                select(Bubble)
                .where(Bubble.conversation_id == conversation_id)
                .order_by(Bubble.created_at.asc())
            )
            bubbles = bubbles_result.scalars().all()
            
            # Get messages for each bubble
            bubbles_with_messages = []
            for bubble in bubbles:
                messages_result = await session.execute(
                    select(Message)
                    .where(Message.bubble_id == bubble.bubble_id)
                    .order_by(Message.created_at.asc())
                )
                messages = messages_result.scalars().all()
                
                # Convert messages to response format
                message_list = []
                for msg in messages:
                    message_list.append(MessageResponse(
                        message_id=str(msg.message_id),
                        content=msg.content,
                        role=msg.role,
                        model_used=msg.model_used,
                        created_at=msg.created_at.isoformat() if msg.created_at else None
                    ))
                
                # Convert bubble to response format
                bubbles_with_messages.append(BubbleResponse(
                    bubble_id=str(bubble.bubble_id),
                    bubble_index=bubble.bubble_index,
                    created_at=bubble.created_at.isoformat() if bubble.created_at else None,
                    messages=message_list
                ))
            
            logger.info(f"Found conversation {conversation_id} with {len(bubbles_with_messages)} bubbles")
            
            return ConversationDetailResponse(
                conversation_id=str(conversation.conversation_id),
                title=conversation.title,
                created_at=conversation.created_at.isoformat() if conversation.created_at else None,
                updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
                bubbles=bubbles_with_messages
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    """Delete a specific conversation and all its associated data"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Retry logic for database operations
        import asyncio
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async for session in get_async_session():
                    try:
                        # First, verify the conversation exists and belongs to the user
                        conv_result = await session.execute(
                            select(Conversation)
                            .where(Conversation.conversation_id == conversation_id)
                            .where(Conversation.user_id == user_id)
                        )
                        conversation = conv_result.scalar_one_or_none()
                        
                        if not conversation:
                            raise HTTPException(status_code=404, detail="Conversation not found")
                        
                        # Get all bubbles for this conversation
                        bubbles_result = await session.execute(
                            select(Bubble)
                            .where(Bubble.conversation_id == conversation_id)
                        )
                        bubbles = bubbles_result.scalars().all()
                        
                        # Collect all messages to process for file cleanup
                        all_messages = []
                        
                        # Get all messages for each bubble
                        for bubble in bubbles:
                            messages_result = await session.execute(
                                select(Message)
                                .where(Message.bubble_id == bubble.bubble_id)
                            )
                            messages = messages_result.scalars().all()
                            all_messages.extend(messages)
                        
                        # cleanup generated images associated with messages
                        import os
                        import re
                        
                        for message in all_messages:
                            if message.content:
                                # Look for local image paths in content
                                # Pattern matches /uploads/images/filename.ext
                                # The URLs in DB are relative like /uploads/images/...
                                image_pattern = r'/uploads/images/([a-zA-Z0-9-]+\.[a-zA-Z0-9]+)'
                                matches = re.findall(image_pattern, message.content)
                                
                                for filename in matches:
                                    try:
                                        # Construct absolute path
                                        # Assuming app runs from root where uploads folder is
                                        file_path = os.path.join("uploads", "images", filename)
                                        
                                        if os.path.exists(file_path):
                                            os.remove(file_path)
                                            logger.info(f"Deleted generated image: {file_path}")
                                        else:
                                            logger.warning(f"Image file not found for deletion: {file_path}")
                                            
                                    except Exception as e:
                                        logger.error(f"Error deleting image file {filename}: {e}")

                        # Now proceed with database deletion
                        
                        # Delete all messages
                        for message in all_messages:
                            await session.delete(message)
                        
                        # Delete all bubbles
                        for bubble in bubbles:
                            await session.delete(bubble)
                        
                        # Finally, delete the conversation
                        await session.delete(conversation)
                        
                        # Commit the transaction
                        await session.commit()
                        
                        logger.info(f"Successfully deleted conversation {conversation_id} and associated images")
                        return {"message": "Conversation deleted successfully"}
                        
                    except HTTPException:
                        raise
                    except Exception as e:
                        logger.error(f"Error deleting conversation (attempt {attempt + 1}/{max_retries}): {e}")
                        
                        # Check if it's a network/DNS error
                        if "getaddrinfo failed" in str(e) or "11002" in str(e):
                            logger.warning(f"Network connectivity issue (attempt {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                logger.error("Network connectivity failed after all retries")
                                raise HTTPException(status_code=503, detail="Service temporarily unavailable - network connectivity issue")
                        else:
                            # For non-network errors, don't retry
                            raise HTTPException(status_code=500, detail="Database error while deleting conversation")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Database session error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise HTTPException(status_code=500, detail="Database connection failed after all retries")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/library/images/test")
async def test_library_endpoint(request: Request):
    """Test endpoint to verify library images route is accessible"""
    try:
        logger.info("🧪 Test endpoint called")
        return {"status": "ok", "message": "Library images endpoint is accessible"}
    except Exception as e:
        logger.error(f"❌ Test endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/library/images", response_model=List[LibraryImageResponse])
async def get_library_images(request: Request):
    """Get all images generated in conversations for the authenticated user"""
    logger.info("📚 Library images endpoint called")
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("❌ Missing or invalid Authorization header")
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        logger.info(f"🔐 Token received: {token[:20]}...")
        email = decode_email_from_token(token)
        if not email:
            logger.warning("❌ Failed to decode email from token")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        logger.info(f"📧 Decoded email: {email}")
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            logger.warning(f"❌ User not found for email: {email}")
            raise HTTPException(status_code=401, detail="User not found")
        
        logger.info(f"✅ Authenticated user_id: {user_id}")
        
        # Retry logic for database operations
        import asyncio
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async for session in get_async_session():
                    try:
                        # Get all conversations for the user
                        conv_result = await session.execute(
                            select(Conversation)
                            .where(Conversation.user_id == user_id)
                            .order_by(Conversation.updated_at.desc())
                        )
                        conversations = conv_result.scalars().all()
                        
                        images = []
                        seen_image_urls = set()  # Track seen image URLs to prevent duplicates
                        
                        # Process each conversation
                        for conv in conversations:
                            # Get all bubbles for this conversation
                            bubbles_result = await session.execute(
                                select(Bubble)
                                .where(Bubble.conversation_id == conv.conversation_id)
                                .order_by(Bubble.created_at.desc())
                            )
                            bubbles = bubbles_result.scalars().all()
                            
                            # Process each bubble
                            for bubble in bubbles:
                                # Get all messages for this bubble
                                messages_result = await session.execute(
                                    select(Message)
                                    .where(Message.bubble_id == bubble.bubble_id)
                                    .where(Message.role == "assistant")
                                    .order_by(Message.created_at.desc())
                                )
                                messages = messages_result.scalars().all()
                                
                                # Process each message to find images
                                for msg in messages:
                                    if msg.content and isinstance(msg.content, str):
                                        # Extract image URLs from markdown format: ![Generated Image](url)
                                        # Use a more robust pattern that handles very long URLs (like base64)
                                        # Match everything between parentheses, including newlines and special chars
                                        image_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
                                        matches = re.findall(image_pattern, msg.content, re.DOTALL)
                                        
                                        # Log if message contains image-related content but no matches found
                                        if not matches and any(keyword in msg.content.lower() for keyword in ['image', 'generated', 'http', 'https', 'imgen', 'dalle', 'blob.core.windows.net', 'data:image']):
                                            logger.debug(f"Message contains image-related keywords but no markdown image found. Content preview: {msg.content[:200]}...")
                                        
                                        for image_url in matches:
                                            # Log base64 images for debugging
                                            if image_url.startswith('data:image/'):
                                                logger.info(f"Found base64 image in message (model: {msg.model_used}): length={len(image_url)} chars, preview={image_url[:100]}...")
                                                # Skip base64 images - they're embedded in messages, not stored in library
                                                logger.debug(f"Skipping base64 image (embedded in message): {image_url[:50]}...")
                                                continue
                                            # Skip base64 data URLs - they're embedded directly in messages, not stored in library
                                            if image_url.startswith('data:image/'):
                                                logger.debug(f"Skipping base64 image (embedded in message): {image_url[:50]}...")
                                                continue
                                            
                                            # Ensure URL has protocol (only for non-base64 URLs)
                                            if not image_url.startswith(('http://', 'https://')):
                                                image_url = f"https://{image_url}"
                                            
                                            # Deduplicate: only add if we haven't seen this URL before
                                            if image_url not in seen_image_urls:
                                                seen_image_urls.add(image_url)
                                                image_domain = image_url.split('/')[2] if len(image_url.split('/')) > 2 else 'unknown'
                                                logger.info(f"Found image in library: URL={image_url[:100]}..., model={msg.model_used}, domain={image_domain}")
                                            images.append(LibraryImageResponse(
                                                image_url=image_url,
                                                model_used=msg.model_used,
                                                conversation_id=str(conv.conversation_id),
                                                conversation_title=conv.title,
                                                created_at=msg.created_at.isoformat() if msg.created_at else "",
                                                message_id=str(msg.message_id)
                                            ))
                        
                        # Log summary by model
                        model_counts = {}
                        for img in images:
                            model = img.model_used or "unknown"
                            model_counts[model] = model_counts.get(model, 0) + 1
                        
                        logger.info(f"Found {len(images)} unique images for user {user_id}")
                        logger.info(f"Image breakdown by model: {model_counts}")
                        return images
                        
                    except Exception as e:
                        logger.error(f"Error fetching library images (attempt {attempt + 1}/{max_retries}): {e}")
                        
                        # Check if it's a network/DNS error
                        if "getaddrinfo failed" in str(e) or "11002" in str(e):
                            logger.warning(f"Network connectivity issue (attempt {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                logger.error("Network connectivity failed after all retries")
                                raise HTTPException(status_code=503, detail="Service temporarily unavailable - network connectivity issue")
                        else:
                            # For non-network errors, don't retry
                            raise HTTPException(status_code=500, detail="Database error while fetching library images")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Database session error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise HTTPException(status_code=500, detail="Database connection failed after all retries")
            
    except HTTPException as he:
        logger.error(f"❌ HTTPException in library images endpoint: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching library images: {e}", exc_info=True)
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/library/images/proxy")
async def proxy_library_image(request: Request, url: str, token: Optional[str] = None):
    """Proxy image requests to bypass CORS issues"""
    try:
        # Get token from multiple sources (header, query parameter, or cookies)
        auth_token = None
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ")[1]
        elif token:
            # Token from query parameter (for image src tags that can't send headers)
            auth_token = token
        else:
            # Try to get token from cookies
            auth_token = request.cookies.get("token")
        
        if not auth_token:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header or cookie")
        
        email = decode_email_from_token(auth_token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Validate URL - reject base64 data URLs (they should be displayed directly, not proxied)
        if not url:
            logger.warning(f"⚠️ Empty URL in proxy request")
            raise HTTPException(status_code=400, detail="Invalid image URL: empty")
        
        if url.startswith('data:image/'):
            logger.warning(f"⚠️ Base64 image URL sent to proxy (should be displayed directly): {url[:50]}...")
            raise HTTPException(status_code=400, detail="Base64 images should be displayed directly, not proxied")
        
        if not (url.startswith('http://') or url.startswith('https://')):
            logger.warning(f"⚠️ Invalid URL format in proxy request: {url[:100]}...")
            raise HTTPException(status_code=400, detail="Invalid image URL: must start with http:// or https://")
        
        # Only allow certain domains for security
        allowed_domains = ['imgen.x.ai', 'oaidalleapiprodscus.blob.core.windows.net', 'dalleproduseast.blob.core.windows.net']
        url_domain = url.split('/')[2] if len(url.split('/')) > 2 else ''
        
        if not any(domain in url_domain for domain in allowed_domains):
            raise HTTPException(status_code=403, detail="Image domain not allowed")
        
        # Fetch image with retry logic
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    follow_redirects=True,
                    verify=True
                ) as client:
                    response = await client.get(
                        url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Accept': 'image/*',
                            'Referer': url.split('/')[0] + '//' + url.split('/')[2] if len(url.split('/')) > 2 else ''
                        }
                    )
                    
                    if response.status_code == 200:
                        # Determine content type
                        content_type = response.headers.get('Content-Type', 'image/jpeg')
                        
                        # Return streaming response
                        return StreamingResponse(
                            iter([response.content]),
                            media_type=content_type,
                            headers={
                                'Cache-Control': 'public, max-age=31536000',  # Cache for 1 year
                                'Access-Control-Allow-Origin': '*',
                                'Access-Control-Allow-Methods': 'GET',
                                'Access-Control-Allow-Headers': '*',
                            }
                        )
                    elif response.status_code == 404:
                        # 404 is definitive - image doesn't exist (likely expired temporary image)
                        # Return 404 immediately without retries - this is expected for expired images
                        # Use Response instead of JSONResponse for cleaner handling
                        return Response(
                            status_code=404,
                            headers={
                                'Cache-Control': 'no-cache, no-store, must-revalidate',
                                'Access-Control-Allow-Origin': '*',
                                'Access-Control-Allow-Methods': 'GET',
                            }
                        )
                    else:
                        # For other errors, allow retry logic to continue
                        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch image: {response.status_code}")
                        
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.warning(f"Timeout fetching image (attempt {attempt + 1}/{max_retries}), retrying...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise HTTPException(status_code=504, detail="Image fetch timeout")
            except httpx.RequestError as e:
                error_msg = str(e)
                # Check for DNS resolution errors (ERR_NAME_NOT_RESOLVED)
                if 'name not resolved' in error_msg.lower() or 'name resolution' in error_msg.lower() or 'nodename nor servname' in error_msg.lower():
                    logger.warning(f"DNS resolution error for image URL {url}: {e}")
                    raise HTTPException(status_code=502, detail=f"Image domain not found or unreachable: {url_domain}")
                if attempt < max_retries - 1:
                    logger.warning(f"Request error fetching image (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise HTTPException(status_code=502, detail=f"Failed to fetch image: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 
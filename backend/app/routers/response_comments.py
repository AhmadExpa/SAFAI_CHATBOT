"""
Response Comments Router
Handles CRUD operations for comments on model responses
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.future import select
from jose import jwt, JWTError
import logging
import uuid
import os

from app.services.database import get_async_session
from app.models.users import User

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response models
class CreateCommentRequest(BaseModel):
    response_id: str
    comment_text: str


class UpdateCommentRequest(BaseModel):
    comment_text: str


class CommentResponse(BaseModel):
    comment_id: str
    response_id: str
    user_id: str
    comment_text: str
    created_at: datetime
    updated_at: datetime


class CreateModelResponseRequest(BaseModel):
    message_id: str
    model_name: str
    content: str
    response_order: int = 0


class ModelResponseWithComments(BaseModel):
    response_id: str
    message_id: str
    model_name: str
    content: str
    response_order: int
    created_at: datetime
    comments: List[CommentResponse] = []


def get_token_from_header(request: Request) -> str:
    """Extract token from Authorization header"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth_header.split(" ", 1)[1]


def decode_email_from_token(token: str) -> str:
    """Decode email from JWT token"""
    SECRET_KEY = os.getenv("SECRET_KEY", "KyleService")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_user_id_from_email(email: str) -> str:
    """Get user_id from email"""
    try:
        async for session in get_async_session():
            result = await session.execute(
                select(User.user_id).where(User.email == email)
            )
            user_id = result.scalar_one_or_none()
            if user_id:
                logger.info(f"Found user_id: {user_id} for email: {email}")
                return str(user_id)
            else:
                logger.warning(f"No user found for email: {email}")
                raise HTTPException(status_code=401, detail="User not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user_id from email: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


async def get_user_id_from_token(request: Request) -> str:
    """Extract and validate user ID from auth token"""
    try:
        token = get_token_from_header(request)
        logger.info(f"Extracted token: {token[:20]}..." if token else "No token")
        
        email = decode_email_from_token(token)
        logger.info(f"Decoded email: {email}")
        
        user_id = await get_user_id_from_email(email)
        logger.info(f"Found user_id: {user_id}")
        
        return user_id
    except HTTPException as e:
        logger.error(f"Auth error: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_user_id_from_token: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


@router.post("/model-responses", response_model=dict)
async def create_model_response(request: Request, response_request: CreateModelResponseRequest):
    """
    Create a new model response for a message.
    Used when storing multi-model chat responses.
    """
    try:
        user_id = await get_user_id_from_token(request)
        
        async for session in get_async_session():
            response_id = str(uuid.uuid4())
            
            await session.execute(
                text("""
                    INSERT INTO model_responses 
                    (response_id, message_id, model_name, content, response_order, created_at, updated_at)
                    VALUES (:response_id, :message_id, :model_name, :content, :response_order, :created_at, :updated_at)
                """),
                {
                    "response_id": response_id,
                    "message_id": response_request.message_id,
                    "model_name": response_request.model_name,
                    "content": response_request.content,
                    "response_order": response_request.response_order,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
            await session.commit()
            
            logger.info(f"Created model response: {response_id} for message: {response_request.message_id}")
            return {"response_id": response_id, "message": "Model response created successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating model response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create model response: {str(e)}")


@router.get("/model-responses/message/{message_id}", response_model=List[ModelResponseWithComments])
async def get_model_responses_for_message(request: Request, message_id: str):
    """
    Get all model responses for a specific message, including their comments.
    """
    try:
        user_id = await get_user_id_from_token(request)
        
        async for session in get_async_session():
            # Get all model responses for the message
            result = await session.execute(
                text("""
                    SELECT response_id, message_id, model_name, content, response_order, created_at, updated_at
                    FROM model_responses
                    WHERE message_id = :message_id
                    ORDER BY response_order ASC, created_at ASC
                """),
                {"message_id": message_id}
            )
            responses = result.fetchall()
            
            if not responses:
                return []
            
            # Get comments for each response
            response_list = []
            for resp in responses:
                comments_result = await session.execute(
                    text("""
                        SELECT comment_id, response_id, user_id, comment_text, created_at, updated_at
                        FROM response_comments
                        WHERE response_id = :response_id
                        ORDER BY created_at ASC
                    """),
                    {"response_id": str(resp[0])}
                )
                comments = comments_result.fetchall()
                
                comment_list = [
                    CommentResponse(
                        comment_id=str(c[0]),
                        response_id=str(c[1]),
                        user_id=str(c[2]),
                        comment_text=c[3],
                        created_at=c[4],
                        updated_at=c[5]
                    ) for c in comments
                ]
                
                response_list.append(
                    ModelResponseWithComments(
                        response_id=str(resp[0]),
                        message_id=str(resp[1]),
                        model_name=resp[2],
                        content=resp[3],
                        response_order=resp[4],
                        created_at=resp[5],
                        comments=comment_list
                    )
                )
            
            return response_list
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching model responses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch model responses: {str(e)}")


@router.post("/comments", response_model=CommentResponse)
async def create_comment(request: Request, comment_request: CreateCommentRequest):
    """
    Create a new comment on a model response.
    Auto-creates response entry if it doesn't exist (for backward compatibility).
    """
    try:
        user_id = await get_user_id_from_token(request)
        
        if not comment_request.comment_text.strip():
            raise HTTPException(status_code=400, detail="Comment text cannot be empty")
        
        async for session in get_async_session():
            # Check if the response exists, if not create a placeholder
            result = await session.execute(
                text("SELECT response_id FROM model_responses WHERE response_id = :response_id"),
                {"response_id": comment_request.response_id}
            )
            existing_response = result.fetchone()
            
            if not existing_response:
                # Auto-create a placeholder response entry for backward compatibility
                logger.info(f"Auto-creating model_response entry for response_id: {comment_request.response_id}")
                await session.execute(
                    text("""
                        INSERT INTO model_responses 
                        (response_id, message_id, model_name, content, response_order, created_at, updated_at)
                        VALUES (:response_id, :message_id, :model_name, :content, :response_order, :created_at, :updated_at)
                    """),
                    {
                        "response_id": comment_request.response_id,
                        "message_id": None,  # NULL for backward compatibility
                        "model_name": "unknown",
                        "content": "",
                        "response_order": 0,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )
            
            comment_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            
            await session.execute(
                text("""
                    INSERT INTO response_comments 
                    (comment_id, response_id, user_id, comment_text, created_at, updated_at)
                    VALUES (:comment_id, :response_id, :user_id, :comment_text, :created_at, :updated_at)
                """),
                {
                    "comment_id": comment_id,
                    "response_id": comment_request.response_id,
                    "user_id": user_id,
                    "comment_text": comment_request.comment_text.strip(),
                    "created_at": created_at,
                    "updated_at": created_at
                }
            )
            await session.commit()
            
            logger.info(f"Created comment: {comment_id} on response: {comment_request.response_id}")
            
            return CommentResponse(
                comment_id=comment_id,
                response_id=comment_request.response_id,
                user_id=user_id,
                comment_text=comment_request.comment_text.strip(),
                created_at=created_at,
                updated_at=created_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create comment: {str(e)}")


@router.get("/comments/response/{response_id}", response_model=List[CommentResponse])
async def get_comments_for_response(request: Request, response_id: str):
    """
    Get all comments for a specific model response.
    """
    try:
        user_id = await get_user_id_from_token(request)
        
        async for session in get_async_session():
            result = await session.execute(
                text("""
                    SELECT comment_id, response_id, user_id, comment_text, created_at, updated_at
                    FROM response_comments
                    WHERE response_id = :response_id
                    ORDER BY created_at ASC
                """),
                {"response_id": response_id}
            )
            comments = result.fetchall()
            
            return [
                CommentResponse(
                    comment_id=str(c[0]),
                    response_id=str(c[1]),
                    user_id=str(c[2]),
                    comment_text=c[3],
                    created_at=c[4],
                    updated_at=c[5]
                ) for c in comments
            ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching comments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch comments: {str(e)}")


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(request: Request, comment_id: str, update_request: UpdateCommentRequest):
    """
    Update an existing comment.
    """
    try:
        user_id = await get_user_id_from_token(request)
        
        if not update_request.comment_text.strip():
            raise HTTPException(status_code=400, detail="Comment text cannot be empty")
        
        async for session in get_async_session():
            # Verify the comment exists and belongs to the user
            result = await session.execute(
                text("""
                    SELECT comment_id, response_id, user_id, comment_text, created_at
                    FROM response_comments
                    WHERE comment_id = :comment_id AND user_id = :user_id
                """),
                {"comment_id": comment_id, "user_id": user_id}
            )
            comment = result.fetchone()
            
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found or unauthorized")
            
            updated_at = datetime.utcnow()
            
            await session.execute(
                text("""
                    UPDATE response_comments
                    SET comment_text = :comment_text, updated_at = :updated_at
                    WHERE comment_id = :comment_id
                """),
                {
                    "comment_text": update_request.comment_text.strip(),
                    "updated_at": updated_at,
                    "comment_id": comment_id
                }
            )
            await session.commit()
            
            logger.info(f"Updated comment: {comment_id}")
            
            return CommentResponse(
                comment_id=comment_id,
                response_id=str(comment[1]),
                user_id=str(comment[2]),
                comment_text=update_request.comment_text.strip(),
                created_at=comment[4],
                updated_at=updated_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating comment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update comment: {str(e)}")


@router.delete("/comments/{comment_id}")
async def delete_comment(request: Request, comment_id: str):
    """
    Delete a comment.
    """
    try:
        user_id = await get_user_id_from_token(request)
        
        async for session in get_async_session():
            # Verify the comment exists and belongs to the user
            result = await session.execute(
                text("SELECT comment_id FROM response_comments WHERE comment_id = :comment_id AND user_id = :user_id"),
                {"comment_id": comment_id, "user_id": user_id}
            )
            
            if not result.fetchone():
                raise HTTPException(status_code=404, detail="Comment not found or unauthorized")
            
            await session.execute(
                text("DELETE FROM response_comments WHERE comment_id = :comment_id"),
                {"comment_id": comment_id}
            )
            await session.commit()
            
            logger.info(f"Deleted comment: {comment_id}")
            return {"message": "Comment deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete comment: {str(e)}")


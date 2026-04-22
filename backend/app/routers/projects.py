from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_async_session
from app.models.projects import Project
from app.models.conversations import Conversation
from app.models.users import User
from jose import jwt, JWTError
import logging
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: Optional[str]
    created_at: str
    updated_at: Optional[str]
    conversation_count: int

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

def decode_email_from_token(token: str) -> str:
    """Decode email from JWT token"""
    import os
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
    """Get user_id from email with retry logic"""
    import asyncio
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
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

@router.get("/projects", response_model=List[ProjectResponse])
async def get_user_projects(request: Request):
    """Get all projects for the authenticated user"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        # Retry logic for database operations
        import asyncio
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async for session in get_async_session():
                    try:
                        # Get projects with conversation count
                        result = await session.execute(
                            select(Project)
                            .where(Project.user_id == user_id)
                            .order_by(Project.updated_at.desc().nullsfirst(), Project.created_at.desc())
                        )
                        projects = result.scalars().all()
                        
                        # Process projects within the session context
                        project_list = []
                        for project in projects:
                            # Count conversations for this project
                            conv_result = await session.execute(
                                select(Conversation)
                                .where(Conversation.project_id == project.project_id)
                            )
                            conversation_count = len(conv_result.scalars().all())
                            
                            project_list.append(ProjectResponse(
                                project_id=str(project.project_id),
                                name=project.name,
                                description=project.description,
                                created_at=project.created_at.isoformat() if project.created_at else None,
                                updated_at=project.updated_at.isoformat() if project.updated_at else None,
                                conversation_count=conversation_count
                            ))
                        
                        logger.info(f"Found {len(project_list)} projects for user {user_id}")
                        return project_list
                        
                    except Exception as e:
                        logger.error(f"Error fetching projects (attempt {attempt + 1}/{max_retries}): {e}")
                        
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
                            raise HTTPException(status_code=500, detail="Database error while fetching projects")
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
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/projects", response_model=ProjectResponse)
async def create_project(request: Request, project_data: ProjectCreateRequest):
    """Create a new project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Create new project
            new_project = Project(
                user_id=user_id,
                name=project_data.name,
                description=project_data.description,
                created_at=datetime.utcnow()
            )
            
            session.add(new_project)
            await session.commit()
            await session.refresh(new_project)
            
            logger.info(f"Created new project: {new_project.project_id} for user {user_id}")
            
            return ProjectResponse(
                project_id=str(new_project.project_id),
                name=new_project.name,
                description=new_project.description,
                created_at=new_project.created_at.isoformat(),
                updated_at=new_project.updated_at.isoformat() if new_project.updated_at else None,
                conversation_count=0
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(request: Request, project_id: str):
    """Get a single project for the authenticated user"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = result.scalar_one_or_none()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            conv_result = await session.execute(
                select(Conversation)
                .where(Conversation.project_id == project.project_id)
            )
            conversation_count = len(conv_result.scalars().all())

            return ProjectResponse(
                project_id=str(project.project_id),
                name=project.name,
                description=project.description,
                created_at=project.created_at.isoformat() if project.created_at else None,
                updated_at=project.updated_at.isoformat() if project.updated_at else None,
                conversation_count=conversation_count
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(request: Request, project_id: str, project_data: ProjectUpdateRequest):
    """Update an existing project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Find the project
            result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Update project fields
            if project_data.name is not None:
                project.name = project_data.name
            if project_data.description is not None:
                project.description = project_data.description
            
            project.updated_at = datetime.utcnow()
            
            await session.commit()
            await session.refresh(project)
            
            # Count conversations for this project
            conv_result = await session.execute(
                select(Conversation)
                .where(Conversation.project_id == project.project_id)
            )
            conversation_count = len(conv_result.scalars().all())
            
            logger.info(f"Updated project: {project_id} for user {user_id}")
            
            return ProjectResponse(
                project_id=str(project.project_id),
                name=project.name,
                description=project.description,
                created_at=project.created_at.isoformat(),
                updated_at=project.updated_at.isoformat(),
                conversation_count=conversation_count
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str):
    """Delete a project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Find the project
            result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Delete the project (conversations will be handled by CASCADE)
            await session.delete(project)
            await session.commit()
            
            logger.info(f"Deleted project: {project_id} for user {user_id}")
            
            return {"message": "Project deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/conversations", response_model=List[dict])
async def get_project_conversations(request: Request, project_id: str):
    """Get all conversations for a specific project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Verify project belongs to user
            project_result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Get conversations for this project
            result = await session.execute(
                select(Conversation)
                .where(Conversation.project_id == project_id)
                .order_by(Conversation.updated_at.desc())
            )
            conversations = result.scalars().all()
            
            conversation_list = []
            for conv in conversations:
                conversation_list.append({
                    "conversation_id": str(conv.conversation_id),
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
                })
            
            logger.info(f"Found {len(conversation_list)} conversations for project {project_id}")
            return conversation_list
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project conversations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

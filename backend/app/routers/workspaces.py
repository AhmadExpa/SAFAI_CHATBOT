from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_async_session
from app.models.workspaces import Workspace
from app.models.users import User
from jose import jwt, JWTError
import logging
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str]
    ai_model: Optional[str]
    created_at: str
    updated_at: Optional[str]

class WorkspaceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    ai_model: Optional[str] = None

class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ai_model: Optional[str] = None

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

@router.get("/workspaces", response_model=List[WorkspaceResponse])
async def get_user_workspaces(request: Request):
    """Get all workspaces for the authenticated user"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            try:
                # Get workspaces
                result = await session.execute(
                    select(Workspace)
                    .where(Workspace.user_id == user_id)
                    .order_by(Workspace.updated_at.desc().nullsfirst(), Workspace.created_at.desc())
                )
                workspaces = result.scalars().all()
                
                workspace_list = []
                for workspace in workspaces:
                    workspace_list.append(WorkspaceResponse(
                        workspace_id=str(workspace.workspace_id),
                        name=workspace.name,
                        description=workspace.description,
                        ai_model=workspace.ai_model,
                        created_at=workspace.created_at.isoformat() if workspace.created_at else None,
                        updated_at=workspace.updated_at.isoformat() if workspace.updated_at else None
                    ))
                
                logger.info(f"Found {len(workspace_list)} workspaces for user {user_id}")
                return workspace_list
                
            except Exception as e:
                logger.error(f"Error fetching workspaces: {e}")
                raise HTTPException(status_code=500, detail="Database error while fetching workspaces")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workspaces: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/workspaces", response_model=WorkspaceResponse)
async def create_workspace(request: Request, workspace_data: WorkspaceCreateRequest):
    """Create a new workspace"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Create new workspace
            new_workspace = Workspace(
                user_id=user_id,
                name=workspace_data.name,
                description=workspace_data.description,
                ai_model=workspace_data.ai_model,
                created_at=datetime.utcnow()
            )
            
            session.add(new_workspace)
            await session.commit()
            await session.refresh(new_workspace)
            
            logger.info(f"Created new workspace: {new_workspace.workspace_id} for user {user_id}")
            
            return WorkspaceResponse(
                workspace_id=str(new_workspace.workspace_id),
                name=new_workspace.name,
                description=new_workspace.description,
                ai_model=new_workspace.ai_model,
                created_at=new_workspace.created_at.isoformat(),
                updated_at=new_workspace.updated_at.isoformat() if new_workspace.updated_at else None
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(request: Request, workspace_id: str):
    """Get a single workspace for the authenticated user"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            result = await session.execute(
                select(Workspace)
                .where(Workspace.workspace_id == workspace_id)
                .where(Workspace.user_id == user_id)
            )
            workspace = result.scalar_one_or_none()

            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")

            return WorkspaceResponse(
                workspace_id=str(workspace.workspace_id),
                name=workspace.name,
                description=workspace.description,
                ai_model=workspace.ai_model,
                created_at=workspace.created_at.isoformat() if workspace.created_at else None,
                updated_at=workspace.updated_at.isoformat() if workspace.updated_at else None
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(request: Request, workspace_id: str, workspace_data: WorkspaceUpdateRequest):
    """Update an existing workspace"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Find the workspace
            result = await session.execute(
                select(Workspace)
                .where(Workspace.workspace_id == workspace_id)
                .where(Workspace.user_id == user_id)
            )
            workspace = result.scalar_one_or_none()
            
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")
            
            # Update workspace fields
            if workspace_data.name is not None:
                workspace.name = workspace_data.name
            if workspace_data.description is not None:
                workspace.description = workspace_data.description
            if workspace_data.ai_model is not None:
                workspace.ai_model = workspace_data.ai_model
            
            workspace.updated_at = datetime.utcnow()
            
            await session.commit()
            await session.refresh(workspace)
            
            logger.info(f"Updated workspace: {workspace_id} for user {user_id}")
            
            return WorkspaceResponse(
                workspace_id=str(workspace.workspace_id),
                name=workspace.name,
                description=workspace.description,
                ai_model=workspace.ai_model,
                created_at=workspace.created_at.isoformat(),
                updated_at=workspace.updated_at.isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(request: Request, workspace_id: str):
    """Delete a workspace"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)

        async for session in get_async_session():
            # Find the workspace
            result = await session.execute(
                select(Workspace)
                .where(Workspace.workspace_id == workspace_id)
                .where(Workspace.user_id == user_id)
            )
            workspace = result.scalar_one_or_none()
            
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")
            
            # Delete the workspace
            await session.delete(workspace)
            await session.commit()
            
            logger.info(f"Deleted workspace: {workspace_id} for user {user_id}")
            
            return {"message": "Workspace deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workspace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


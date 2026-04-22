"""
Personalities Router - AI Assistant Personalities API
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete as sql_delete
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid
import logging

from app.models.personalities import Personality
from app.services.database import get_async_session

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic Models
class PersonalityResponse(BaseModel):
    """Personality response model (without system_prompt for security)"""
    id: str
    name: str
    highlight: Optional[str] = None
    description: Optional[str] = None
    avatar_emoji: Optional[str] = None
    avatar_url: Optional[str] = None
    rules: dict = {}
    display_order: int = 0
    
    class Config:
        from_attributes = True


class PersonalityDetailResponse(PersonalityResponse):
    """Detailed personality response (includes system_prompt for authorized users)"""
    system_prompt: str
    is_active: bool
    created_at: str
    updated_at: str


class PersonalityCreate(BaseModel):
    """Create personality request"""
    name: str = Field(..., min_length=1, max_length=100)
    highlight: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    avatar_emoji: Optional[str] = Field(None, max_length=10)
    avatar_url: Optional[str] = Field(None, max_length=500)
    system_prompt: str = Field(..., min_length=10)
    rules: dict = {}
    display_order: int = 0


class PersonalityUpdate(BaseModel):
    """Update personality request"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    highlight: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    avatar_emoji: Optional[str] = Field(None, max_length=10)
    avatar_url: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = Field(None, min_length=10)
    rules: Optional[dict] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


# Database dependency
async def get_db():
    async for session in get_async_session():
        yield session


# ==================== GET Endpoints ====================

@router.get("/", response_model=List[PersonalityResponse])
async def get_all_personalities(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all personalities
    
    - **active_only**: Only return active personalities (default: true)
    """
    try:
        logger.info(f"Fetching personalities (active_only={active_only})")
        
        query = select(Personality).order_by(Personality.display_order, Personality.name)
        
        if active_only:
            query = query.where(Personality.is_active == True)
        
        result = await db.execute(query)
        personalities = result.scalars().all()
        
        logger.info(f"Found {len(personalities)} personalities")
        
        return [PersonalityResponse(**p.to_public_dict()) for p in personalities]
        
    except Exception as e:
        logger.error(f"Error fetching personalities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch personalities: {str(e)}"
        )


@router.get("/{personality_id}", response_model=PersonalityResponse)
async def get_personality(
    personality_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single personality by ID
    
    - **personality_id**: UUID of the personality
    """
    try:
        logger.info(f"Fetching personality: {personality_id}")
        
        # Validate UUID
        try:
            uuid.UUID(personality_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid personality ID format"
            )
        
        # Query database
        result = await db.execute(
            select(Personality).where(Personality.id == uuid.UUID(personality_id))
        )
        personality = result.scalar_one_or_none()
        
        if not personality:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Personality not found: {personality_id}"
            )
        
        if not personality.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personality is not active"
            )
        
        return PersonalityResponse(**personality.to_public_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching personality {personality_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch personality: {str(e)}"
        )


@router.get("/{personality_id}/prompt")
async def get_personality_prompt(
    personality_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the system prompt for a personality (for internal use)
    
    - **personality_id**: UUID of the personality
    - **Returns**: system_prompt and rules
    """
    try:
        logger.info(f"Fetching prompt for personality: {personality_id}")
        
        # Validate UUID
        try:
            uuid.UUID(personality_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid personality ID format"
            )
        
        # Query database
        result = await db.execute(
            select(Personality).where(Personality.id == uuid.UUID(personality_id))
        )
        personality = result.scalar_one_or_none()
        
        if not personality:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Personality not found: {personality_id}"
            )
        
        if not personality.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personality is not active"
            )
        
        return {
            "id": str(personality.id),
            "name": personality.name,
            "system_prompt": personality.system_prompt,
            "rules": personality.rules
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prompt for personality {personality_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch personality prompt: {str(e)}"
        )


# ==================== POST Endpoints (Admin) ====================

@router.post("/", response_model=PersonalityDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_personality(
    personality: PersonalityCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new personality (Admin only)
    
    - **personality**: Personality data
    """
    try:
        logger.info(f"Creating personality: {personality.name}")
        
        # Check if personality with same name exists
        result = await db.execute(
            select(Personality).where(Personality.name == personality.name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Personality with name '{personality.name}' already exists"
            )
        
        # Create new personality
        new_personality = Personality(
            name=personality.name,
            highlight=personality.highlight,
            description=personality.description,
            avatar_emoji=personality.avatar_emoji,
            avatar_url=personality.avatar_url,
            system_prompt=personality.system_prompt,
            rules=personality.rules,
            display_order=personality.display_order
        )
        
        db.add(new_personality)
        await db.commit()
        await db.refresh(new_personality)
        
        logger.info(f"Personality created: {new_personality.id}")
        
        return PersonalityDetailResponse(**new_personality.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating personality: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create personality: {str(e)}"
        )


# ==================== PUT Endpoints (Admin) ====================

@router.put("/{personality_id}", response_model=PersonalityDetailResponse)
async def update_personality(
    personality_id: str,
    personality_update: PersonalityUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a personality (Admin only)
    
    - **personality_id**: UUID of the personality
    - **personality_update**: Updated personality data
    """
    try:
        logger.info(f"Updating personality: {personality_id}")
        
        # Validate UUID
        try:
            uuid.UUID(personality_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid personality ID format"
            )
        
        # Find personality
        result = await db.execute(
            select(Personality).where(Personality.id == uuid.UUID(personality_id))
        )
        personality = result.scalar_one_or_none()
        
        if not personality:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Personality not found: {personality_id}"
            )
        
        # Update fields
        update_data = personality_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(personality, field, value)
        
        await db.commit()
        await db.refresh(personality)
        
        logger.info(f"Personality updated: {personality_id}")
        
        return PersonalityDetailResponse(**personality.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating personality {personality_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personality: {str(e)}"
        )


# ==================== DELETE Endpoints (Admin) ====================

@router.delete("/{personality_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_personality(
    personality_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a personality (Admin only)
    
    - **personality_id**: UUID of the personality
    """
    try:
        logger.info(f"Deleting personality: {personality_id}")
        
        # Validate UUID
        try:
            uuid.UUID(personality_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid personality ID format"
            )
        
        # Find personality
        result = await db.execute(
            select(Personality).where(Personality.id == uuid.UUID(personality_id))
        )
        personality = result.scalar_one_or_none()
        
        if not personality:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Personality not found: {personality_id}"
            )
        
        # Delete personality
        await db.execute(
            sql_delete(Personality).where(Personality.id == uuid.UUID(personality_id))
        )
        await db.commit()
        
        logger.info(f"Personality deleted: {personality_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting personality {personality_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete personality: {str(e)}"
        )


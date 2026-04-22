"""
Personality models for AI assistant personalities
"""

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.models.users import Base


class Personality(Base):
    """AI Assistant Personality Model"""
    
    __tablename__ = "personalities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    highlight = Column(String(200))
    description = Column(Text)
    avatar_emoji = Column(String(10))
    avatar_url = Column(String(500))
    system_prompt = Column(Text, nullable=False)
    rules = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Personality(name='{self.name}', emoji='{self.avatar_emoji}')>"
    
    def to_dict(self):
        """Convert personality to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "highlight": self.highlight,
            "description": self.description,
            "avatar_emoji": self.avatar_emoji,
            "avatar_url": self.avatar_url,
            "system_prompt": self.system_prompt,
            "rules": self.rules,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_public_dict(self):
        """Convert personality to public dictionary (without system_prompt)"""
        return {
            "id": str(self.id),
            "name": self.name,
            "highlight": self.highlight,
            "description": self.description,
            "avatar_emoji": self.avatar_emoji,
            "avatar_url": self.avatar_url,
            "rules": self.rules,
            "display_order": self.display_order
        }


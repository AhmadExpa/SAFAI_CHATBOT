from sqlalchemy import Column, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .users import Base

class Conversation(Base):
    """
    Conversation model representing a single chat session.
    
    Conversation Structure:
    - One conversation per chat session (created when user clicks "New Chat")
    - Contains multiple bubbles (request-response pairs)
    - Each bubble represents one user request and its corresponding assistant response
    - Bubbles can contain multiple request-response pairs (when user modifies and resends)
    - This implements ChatGPT-like conversation management
    """
    __tablename__ = "conversations"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False, comment="Title of the conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, comment="Last updated timestamp")

    user = relationship("User", back_populates="conversations")
    project = relationship("Project", back_populates="conversations")
    bubbles = relationship("Bubble", back_populates="conversation") 
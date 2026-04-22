from sqlalchemy import Column, Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .users import Base

class Bubble(Base):
    """
    Bubble model representing a single request-response pair within a conversation.
    
    Bubble Structure:
    - Each bubble represents one user request and its corresponding assistant response
    - bubble_index represents the order of bubbles within a conversation
    - A bubble can contain multiple request-response pairs (when user modifies and resends)
    - Each request-response pair within a bubble has the same message_index
    - This implements ChatGPT-like conversation structure
    """
    __tablename__ = "bubbles"

    bubble_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False)
    bubble_index = Column(Integer, nullable=False, comment="Order of bubble within conversation")
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="bubbles")
    messages = relationship("Message", back_populates="bubble")

    __table_args__ = (
        # Ensure bubble_index is non-negative
        CheckConstraint('bubble_index >= 0', name='check_bubble_index_positive'),
        # Ensure reasonable bubble_index range
        CheckConstraint('bubble_index <= 999999', name='check_bubble_index_reasonable'),
    ) 
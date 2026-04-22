from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .users import Base

class Message(Base):
    """
    Message model representing individual messages within a bubble.
    
    Message Index Logic:
    - message_index represents the position of the bubble within the conversation
    - Both user request and assistant response have the same message_index
    - message_index 0: First request-response pair (bubble 0)
    - message_index 1: Second request-response pair (bubble 1)
    - message_index 2: Third request-response pair (bubble 2)
    - This implements ChatGPT-like conversation structure
    """
    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bubble_id = Column(UUID(as_uuid=True), ForeignKey("bubbles.bubble_id", ondelete="CASCADE"), nullable=False)
    message_index = Column(Integer, nullable=False, comment="Index of the bubble within conversation (same for user and assistant in bubble)")
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    model_used = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    bubble = relationship("Bubble", back_populates="messages")
    model_responses = relationship("ModelResponse", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system', 'function')", name="valid_role"),
        CheckConstraint("message_index >= 0", name="check_message_index_positive"),
        # Ensure reasonable message_index range
        CheckConstraint(
            "message_index >= 0 AND message_index <= 999999", 
            name="check_message_index_reasonable"
        ),
    ) 
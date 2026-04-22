from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .users import Base

class ModelResponse(Base):
    """
    ModelResponse model representing individual AI model responses.
    
    This table supports multi-model chat functionality where multiple AI models
    can respond to a single user message. Each row represents one model's response.
    
    Structure:
    - Multiple model responses can be linked to one user message
    - Each response is from a specific AI model (GPT-4, Claude, etc.)
    - Responses have an order for consistent display
    - Each response can have multiple comments attached
    """
    __tablename__ = "model_responses"

    response_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.message_id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(100), nullable=False, comment="AI model that generated this response")
    content = Column(Text, nullable=False, comment="The actual response content")
    response_order = Column(Integer, nullable=False, default=0, comment="Display order of response")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="model_responses")
    comments = relationship("ResponseComment", back_populates="response", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("response_order >= 0", name="check_response_order_positive"),
    )


class ResponseComment(Base):
    """
    ResponseComment model representing user comments on model responses.
    
    This table allows users to annotate and provide feedback on specific
    model responses. Each comment is attached to one model response.
    
    Structure:
    - Each comment belongs to one model response
    - Comments are created by users
    - Comments can be updated over time
    - Empty comments are not allowed
    """
    __tablename__ = "response_comments"

    comment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    response_id = Column(UUID(as_uuid=True), ForeignKey("model_responses.response_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    comment_text = Column(Text, nullable=False, comment="The comment content")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    response = relationship("ModelResponse", back_populates="comments")
    user = relationship("User", back_populates="response_comments")

    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(comment_text)) > 0", name="check_comment_not_empty"),
    )


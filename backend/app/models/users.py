from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100))
    password = Column(Text, nullable=False)  # hashed
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user")
    projects = relationship("Project", back_populates="user")
    project_files = relationship("ProjectFile", back_populates="user")
    response_comments = relationship("ResponseComment", back_populates="user")
    workspaces = relationship("Workspace", back_populates="user") 
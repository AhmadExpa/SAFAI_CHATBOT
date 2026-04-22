from sqlalchemy import Column, String, Integer, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .users import Base

class ProjectFile(Base):
    __tablename__ = "project_files"
    
    file_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    filename = Column(Text, nullable=False)  # Generated filename for storage
    original_filename = Column(Text, nullable=False)  # Original filename from user
    file_path = Column(Text, nullable=False)  # Path to file in storage
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(Text, nullable=False)  # MIME type
    file_content = Column(Text)  # For text files, store content directly
    upload_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)
    
    # Relationships
    project = relationship("Project", back_populates="files")
    user = relationship("User", back_populates="project_files")

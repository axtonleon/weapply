# job-application-backend\src\job_app\db\models.py

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, LargeBinary, JSON, func
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

# Base class for declarative models
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    resumes = relationship("Resume", back_populates="owner")
    job_descriptions = relationship("JobDescription", back_populates="owner")
    generated_documents = relationship("GeneratedDocument", back_populates="owner")

class FileRecord(Base):
    """
    Model for storing file data directly in the database.
    This table holds the binary content and metadata for any file uploaded
    to the application, such as resumes or generated documents.
    """
    __tablename__ = "file_records"

    id = Column(Integer, primary_key=True, index=True)
    
    # --- File Metadata ---
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False) 

    # --- File Content ---
    content = Column(LargeBinary, nullable=False)

    # --- Timestamps and extra info ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_ = Column("metadata", JSON, nullable=True)

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    extracted_text = Column(String, nullable=True)


    file_id = Column(Integer, ForeignKey("file_records.id"), nullable=False, unique=True)

  
    owner = relationship("User", back_populates="resumes")
    file = relationship("FileRecord", cascade="all, delete-orphan", single_parent=True)
    generated_documents = relationship("GeneratedDocument", back_populates="source_resume")

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    company = Column(String, nullable=True)
    description_text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="job_descriptions")
    generated_documents = relationship("GeneratedDocument", back_populates="source_job_description")

class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    source_resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)
    source_job_description_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=True)
    content = Column(String, nullable=True) # For text-only content
    created_at = Column(DateTime, default=datetime.utcnow)
    task_id = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False)
    error_message = Column(String, nullable=True)
    
    file_id = Column(Integer, ForeignKey("file_records.id"), nullable=True, unique=True)
    
   
    owner = relationship("User", back_populates="generated_documents")
    source_resume = relationship("Resume", back_populates="generated_documents")
    source_job_description = relationship("JobDescription", back_populates="generated_documents")
    file = relationship("FileRecord", cascade="all, delete-orphan", single_parent=True)
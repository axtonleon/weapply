# job-application-backend\src\job_app\schemas\generated_document.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any
from enum import Enum

# Schema for a generated document response
class GeneratedDocumentResponse(BaseModel):
    id: int
    owner_id: int
    type: str # e.g., 'resume_rewrite', 'tailored_resume', 'cover_letter', 'interview_questions'
    source_resume_id: int | None = None
    source_job_description_id: int | None = None
    content: str | None = None # The generated text content
    storage_path: str | None = None # Optional: if saving as file
    created_at: datetime
    task_id: str | None = None # The Celery task ID associated with this generation
    status: str # e.g., 'pending', 'processing', 'completed', 'failed', 'cancelled'
    error_message: str | None = None # Details if status is 'failed'

    model_config = ConfigDict(from_attributes=True)

# Schema for a task status response
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str # e.g., 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'RETRY', 'REVOKED'
    result: Any | None = None # Optional: The result if status is SUCCESS
    info: Any | None = None # Optional: Information about the task state (e.g., exception details)
    generated_document_id: int | None = None # Link back to the GeneratedDocument record if one exists

    model_config = ConfigDict(arbitrary_types_allowed=True) # Allow 'result' and 'info' to be Any''

class GenerationType(str, Enum):
    """Defines the type of resume generation requested."""
    REWRITE_WITH_SAMPLE = "rewrite_with_sample"       # General rewrite following sample format
    TAILOR_WITH_SAMPLE = "tailor_with_sample"         # Tailored to JD following sample format

# Schema for updating generated document content
class GeneratedDocumentUpdate(BaseModel):
    content: str
    
    model_config = ConfigDict(from_attributes=True)


# job-application-backend\src\job_app\schemas\resume.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# Schema for a resume upload request
# FastAPI handles File uploads separately, so this is mainly for metadata if any
# The actual file data is handled by FastAPI's UploadFile
class ResumeUpload(BaseModel):
    # Add any additional metadata fields here if needed with the file upload
    # Example: description: str | None = None
    pass # No extra fields needed for now, just the file

class FileInfo(BaseModel):
    id: int
    filename: str
    content_type: str
    size: int

# --- The main response schema ---
class ResumeResponse(BaseModel):
    id: int
    owner_id: int
    upload_timestamp: datetime
    extracted_text: Optional[str] = None

    # This field will be populated from the 'resume.file' relationship
    # using the FileInfo schema we just defined.
    file: FileInfo 

    class Config:
        # This setting allows Pydantic to read data from ORM models (e.g., resume.file)
        from_attributes = True
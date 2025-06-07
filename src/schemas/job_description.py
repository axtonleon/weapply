# job-application-backend\src\job_app\schemas\job_description.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime

# Schema for creating a job description (used in POST requests)
class JobDescriptionCreate(BaseModel):
    title: str | None = None
    company: str | None = None
    description_text: str # The main job description text is required

# Schema for a job description response
class JobDescriptionResponse(BaseModel):
    id: int
    owner_id: int
    title: str | None = None
    company: str | None = None
    description_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
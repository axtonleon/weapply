# job-application-backend\src\job_app\schemas\__init__.py

from .user import UserCreate, UserResponse, Token # Keep existing imports
# Add new schema imports
from .resume import ResumeUpload, ResumeResponse
from .job_description import JobDescriptionCreate, JobDescriptionResponse
from .generated_document import GeneratedDocumentResponse, TaskStatusResponse # Import new schemas
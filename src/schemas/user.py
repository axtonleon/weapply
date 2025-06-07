# job-application-backend\src\job_app\schemas\user.py

from pydantic import BaseModel, EmailStr, ConfigDict # Import ConfigDict for Pydantic v2+
from datetime import datetime

# Base schema for user, reusable
class UserBase(BaseModel):
    email: EmailStr # Pydantic validates this as an email format

# Schema for creating a user (used in POST requests)
class UserCreate(UserBase):
    password: str # Password is required for creation

# Schema for returning user data (excluding password_hash)
class UserResponse(UserBase):
    id: int # Include the database ID
    created_at: datetime # Include the creation timestamp

    # Pydantic v2 and later setting for ORM compatibility
    # Allows Pydantic models to be created from SQLAlchemy model instances
    model_config = ConfigDict(from_attributes=True)


# Schemas for authentication (login endpoint response)
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

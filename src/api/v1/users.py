# job-application-backend\src\job_app\api\v1\users.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # Required for login form data
from sqlalchemy.orm import Session # Required for database interaction
from datetime import timedelta # Required for token expiration

# Import dependencies, models, schemas, security functions from your job_app package structure
from src.db.database import get_db # Dependency to get DB session
from src.db.models import User # SQLAlchemy User model
from src.schemas.user import UserCreate, UserResponse, Token # Pydantic schemas for validation/response
from src.security.passwords import hash_password, verify_password # Password utilities
from src.security.auth import create_access_token # JWT creation utility
from src.security.dependencies import get_current_user # Authentication dependency
from src.core.config import settings # Application settings

# Create an API router for user-related endpoints
router = APIRouter(
    prefix="/users", # This router's routes will start with /users
    tags=["users"], # Tag for documentation (groups endpoints in Swagger UI)
)

# Endpoint for user registration
@router.post(
    "/", # Path is just / relative to the router's prefix (/users)
    response_model=UserResponse, # Define the structure of the successful response body
    status_code=status.HTTP_201_CREATED # Return 201 Created on success
)
def create_user(
    user: UserCreate, # Pydantic model for request body validation
    db: Session = Depends(get_db) # Inject database session dependency
):
    """
    Register a new user.
    Checks if email exists, hashes password, and saves user to the database.
    """
    # Check if a user with the provided email already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        # If user exists, raise HTTP exception (400 Bad Request)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash the provided password before storing it
    hashed_password = hash_password(user.password)

    # Create a new User model instance
    new_user = User(
        email=user.email,
        password_hash=hashed_password
    )

    # Add the new user to the database session, commit, and refresh
    db.add(new_user)
    db.commit()
    db.refresh(new_user) # Refresh to load database-generated fields like ID and created_at

    # Return the newly created user object (will be serialized by UserResponse schema)
    return new_user

# Endpoint for user login (obtaining an access token)
# Uses OAuth2PasswordRequestForm to expect 'username' and 'password' form data
@router.post(
    "/login", # Path is /login relative to /users
    response_model=Token # Define the structure of the successful response body (access_token and token_type)
)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), # Inject form data dependency
    db: Session = Depends(get_db) # Inject database session dependency
):
    """
    Authenticate a user and return an access token.
    Expects 'username' (email) and 'password' in form data.
    """
    # Find the user by email (which is the 'username' in OAuth2PasswordRequestForm)
    user = db.query(User).filter(User.email == form_data.username).first()

    # Verify the user exists and the password is correct
    if not user or not verify_password(form_data.password, user.password_hash):
        # If authentication fails, raise HTTP exception (401 Unauthorized)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}, # Standard header for OAuth2 challenges
        )

    # If authentication is successful, create a JWT access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id), # Use user ID as the subject of the token
        expires_delta=access_token_expires # Set expiration time
    )

    # Return the access token and token type
    return {"access_token": access_token, "token_type": "bearer"}


# Endpoint to get details of the currently authenticated user
# Requires a valid JWT access token in the Authorization header
@router.get(
    "/me", # Path is /me relative to /users
    response_model=UserResponse # Define the structure of the successful response body
)
def read_users_me(
    current_user: User = Depends(get_current_user) # Inject the authentication dependency
    # The get_current_user dependency handles token validation and fetching the user
    # If it's successful, 'current_user' will hold the authenticated User object
    # If it fails, it automatically raises a 401 HTTPException
):
    """
    Retrieve information about the current authenticated user.
    Requires a valid JWT token.
    """
    # Since the dependency handled authentication and user fetching,
    # we simply return the 'current_user' object.
    # Pydantic's UserResponse schema will automatically serialize it.
    return current_user
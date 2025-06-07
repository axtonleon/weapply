# job-application-backend\src\job_app\security\dependencies.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # For Bearer token scheme
from sqlalchemy.orm import Session # For database session
from jose import JWTError # Import JWTError explicitly

# Import database dependency and models from your job_app package structure
from src.db.database import get_db
from src.db.models import User # Import the User model

# Import authentication functions from your job_app package structure
from src.security.auth import verify_token # Import verify_token

# Define the OAuth2 scheme
# tokenUrl tells the client (like Swagger UI) where to get a token
# This should be the URL of your login endpoint
# We are planning to put API endpoints under /api/v1, so the login URL will be /api/v1/users/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

# Dependency to get the current authenticated user
# This function will be called by FastAPI whenever 'Depends(get_current_user)' is used in an endpoint
def get_current_user(
    token: str = Depends(oauth2_scheme), # Automatically gets token from Authorization: Bearer header
    db: Session = Depends(get_db) # Gets the database session
) -> User:
    """Retrieves the current user based on the JWT token."""

    # Define the standard exception for failed credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}, # Standard header for OAuth2 challenges
    )

    try:
        # Verify the token using your utility function
        payload = verify_token(token)

        # If verification failed (e.g., token invalid or expired), verify_token returns None
        if payload is None:
             raise credentials_exception

        # Extract the user ID (subject 'sub') from the token payload
        user_id: str | None = payload.get("sub")
        if user_id is None:
            # Token is valid but missing the user ID claim - invalid token structure
            raise credentials_exception

    except JWTError: # Catch specific JWT errors (should be handled by verify_token, but good to have here)
        raise credentials_exception
    except Exception:
         # Catch any other unexpected errors during token processing
         raise credentials_exception


    # Fetch the user from the database using the extracted user ID
    user = db.query(User).filter(User.id == int(user_id)).first() # Convert user_id to int as it's stored as int in DB
    if user is None:
        # Token was valid and had a user ID, but no user with that ID exists in the database
        # This could happen if a user was deleted but still has an active token
        raise credentials_exception

    # If everything is successful, return the authenticated user object
    return user
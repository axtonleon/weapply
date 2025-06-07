# job-application-backend\src\job_app\security\auth.py

from datetime import datetime, timedelta, timezone
from typing import Union, Any
from jose import jwt, JWTError

# Import settings from your job_app package structure
from src.core.config import settings

# Function to create access token
def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Creates a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration from settings
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Data to encode in the token payload
    # 'exp' is the expiration timestamp (required)
    # 'sub' is the subject, typically the user ID
    to_encode = {"exp": expire, "sub": str(subject)}

    # Encode the token using the secret key and algorithm from settings
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY_FOR_AUTH, algorithm=settings.ALGORITHM)

    return encoded_jwt

# Function to verify token and get payload
def verify_token(token: str) -> dict | None:
    """Verifies a JWT token and returns its payload, or None if invalid/expired."""
    try:
        # Decode the token
        # Pass the same algorithm used for encoding
        payload = jwt.decode(
            token,
            settings.SECRET_KEY_FOR_AUTH,
            algorithms=[settings.ALGORITHM]
        )

        # You might add checks here, e.g., ensure the 'sub' claim exists

        return payload

    except JWTError:
        # Catch specific JWT errors (invalid signature, expired token, etc.)
        return None # Indicate invalid token
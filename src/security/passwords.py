# job-application-backend\src\job_app\security\passwords.py

import bcrypt # Ensure you have bcrypt installed (pip install bcrypt)

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    # bcrypt requires bytes for input and output
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8') # Store the hash as a string

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    try:
        # bcrypt.checkpw handles the encoding internally
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        # Handle cases where the hash might be invalid or the wrong format
        return False
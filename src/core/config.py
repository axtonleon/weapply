# job-application-backend\src\job_app\core\config.py

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# load_dotenv() is still good to have here to ensure .env is loaded
# before Pydantic initializes the Settings.
load_dotenv()

class Settings(BaseSettings):
    """
    Application configuration settings.
    Pydantic will automatically read from environment variables or a .env file.
    The default values defined here are used if the corresponding environment
    variable is not found.
    """
    # --- Database Settings ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/resumeapp") 
    # --- Authentication Settings ---
    SECRET_KEY_FOR_AUTH: str = os.getenv("SECRET_KEY_FOR_AUTH", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- AI Service Settings ---
    # Optional field: Pydantic will set this to None if GOOGLE_API_KEY is not in the environment.
    GOOGLE_API_KEY: str | None = None



    # --- Feature Flag for Storage ---
    # This is a key setting to control which storage backend to use.
    # It can be set to "s3" or "database" in the .env file.
    FILE_STORAGE_TYPE: str = "database"

    # --- File Upload Constraints ---
    MAX_FILE_SIZE: int = 10 * 1024 * 1024

    class Config:
        # Pydantic-settings configuration
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = "ignore" # Ignore extra env vars not defined in the model

# Create a single, reusable instance of the settings
settings = Settings()
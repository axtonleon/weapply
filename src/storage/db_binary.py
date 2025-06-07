import io
import logging
from typing import Dict, Any, Optional

from fastapi import UploadFile
from sqlalchemy import create_engine, text, insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from src.core.config import settings

from sqlalchemy.orm import Session, joinedload

from src.db.models import Resume, FileRecord, GeneratedDocument, User


DATABASE_URL =  settings.DATABASE_URL


logger = logging.getLogger(__name__)


from src.db.models import FileRecord, Resume, User

logger = logging.getLogger(__name__)

def upload_file_to_db(
    db: Session,
    file_content: bytes,
    filename: str,
    content_type: str,
    uploader: User
) -> FileRecord:
    """
    Saves file content to the database using the ORM.
    This is a synchronous function that works with a standard SQLAlchemy session.

    Args:
        db: The SQLAlchemy Session.
        file_content: The byte content of the file.
        filename: The original filename.
        content_type: The MIME type of the file.
        uploader: The User object of the person uploading the file.

    Returns:
        The created FileRecord ORM object, not yet committed.
    """
    if not file_content:
        raise ValueError("File content cannot be empty")

    logger.info(
        f"DB-STORAGE: Staging upload of '{filename}' ({len(file_content)} bytes) "
        f"for user '{uploader.email}'."
    )
    
    # Create the FileRecord instance using the ORM model
    db_file = FileRecord(
        filename=filename,
        content_type=content_type,
        content=file_content,
        size=len(file_content),
        # You can store contextual metadata here
        metadata_={"uploader_user_id": uploader.id} 
    )

    # Add the object to the session.
    # The CALLER will be responsible for db.commit() or db.rollback().
    db.add(db_file)
    db.flush() # Use flush to assign an ID to db_file before the transaction is committed.
    
    logger.info(f"DB-STORAGE: Flushed file '{filename}' to DB. Assigned provisional ID: {db_file.id}")
    return db_file


def download_file_from_db(db: Session, file_id: int, current_user: User) -> Optional[FileRecord]:
    """
    Retrieves a file from the database by its ID, but ONLY if the current user
    has permission to access it. This is the secure, recommended implementation.

    Permission is granted if the user owns the Resume or GeneratedDocument
    that the file is linked to.
    """
    logger.info(
        f"DB-STORAGE: User '{current_user.email}' attempting to download file with ID: {file_id}"
    )

    # --- NEW, MORE ROBUST LOGIC USING EXISTS ---

    # 1. Check if the file itself exists first.
    file_record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_record:
        logger.warning(f"DB-STORAGE: File not found for file_id {file_id}. Access denied.")
        return None

    # 2. Now, check for permission. Does the current user own a document
    #    that is linked to this specific file?
    
    # Subquery to check for a matching Resume
    has_resume_permission = db.query(Resume.id).filter(
        Resume.file_id == file_id,
        Resume.owner_id == current_user.id
    ).exists()

    # Subquery to check for a matching GeneratedDocument
    has_doc_permission = db.query(GeneratedDocument.id).filter(
        GeneratedDocument.file_id == file_id,
        GeneratedDocument.owner_id == current_user.id
    ).exists()

    # Use sqlalchemy's or_() to check if at least one of the permissions is true
    permission_granted = db.query(has_resume_permission.correlate(None) | has_doc_permission.correlate(None)).scalar()

    if not permission_granted:
        logger.warning(
            f"DB-STORAGE: Access denied for user '{current_user.email}' on file_id {file_id}. "
            "User does not own the associated document."
        )
        return None
    
    # 3. If permission is granted, return the file record.
    logger.info(
        f"DB-STORAGE: Access granted. Returning file '{file_record.filename}' to user '{current_user.email}'."
    )
    return file_record

def delete_file_from_db(db: Session, file_id: int, current_user: User) -> bool:
    """
    Deletes a file record from the database.
    Ensures the user owns the resume/document associated with the file.
    """
    # First, find the file record.
    file_to_delete = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_to_delete:
        return False # File doesn't exist

    # Check for permission: Does this file belong to a resume or generated doc owned by the user?
    # This is a simplified permission check.
    resume_owner = db.query(Resume).filter(Resume.file_id == file_id, Resume.owner_id == current_user.id).first()
    # You would add a similar check for GeneratedDocument if they can be deleted.

    if not resume_owner:
        logger.warning(f"User {current_user.id} attempted to delete unauthorized file {file_id}.")
        return False

    # If permission is granted, delete the object.
    db.delete(file_to_delete)
    # The caller is responsible for db.commit()
    logger.info(f"User {current_user.id} deleted file {file_id} ('{file_to_delete.filename}').")
    return True


def get_resume_file_content(db: Session, resume_id: int) -> Optional[tuple[bytes, str]]:
    """Fetches the file content and filename associated with a resume ID."""
    logger.info(f"Attempting to fetch file content for resume_id: {resume_id}")
    # Use joinedload for an efficient single query
    resume = db.query(Resume).options(
        joinedload(Resume.file)
    ).filter(Resume.id == resume_id).first()

    if not resume or not resume.file:
        logger.warning(f"Resume {resume_id} or its associated file not found.")
        return None
    
    return resume.file.content, resume.file.filename

# --- NEW FUNCTION ---
def get_file_by_filename(db: Session, filename: str) -> Optional[tuple[bytes, str]]:
    """
    Fetches the binary content and filename of a file record by its filename.
    This is used to retrieve sample templates.
    """
    logger.info(f"Attempting to fetch file content for filename: '{filename}'")
    
    file_record = db.query(FileRecord).filter(FileRecord.filename == filename).first()

    if not file_record:
        logger.warning(f"File with filename '{filename}' not found in the database.")
        return None
        
    logger.info(f"Successfully retrieved file content for '{filename}'.")
    return file_record.content, file_record.filename

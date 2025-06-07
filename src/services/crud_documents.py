# src/job_app/services/crud_documents.py

from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from src.db.models import User, Resume, JobDescription, GeneratedDocument
from src.schemas.job_description import JobDescriptionCreate

# --- Reusable Getters with Permission Checks ---

def get_resume_by_id(db: Session, resume_id: int, user: User) -> Optional[Resume]:
    """Fetches a resume by its ID, ensuring it belongs to the specified user."""
    return db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.owner_id == user.id
    ).first()

def get_job_description_by_id(db: Session, jd_id: int, user: User) -> Optional[JobDescription]:
    """Fetches a job description by its ID, ensuring it belongs to the user."""
    return db.query(JobDescription).filter(
        JobDescription.id == jd_id,
        JobDescription.owner_id == user.id
    ).first()

def get_generated_document_by_id(db: Session, doc_id: int, user: User) -> Optional[GeneratedDocument]:
    """Fetches a generated document by its ID, ensuring it belongs to the user."""
    # Eagerly load the associated file to prevent extra DB queries later
    return db.query(GeneratedDocument).options(
        joinedload(GeneratedDocument.file)
    ).filter(
        GeneratedDocument.id == doc_id,
        GeneratedDocument.owner_id == user.id
    ).first()

# --- List Functions ---

def get_all_resumes_for_user(db: Session, user: User) -> List[Resume]:
    """Fetches all resumes for a given user."""
    return db.query(Resume).filter(Resume.owner_id == user.id).all()

def get_all_job_descriptions_for_user(db: Session, user: User) -> List[JobDescription]:
    """Fetches all job descriptions for a given user."""
    return db.query(JobDescription).filter(JobDescription.owner_id == user.id).all()

def get_all_generated_documents_for_user(db: Session, user: User) -> List[GeneratedDocument]:
    """Fetches all generated documents for a given user."""
    return db.query(GeneratedDocument).filter(GeneratedDocument.owner_id == user.id).order_by(GeneratedDocument.created_at.desc()).all()


# --- Creation Functions ---

def create_resume_for_user(db: Session, user: User, file_record) -> Resume:
    """Creates a new Resume record linked to a user and a file record."""
    db_resume = Resume(owner=user, file=file_record)
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    return db_resume

def create_job_description_for_user(db: Session, user: User, jd_create: JobDescriptionCreate) -> JobDescription:
    """Creates a new JobDescription record for a user."""
    db_jd = JobDescription(
        owner=user,
        title=jd_create.title,
        company=jd_create.company,
        description_text=jd_create.description_text
    )
    db.add(db_jd)
    db.commit()
    db.refresh(db_jd)
    return db_jd

def create_generated_document_for_task(
    db: Session,
    user: User,
    doc_type: str,
    resume: Resume,
    job_description: Optional[JobDescription] = None
) -> GeneratedDocument:
    """Creates the initial GeneratedDocument record with a 'pending' status."""
    db_generated_doc = GeneratedDocument(
        owner=user,
        type=doc_type,
        source_resume=resume,
        source_job_description=job_description,
        status="pending"
    )
    db.add(db_generated_doc)
    db.commit()
    db.refresh(db_generated_doc)
    return db_generated_doc
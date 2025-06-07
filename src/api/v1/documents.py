import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.responses import StreamingResponse

# --- Local Imports ---
from src.db.database import get_db
from src.db.models import User, FileRecord
from src.security.dependencies import get_current_user
from src.schemas.resume import ResumeResponse
from src.schemas.job_description import JobDescriptionCreate, JobDescriptionResponse
from src.schemas.generated_document import GeneratedDocumentResponse, GeneratedDocumentUpdate
from src.storage.db_binary import upload_file_to_db # Keep this for direct file uploads
from src.services.ai.processing import (
    extract_resume_text_bg_task, resume_rewrite_bg_task, cover_letter_bg_task,
    tailored_resume_bg_task, interview_questions_bg_task
)
# VVV The new CRUD service layer VVV
from src.services import crud_documents

router = APIRouter(prefix="/documents", tags=["documents"])

# --- Helper Function for a Common Pattern ---
# This reduces code duplication in the processing endpoints
def start_generation_task(
    db: Session,
    user: User,
    background_tasks: BackgroundTasks,
    resume_id: int,
    jd_id: Optional[int],
    doc_type: str,
    task_function
) -> GeneratedDocumentResponse:
    """Helper to validate inputs and kick off a generation background task."""
    resume = crud_documents.get_resume_by_id(db, resume_id, user)
    if not resume or not resume.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume not found or its text has not been extracted yet."
        )

    job_description = None
    if jd_id:
        job_description = crud_documents.get_job_description_by_id(db, jd_id, user)
        if not job_description:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job description not found.")

    doc = crud_documents.create_generated_document_for_task(
        db, user, doc_type, resume, job_description
    )

    task_args = (doc.id, resume.id, jd_id, user.id) if jd_id else (doc.id, resume.id, user.id)
    background_tasks.add_task(task_function, *task_args)

    return doc

# --- Resume Endpoints ---
@router.post("/resumes/", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume_endpoint(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads a resume, saves it to the DB, and triggers text extraction."""
    # ... (file content type and size validation can go here) ...
    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Cannot upload an empty file.")
    try:
        file_record = upload_file_to_db(db, file_content, file.filename, file.content_type, current_user)
        resume = crud_documents.create_resume_for_user(db, current_user, file_record)
        background_tasks.add_task(extract_resume_text_bg_task, resume.id, current_user.id)
        return resume
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

@router.get("/resumes/", response_model=List[ResumeResponse])
def list_resumes_endpoint(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists all resumes for the current user."""
    return crud_documents.get_all_resumes_for_user(db, current_user)

@router.get("/resumes/{resume_id}", response_model=ResumeResponse)
def get_resume_endpoint(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves a specific resume by ID."""
    resume = crud_documents.get_resume_by_id(db, resume_id, current_user)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return resume

# --- Job Description Endpoints ---
@router.post("/job-descriptions/", response_model=JobDescriptionResponse, status_code=status.HTTP_201_CREATED)
def create_job_description_endpoint(
    job_description: JobDescriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a new job description."""
    return crud_documents.create_job_description_for_user(db, current_user, job_description)

@router.get("/job-descriptions/", response_model=List[JobDescriptionResponse])
def list_job_descriptions_endpoint(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists all job descriptions for the current user."""
    return crud_documents.get_all_job_descriptions_for_user(db, current_user)

@router.get("/job-descriptions/{jd_id}", response_model=JobDescriptionResponse)
def get_job_description_endpoint(jd_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves a specific job description by ID."""
    jd = crud_documents.get_job_description_by_id(db, jd_id, current_user)
    if not jd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job Description not found.")
    return jd

# --- Generated Document & Processing Endpoints ---
@router.post("/process/rewrite-resume/{resume_id}", response_model=GeneratedDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_resume_rewrite_endpoint(
    resume_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Triggers a resume rewrite task."""
    return start_generation_task(db, current_user, background_tasks, resume_id, None, "resume_rewrite", resume_rewrite_bg_task)

@router.post("/process/cover-letter/", response_model=GeneratedDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_cover_letter_endpoint(
    resume_id: int,
    job_description_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Triggers a cover letter generation task."""
    return start_generation_task(db, current_user, background_tasks, resume_id, job_description_id, "cover_letter", cover_letter_bg_task)

@router.post("/process/tailor-resume/", response_model=GeneratedDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_tailored_resume_endpoint(
    resume_id: int,
    job_description_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Triggers a tailored resume generation task."""
    return start_generation_task(db, current_user, background_tasks, resume_id, job_description_id, "tailored_resume", tailored_resume_bg_task)

@router.post("/process/interview-questions/", response_model=GeneratedDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_interview_questions_endpoint(
    resume_id: int,
    job_description_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Triggers an interview questions generation task."""
    return start_generation_task(db, current_user, background_tasks, resume_id, job_description_id, "interview_questions", interview_questions_bg_task)

@router.get("/generated/", response_model=List[GeneratedDocumentResponse])
def list_generated_documents_endpoint(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists all generated documents for the current user."""
    return crud_documents.get_all_generated_documents_for_user(db, current_user)

@router.get("/generated/{doc_id}", response_model=GeneratedDocumentResponse)
def get_generated_document_endpoint(doc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves a specific generated document by ID."""
    doc = crud_documents.get_generated_document_by_id(db, doc_id, current_user)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated document not found.")
    return doc

@router.get("/generated/{doc_id}/download")
def download_generated_document_endpoint(doc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Downloads the PDF file associated with a specific generated document."""
    doc = crud_documents.get_generated_document_by_id(db, doc_id, current_user)
    if not doc or not doc.file or not doc.file.content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Downloadable file not found for this document."
        )
    return StreamingResponse(
        io.BytesIO(doc.file.content),
        media_type=doc.file.content_type,
        headers={"Content-Disposition": f"attachment; filename=\"{doc.file.filename}\""}
    )

@router.patch("/generated/{doc_id}/content", response_model=GeneratedDocumentResponse)
def update_generated_document_content_endpoint(
    doc_id: int,
    update_data: GeneratedDocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates the content of a generated document and regenerates its PDF.
    
    This endpoint allows users to modify the AI-generated content and automatically
    regenerates the PDF version of the document.
    
    Args:
        doc_id: ID of the document to update
        update_data: New content for the document
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated GeneratedDocument
        
    Raises:
        HTTPException: If document not found or update fails
    """
    try:
        updated_doc = crud_documents.update_generated_document_content(
            db=db,
            doc_id=doc_id,
            user=current_user,
            new_content=update_data.content
        )
        
        if not updated_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Generated document not found."
            )
            
        return updated_doc
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document: {str(e)}"
        )

# @router.post(
#     "/process/generate-with-sample/",
#     response_model=GeneratedDocumentResponse,
#     status_code=status.HTTP_202_ACCEPTED
# )
# def trigger_sample_based_generation(
#     resume_id: int,
#     background_tasks: BackgroundTasks, # <-- Add BackgroundTasks dependency
#   # sample_object_name: str, # <-- This should probably be selected on the frontend and passed
#     # For simplicity here, we'll hardcode it in the background task or pass via a param.
#     # Let's add a parameter for the sample object name for flexibility.
#     sample_object_name: str = Form(..., description="S3 object key for the sample document (e.g., resumesamples/template.docx)"),
#     job_description_id: int | None = Form(None, description="Optional Job Description ID for tailoring"), # Change Query to Form if part of body
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     Trigger resume generation (rewrite or tailored) using a sample document's
#     format and style via filename using BackgroundTasks.
#     """
#     # 1. Validate User, Resume
#     resume = db.query(Resume).filter(Resume.id == resume_id, Resume.owner_id == current_user.id).first()
#     if not resume:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

#     if not resume.extracted_text:
#          raise HTTPException(
#              status_code=status.HTTP_400_BAD_REQUEST,
#              detail="Resume text extraction is not complete. Please wait or re-upload."
#          )

#     # 2. Determine Generation Type and Validate Job Description (if needed)
#     # Validation of JD content moved to the background task
#     job_description = None
#     generation_type_enum = GenerationType.REWRITE_WITH_SAMPLE # Default
#     generated_doc_type_str = "resume_rewrite_with_sample"

#     if job_description_id is not None:
#         # Validate existence but content check moved to task
#         job_description = db.query(JobDescription).filter(JobDescription.id == job_description_id, JobDescription.owner_id == current_user.id).first()
#         if not job_description:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job Description not found")
#         generation_type_enum = GenerationType.TAILOR_WITH_SAMPLE
#         generated_doc_type_str = "tailored_resume_with_sample"


#     # 3. Create GeneratedDocument entry
#     db_generated_doc = GeneratedDocument(
#         owner_id=current_user.id,
#         type=generated_doc_type_str,
#         source_resume_id=resume.id,
#         source_job_description_id=job_description_id, # Can be None
#         status="pending",
#         # task_id is no longer applicable
#     )

#     db.add(db_generated_doc)
#     db.commit()
#     db.refresh(db_generated_doc)

#     # 4. Add the Background Task
#     try:
#         background_tasks.add_task(
#             resume_generation_with_sample_bg_task,
#             db_generated_doc.id,
#             resume.id,
#             sample_object_name,  # Pass the sample object name
#             generation_type_enum.value, # Pass enum value as string
#             current_user.id,
#             job_description_id   # Pass JD ID (can be None)
#         )
#         print(f"Added sample-based generation background task for generated document {db_generated_doc.id} (Type: {generation_type_enum.value})")

#     except Exception as e:
#         print(f"Failed to add sample-based generation background task for generated document {db_generated_doc.id}: {e}")
#         db.rollback()
#         db_generated_doc.status = "failed_to_queue"
#         db_generated_doc.error_message = f"Failed to add task to queue: {e}"
#         db.commit()
#         raise HTTPException(
#              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#              detail="Failed to queue AI processing task."
#         )

#     # 5. Return the initial GeneratedDocument record
#     return db_generated_doc
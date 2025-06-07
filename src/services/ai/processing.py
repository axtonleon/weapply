"""AI processing service for resume and document generation.

This module provides functionality for processing resumes and generating various documents
using AI models. It includes text extraction, document generation, and background task handling.
"""

from __future__ import annotations

import os
import sys
import traceback
import asyncio
import tempfile
import shutil
import logging
from typing import Dict, Any, List, Generator, Optional, Tuple
from enum import Enum

import aiofiles
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

# Langchain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_google_genai import ChatGoogleGenerativeAI

# Local imports
from src.services.pdf_generator import create_pdf_from_text
from src.db.models import Resume, JobDescription, GeneratedDocument, User
from src.core.config import settings
from src.db.database import SessionLocal
from src.schemas.generated_document import GenerationType
from src.storage.db_binary import (
    download_file_from_db,
    get_file_by_filename,
    get_resume_file_content,
    upload_file_to_db
)

# Configure logging
logger = logging.getLogger(__name__)

class AIProcessingError(Exception):
    """Base exception for AI processing errors."""
    pass

class ConfigurationError(AIProcessingError):
    """Raised when there are configuration issues."""
    pass

class DocumentProcessingError(AIProcessingError):
    """Raised when there are issues processing documents."""
    pass

# --- Helper function to get DB session in tasks ---
def get_db_session() -> Generator[Session, None, None]:
    """Get a database session for use in background tasks.
    
    Yields:
        Session: A SQLAlchemy database session.
        
    Note:
        The session is automatically closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Document Parsing Helper (called by extract_resume_text_task) ---
# This function is async and needs to be called correctly from the sync Celery task
# Now it will be called directly by the async background task function
async def extract_text_from_resume_file(file_content_bytes: bytes, filename: str) -> str:
    """Extract text from resume file content (PDF or DOCX bytes).
    
    Args:
        file_content_bytes: The byte content of the file.
        filename: The original filename (used to determine file type).
        
    Returns:
        str: The extracted text content, or an empty string if extraction fails.
        
    Raises:
        DocumentProcessingError: If the file type is unsupported or extraction fails.
    """
    temp_dir = None
    temp_file_path = None

    try:
        file_extension = os.path.splitext(filename)[1].lower()
        supported_extensions = [".pdf", ".docx"]
        
        if file_extension not in supported_extensions:
            raise DocumentProcessingError(
                f"Unsupported file type for text extraction: {file_extension} from filename {filename}"
            )

        temp_dir = tempfile.mkdtemp()
        base_filename = os.path.basename(filename)
        temp_file_path = os.path.join(temp_dir, base_filename)

        logger.debug(f"Writing to temporary file: {temp_file_path}")

        async with aiofiles.open(temp_file_path, 'wb') as temp_f:
            await temp_f.write(file_content_bytes)

        logger.debug(f"Successfully wrote {len(file_content_bytes)} bytes to temporary file.")

        loader = None
        if file_extension == ".pdf":
            loader = PyPDFLoader(temp_file_path)
        elif file_extension == ".docx":
            loader = Docx2txtLoader(temp_file_path)

        logger.debug(f"Using loader {type(loader).__name__} for {temp_file_path}")

        documents = await loader.aload()
        full_text = "\n".join([doc.page_content for doc in documents])

        logger.debug(f"Successfully extracted text (length: {len(full_text)}).")
        return full_text.strip()

    except Exception as e:
        logger.error(f"Failed to extract text from {filename}: {e}", exc_info=True)
        raise DocumentProcessingError(f"Text extraction failed: {str(e)}")

    finally:
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.debug(f"Removed temporary file {temp_file_path}")
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.debug(f"Removed temporary directory {temp_dir}")
        except Exception as cleanup_e:
            logger.error(f"Failed during cleanup: {cleanup_e}", exc_info=True)



# --- AI Processing Functions (core logic) ---
# These remain mostly synchronous as they interact with Langchain/Gemini which might be sync wrappers

def get_gemini_chat_model() -> ChatGoogleGenerativeAI:
    """Initialize and return the Gemini chat model.
    
    Returns:
        ChatGoogleGenerativeAI: Configured Gemini chat model instance.
        
    Raises:
        ConfigurationError: If the Google API key is not set.
    """
    google_api_key = settings.GOOGLE_API_KEY
    if not google_api_key:
        raise ConfigurationError("GOOGLE_API_KEY is not set in environment variables or .env")

    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        temperature=0.7,
        google_api_key=google_api_key
    )

# --- NEW: RAG-based Resume Generation using a Sample Document ---
# This core processing function will be called by an async background task wrapper
async def process_resume_generation_with_sample(
    user_resume_text: str,
    sample_text: str,
    generation_type: GenerationType,
    jd_text: Optional[str] = None,
) -> Optional[str]:
    """Process a resume generation task using a RAG approach with a sample document.
    
    Args:
        user_resume_text: Extracted text of the user's resume.
        sample_text: Extracted text of the sample resume file.
        generation_type: The type of generation (REWRITE_WITH_SAMPLE or TAILOR_WITH_SAMPLE).
        jd_text: Optional. The text of the Job Description for tailoring.
        
    Returns:
        Optional[str]: The generated resume content, or None if processing fails.
        
    Raises:
        DocumentProcessingError: If input validation fails or processing errors occur.
    """
    try:
        # Validate inputs
        if not user_resume_text or len(user_resume_text.strip()) < 50:
            raise DocumentProcessingError("User resume text not available or too short.")

        if not sample_text or len(sample_text.strip()) < 50:
            raise DocumentProcessingError("Sample text not available or too short.")

        if generation_type == GenerationType.TAILOR_WITH_SAMPLE:
            if not jd_text or len(jd_text.strip()) < 50:
                raise DocumentProcessingError("Job Description text is empty or too short for TAILOR_WITH_SAMPLE type.")

        # Define system template
        system_template = """You are an expert resume writer and editor. Your task is to generate a new resume based on the provided user's resume content.
CRITICAL INSTRUCTION: Follow the structure, tone, and formatting examples provided in the Sample Resume Format. Do NOT deviate from the sample's overall layout and sectioning.
Use the user's resume content as the source material for information (experience, skills, education, etc.).
Do NOT include information not present in the user's original resume (unless it's a rephrasing/improvement of existing info).
Do NOT include placeholder text like '[Your Name]', '[Address]', '[Phone]', '[Email]', etc., unless it was explicitly present and complete in the sample or user resume.
Provide the output as plain text or using simple markdown for sections (like headings or bullet points), mimicking the sample's style."""

        # Define human templates based on generation type
        human_template_rewrite = """Sample Resume Format:
{sample_text}

---

User's Original Resume:
{user_resume_text}

---

Generate a new resume by rewriting the user's resume content, following the style and structure of the Sample Resume Format."""

        human_template_tailor = """Sample Resume Format:
{sample_text}

---

User's Original Resume:
{user_resume_text}

---

Job Description:
{jd_text}

---

Generate a new resume by tailoring the user's resume content to the provided Job Description, while strictly following the style and structure of the Sample Resume Format. Highlight experience and skills most relevant to the job requirements, using the user's resume as the sole source of information."""

        # Create prompt based on generation type
        if generation_type == GenerationType.REWRITE_WITH_SAMPLE:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_template),
                ("human", human_template_rewrite)
            ])
            input_variables = {"sample_text": sample_text, "user_resume_text": user_resume_text}
        elif generation_type == GenerationType.TAILOR_WITH_SAMPLE:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_template),
                ("human", human_template_tailor)
            ])
            input_variables = {"sample_text": sample_text, "user_resume_text": user_resume_text, "jd_text": jd_text}
        else:
            raise DocumentProcessingError(f"Unsupported generation_type enum value: {generation_type}")

        # Invoke LLM Chain
        llm = get_gemini_chat_model()
        chain = prompt | llm | StrOutputParser()
        generated_content = chain.invoke(input_variables)

        # Validate output
        if not generated_content or len(generated_content.strip()) < 100:
            logger.warning("AI returned little or no content.")
            return None

        return generated_content.strip()

    except ConfigurationError as ce:
        logger.error(f"Configuration issue during resume generation: {ce}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during resume generation: {e}", exc_info=True)
        raise DocumentProcessingError(f"Resume generation failed: {str(e)}")


def process_resume_rewrite(resume_text: str) -> Optional[str]:
    """Process a resume rewrite task.
    
    Args:
        resume_text: The text content of the resume to rewrite.
        
    Returns:
        Optional[str]: The rewritten resume content, or None if processing fails.
        
    Raises:
        DocumentProcessingError: If input validation fails or processing errors occur.
    """
    try:
        if not resume_text:
            raise DocumentProcessingError("Resume text not available.")

        llm = get_gemini_chat_model()
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert resume writer. Rewrite the following resume text into a modern, professional format. Focus on improving clarity, conciseness, and impact. Highlight key skills, quantifiable achievements, and relevant experience. Ensure consistent formatting (e.g., bullet points, section headers). Do NOT include placeholder text like '[Your Name]' or contact info unless it was in the original text. Just provide the rewritten resume content as plain text or using simple markdown for sections."),
            ("human", "Here is the original resume text:\n{resume_text}"),
        ])

        chain = rewrite_prompt | llm | StrOutputParser()
        rewritten_resume_content = chain.invoke({"resume_text": resume_text})

        if not rewritten_resume_content or len(rewritten_resume_content.strip()) < 50:
            logger.warning("AI returned little or no content for resume rewrite.")
            return None

        return rewritten_resume_content.strip()

    except ConfigurationError as ce:
        logger.error(f"Configuration issue during resume rewrite: {ce}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during resume rewrite: {e}", exc_info=True)
        raise DocumentProcessingError(f"Resume rewrite failed: {str(e)}")


def process_cover_letter(resume_text: str, jd_text: str) -> Optional[str]:
    """Process a cover letter generation task.
    
    Args:
        resume_text: The text content of the resume.
        jd_text: The text content of the job description.
        
    Returns:
        Optional[str]: The generated cover letter content, or None if processing fails.
        
    Raises:
        DocumentProcessingError: If input validation fails or processing errors occur.
    """
    try:
        if not resume_text:
            raise DocumentProcessingError("Resume text not available.")

        if not jd_text or len(jd_text.strip()) < 50:
            raise DocumentProcessingError("Job Description text is empty or too short.")

        llm = get_gemini_chat_model()
        cover_letter_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert cover letter writer. Write a professional and compelling cover letter for a job application. Tailor the letter specifically to the provided job description, drawing relevant skills and experiences from the candidate's resume. Use a standard business letter format (without placeholders for addresses/date unless present in resume, focus on the body). Keep it concise and impactful. Address the company and position if possible, otherwise use a standard greeting. Just provide the full cover letter text."),
            ("human", "Here is the candidate's resume:\n{resume_text}\n\nHere is the job description:\n{jd_text}"),
        ])

        chain = cover_letter_prompt | llm | StrOutputParser()
        cover_letter_content = chain.invoke({"resume_text": resume_text, "jd_text": jd_text})

        if not cover_letter_content or len(cover_letter_content.strip()) < 100:
            logger.warning("AI returned little or no content for cover letter.")
            return None

        return cover_letter_content.strip()

    except ConfigurationError as ce:
        logger.error(f"Configuration issue during cover letter generation: {ce}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during cover letter generation: {e}", exc_info=True)
        raise DocumentProcessingError(f"Cover letter generation failed: {str(e)}")


def process_tailored_resume(resume_text: str, jd_text: str) -> Optional[str]:
    """Process a tailored resume generation task.
    
    Args:
        resume_text: The text content of the resume.
        jd_text: The text content of the job description.
        
    Returns:
        Optional[str]: The generated tailored resume content, or None if processing fails.
        
    Raises:
        DocumentProcessingError: If input validation fails or processing errors occur.
    """
    try:
        if not resume_text:
            raise DocumentProcessingError("Resume text not available.")

        if not jd_text or len(jd_text.strip()) < 50:
            raise DocumentProcessingError("Job Description text is empty or too short.")

        llm = get_gemini_chat_model()
        tailored_resume_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert resume writer and ATS optimizer. Your goal is to tailor the provided resume text towards the given job description. Read both carefully. Focus on highlighting the most relevant experience, skills, and keywords from the resume that match the job requirements. Adjust summary, experience, and skills sections accordingly. Maintain a professional resume structure (plain text or markdown sections). Do NOT hallucinate information not present in the original resume. Just provide the tailored resume content."),
            ("human", "Here is the original resume text:\n{resume_text}\n\nHere is the job description:\n{jd_text}"),
        ])

        chain = tailored_resume_prompt | llm | StrOutputParser()
        tailored_resume_content = chain.invoke({"resume_text": resume_text, "jd_text": jd_text})

        if not tailored_resume_content or len(tailored_resume_content.strip()) < 50:
            logger.warning("AI returned little or no content for tailored resume.")
            return None

        return tailored_resume_content.strip()

    except ConfigurationError as ce:
        logger.error(f"Configuration issue during tailored resume generation: {ce}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during tailored resume generation: {e}", exc_info=True)
        raise DocumentProcessingError(f"Tailored resume generation failed: {str(e)}")


def process_interview_questions(resume_text: str, jd_text: str) -> Optional[str]:
    """Process an interview question generation task.
    
    Args:
        resume_text: The text content of the resume.
        jd_text: The text content of the job description.
        
    Returns:
        Optional[str]: The generated interview questions, or None if processing fails.
        
    Raises:
        DocumentProcessingError: If input validation fails or processing errors occur.
    """
    try:
        if not resume_text:
            raise DocumentProcessingError("Resume text not available.")

        if not jd_text or len(jd_text.strip()) < 50:
            raise DocumentProcessingError("Job Description text is empty or too short.")

        llm = get_gemini_chat_model()
        questions_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert interviewer. Generate a list of 5 to 10 potential interview questions specifically tailored to the candidate's background (from the resume) and the requirements of the job (from the job description). Focus on behavioral and technical questions relevant to the role and experience. Format the output as a clear, numbered list of questions."),
            ("human", "Here is the candidate's resume:\n{resume_text}\n\nHere is the job description:\n{jd_text}"),
        ])

        chain = questions_prompt | llm | StrOutputParser()
        interview_questions_content = chain.invoke({"resume_text": resume_text, "jd_text": jd_text})

        if not interview_questions_content or len(interview_questions_content.strip()) < 50:
            logger.warning("AI returned little or no content for interview questions.")
            return None

        return interview_questions_content.strip()

    except ConfigurationError as ce:
        logger.error(f"Configuration issue during interview questions generation: {ce}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during interview questions generation: {e}", exc_info=True)
        raise DocumentProcessingError(f"Interview questions generation failed: {str(e)}")


# --- Background Task Functions (replacing Celery tasks) ---
# These are the functions that will be added to BackgroundTasks.
# They handle fetching data, calling processing functions, and updating DB status.

async def extract_resume_text_bg_task(resume_id: int, user_id: int):
    """Background task to extract text from a USER'S resume file stored in the database."""
    db: Session = next(get_db_session())
    try:
        # 1. Fetch the resume's file content directly from the database using its ID.
        print(f"Extraction BG Task: Fetching file from DB for resume {resume_id}.")
        result = get_resume_file_content(db, resume_id)
        if not result:
            print(f"Extraction BG Task Error: Could not retrieve file from DB for resume {resume_id}.")
            return

        file_content_bytes, original_filename = result

        # 2. Extract text from the file content.
        extracted_text = await extract_text_from_resume_file(file_content_bytes, original_filename)

        # 3. Update the Resume model with the extracted text.
        resume = db.query(Resume).filter(Resume.id == resume_id, Resume.owner_id == user_id).first()
        if not resume:
             print(f"Extraction BG Task Error: Resume {resume_id} not found after file processing.")
             return

        if extracted_text:
            resume.extracted_text = extracted_text; db.commit()
            print(f"Extraction BG Task Success: Extracted and saved text for resume {resume.id}")
        else:
            print(f"Extraction BG Task Failed: No text was extracted for resume {resume.id}.")

    except Exception as e:
        print(f"Extraction BG Task Runtime Error for resume {resume_id}: {e}"); traceback.print_exc(); db.rollback()
    finally:
        db.close()



async def resume_generation_with_sample_bg_task(
    generated_document_id: int,
    user_resume_id: int,
    sample_object_name: str,  # The FILENAME of the sample template, e.g., "template1.docx"
    generation_type_str: str,
    user_id: int,
    job_description_id: int | None = None
):
    """
    Background task to generate a resume using a sample template fetched from the DATABASE.

    This function follows a robust, multi-step process:
    1.  Sets the document status to 'processing'.
    2.  Acquires all necessary data (user resume, JD, sample template).
    3.  Calls the core AI service to generate content.
    4.  Updates the document with the final result ('completed' or 'failed').
    """
    db: Session = next(get_db_session())
    
    # --- 1. SETUP PHASE ---
    # Fetch the document record we need to update. This is the central object for the task.
    doc = db.query(GeneratedDocument).get(generated_document_id)
    if not doc:
        logger.error(f"RAG_TASK_FAIL: GeneratedDocument {generated_document_id} not found. Task cannot proceed.")
        db.close()
        return

    try:
        # Update status immediately to provide feedback to the user that the task has started.
        doc.status = "processing"
        db.commit()
        logger.info(f"RAG_TASK_START: Processing document {doc.id} for user {user_id}.")

        # --- 2. DATA ACQUISITION PHASE ---
        # Fetch all required text data upfront.

        # a. Get the user's resume text (from the already extracted text field)
        user_resume = db.query(Resume).filter(Resume.id == user_resume_id, Resume.owner_id == user_id).first()
        if not user_resume or not user_resume.extracted_text:
            error_msg = f"Source resume (ID: {user_resume_id}) or its text content not found."
            logger.error(f"RAG_TASK_FAIL (doc: {doc.id}): {error_msg}")
            doc.status = "failed"; doc.error_message = error_msg; db.commit()
            return

        user_resume_text = user_resume.extracted_text
        logger.info(f"RAG_TASK_PROGRESS (doc: {doc.id}): Successfully loaded user resume text.")

        # b. Get the job description text, if an ID was provided.
        jd_text = None
        if job_description_id:
            jd = db.query(JobDescription).filter(JobDescription.id == job_description_id, JobDescription.owner_id == user_id).first()
            if not jd or not jd.description_text:
                error_msg = f"Source job description (ID: {job_description_id}) or its text not found."
                logger.error(f"RAG_TASK_FAIL (doc: {doc.id}): {error_msg}")
                doc.status = "failed"; doc.error_message = error_msg; db.commit()
                return
            jd_text = jd.description_text
            logger.info(f"RAG_TASK_PROGRESS (doc: {doc.id}): Successfully loaded job description text.")

        # c. Get the sample template file content from the database using its filename.
        sample_result = get_file_by_filename(db, sample_object_name)
        if not sample_result:
            error_msg = f"Sample template file '{sample_object_name}' not found in the database. Ensure it has been uploaded."
            logger.error(f"RAG_TASK_FAIL (doc: {doc.id}): {error_msg}")
            doc.status = "failed"; doc.error_message = error_msg; db.commit()
            return
        
        sample_file_bytes, sample_filename = sample_result
        logger.info(f"RAG_TASK_PROGRESS (doc: {doc.id}): Successfully fetched sample template '{sample_filename}'.")

        # --- 3. PROCESSING PHASE ---
        # Now that we have all data, we can process it.

        # a. Extract text from the sample template file.
        sample_text = await extract_text_from_resume_file(sample_file_bytes, sample_filename)
        if not sample_text:
            error_msg = f"Failed to extract text from the sample template '{sample_filename}'."
            logger.error(f"RAG_TASK_FAIL (doc: {doc.id}): {error_msg}")
            doc.status = "failed"; doc.error_message = error_msg; db.commit()
            return
        logger.info(f"RAG_TASK_PROGRESS (doc: {doc.id}): Successfully extracted text from sample template.")

        # b. Convert generation type string to Enum for type safety.
        try:
            generation_type = GenerationType(generation_type_str)
        except ValueError:
            error_msg = f"Invalid generation type provided: '{generation_type_str}'."
            logger.error(f"RAG_TASK_FAIL (doc: {doc.id}): {error_msg}")
            doc.status = "failed"; doc.error_message = error_msg; db.commit()
            return

        # c. Call the core AI processing function.
        logger.info(f"RAG_TASK_PROGRESS (doc: {doc.id}): Invoking AI model for generation type '{generation_type.value}'.")
        ai_result = await process_resume_generation_with_sample(
            user_resume_text=user_resume_text,
            sample_text=sample_text,
            generation_type=generation_type,
            jd_text=jd_text
        )

        # --- 4. RESULT HANDLING PHASE ---
        # Update the document based on the outcome of the AI processing.
        if ai_result:
            doc.content = ai_result
            doc.status = "completed"
            doc.error_message = None
            db.commit()
            logger.info(f"RAG_TASK_SUCCESS: Successfully completed and saved document {doc.id}.")
        else:
            error_msg = "AI processing failed or returned no content. Please try again or use a different sample."
            logger.warning(f"RAG_TASK_FAIL (doc: {doc.id}): {error_msg}")
            doc.status = "failed"
            doc.error_message = error_msg
            db.commit()

    except Exception as e:
        # This is a final safety net for any unexpected errors during the process.
        error_msg = f"An unexpected error occurred: {e}"
        logger.error(f"RAG_TASK_UNEXPECTED_ERROR (doc: {doc.id}): {error_msg}", exc_info=True)
        db.rollback() # Rollback any uncommitted changes from the try block
        
        # Re-fetch the document in a clean state to update its status
        doc_on_fail = db.query(GeneratedDocument).get(generated_document_id)
        if doc_on_fail:
            doc_on_fail.status = "failed"
            doc_on_fail.error_message = "An unexpected server error occurred. Please report this issue."
            db.commit()
            
    finally:
        # Always ensure the database connection is closed.
        db.close()


async def resume_rewrite_bg_task(generated_document_id: int, resume_id: int, user_id: int):
    """
    Background task to perform resume rewriting.
    After generating text, it now also creates a PDF version and saves it
    to the database, linking it to the GeneratedDocument.
    """
    db: Session = next(get_db_session())
    doc = db.query(GeneratedDocument).get(generated_document_id)
    if not doc:
        logger.error(f"Rewrite BG Task Error: GeneratedDocument {generated_document_id} not found.")
        db.close()
        return

    try:
        doc.status = "processing"; db.commit()

        # --- Fetch Source Data ---
        user = db.query(User).get(user_id) # We need the user object for the uploader
        resume = db.query(Resume).filter(Resume.id == resume_id, Resume.owner_id == user_id).first()
        if not resume or not resume.extracted_text:
            raise ValueError(f"Source resume (ID: {resume_id}) or its text not found.")
        
        # --- Call AI for Text Generation ---
        ai_result = process_resume_rewrite(resume.extracted_text)

        # --- Process and Save Result ---
        if ai_result:
            # 1. Save the raw text content to the document record.
            doc.content = ai_result
            logger.info(f"AI generation successful for doc {doc.id}. Generating PDF.")

            # 2. Generate the PDF from the AI-generated text.
            pdf_bytes = create_pdf_from_text(ai_result)

            if pdf_bytes:
                # 3. Create a unique filename for the PDF.
                pdf_filename = f"{doc.type}_{doc.id}_{user_id}.pdf"
                
                # 4. Use our existing service to upload the PDF bytes to the DB.
                # This creates a new FileRecord.
                db_file_record = upload_file_to_db(
                    db=db,
                    file_content=pdf_bytes,
                    filename=pdf_filename,
                    content_type="application/pdf",
                    uploader=user
                )
                
                # 5. Link the new FileRecord to our GeneratedDocument.
                # This populates the 'file_id' foreign key.
                doc.file = db_file_record
                logger.info(f"Successfully saved and linked PDF '{pdf_filename}' to doc {doc.id}.")
            else:
                logger.warning(f"PDF generation failed for doc {doc.id}. It will only have text content.")

            # 6. Mark the task as complete and commit everything.
            doc.status = "completed"
            doc.error_message = None
            db.commit()
            logger.info(f"Rewrite BG Task Success: Completed document {doc.id}.")

        else:
            # AI processing failed
            raise ValueError("AI processing failed or returned no content.")

    except Exception as e:
        logger.error(f"Rewrite BG Task Runtime Error for document {doc.id}: {e}", exc_info=True)
        db.rollback()
        doc_on_fail = db.query(GeneratedDocument).get(generated_document_id)
        if doc_on_fail:
            doc_on_fail.status = "failed"
            doc_on_fail.content = None # Clear partial content
            doc_on_fail.error_message = f"Processing error: {e}"
            db.commit()
    finally:
        db.close()


async def cover_letter_bg_task(generated_document_id: int, resume_id: int, job_description_id: int, user_id: int):
    """
    Background task to generate a cover letter, save it as text, and create a downloadable PDF version.
    """
    db: Session = next(get_db_session())
    doc = db.query(GeneratedDocument).get(generated_document_id)
    if not doc:
        logger.error(f"CoverLetter BG Task Error: GeneratedDocument {generated_document_id} not found.")
        db.close()
        return

    try:
        doc.status = "processing"; db.commit()

        # --- Fetch Source Data ---
        user = db.query(User).get(user_id)
        resume = db.query(Resume).filter(Resume.id == resume_id, Resume.owner_id == user_id).first()
        job_description = db.query(JobDescription).filter(JobDescription.id == job_description_id, JobDescription.owner_id == user_id).first()

        if not resume or not resume.extracted_text:
            raise ValueError(f"Source resume (ID: {resume_id}) or its text not found.")
        if not job_description or not job_description.description_text:
            raise ValueError(f"Source job description (ID: {job_description_id}) or its text not found.")

        # --- Call AI for Text Generation ---
        ai_result = process_cover_letter(resume.extracted_text, job_description.description_text)

        # --- Process and Save Result ---
        if ai_result:
            doc.content = ai_result
            logger.info(f"AI generation successful for cover letter doc {doc.id}. Generating PDF.")

            pdf_bytes = create_pdf_from_text(ai_result)
            if pdf_bytes:
                pdf_filename = f"{doc.type}_{doc.id}_{user_id}.pdf"
                db_file_record = upload_file_to_db(
                    db=db,
                    file_content=pdf_bytes,
                    filename=pdf_filename,
                    content_type="application/pdf",
                    uploader=user
                )
                doc.file = db_file_record
                logger.info(f"Successfully saved and linked PDF '{pdf_filename}' to doc {doc.id}.")
            else:
                logger.warning(f"PDF generation failed for cover letter doc {doc.id}.")

            doc.status = "completed"
            doc.error_message = None
            db.commit()
            logger.info(f"CoverLetter BG Task Success: Completed document {doc.id}.")
        else:
            raise ValueError("AI processing failed or returned no content for the cover letter.")

    except Exception as e:
        logger.error(f"CoverLetter BG Task Runtime Error for document {doc.id}: {e}", exc_info=True)
        db.rollback()
        doc_on_fail = db.query(GeneratedDocument).get(generated_document_id)
        if doc_on_fail:
            doc_on_fail.status = "failed"
            doc_on_fail.content = None
            doc_on_fail.error_message = f"Processing error: {e}"
            db.commit()
    finally:
        db.close()
        
async def tailored_resume_bg_task(generated_document_id: int, resume_id: int, job_description_id: int, user_id: int):
    """
    Background task to generate a tailored resume, save it as text, and create a downloadable PDF version.
    """
    db: Session = next(get_db_session())
    doc = db.query(GeneratedDocument).get(generated_document_id)
    if not doc:
        logger.error(f"TailoredResume BG Task Error: GeneratedDocument {generated_document_id} not found.")
        db.close()
        return

    try:
        doc.status = "processing"; db.commit()

        # --- Fetch Source Data ---
        user = db.query(User).get(user_id)
        resume = db.query(Resume).filter(Resume.id == resume_id, Resume.owner_id == user_id).first()
        job_description = db.query(JobDescription).filter(JobDescription.id == job_description_id, JobDescription.owner_id == user_id).first()

        if not resume or not resume.extracted_text:
            raise ValueError(f"Source resume (ID: {resume_id}) or its text not found.")
        if not job_description or not job_description.description_text:
            raise ValueError(f"Source job description (ID: {job_description_id}) or its text not found.")

        # --- Call AI for Text Generation ---
        ai_result = process_tailored_resume(resume.extracted_text, job_description.description_text)

        # --- Process and Save Result ---
        if ai_result:
            doc.content = ai_result
            logger.info(f"AI generation successful for tailored resume doc {doc.id}. Generating PDF.")

            pdf_bytes = create_pdf_from_text(ai_result)
            if pdf_bytes:
                pdf_filename = f"{doc.type}_{doc.id}_{user_id}.pdf"
                db_file_record = upload_file_to_db(
                    db=db,
                    file_content=pdf_bytes,
                    filename=pdf_filename,
                    content_type="application/pdf",
                    uploader=user
                )
                doc.file = db_file_record
                logger.info(f"Successfully saved and linked PDF '{pdf_filename}' to doc {doc.id}.")
            else:
                logger.warning(f"PDF generation failed for tailored resume doc {doc.id}.")

            doc.status = "completed"
            doc.error_message = None
            db.commit()
            logger.info(f"TailoredResume BG Task Success: Completed document {doc.id}.")
        else:
            raise ValueError("AI processing failed or returned no content for the tailored resume.")

    except Exception as e:
        logger.error(f"TailoredResume BG Task Runtime Error for document {doc.id}: {e}", exc_info=True)
        db.rollback()
        doc_on_fail = db.query(GeneratedDocument).get(generated_document_id)
        if doc_on_fail:
            doc_on_fail.status = "failed"
            doc_on_fail.content = None
            doc_on_fail.error_message = f"Processing error: {e}"
            db.commit()
    finally:
        db.close()
        
async def interview_questions_bg_task(generated_document_id: int, resume_id: int, job_description_id: int, user_id: int):
    """
    Background task to generate interview questions, save them as text, and create a downloadable PDF version.
    """
    db: Session = next(get_db_session())
    doc = db.query(GeneratedDocument).get(generated_document_id)
    if not doc:
        logger.error(f"InterviewQ BG Task Error: GeneratedDocument {generated_document_id} not found.")
        db.close()
        return

    try:
        doc.status = "processing"; db.commit()

        # --- Fetch Source Data ---
        user = db.query(User).get(user_id)
        resume = db.query(Resume).filter(Resume.id == resume_id, Resume.owner_id == user_id).first()
        job_description = db.query(JobDescription).filter(JobDescription.id == job_description_id, JobDescription.owner_id == user_id).first()

        if not resume or not resume.extracted_text:
            raise ValueError(f"Source resume (ID: {resume_id}) or its text not found.")
        if not job_description or not job_description.description_text:
            raise ValueError(f"Source job description (ID: {job_description_id}) or its text not found.")

        # --- Call AI for Text Generation ---
        ai_result = process_interview_questions(resume.extracted_text, job_description.description_text)

        # --- Process and Save Result ---
        if ai_result:
            doc.content = ai_result
            logger.info(f"AI generation successful for interview questions doc {doc.id}. Generating PDF.")

            pdf_bytes = create_pdf_from_text(ai_result)
            if pdf_bytes:
                pdf_filename = f"{doc.type}_{doc.id}_{user_id}.pdf"
                db_file_record = upload_file_to_db(
                    db=db,
                    file_content=pdf_bytes,
                    filename=pdf_filename,
                    content_type="application/pdf",
                    uploader=user
                )
                doc.file = db_file_record
                logger.info(f"Successfully saved and linked PDF '{pdf_filename}' to doc {doc.id}.")
            else:
                logger.warning(f"PDF generation failed for interview questions doc {doc.id}.")

            doc.status = "completed"
            doc.error_message = None
            db.commit()
            logger.info(f"InterviewQ BG Task Success: Completed document {doc.id}.")
        else:
            raise ValueError("AI processing failed or returned no content for the interview questions.")

    except Exception as e:
        logger.error(f"InterviewQ BG Task Runtime Error for document {doc.id}: {e}", exc_info=True)
        db.rollback()
        doc_on_fail = db.query(GeneratedDocument).get(generated_document_id)
        if doc_on_fail:
            doc_on_fail.status = "failed"
            doc_on_fail.content = None
            doc_on_fail.error_message = f"Processing error: {e}"
            db.commit()
    finally:
        db.close()
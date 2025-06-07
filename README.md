# Job Application Backend

A powerful FastAPI-based backend service for managing job applications, featuring AI-powered resume and cover letter generation, document processing, and secure file storage.

## Features

- **AI-Powered Document Generation**

  - Resume rewriting and optimization
  - Cover letter generation
  - Interview question generation
  - Tailored resume creation based on job descriptions
  - Sample-based resume formatting

- **Document Management**

  - PDF and DOCX file processing
  - Text extraction from documents
  - PDF generation from text
  - Secure file storage and retrieval
  - Document version control

- **Security & Authentication**

  - JWT-based authentication
  - Secure password hashing
  - Role-based access control
  - File access permissions

- **Database & Storage**
  - PostgreSQL database integration
  - Binary file storage
  - Efficient file retrieval
  - Transaction management

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT with Python-Jose
- **File Processing**: PyPDF, docx2txt, xhtml2pdf
- **AI Integration**: LangChain with Google's Gemini AI
- **Async Support**: aiohttp, aiofiles
- **Security**: bcrypt, argon2-cffi

## Prerequisites

- Python 3.8+
- PostgreSQL
- Google Cloud API key (for Gemini AI)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/job-application-backend.git
   cd job-application-backend
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On Unix or MacOS
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory with the following variables:

   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   SECRET_KEY=your-secret-key
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   GOOGLE_API_KEY=your-google-api-key
   ```

5. Initialize the database:
   ```bash
   alembic upgrade head
   ```

## Running the Application

1. Start the development server:

   ```bash
   uvicorn src.main:app --reload
   ```

2. Access the API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication

- `POST /auth/token`: Get access token
- `POST /auth/register`: Register new user

### Documents

- `POST /documents/process/rewrite-resume/{resume_id}`: Rewrite resume
- `POST /documents/process/cover-letter`: Generate cover letter
- `POST /documents/process/tailored-resume`: Create tailored resume
- `POST /documents/process/interview-questions`: Generate interview questions
- `GET /documents/generated/`: List generated documents
- `GET /documents/generated/{doc_id}`: Get specific document
- `PATCH /documents/generated/{doc_id}/content`: Update document content
- `GET /documents/generated/{doc_id}/download`: Download document PDF

## Project Structure

```
src/
├── api/            # API endpoints and routers
├── core/           # Core configuration
├── db/             # Database models and connection
├── schemas/        # Pydantic models
├── security/       # Authentication and security
├── services/       # Business logic
│   ├── ai/        # AI processing
│   └── crud/      # Database operations
└── storage/        # File storage handling
```

## Development

### Running Tests

```bash
pytest
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Deployment

The application can be deployed using Docker:

1. Build the Docker image:

   ```bash
   docker build -t job-application-backend .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 job-application-backend
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request


## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

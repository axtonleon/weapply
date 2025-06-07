# job-application-backend\src\job_app\main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# Import the users router from your new structure
from src.api.v1 import users,documents  # Assuming v1 is where users.py is located
from src.core.config import settings


print(settings.DATABASE_URL)

# Create a FastAPI instance
app = FastAPI(
    title="Job Application AI Backend",
    description="Backend API for AI-powered job application assistance",
    version="0.1.0",
    
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the users router
# All endpoints defined in users.py will now be available under /api/v1/users/...
app.include_router(users.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1") 

# Basic root endpoint   
@app.get("/")
async def read_root():
    return RedirectResponse(url="/docs")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

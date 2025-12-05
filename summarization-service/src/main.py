"""
Summarization Service - FastAPI Application
Main entry point for the podcast summarization API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading

from config import SUMMARIZATION_API_PORT, SUMMARIZATION_FRONTEND_URL, SUMMARIZATION_MODEL
from models import HealthResponse
from routers import summaries
from services.gemini_service import get_gemini_service
from services.file_watcher import start_file_watcher


# File watcher thread
file_watcher_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes services on startup and cleans up on shutdown.
    """
    global file_watcher_thread
    
    # Startup: Initialize services
    print("\n" + "="*60)
    print("🚀 Starting Summarization Service")
    print("="*60)
    
    # Pre-load Gemini service
    print("\n📦 Initializing Gemini service...")
    try:
        get_gemini_service()
        print("✅ Gemini service initialized")
    except Exception as e:
        print(f"❌ Gemini service initialization failed: {e}")
        raise
    
    # Start file watcher in background thread
    print("\n👁️  Starting file watcher...")
    file_watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    file_watcher_thread.start()
    print("✅ File watcher started")
    
    print("\n" + "="*60)
    print("✅ Summarization Service is ready!")
    print(f"   Model: {SUMMARIZATION_MODEL}")
    print("="*60 + "\n")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down Summarization Service...")


# Create FastAPI app
app = FastAPI(
    title="Podcast Summarization Service",
    description="AI-powered summarization for podcast transcripts using Gemini API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[SUMMARIZATION_FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(summaries.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Podcast Summarization Service",
        "version": "1.0.0",
        "model": SUMMARIZATION_MODEL,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Verifies Gemini API is configured.
    """
    try:
        # Check if Gemini service is accessible
        gemini_service = get_gemini_service()
        
        return HealthResponse(
            status="healthy",
            gemini_api_configured=gemini_service is not None,
            model_name=SUMMARIZATION_MODEL,
            file_watcher_active=file_watcher_thread is not None and file_watcher_thread.is_alive()
        )
    
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            gemini_api_configured=False,
            model_name=SUMMARIZATION_MODEL,
            file_watcher_active=False
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SUMMARIZATION_API_PORT,
        reload=True
    )

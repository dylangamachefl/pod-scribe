"""
Summarization Service - FastAPI Application
Main entry point for the podcast summarization API.
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import (
    SUMMARIZATION_API_PORT, 
    SUMMARIZATION_FRONTEND_URL, 
    STAGE1_MODEL,
    STAGE2_MODEL
)
from models import HealthResponse
from routers import summaries
from services.gemini_service import get_gemini_service
from event_subscriber import start_summarization_event_subscriber



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes services on startup and cleans up on shutdown.
    """
    # Startup: Initialize services
    print("\n" + "="*60)
    print("🚀 Starting Summarization Service")
    print("="*60)
    
    # Pre-load Gemini service
    print("\n📦 Initializing services...")
    try:
        # Initialize database
        from podcast_transcriber_shared.database import init_db
        await init_db()
        print("✅ Database initialized")
        
        # Initialize Gemini service
        get_gemini_service()
        print("✅ Gemini service initialized")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        raise
    
    # Start event subscriber in background (async task)
    print("\n📡 Starting event subscriber as background task...")
    subscriber_task = asyncio.create_task(start_summarization_event_subscriber())
    print("✅ Event subscriber started (listening for EpisodeTranscribed events)")
    
    print("\n" + "="*60)
    print("✅ Summarization Service is ready!")
    print(f"   Stage 1 Model (Thinker): {STAGE1_MODEL}")
    print(f"   Stage 2 Model (Structurer): {STAGE2_MODEL}")
    print(f"   Architecture: Event-Driven Only (no file watching)")
    print("="*60 + "\n")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down Summarization Service...")
    # Cancel subscriber task
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        print("✅ Event subscriber stopped")



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
        "version": "2.0.0",
        "architecture": "two-stage",
        "stage1_model": STAGE1_MODEL,
        "stage2_model": STAGE2_MODEL,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Verifies Gemini API is configured and event subscriber is running.
    """
    try:
        # Check if Gemini service is accessible
        gemini_service = get_gemini_service()
        
        return HealthResponse(
            status="healthy",
            gemini_api_configured=gemini_service is not None,
            model_name=f"{STAGE1_MODEL} + {STAGE2_MODEL}",
            event_subscriber_active=True  # Task-based, always active if service is running
        )
    
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            gemini_api_configured=False,
            model_name=f"{STAGE1_MODEL} + {STAGE2_MODEL}",
            event_subscriber_active=False
        )



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SUMMARIZATION_API_PORT,
        reload=True
    )

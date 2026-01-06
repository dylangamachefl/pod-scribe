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
    OLLAMA_SUMMARIZER_MODEL
)
from models import HealthResponse
from routers import summaries
from services.ollama_service import get_ollama_service
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
    
    # Pre-load Ollama service
    print("\n📦 Initializing services...")
    try:
        # Initialize database
        from podcast_transcriber_shared.database import init_db
        await init_db()
        print("✅ Database initialized")
        
        # Initialize Ollama service
        get_ollama_service()
        print("✅ Ollama service initialized")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        raise
    
    # Start event subscriber in background (async task)
    print("\n📡 Starting event subscriber as background task...")
    subscriber_task = asyncio.create_task(start_summarization_event_subscriber())
    print("✅ Event subscriber started (listening for EpisodeTranscribed events)")
    
    print("\n" + "="*60)
    print("✅ Summarization Service is ready!")
    print(f"   Model: {OLLAMA_SUMMARIZER_MODEL}")
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
    description="AI-powered summarization for podcast transcripts using local Ollama models",
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
        "model": OLLAMA_SUMMARIZER_MODEL,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.
    Verifies all critical dependencies are operational.
    """
    from fastapi.responses import JSONResponse
    
    checks = {
        "ollama": False,
        "redis": False,
        "postgres": False
    }
    
    try:
        # Check Ollama connection
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                from config import OLLAMA_API_URL
                response = await client.get(f"{OLLAMA_API_URL}/api/tags")
                checks["ollama"] = response.status_code == 200
        except Exception as e:
            print(f"Health check: Ollama failed - {e}")
        
        # Check Redis connection
        try:
            from podcast_transcriber_shared.events import get_event_bus
            event_bus = get_event_bus()
            await event_bus._connect()
            if event_bus.client:
                await event_bus.client.ping()
                checks["redis"] = True
        except Exception as e:
            print(f"Health check: Redis failed - {e}")
        
        # Check PostgreSQL connection
        try:
            from podcast_transcriber_shared.database import get_episode_by_id
            # Simple query to verify connection
            await get_episode_by_id("health_check_test")
            checks["postgres"] = True
        except Exception as e:
            # Expected to fail for non-existent ID, but connection works
            if "health_check_test" in str(e) or "not found" in str(e).lower():
                checks["postgres"] = True
            else:
                print(f"Health check: PostgreSQL failed - {e}")
        
        # Determine overall status
        all_healthy = all(checks.values())
        status = "healthy" if all_healthy else ("degraded" if any(checks.values()) else "unhealthy")
        status_code = 200 if all_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": status,
                "checks": checks,
                "service": "summarization-service",
                "model": OLLAMA_SUMMARIZER_MODEL
            }
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "checks": checks,
                "error": str(e),
                "service": "summarization-service"
            }
        )



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SUMMARIZATION_API_PORT,
        reload=True
    )

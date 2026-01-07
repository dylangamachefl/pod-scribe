"""
RAG Backend - FastAPI Application
Main entry point for the RAG service API.
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import RAG_FRONTEND_URL
from models import HealthResponse
from routers import chat, ingest, downloads
from services.embeddings import get_embedding_service
from services.qdrant_service import get_qdrant_service
from services.ollama_client import get_ollama_chat_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes services on startup and cleans up on shutdown.
    """
    # Startup: Initialize services
    print("\n" + "="*60)
    print("🚀 Starting RAG Service")
    print("="*60)
    
    # Pre-load services (singletons)
    print("\n📦 Initializing services...")
    try:
        # Initialize database
        from podcast_transcriber_shared.database import init_db
        await init_db()
        print("✅ Database initialized")
        
        # Initialize other services
        get_embedding_service()
        get_qdrant_service()
        get_ollama_chat_client()
        print("✅ All services initialized")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        raise
    
    # Start event subscriber in background
    print("\n📡 Starting event subscriber as background task...")
    from event_subscriber import start_rag_event_subscriber, recover_stuck_episodes
    
    # Run recovery for stuck episodes (if any)
    await recover_stuck_episodes()

    subscriber_task = asyncio.create_task(start_rag_event_subscriber())
    print("✅ Event subscriber started in background")
    
    print("\n" + "="*60)
    print("✅ RAG Service is ready!")
    print("="*60 + "\n")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down RAG Service...")
    # Cancel subscriber task
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        print("✅ Event subscriber stopped")



# Create FastAPI app
app = FastAPI(
    title="Podcast RAG Backend",
    description="Retrieval-Augmented Generation API for podcast transcripts",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[RAG_FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(downloads.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Podcast RAG Backend",
        "version": "1.0.0",
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
        "qdrant": False,
        "redis": False,
        "postgres": False,
        "ollama": False
    }
    
    try:
        # Check Qdrant connection
        try:
            qdrant_service = get_qdrant_service()
            await qdrant_service.get_collection_stats()
            checks["qdrant"] = True
        except Exception as e:
            print(f"Health check: Qdrant failed - {e}")
        
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
        
        # Check Ollama connection
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                from config import OLLAMA_API_URL
                response = await client.get(f"{OLLAMA_API_URL}/api/tags")
                checks["ollama"] = response.status_code == 200
        except Exception as e:
            print(f"Health check: Ollama failed - {e}")
        
        # Determine overall status
        all_healthy = all(checks.values())
        status = "healthy" if all_healthy else ("degraded" if any(checks.values()) else "unhealthy")
        status_code = 200 if all_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": status,
                "checks": checks,
                "service": "rag-service"
            }
        )
    
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "checks": checks,
                "error": str(e),
                "service": "rag-service"
            }
        )


if __name__ == "__main__":
    import uvicorn
    from config import RAG_API_PORT
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=RAG_API_PORT,
        reload=True
    )

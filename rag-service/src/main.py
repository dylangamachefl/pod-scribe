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
from services.qdrant_client import get_qdrant_service
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
    from event_subscriber import start_rag_event_subscriber
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
    Health check endpoint.
    Verifies all services are operational.
    """
    try:
        # Check if services are accessible
        embedding_service = get_embedding_service()
        qdrant_service = get_qdrant_service()
        chat_client = get_ollama_chat_client()
        
        # Test Qdrant connection
        try:
            qdrant_service.get_collection_stats()
            qdrant_connected = True
        except:
            qdrant_connected = False
        
        # Test Ollama connection
        try:
            import requests
            response = requests.get(f"{chat_client.api_url}/api/tags", timeout=5)
            ollama_connected = response.status_code == 200
        except:
            ollama_connected = False
        
        return HealthResponse(
            status="healthy" if (qdrant_connected and ollama_connected) else "degraded",
            qdrant_connected=qdrant_connected,
            embedding_model_loaded=embedding_service is not None,
            gemini_api_configured=ollama_connected  # Reuse field name for Ollama status
        )
    
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            qdrant_connected=False,
            embedding_model_loaded=False,
            gemini_api_configured=False
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

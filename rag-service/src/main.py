"""
RAG Backend - FastAPI Application
Main entry point for the RAG service API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading

from config import RAG_FRONTEND_URL
from models import HealthResponse
from routers import chat, summaries, ingest, downloads
from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service
from services.gemini_client import get_summary_client, get_chat_client
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
    print("🚀 Starting RAG Backend Service")
    print("="*60)
    
    # Pre-load services (singletons)
    print("\n📦 Initializing services...")
    try:
        get_embedding_service()
        get_qdrant_service()
        get_summary_client()
        get_chat_client()
        print("✅ All services initialized")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        raise
    
    # Start file watcher in background thread
    print("\n👁️  Starting file watcher...")
    file_watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    file_watcher_thread.start()
    print("✅ File watcher started")
    
    print("\n" + "="*60)
    print("✅ RAG Backend Service is ready!")
    print("="*60 + "\n")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down RAG Backend Service...")


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
app.include_router(summaries.router)
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
        summary_client = get_summary_client()
        chat_client = get_chat_client()
        
        # Test Qdrant connection
        try:
            qdrant_service.get_collection_stats()
            qdrant_connected = True
        except:
            qdrant_connected = False
        
        return HealthResponse(
            status="healthy" if qdrant_connected else "degraded",
            qdrant_connected=qdrant_connected,
            embedding_model_loaded=embedding_service is not None,
            gemini_api_configured=(summary_client is not None and chat_client is not None)
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

"""
Chat Router
Handles episode-scoped Q&A using hybrid search (BM25 + FAISS).
"""
from fastapi import APIRouter, HTTPException
import time

from models import ChatRequest, ChatResponse, SourceCitation
from services.ollama_client import get_ollama_chat_client
from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service
from services.hybrid_retriever import get_hybrid_retriever_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Answer a question about a specific episode using hybrid search (BM25 + FAISS).
    
    The hybrid retriever combines:
    - BM25: Keyword-based matching
    - FAISS: Semantic vector search
    
    Results are filtered to the specified episode only.
    """
    try:
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"📝 RAG Chat Request")
        print(f"   Question: {request.question[:100]}...")
        print(f"   Episode: {request.episode_title}")
        print(f"{'='*60}")
        
        # Get services with error handling
        try:
            embeddings_service = get_embedding_service()
            print("✅ Embeddings service loaded")
        except Exception as e:
            print(f"❌ Failed to load embeddings service: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Embeddings service unavailable: {str(e)}"
            )
        
        try:
            qdrant_service = get_qdrant_service()
            print("✅ Qdrant service connected")
        except Exception as e:
            print(f"❌ Failed to connect to Qdrant: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Vector database unavailable. Ensure Qdrant is running: {str(e)}"
            )
        
        # Get or create hybrid retriever
        try:
            hybrid_service = get_hybrid_retriever_service()
            print("✅ Hybrid retriever loaded")
        except ValueError:
            # First time initialization
            print("⚠️  Hybrid retriever not initialized, creating...")
            try:
                hybrid_service = get_hybrid_retriever_service(
                    embeddings_service=embeddings_service,
                    qdrant_service=qdrant_service
                )
                # Try to load existing indexes
                if not hybrid_service.load_indexes():
                    # Build new indexes if loading fails
                    print("📊 Building new hybrid search indexes...")
                    hybrid_service.build_indexes()
                    hybrid_service.save_indexes()
                    print("✅ Indexes built and saved")
            except Exception as e:
                print(f"❌ Failed to initialize hybrid retriever: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize search indexes: {str(e)}"
                )
        
        # Perform hybrid search scoped to the episode
        print(f"🔍 Searching for relevant chunks...")
        try:
            retrieved_chunks = hybrid_service.search(
                query=request.question,
                k=5,
                bm25_weight=request.bm25_weight,
                faiss_weight=request.faiss_weight,
                episode_filter=request.episode_title  # Always filter by episode
            )
            print(f"✅ Found {len(retrieved_chunks)} relevant chunks")
        except Exception as e:
            print(f"❌ Search failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Search failed: {str(e)}"
            )
        
        if not retrieved_chunks:
            print(f"⚠️  No content found for episode: {request.episode_title}")
            raise HTTPException(
                status_code=404,
                detail=f"No content found for episode: {request.episode_title}. The episode may not have been ingested yet."
            )
        
        # Use Ollama chat client with retrieved chunks
        print(f"🤖 Generating answer with Ollama...")
        try:
            chat_client = get_ollama_chat_client()
            response = chat_client.answer_with_retrieved_chunks(
                question=request.question,
                retrieved_chunks=retrieved_chunks,
                conversation_history=request.conversation_history
            )
            print(f"✅ Answer generated ({len(response['answer'])} chars)")
        except Exception as e:
            print(f"❌ Ollama generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"AI generation failed. Ensure Ollama is running with qwen2.5:7b model: {str(e)}"
            )
        
        # Format sources
        sources = [
            SourceCitation(
                podcast_name=chunk["podcast_name"],
                episode_title=chunk["episode_title"],
                speaker=chunk["speaker"],
                timestamp=chunk["timestamp"],
                text_snippet=chunk["text"][:200] + "...",  # Truncate for display
                relevance_score=1.0  # Ensemble doesn't return individual scores
            )
            for chunk in retrieved_chunks
        ]
        
        processing_time = (time.time() - start_time) * 1000
        print(f"✅ Request completed in {processing_time:.0f}ms")
        print(f"{'='*60}\n")
        
        return ChatResponse(
            answer=response["answer"],
            sources=sources,
            processing_time_ms=processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )


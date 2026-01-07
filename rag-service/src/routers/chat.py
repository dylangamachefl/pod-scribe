"""
Chat Router
Handles episode-scoped Q&A using hybrid search (BM25 + FAISS).
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import time
import json

from models import ChatRequest, ChatResponse, SourceCitation
from services.ollama_client import get_ollama_chat_client
from services.embeddings import get_embedding_service
from services.qdrant_service import get_qdrant_service
from services.hybrid_retriever import get_hybrid_retriever_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def ask_question_stream(request: ChatRequest):
    """
    Answer a question and stream the response chunk-by-chunk.
    """
    try:
        # 1. Setup services (match ask_question logic)
        embeddings_service = get_embedding_service()
        qdrant_service = get_qdrant_service()
        
        try:
            hybrid_service = get_hybrid_retriever_service()
        except ValueError:
            # Initialize if not already done
            hybrid_service = get_hybrid_retriever_service(
                embeddings_service=embeddings_service,
                qdrant_service=qdrant_service
            )
            if not hybrid_service._loaded_from_disk:
                await hybrid_service.build_bm25_index()
        
        if hybrid_service.bm25_retriever is None:
            await hybrid_service.build_bm25_index()
        
        # 2. Retrieval
        retrieved_chunks = hybrid_service.search(
            query=request.question,
            k=5,
            episode_filter=request.episode_title
        )
        
        if not retrieved_chunks:
            # For streaming, we can either return 404 immediately or stream a "not found" message
            # The frontend usually expects a response once it connects, so let's raise 404
            raise HTTPException(
                status_code=404, 
                detail=f"No content found for episode: {request.episode_title}"
            )

        # 3. Extract sources
        sources = [
            {
                "speaker": c["speaker"], 
                "timestamp": c["timestamp"], 
                "episode": c["episode_title"]
            } 
            for c in retrieved_chunks
        ]
        
        # 4. Stream Generator
        def stream_generator():
            try:
                chat_client = get_ollama_chat_client()
                
                # Send sources first as metadata
                yield f"METADATA:{json.dumps({'sources': sources})}\n"
                
                # Send answer chunks
                for chunk in chat_client.generate_answer_stream(
                    question=request.question,
                    retrieved_chunks=retrieved_chunks,
                    conversation_history=request.conversation_history
                ):
                    yield chunk
            except Exception as e:
                print(f"❌ Error in stream generator: {e}")
                yield f"\n[Error: {str(e)}]"

        return StreamingResponse(stream_generator(), media_type="text/plain")

    except HTTPException:
        # Re-raise HTTP exceptions (like our 404)
        raise
    except Exception as e:
        print(f"❌ Streaming setup error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Answer a question about a specific episode using hybrid search (BM25 + Qdrant).
    
    The hybrid retriever combines:
    - BM25: Keyword-based matching (local index)
    - Qdrant: Semantic vector search (remote database)
    
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
                # BM25 index loads from disk on init if available
                # If not available, it will be built on first search or manually
                if not hybrid_service._loaded_from_disk:
                    print("📊 Building BM25 index from Qdrant...")
                    await hybrid_service.build_bm25_index()
                    print("✅ BM25 index built and saved")
            except Exception as e:
                print(f"❌ Failed to initialize hybrid retriever: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize search indexes: {str(e)}"
                )
        
        # Ensure BM25 index exists before search
        if hybrid_service.bm25_retriever is None:
            print("📊 BM25 index not available, building from Qdrant...")
            await hybrid_service.build_bm25_index()
        
        from podcast_transcriber_shared.gpu_lock import get_gpu_lock
        
        # Perform hybrid search (episode-scoped or global)
        print(f"🔍 Searching for relevant chunks...")
        try:
            # Acquire lock for embedding query inside search
            async with get_gpu_lock().acquire():
                retrieved_chunks = await hybrid_service.search(
                    query=request.question,
                    k=5,
                    bm25_weight=request.bm25_weight,
                    qdrant_weight=request.faiss_weight,
                    episode_filter=request.episode_title  # May be None for global search
                )
            print(f"✅ Found {len(retrieved_chunks)} relevant chunks")
        except Exception as e:
            print(f"❌ Search failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Search failed: {str(e)}"
            )
        
        if not retrieved_chunks:
            search_scope = f"episode: {request.episode_title}" if request.episode_title else "global library"
            print(f"⚠️  No content found for {search_scope}")
            raise HTTPException(
                status_code=404,
                detail=f"No relevant content found in {search_scope}."
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


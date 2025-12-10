#!/usr/bin/env python3
"""
Hybrid Search Index Builder
Builds BM25 and FAISS indexes from Qdrant for the RAG service.

Run this script after ingesting transcripts to enable the chat feature.
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service
from services.hybrid_retriever import get_hybrid_retriever_service


def main():
    """Build and save hybrid search indexes."""
    print("=" * 60)
    print("Building Hybrid Search Indexes")
    print("=" * 60)
    
    try:
        # Initialize services
        print("\n1. Initializing services...")
        embeddings_service = get_embedding_service()
        print("   ✅ Embeddings service initialized")
        
        qdrant_service = get_qdrant_service()
        print("   ✅ Qdrant service connected")
        
        # Create hybrid retriever
        print("\n2. Creating hybrid retriever...")
        hybrid_service = get_hybrid_retriever_service(
            embeddings_service=embeddings_service,
            qdrant_service=qdrant_service
        )
        print("   ✅ Hybrid retriever created")
        
        # Build indexes from Qdrant
        print("\n3. Building indexes from Qdrant data...")
        result = hybrid_service.build_indexes()
        
        if result["status"] == "empty":
            print("\n⚠️  No documents found in Qdrant.")
            print("   Please ingest transcripts first before building indexes.")
            return 1
        
        print(f"   ✅ Indexed {result['documents_indexed']} documents")
        print(f"   ✅ BM25 weight: {result['bm25_weight']}")
        print(f"   ✅ FAISS weight: {result['faiss_weight']}")
        
        # Save indexes to disk
        print("\n4. Saving indexes to disk...")
        hybrid_service.save_indexes()
        print("   ✅ Indexes saved successfully")
        
        print("\n" + "=" * 60)
        print("✅ Index build complete! RAG chat is ready to use.")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ Error building indexes: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
Hybrid Retriever Service
Combines BM25 (keyword-based) and Qdrant (semantic vector) search.
FAISS removed to eliminate O(N) memory loading at startup.
"""
from typing import List, Dict, Optional
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

from config import (
    BM25_WEIGHT,
    QDRANT_WEIGHT,
    HYBRID_TOP_K,
    INDEXES_PATH,
    TOP_K_RESULTS
)


class HybridRetrieverService:
    """Service for hybrid search combining BM25 and Qdrant vector search."""
    
    def __init__(self, embeddings_service, qdrant_service):
        self.embeddings_service = embeddings_service
        self.qdrant_service = qdrant_service
        
        self.bm25_retriever: Optional[BM25Retriever] = None
        self._document_count: int = 0
        
        print("✅ HybridRetrieverService initialized")
    
    async def build_bm25_index(self, force_rebuild: bool = False) -> Dict:
        """
        Build BM25 index from all documents in Qdrant using scrolling/pagination.
        Avoids loading all docs into memory at once during fetch,
        though BM25Retriever will still store them.
        """
        if self.bm25_retriever is not None and not force_rebuild:
            print("ℹ️  BM25 index already loaded, skipping rebuild")
            return {"status": "already_loaded", "documents_indexed": self._document_count}
        
        print("Building BM25 index from Qdrant (using scrolling)...")
        
        temp_documents = []
        offset = None
        total_fetched = 0
        batch_size = 500  # Smaller batches to manage memory
        
        while True:
            # Scroll through Qdrant
            # Returns (points, next_page_offset)
            # We must use with_vectors=False to save memory!
            points, offset = await self.qdrant_service.client.scroll(
                collection_name=self.qdrant_service.collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            for point in points:
                doc = Document(
                    page_content=point.payload["text"],
                    metadata={
                        "episode_title": point.payload.get("episode_title", "Unknown"),
                        "podcast_name": point.payload.get("podcast_name", "Unknown"),
                        "speaker": point.payload.get("speaker", "UNKNOWN"),
                        "timestamp": point.payload.get("timestamp", "00:00:00"),
                        "chunk_index": point.payload.get("chunk_index", 0),
                        "source_file": point.payload.get("source_file", ""),
                        "point_id": str(point.id)
                    }
                )
                temp_documents.append(doc)

            total_fetched += len(points)
            print(f"   Fetched {total_fetched} documents...", end='\r')

            if offset is None:
                # End of collection
                break

        print(f"\n✅ Fetched {total_fetched} documents total.")

        if not temp_documents:
            print("⚠️  No documents found in Qdrant. BM25 index not built.")
            return {"status": "empty", "documents_indexed": 0}
        
        # Build BM25 retriever
        print(f"Building BM25 index structure...")
        self.bm25_retriever = BM25Retriever.from_documents(temp_documents)
        self.bm25_retriever.k = HYBRID_TOP_K
        self._document_count = len(temp_documents)
        
        return {
            "status": "success",
            "documents_indexed": self._document_count
        }
    
    def add_documents(self, new_documents: List[Document]) -> None:
        """Incrementally add documents to BM25 index."""
        if not new_documents:
            return
        
        print(f"Adding {len(new_documents)} documents to BM25 index...")
        
        existing_docs = []
        if self.bm25_retriever and hasattr(self.bm25_retriever, 'docs'):
            existing_docs = self.bm25_retriever.docs
        
        all_docs = existing_docs + new_documents
        self.bm25_retriever = BM25Retriever.from_documents(all_docs)
        self.bm25_retriever.k = HYBRID_TOP_K
        self._document_count = len(all_docs)
        
        print(f"✅ BM25 index updated: now {self._document_count} documents")
    

    async def search(
        self,
        query: str,
        k: int = HYBRID_TOP_K,
        bm25_weight: Optional[float] = None,
        qdrant_weight: Optional[float] = None,
        episode_filter: Optional[str] = None
    ) -> List[Dict]:
        """Search using hybrid approach with Reciprocal Rank Fusion (RRF)."""
        if bm25_weight is None:
            bm25_weight = BM25_WEIGHT
        if qdrant_weight is None:
            qdrant_weight = QDRANT_WEIGHT
        
        # Ensure BM25 index is built if missing
        if self.bm25_retriever is None:
            await self.build_bm25_index()
        
        # BM25 Search
        bm25_results = []
        if self.bm25_retriever:
            try:
                # We fetch more results than k to ensure we have enough after filtering
                self.bm25_retriever.k = k * 2 if episode_filter else k
                bm25_docs = self.bm25_retriever.invoke(query)
                if episode_filter:
                    bm25_docs = [d for d in bm25_docs if d.metadata.get("episode_title") == episode_filter]
                bm25_results = bm25_docs[:k]
            except Exception as e:
                print(f"⚠️  BM25 search failed: {e}")
        
        # Qdrant Search with pre-filtering
        qdrant_results = []
        try:
            query_vector = await self.embeddings_service.embed_text(query)
            qdrant_results = await self.qdrant_service.search(
                query_vector=query_vector,
                limit=k,
                episode_filter=episode_filter
            )
        except Exception as e:
            print(f"⚠️  Qdrant search failed: {e}")
        
        # Merge using Reciprocal Rank Fusion (RRF)
        return self._merge_results_rrf(bm25_results, qdrant_results, k)
    
    def _merge_results_rrf(self, bm25_results, qdrant_results, k, rrf_k=60):
        """
        Merge results using Reciprocal Rank Fusion (RRF).
        Formula: score = sum(1 / (rrf_k + rank))
        """
        doc_scores = {}
        
        # Helper to get or create doc entry
        def get_doc_entry(text, metadata, source):
            if text not in doc_scores:
                doc_scores[text] = {
                    "text": text,
                    "score": 0.0,
                    "sources": [],
                    **metadata
                }
            if source not in doc_scores[text]["sources"]:
                doc_scores[text]["sources"].append(source)
            return doc_scores[text]

        # BM25 Ranks
        for rank, doc in enumerate(bm25_results):
            text = doc.page_content
            metadata = {
                "episode_title": doc.metadata.get("episode_title", "Unknown"),
                "podcast_name": doc.metadata.get("podcast_name", "Unknown"),
                "speaker": doc.metadata.get("speaker", "UNKNOWN"),
                "timestamp": doc.metadata.get("timestamp", "00:00:00"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "source_file": doc.metadata.get("source_file", "")
            }
            entry = get_doc_entry(text, metadata, "bm25")
            entry["score"] += 1.0 / (rrf_k + rank + 1)
        
        # Qdrant Ranks
        for rank, doc in enumerate(qdrant_results):
            text = doc["text"]
            metadata = {
                "episode_title": doc.get("episode_title", "Unknown"),
                "podcast_name": doc.get("podcast_name", "Unknown"),
                "speaker": doc.get("speaker", "UNKNOWN"),
                "timestamp": doc.get("timestamp", "00:00:00"),
                "chunk_index": doc.get("chunk_index", 0),
                "source_file": doc.get("source_file", "")
            }
            entry = get_doc_entry(text, metadata, "qdrant")
            entry["score"] += 1.0 / (rrf_k + rank + 1)
        
        # Sort by RRF score
        sorted_results = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:k]

    


_hybrid_retriever_service = None

def get_hybrid_retriever_service(embeddings_service=None, qdrant_service=None):
    global _hybrid_retriever_service
    if _hybrid_retriever_service is None:
        if embeddings_service is None or qdrant_service is None:
            raise ValueError("Must provide embeddings_service and qdrant_service on first call")
        _hybrid_retriever_service = HybridRetrieverService(embeddings_service, qdrant_service)
    return _hybrid_retriever_service

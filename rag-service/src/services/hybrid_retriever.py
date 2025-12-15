"""
Hybrid Retriever Service
Combines BM25 (keyword-based) and Qdrant (semantic vector) search.
FAISS removed to eliminate O(N) memory loading at startup.
"""
from typing import List, Dict, Optional
from pathlib import Path
import pickle
import json
import os
import shutil

from filelock import FileLock, Timeout
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
        
        # Ensure indexes directory exists
        INDEXES_PATH.mkdir(parents=True, exist_ok=True)
        
        # Try to load BM25 index from disk
        self._loaded_from_disk = self.load_bm25_index()
        
        print("✅ HybridRetrieverService initialized")
    
    def build_bm25_index(self, force_rebuild: bool = False) -> Dict:
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
            points, offset = self.qdrant_service.client.scroll(
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
        
        # Save to disk
        self.save_bm25_index()
        
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
        
        self.save_bm25_index()
        print(f"✅ BM25 index updated: now {self._document_count} documents")
    

    def search(
        self,
        query: str,
        k: int = HYBRID_TOP_K,
        bm25_weight: Optional[float] = None,
        qdrant_weight: Optional[float] = None,
        episode_filter: Optional[str] = None
    ) -> List[Dict]:
        """Search using hybrid approach."""
        if bm25_weight is None:
            bm25_weight = BM25_WEIGHT
        if qdrant_weight is None:
            qdrant_weight = QDRANT_WEIGHT
        
        # Normalize weights
        total_weight = bm25_weight + qdrant_weight
        bm25_weight = bm25_weight / total_weight
        qdrant_weight = qdrant_weight / total_weight
        
        # BM25 Search
        bm25_results = []
        if self.bm25_retriever:
            try:
                self.bm25_retriever.k = k
                bm25_docs = self.bm25_retriever.invoke(query)
                if episode_filter:
                    bm25_docs = [d for d in bm25_docs if d.metadata.get("episode_title") == episode_filter]
                bm25_results = bm25_docs[:k]
            except Exception as e:
                print(f"⚠️  BM25 search failed: {e}")
        
        # Qdrant Search
        qdrant_results = []
        try:
            query_vector = self.embeddings_service.embed_text(query)
            qdrant_docs = self.qdrant_service.search(
                query_vector=query_vector,
                limit=k,
                podcast_filter=None
            )
            if episode_filter:
                qdrant_docs = [d for d in qdrant_docs if d.get("episode_title") == episode_filter]
            qdrant_results = qdrant_docs[:k]
        except Exception as e:
            print(f"⚠️  Qdrant search failed: {e}")
        
        # Merge
        return self._merge_results(bm25_results, qdrant_results, bm25_weight, qdrant_weight, k)
    
    def _merge_results(self, bm25_results, qdrant_results, bm25_weight, qdrant_weight, k):
        doc_scores = {}
        
        # Rank-based scoring for BM25
        for rank, doc in enumerate(bm25_results):
            text = doc.page_content
            score = (k - rank) / k if rank < k else 0.0
            weighted_score = score * bm25_weight
            
            doc_scores[text] = {
                "text": text,
                "episode_title": doc.metadata.get("episode_title", "Unknown"),
                "podcast_name": doc.metadata.get("podcast_name", "Unknown"),
                "score": weighted_score,
                "sources": ["bm25"],
                **{k: v for k, v in doc.metadata.items() if k not in ["episode_title", "podcast_name"]}
            }
        
        # Relevance-based scoring for Qdrant
        for doc in qdrant_results:
            text = doc["text"]
            base_score = doc.get("relevance_score", 0.0)
            weighted_score = base_score * qdrant_weight
            
            if text in doc_scores:
                doc_scores[text]["score"] += weighted_score
                doc_scores[text]["sources"].append("qdrant")
            else:
                doc_scores[text] = {
                    "text": text,
                    "score": weighted_score,
                    "sources": ["qdrant"],
                    **{k: v for k, v in doc.items() if k not in ["text", "relevance_score", "score"]}
                }
        
        sorted_results = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:k]
    
    def save_bm25_index(self):
        """Save BM25 index to disk atomically using temporary file."""
        if not self.bm25_retriever:
            return
        
        print(f"Saving BM25 index to {INDEXES_PATH}...")
        
        lock_path = INDEXES_PATH / "bm25_retriever.pkl.lock"
        lock = FileLock(lock_path, timeout=10)
        
        try:
            with lock:
                bm25_path = INDEXES_PATH / "bm25_retriever.pkl"
                temp_path = INDEXES_PATH / "bm25_retriever.pkl.tmp"

                # Write to temp file
                with open(temp_path, 'wb') as f:
                    pickle.dump(self.bm25_retriever, f)
                
                # Atomic rename
                os.replace(temp_path, bm25_path)
            
            print(f"✅ BM25 index saved atomically (count: {self._document_count})")
        except Exception as e:
            print(f"⚠️  Error saving BM25 index: {e}")
            # Try to cleanup temp file
            try:
                if (INDEXES_PATH / "bm25_retriever.pkl.tmp").exists():
                    os.remove(INDEXES_PATH / "bm25_retriever.pkl.tmp")
            except:
                pass
    
    def load_bm25_index(self) -> bool:
        """Load BM25 index from disk."""
        try:
            bm25_path = INDEXES_PATH / "bm25_retriever.pkl"
            
            if not bm25_path.exists():
                return False
            
            lock_path = INDEXES_PATH / "bm25_retriever.pkl.lock"
            lock = FileLock(lock_path, timeout=10)
            
            try:
                with lock:
                    with open(bm25_path, 'rb') as f:
                        self.bm25_retriever = pickle.load(f)
                
                if hasattr(self.bm25_retriever, 'docs'):
                    self._document_count = len(self.bm25_retriever.docs)
                else:
                    self._document_count = 0
                
                print(f"✅ BM25 index loaded: {self._document_count} documents")
                return True
            except Timeout:
                print(f"⚠️  Could not acquire lock to load BM25 index")
                return False
            
        except Exception as e:
            print(f"⚠️  Error loading BM25 index: {str(e)}")
            return False


_hybrid_retriever_service = None

def get_hybrid_retriever_service(embeddings_service=None, qdrant_service=None):
    global _hybrid_retriever_service
    if _hybrid_retriever_service is None:
        if embeddings_service is None or qdrant_service is None:
            raise ValueError("Must provide embeddings_service and qdrant_service on first call")
        _hybrid_retriever_service = HybridRetrieverService(embeddings_service, qdrant_service)
    return _hybrid_retriever_service

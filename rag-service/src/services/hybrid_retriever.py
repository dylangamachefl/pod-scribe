"""
Hybrid Retriever Service
Combines BM25 (keyword-based) and Qdrant (semantic vector) search.
FAISS removed to eliminate O(N) memory loading at startup.
"""
from typing import List, Dict, Optional
from pathlib import Path
import pickle
import json

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
        """
        Initialize hybrid retriever service.
        
        Args:
            embeddings_service: Service for generating embeddings
            qdrant_service: Service for accessing Qdrant vector database
        """
        self.embeddings_service = embeddings_service
        self.qdrant_service = qdrant_service
        
        self.bm25_retriever: Optional[BM25Retriever] = None
        self.documents: List[Document] = []
        
        # Ensure indexes directory exists
        INDEXES_PATH.mkdir(parents=True, exist_ok=True)
        
        # Try to load BM25 index from disk
        self._loaded_from_disk = self.load_bm25_index()
        
        print("✅ HybridRetrieverService initialized")
    
    def build_bm25_index(self, force_rebuild: bool = False) -> Dict:
        """
        Build BM25 index from all documents in Qdrant.
        This should only be called once at startup or when explicitly rebuilding.
        
        Args:
            force_rebuild: If True, rebuild even if index exists
            
        Returns:
            Dictionary with build statistics
        """
        if self.bm25_retriever is not None and not force_rebuild:
            print("ℹ️  BM25 index already loaded, skipping rebuild")
            return {
                "status": "already_loaded",
                "documents_indexed": len(self.documents)
            }
        
        print("Building BM25 index from Qdrant...")
        
        # Get all points from Qdrant (just text and metadata, NOT vectors!)
        collection_info = self.qdrant_service.client.scroll(
            collection_name=self.qdrant_service.collection_name,
            limit=10000,  # Adjust based on your collection size
            with_payload=True,
            with_vectors=False  # ✅ Don't load vectors into memory!
        )
        
        points = collection_info[0]  # First element is the list of points
        
        if not points:
            print("⚠️  No documents found in Qdrant. BM25 index not built.")
            return {
                "status": "empty",
                "documents_indexed": 0
            }
        
        # Convert Qdrant points to LangChain Documents (text only)
        self.documents = []
        
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
            self.documents.append(doc)
        
        # Build BM25 retriever
        print(f"Building BM25 index from {len(self.documents)} documents...")
        self.bm25_retriever = BM25Retriever.from_documents(self.documents)
        self.bm25_retriever.k = HYBRID_TOP_K
        
        print(f"✅ BM25 index built successfully: {len(self.documents)} documents")
        
        # Save to disk for next startup
        self.save_bm25_index()
        
        return {
            "status": "success",
            "documents_indexed": len(self.documents)
        }
    
    def add_documents(self, new_documents: List[Document]) -> None:
        """
        Incrementally add documents to BM25 index.
        
        Args:
            new_documents: List of new documents to add
        """
        if not new_documents:
            return
        
        print(f"Adding {len(new_documents)} documents to BM25 index...")
        
        # Add to documents list
        self.documents.extend(new_documents)
        
        # Rebuild BM25 retriever with all documents
        # BM25Retriever doesn't support incremental updates, so we rebuild
        self.bm25_retriever = BM25Retriever.from_documents(self.documents)
        self.bm25_retriever.k = HYBRID_TOP_K
        
        # Save updated index
        self.save_bm25_index()
        
        print(f"✅ BM25 index updated: now {len(self.documents)} documents")
    
    def search(
        self,
        query: str,
        k: int = HYBRID_TOP_K,
        bm25_weight: Optional[float] = None,
        qdrant_weight: Optional[float] = None,
        episode_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search using hybrid approach: BM25 (keyword) + Qdrant (semantic).
        
        Args:
            query: Search query
            k: Number of results to return
            bm25_weight: Override BM25 weight (default from config)
            qdrant_weight: Override Qdrant weight (default from config)
            episode_filter: Optional filter by episode title
            
        Returns:
            List of retrieved chunks with metadata
        """
        if bm25_weight is None:
            bm25_weight = BM25_WEIGHT
        if qdrant_weight is None:
            qdrant_weight = QDRANT_WEIGHT
        
        # Ensure weights sum to 1.0
        total_weight = bm25_weight + qdrant_weight
        bm25_weight = bm25_weight / total_weight
        qdrant_weight = qdrant_weight / total_weight
        
        # Get BM25 results (keyword-based)
        bm25_results = []
        if self.bm25_retriever:
            try:
                self.bm25_retriever.k = k
                bm25_docs = self.bm25_retriever.invoke(query)
                
                # Filter by episode if specified
                if episode_filter:
                    bm25_docs = [
                        doc for doc in bm25_docs
                        if doc.metadata.get("episode_title") == episode_filter
                    ]
                
                bm25_results = bm25_docs[:k]
            except Exception as e:
                print(f"⚠️  BM25 search failed: {e}")
        
        # Get Qdrant results (semantic vector search)
        qdrant_results = []
        try:
            # Generate query embedding
            query_vector = self.embeddings_service.embed_text(query)
            
            # Search Qdrant directly (no local copy needed!)
            qdrant_docs = self.qdrant_service.search(
                query_vector=query_vector,
                limit=k,
                podcast_filter=None  # We'll filter after merging
            )
            
            # Filter by episode if specified
            if episode_filter:
                qdrant_docs = [
                    doc for doc in qdrant_docs
                    if doc.get("episode_title") == episode_filter
                ]
            
            qdrant_results = qdrant_docs[:k]
        except Exception as e:
            print(f"⚠️  Qdrant search failed: {e}")
        
        # Merge results with weighted scoring
        merged_results = self._merge_results(
            bm25_results=bm25_results,
            qdrant_results=qdrant_results,
            bm25_weight=bm25_weight,
            qdrant_weight=qdrant_weight,
            k=k
        )
        
        return merged_results
    
    def _merge_results(
        self,
        bm25_results: List[Document],
        qdrant_results: List[Dict],
        bm25_weight: float,
        qdrant_weight: float,
        k: int
    ) -> List[Dict]:
        """
        Merge and rank results from BM25 and Qdrant searches.
        
        Uses weighted scoring: higher rank = higher score.
        """
        # Track scores by document text (deduplication)
        doc_scores: Dict[str, Dict] = {}
        
        # Process BM25 results (rank-based scoring)
        for rank, doc in enumerate(bm25_results):
            text = doc.page_content
            # Rank-based score: first result gets 1.0, second gets 0.9, etc.
            score = (k - rank) / k if rank < k else 0.0
            weighted_score = score * bm25_weight
            
            doc_scores[text] = {
                "text": text,
                "episode_title": doc.metadata.get("episode_title", "Unknown"),
                "podcast_name": doc.metadata.get("podcast_name", "Unknown"),
                "speaker": doc.metadata.get("speaker", "UNKNOWN"),
                "timestamp": doc.metadata.get("timestamp", "00:00:00"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "source_file": doc.metadata.get("source_file", ""),
                "score": weighted_score,
                "sources": ["bm25"]
            }
        
        # Process Qdrant results (relevance-based scoring)
        for rank, doc in enumerate(qdrant_results):
            text = doc["text"]
            # Qdrant provides relevance_score (cosine similarity)
            # Normalize to 0-1 range and apply weight
            base_score = doc.get("relevance_score", 0.0)
            weighted_score = base_score * qdrant_weight
            
            if text in doc_scores:
                # Document found in both: combine scores
                doc_scores[text]["score"] += weighted_score
                doc_scores[text]["sources"].append("qdrant")
            else:
                # Only in Qdrant results
                doc_scores[text] = {
                    "text": text,
                    "episode_title": doc.get("episode_title", "Unknown"),
                    "podcast_name": doc.get("podcast_name", "Unknown"),
                    "speaker": doc.get("speaker", "UNKNOWN"),
                    "timestamp": doc.get("timestamp", "00:00:00"),
                    "chunk_index": doc.get("chunk_index", 0),
                    "source_file": doc.get("source_file", ""),
                    "score": weighted_score,
                    "sources": ["qdrant"]
                }
        
        # Sort by combined score and return top k
        sorted_results = sorted(
            doc_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        return sorted_results[:k]
    
    def save_bm25_index(self):
        """Save BM25 index to disk for fast startup."""
        if not self.bm25_retriever:
            print("⚠️  No BM25 index to save")
            return
        
        print(f"Saving BM25 index to {INDEXES_PATH}...")
        
        # Save BM25 retriever
        bm25_path = INDEXES_PATH / "bm25_retriever.pkl"
        with open(bm25_path, 'wb') as f:
            pickle.dump(self.bm25_retriever, f)
        
        # Save documents metadata
        docs_metadata_path = INDEXES_PATH / "documents_metadata.json"
        metadata = [
            {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in self.documents
        ]
        with open(docs_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ BM25 index saved successfully")
    
    def load_bm25_index(self) -> bool:
        """
        Load BM25 index from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            bm25_path = INDEXES_PATH / "bm25_retriever.pkl"
            docs_metadata_path = INDEXES_PATH / "documents_metadata.json"
            
            if not (bm25_path.exists() and docs_metadata_path.exists()):
                print("ℹ️  No saved BM25 index found, will build on first search or explicit rebuild")
                return False
            
            print(f"Loading BM25 index from {INDEXES_PATH}...")
            
            # Load BM25 retriever
            with open(bm25_path, 'rb') as f:
                self.bm25_retriever = pickle.load(f)
            
            # Load documents metadata
            with open(docs_metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                self.documents = [
                    Document(page_content=item["content"], metadata=item["metadata"])
                    for item in metadata
                ]
            
            print(f"✅ BM25 index loaded: {len(self.documents)} documents")
            return True
            
        except Exception as e:
            print(f"⚠️  Error loading BM25 index: {str(e)}")
            print("   Will rebuild index from Qdrant on next search")
            return False


# Singleton instance
_hybrid_retriever_service = None


def get_hybrid_retriever_service(embeddings_service=None, qdrant_service=None):
    """Get or create the hybrid retriever service singleton."""
    global _hybrid_retriever_service
    if _hybrid_retriever_service is None:
        if embeddings_service is None or qdrant_service is None:
            raise ValueError("Must provide embeddings_service and qdrant_service on first call")
        _hybrid_retriever_service = HybridRetrieverService(embeddings_service, qdrant_service)
    return _hybrid_retriever_service

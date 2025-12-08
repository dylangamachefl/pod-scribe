"""
Hybrid Retriever Service
Combines BM25 (keyword-based) and FAISS (semantic vector) search using EnsembleRetriever.
"""
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pickle
import json

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_classic.retrievers.ensemble import EnsembleRetriever

from config import (
    BM25_WEIGHT,
    FAISS_WEIGHT,
    HYBRID_TOP_K,
    INDEXES_PATH,
    EMBEDDING_DIMENSION
)


class HybridRetrieverService:
    """Service for hybrid search combining BM25 and FAISS."""
    
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
        self.faiss_retriever: Optional[FAISS] = None
        self.ensemble_retriever: Optional[EnsembleRetriever] = None
        
        self.documents: List[Document] = []
        
        # Ensure indexes directory exists
        INDEXES_PATH.mkdir(parents=True, exist_ok=True)
        
        print("✅ HybridRetrieverService initialized")
    
    def build_indexes(self) -> Dict:
        """
        Build BM25 and FAISS indexes from all documents in Qdrant.
        
        Returns:
            Dictionary with build statistics
        """
        print("Building hybrid search indexes...")
        
        # Get all points from Qdrant
        collection_info = self.qdrant_service.client.scroll(
            collection_name=self.qdrant_service.collection_name,
            limit=10000,  # Adjust based on your collection size
            with_payload=True,
            with_vectors=True
        )
        
        points = collection_info[0]  # First element is the list of points
        
        if not points:
            print("⚠️  No documents found in Qdrant. Indexes not built.")
            return {
                "status": "empty",
                "documents_indexed": 0
            }
        
        # Convert Qdrant points to LangChain Documents
        self.documents = []
        embeddings_list = []
        
        for point in points:
            # Create document with text content and metadata
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
            embeddings_list.append(point.vector)
        
        # Build BM25 retriever
        print(f"Building BM25 index from {len(self.documents)} documents...")
        self.bm25_retriever = BM25Retriever.from_documents(self.documents)
        self.bm25_retriever.k = HYBRID_TOP_K
        
        # Build FAISS retriever
        print(f"Building FAISS index from {len(self.documents)} documents...")
        
        # Create custom embeddings wrapper for FAISS
        embeddings_wrapper = FAISSEmbeddingsWrapper(
            self.embeddings_service,
            precomputed_embeddings=embeddings_list,
            documents=self.documents
        )
        
        self.faiss_retriever = FAISS.from_documents(
            self.documents,
            embeddings_wrapper
        )
        
        # Create ensemble retriever
        print("Creating ensemble retriever...")
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.faiss_retriever.as_retriever(search_kwargs={"k": HYBRID_TOP_K})],
            weights=[BM25_WEIGHT, FAISS_WEIGHT]
        )
        
        print(f"✅ Hybrid indexes built successfully: {len(self.documents)} documents")
        
        return {
            "status": "success",
            "documents_indexed": len(self.documents),
            "bm25_weight": BM25_WEIGHT,
            "faiss_weight": FAISS_WEIGHT
        }
    
    def search(
        self,
        query: str,
        k: int = HYBRID_TOP_K,
        bm25_weight: Optional[float] = None,
        faiss_weight: Optional[float] = None,
        episode_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search using hybrid retriever (BM25 + FAISS).
        
        Args:
            query: Search query
            k: Number of results to return
            bm25_weight: Override BM25 weight (default from config)
            faiss_weight: Override FAISS weight (default from config)
            episode_filter: Optional filter by episode title
            
        Returns:
            List of retrieved chunks with metadata
        """
        if not self.ensemble_retriever:
            raise ValueError("Indexes not built. Call build_indexes() first.")
        
        # Update weights if provided
        if bm25_weight is not None and faiss_weight is not None:
            self.ensemble_retriever.weights = [bm25_weight, faiss_weight]
        
        # Update k for retrievers
        self.bm25_retriever.k = k
        
        # Perform retrieval
        results = self.ensemble_retriever.get_relevant_documents(query)
        
        # Filter by episode if specified
        if episode_filter:
            results = [
                doc for doc in results
                if doc.metadata.get("episode_title") == episode_filter
            ]
        
        # Format results
        formatted_results = []
        for doc in results[:k]:  # Ensure we don't exceed k results
            formatted_results.append({
                "text": doc.page_content,
                "episode_title": doc.metadata.get("episode_title", "Unknown"),
                "podcast_name": doc.metadata.get("podcast_name", "Unknown"),
                "speaker": doc.metadata.get("speaker", "UNKNOWN"),
                "timestamp": doc.metadata.get("timestamp", "00:00:00"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "source_file": doc.metadata.get("source_file", "")
            })
        
        return formatted_results
    
    def save_indexes(self):
        """Save BM25 and FAISS indexes to disk."""
        print(f"Saving indexes to {INDEXES_PATH}...")
        
        # Save BM25 retriever
        bm25_path = INDEXES_PATH / "bm25_retriever.pkl"
        with open(bm25_path, 'wb') as f:
            pickle.dump(self.bm25_retriever, f)
        
        # Save FAISS index
        faiss_path = INDEXES_PATH / "faiss_index"
        self.faiss_retriever.save_local(str(faiss_path))
        
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
        
        print(f"✅ Indexes saved successfully")
    
    def load_indexes(self) -> bool:
        """
        Load BM25 and FAISS indexes from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            print(f"Loading indexes from {INDEXES_PATH}...")
            
            # Check if index files exist
            bm25_path = INDEXES_PATH / "bm25_retriever.pkl"
            faiss_path = INDEXES_PATH / "faiss_index"
            docs_metadata_path = INDEXES_PATH / "documents_metadata.json"
            
            if not (bm25_path.exists() and faiss_path.exists() and docs_metadata_path.exists()):
                print("⚠️  Index files not found. Need to build indexes first.")
                return False
            
            # Load BM25 retriever
            with open(bm25_path, 'rb') as f:
                self.bm25_retriever = pickle.load(f)
            
            # Load FAISS index
            embeddings_wrapper = FAISSEmbeddingsWrapper(self.embeddings_service)
            self.faiss_retriever = FAISS.load_local(
                str(faiss_path),
                embeddings_wrapper,
                allow_dangerous_deserialization=True  # We trust our own saved indexes
            )
            
            # Load documents metadata
            with open(docs_metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                self.documents = [
                    Document(page_content=item["content"], metadata=item["metadata"])
                    for item in metadata
                ]
            
            # Create ensemble retriever
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, self.faiss_retriever.as_retriever(search_kwargs={"k": HYBRID_TOP_K})],
                weights=[BM25_WEIGHT, FAISS_WEIGHT]
            )
            
            print(f"✅ Indexes loaded successfully: {len(self.documents)} documents")
            return True
            
        except Exception as e:
            print(f"❌ Error loading indexes: {str(e)}")
            return False


class FAISSEmbeddingsWrapper:
    """
    Wrapper for embeddings service to work with FAISS.
    Supports using precomputed embeddings during initial index build.
    """
    
    def __init__(self, embeddings_service, precomputed_embeddings=None, documents=None):
        self.embeddings_service = embeddings_service
        self.precomputed_embeddings = precomputed_embeddings
        self.documents = documents
        self._embedding_cache = {}
        
        # Cache precomputed embeddings by document content
        if precomputed_embeddings and documents:
            for doc, emb in zip(documents, precomputed_embeddings):
                self._embedding_cache[doc.page_content] = emb
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        embeddings = []
        for text in texts:
            # Check cache first
            if text in self._embedding_cache:
                embeddings.append(self._embedding_cache[text])
            else:
                # Generate new embedding
                emb = self.embeddings_service.embed_text(text)
                self._embedding_cache[text] = emb
                embeddings.append(emb)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a query string."""
        return self.embeddings_service.embed_text(text)


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

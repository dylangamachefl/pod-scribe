"""
Qdrant Vector Database Client
Handles all interactions with the Qdrant vector database.
"""
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest
)
from datetime import datetime
import uuid

from config import QDRANT_URL, QDRANT_COLLECTION_NAME, EMBEDDING_DIMENSION, TOP_K_RESULTS


class QdrantService:
    """Service for vector database operations."""
    
    def __init__(self):
        """Initialize Qdrant client and ensure collection exists."""
        print(f"Connecting to Qdrant at {QDRANT_URL}")
        self.client = QdrantClient(url=QDRANT_URL)
        self.collection_name = QDRANT_COLLECTION_NAME
        
        self._ensure_collection_exists()
        print(f"✅ Qdrant connected: collection '{self.collection_name}'")
    
    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]
        
        if self.collection_name not in collection_names:
            print(f"Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=Distance.COSINE  # Cosine similarity for semantic search
                )
            )
    
    def insert_chunks(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        metadata: Dict
    ) -> int:
        """
        Insert text chunks with embeddings into Qdrant.
        
        Args:
            chunks: List of text chunks with metadata
            embeddings: Corresponding embedding vectors
            metadata: Podcast/episode metadata
            
        Returns:
            Number of chunks inserted
        """
        points = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            
            payload = {
                # Chunk content
                "text": chunk["text"],
                "chunk_index": i,
                
                # Episode metadata
                "episode_id": metadata.get("episode_id", "unknown"),  # For idempotency checks
                "episode_title": metadata.get("episode_title", "Unknown"),
                "podcast_name": metadata.get("podcast_name", "Unknown"),
                "speaker": chunk.get("speaker", "UNKNOWN"),
                "timestamp": chunk.get("timestamp", "00:00:00"),
                
                # Indexing metadata
                "created_at": datetime.now().isoformat(),
                "source_file": metadata.get("source_file", "")
            }
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            )
        
        # Batch insert
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return len(points)
    
    def search(
        self,
        query_vector: List[float],
        limit: int = TOP_K_RESULTS,
        podcast_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for similar chunks using vector similarity.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            podcast_filter: Optional filter by podcast name
            
        Returns:
            List of matching chunks with metadata and scores
        """
        # Build filter if podcast specified
        search_filter = None
        if podcast_filter:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="podcast_name",
                        match=MatchValue(value=podcast_filter)
                    )
                ]
            )
        
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=search_filter
        ).points
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "text": result.payload["text"],
                "episode_title": result.payload["episode_title"],
                "podcast_name": result.payload["podcast_name"],
                "speaker": result.payload["speaker"],
                "timestamp": result.payload["timestamp"],
                "relevance_score": float(result.score),
                "chunk_index": result.payload.get("chunk_index", 0)
            })
        
        return formatted_results
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the collection."""
        collection_info = self.client.get_collection(self.collection_name)
        return {
            "total_points": collection_info.points_count,
            "collection_name": self.collection_name,
            "vector_dimension": EMBEDDING_DIMENSION
        }
    
    def delete_episode(self, episode_title: str):
        """Delete all chunks for a specific episode."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="episode_title",
                        match=MatchValue(value=episode_title)
                    )
                ]
            )
        )


# Singleton instance
_qdrant_service = None

def get_qdrant_service() -> QdrantService:
    """Get or create the Qdrant service singleton."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service

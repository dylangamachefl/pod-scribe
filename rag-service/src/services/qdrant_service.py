"""
Qdrant Vector Database Client (Async)
Handles all interactions with the Qdrant vector database using async client.
"""
from typing import List, Dict, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)
from datetime import datetime
import uuid

from config import QDRANT_URL, QDRANT_COLLECTION_NAME, EMBEDDING_DIMENSION, TOP_K_RESULTS
from podcast_transcriber_shared.logging_config import get_logger

logger = get_logger(__name__)


class QdrantService:
    """Service for vector database operations with async support."""
    
    def __init__(self):
        """Initialize async Qdrant client."""
        logger.info("connecting_to_qdrant", url=QDRANT_URL, collection=QDRANT_COLLECTION_NAME)
        self.client = AsyncQdrantClient(url=QDRANT_URL)
        self.collection_name = QDRANT_COLLECTION_NAME
        self._initialized = False
    
    async def initialize(self):
        """Ensure collection exists. Call this before using the service."""
        if not self._initialized:
            await self._ensure_collection_exists()
            self._initialized = True
            logger.info("qdrant_initialized", collection=self.collection_name)
    
    async def _ensure_collection_exists(self):
        """Create collection if it doesn't exist."""
        collections = await self.client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if self.collection_name not in collection_names:
            logger.info("creating_qdrant_collection", collection=self.collection_name)
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=Distance.COSINE  # Cosine similarity for semantic search
                )
            )
    
    async def insert_chunks(
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
        await self.initialize()
        
        points = []
        
        # Define a namespace for RAG chunks
        CHUNK_NAMESPACE = uuid.UUID('f0000000-0000-0000-0000-000000000000')
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            episode_id = metadata.get("episode_id", "unknown")
            # Create a deterministic UUID based on episode_id and chunk_index
            point_id = str(uuid.uuid5(CHUNK_NAMESPACE, f"{episode_id}_{i}"))
            
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
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return len(points)
    
    async def search(
        self,
        query_vector: List[float],
        limit: int = TOP_K_RESULTS,
        podcast_filter: Optional[str] = None,
        episode_filter: Optional[str] = None,
        episode_id_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for similar chunks using vector similarity with optional filters.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            podcast_filter: Optional filter by podcast name
            episode_filter: Optional filter by episode title
            episode_id_filter: Optional filter by episode ID
            
        Returns:
            List of matching chunks with metadata and scores
        """
        await self.initialize()
        
        # Build filter conditions
        must_conditions = []
        
        if podcast_filter:
            must_conditions.append(
                FieldCondition(
                    key="podcast_name",
                    match=MatchValue(value=podcast_filter)
                )
            )
            
        if episode_filter:
            must_conditions.append(
                FieldCondition(
                    key="episode_title",
                    match=MatchValue(value=episode_filter)
                )
            )
            
        if episode_id_filter:
            must_conditions.append(
                FieldCondition(
                    key="episode_id",
                    match=MatchValue(value=episode_id_filter)
                )
            )
        
        search_filter = Filter(must=must_conditions) if must_conditions else None
        
        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=search_filter
        )
        
        # Format results
        formatted_results = []
        for result in results.points:
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
    
    async def get_collection_stats(self) -> Dict:
        """Get statistics about the collection."""
        await self.initialize()
        
        collection_info = await self.client.get_collection(self.collection_name)
        return {
            "total_points": collection_info.points_count,
            "collection_name": self.collection_name,
            "vector_dimension": EMBEDDING_DIMENSION
        }
    
    async def delete_episode(self, episode_title: str):
        """Delete all chunks for a specific episode."""
        await self.initialize()
        
        await self.client.delete(
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
    
    async def scroll(self, scroll_filter: Filter, limit: int = 1):
        """
        Scroll through points with a filter.
        Used for idempotency checks.
        """
        await self.initialize()
        
        results = await self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=scroll_filter,
            limit=limit
        )
        return results


# Singleton instance
_qdrant_service = None

def get_qdrant_service() -> QdrantService:
    """Get or create the Qdrant service singleton."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service

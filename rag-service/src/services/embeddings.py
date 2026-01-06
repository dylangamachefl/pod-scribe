"""
Service for generating embeddings from text using Ollama with async support and retry logic.
"""
import asyncio
import httpx
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import OLLAMA_API_URL, OLLAMA_EMBED_MODEL, EMBEDDING_DIMENSION
from podcast_transcriber_shared.gpu_lock import get_gpu_lock
from podcast_transcriber_shared.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating embeddings from text using Ollama with async support."""
    
    def __init__(self):
        """Initialize the Ollama embedding service."""
        from config import OLLAMA_TIMEOUT
        self.api_url = OLLAMA_API_URL
        self.model_name = OLLAMA_EMBED_MODEL
        self.timeout = OLLAMA_TIMEOUT
        self._client = None
        
        logger.info("embedding_service_initialized", 
                   model=self.model_name, 
                   dimension=EMBEDDING_DIMENSION,
                   timeout=self.timeout)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single text."""
        embeddings = await self.embed_batch([text])
        return embeddings[0] if embeddings else []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout, httpx.ConnectError)),
        reraise=True
    )
    async def _embed_batch_chunk(self, batch: List[str], batch_num: int) -> List[List[float]]:
        """
        Generate embeddings for a single batch chunk with automatic retry logic.
        Uses tenacity for exponential backoff on failures.
        """
        client = await self._get_client()
        
        logger.info("requesting_embeddings", 
                   batch_num=batch_num, 
                   batch_size=len(batch))
        
        async with get_gpu_lock().acquire():
            response = await client.post(
                f"{self.api_url}/api/embed",
                json={
                    "model": self.model_name,
                    "input": batch
                }
            )
        
        response.raise_for_status()
        result = response.json()
        embeddings = result.get("embeddings", [])
        
        logger.info("embeddings_generated", 
                   batch_num=batch_num, 
                   embedding_count=len(embeddings))
        
        return embeddings
    
    async def embed_batch(self, texts: List[str], chunk_size: int = 16) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        Splits large batches into smaller chunks for Ollama stability.
        Uses tenacity for automatic retry with exponential backoff.
        """
        if not texts:
            return []
        
        all_embeddings = []
        
        # Process in chunks to avoid overwhelming the Ollama worker
        for i in range(0, len(texts), chunk_size):
            batch = texts[i:i + chunk_size]
            batch_num = i//chunk_size + 1
            
            try:
                embeddings = await self._embed_batch_chunk(batch, batch_num)
                all_embeddings.extend(embeddings)
            except Exception as e:
                logger.error("embedding_batch_failed", 
                           batch_num=batch_num,
                           batch_size=len(batch),
                           error=str(e),
                           exc_info=True)
                raise RuntimeError(f"Failed to generate embeddings for batch {batch_num} after retries: {e}")
        
        return all_embeddings
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return EMBEDDING_DIMENSION

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()


# Singleton instance
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

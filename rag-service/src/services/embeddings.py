import asyncio
import httpx
from typing import List, Optional

from config import OLLAMA_API_URL, OLLAMA_EMBED_MODEL, EMBEDDING_DIMENSION
from podcast_transcriber_shared.gpu_lock import get_gpu_lock


class EmbeddingService:
    """Service for generating embeddings from text using Ollama with async support."""
    
    def __init__(self):
        """Initialize the Ollama embedding service."""
        from config import OLLAMA_TIMEOUT
        self.api_url = OLLAMA_API_URL
        self.model_name = OLLAMA_EMBED_MODEL
        self.timeout = OLLAMA_TIMEOUT
        self._client = None
        
        print(f"✅ Embedding service configured with Ollama (Async)")
        print(f"   Model: {self.model_name}")
        print(f"   Dimension: {EMBEDDING_DIMENSION}")
        print(f"   Timeout: {self.timeout}s")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single text."""
        embeddings = await self.embed_batch([text])
        return embeddings[0] if embeddings else []
    
    async def embed_batch(self, texts: List[str], chunk_size: int = 16) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        Splits very large batches into smaller chunks for Ollama stability.
        Includes retry logic for robustness against timeouts.
        """
        if not texts:
            return []
            
        client = await self._get_client()
        all_embeddings = []
        
        # Process in chunks to avoid overwhelming the Ollama worker
        for i in range(0, len(texts), chunk_size):
            batch = texts[i:i + chunk_size]
            max_retries = 3
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    print(f"   Requesting embeddings for batch {i//chunk_size + 1} ({len(batch)} texts, attempt {retry_count + 1})...")

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
                    all_embeddings.extend(result.get("embeddings", []))
                    break # Success, move to next batch
                except (httpx.HTTPError, httpx.ReadTimeout) as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"❌ Ollama API error after {max_retries} retries: {e}")
                        raise RuntimeError(f"Failed to generate batch embeddings after retries: {e}")
                    
                    wait_time = 2 ** retry_count
                    print(f"⚠️  Timeout or error during embedding, retrying in {wait_time}s... ({e})")
                    await asyncio.sleep(wait_time)
        
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

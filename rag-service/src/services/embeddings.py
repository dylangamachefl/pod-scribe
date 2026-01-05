"""
Embedding Service using Ollama
Handles text-to-vector conversion using Ollama's nomic-embed-text model.
"""
from typing import List
import requests

from config import OLLAMA_API_URL, OLLAMA_EMBED_MODEL, EMBEDDING_DIMENSION


class EmbeddingService:
    """Service for generating embeddings from text using Ollama."""
    
    def __init__(self):
        """Initialize the Ollama embedding service."""
        self.api_url = OLLAMA_API_URL
        self.model_name = OLLAMA_EMBED_MODEL
        from config import OLLAMA_TIMEOUT
        self.timeout = OLLAMA_TIMEOUT
        print(f"✅ Embedding service configured with Ollama")
        print(f"   Model: {self.model_name}")
        print(f"   API URL: {self.api_url}")
        print(f"   Dimension: {EMBEDDING_DIMENSION}")
        print(f"   Timeout: {self.timeout}s")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for a single text using Ollama.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        embeddings = self.embed_batch([text])
        return embeddings[0] if embeddings else []
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using Ollama's /api/embed endpoint.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
            
        try:
            print(f"   Requesting embeddings for batch of {len(texts)} texts...")
            response = requests.post(
                f"{self.api_url}/api/embed",
                json={
                    "model": self.model_name,
                    "input": texts
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embeddings", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Ollama API error during batch embedding: {e}")
            raise RuntimeError(f"Failed to generate batch embeddings: {e}")
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return EMBEDDING_DIMENSION


# Singleton instance
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

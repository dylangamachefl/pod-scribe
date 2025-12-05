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
        print(f"✅ Embedding service configured with Ollama")
        print(f"   Model: {self.model_name}")
        print(f"   API URL: {self.api_url}")
        print(f"   Dimension: {EMBEDDING_DIMENSION}")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for a single text using Ollama.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = requests.post(
                f"{self.api_url}/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Ollama API error during embedding: {e}")
            raise RuntimeError(f"Failed to generate embedding: {e}")
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        total = len(texts)
        
        for idx, text in enumerate(texts):
            if idx % 10 == 0 and total > 10:
                print(f"   Embedding progress: {idx}/{total}")
            
            embedding = self.embed_text(text)
            embeddings.append(embedding)
        
        return embeddings
    
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

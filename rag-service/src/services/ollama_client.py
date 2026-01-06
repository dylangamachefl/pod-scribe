"""
Ollama API Client
Handles chat and embedding operations using Ollama models.
"""
from typing import List, Dict, Optional
import requests
import httpx
import json
import time

from config import OLLAMA_API_URL, OLLAMA_CHAT_MODEL
from podcast_transcriber_shared.gpu_lock import get_gpu_lock


class OllamaChatClient:
    """Async client for Q&A using Ollama models with hybrid search."""
    
    def __init__(self):
        """Initialize Ollama chat client."""
        self.api_url = OLLAMA_API_URL
        self.model_name = OLLAMA_CHAT_MODEL
        self._client = None
        print(f"✅ Async Ollama Chat Client configured with model: {self.model_name}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    def _build_prompt(self, question: str, retrieved_chunks: List[Dict], conversation_history: Optional[List[Dict]] = None) -> str:
        """Build the prompt for Ollama."""
        # ... (same building logic)
        history_text = ""
        if conversation_history:
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in conversation_history[-5:]
            ])
        
        context_text = ""
        for i, chunk in enumerate(retrieved_chunks):
            context_text += f"\n[Source {i+1}] {chunk['podcast_name']} - {chunk['episode_title']}\n"
            context_text += f"Speaker: {chunk['speaker']} | Timestamp: {chunk['timestamp']}\n"
            context_text += f"{chunk['text']}\n"
        
        history_section = f"CONVERSATION HISTORY:\n{history_text}\n\n" if history_text else ""
        
        return f"""You are a helpful AI assistant answering questions about podcast content.
{history_section}RETRIEVED RELEVANT EXCERPTS:
{context_text}
USER QUESTION: {question}
Please provide a comprehensive answer based on the excerpts above. Reference specific sources, speakers, and episodes when relevant. If the excerpts don't fully answer the question, acknowledge this clearly.
"""

    async def answer_with_retrieved_chunks(
        self,
        question: str,
        retrieved_chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """Answer a question using retrieved chunks asynchronously."""
        if not retrieved_chunks:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "processing_time_ms": 0,
                "context_method": "hybrid_retrieval",
                "model": self.model_name
            }
        
        prompt = self._build_prompt(question, retrieved_chunks, conversation_history)
        client = await self._get_client()
        
        try:
            start_time = time.time()

            # Acquire GPU lock for inference
            async with get_gpu_lock().acquire():
                response = await client.post(
                    f"{self.api_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }
                )

            response.raise_for_status()
            result = response.json()
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "answer": result.get("response", ""),
                "processing_time_ms": processing_time,
                "context_method": "hybrid_retrieval",
                "model": self.model_name
            }
        except Exception as e:
            print(f"❌ Ollama API error: {e}")
            return {
                "answer": f"Error: {str(e)}",
                "processing_time_ms": 0,
                "context_method": "error",
                "model": self.model_name
            }

    async def generate_answer_stream(
        self,
        question: str,
        retrieved_chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ):
        """Yield answer chunks from Ollama asynchronously."""
        if not retrieved_chunks:
            yield json.dumps({"answer": "No relevant info found."})
            return
            
        prompt = self._build_prompt(question, retrieved_chunks, conversation_history)
        client = await self._get_client()
        
        try:
            # Note: Streaming holds the lock for the duration of generation
            async with get_gpu_lock().acquire():
                async with client.stream(
                    "POST",
                    f"{self.api_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": True
                    }
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            if not chunk.get("done", False):
                                yield chunk.get("response", "")
        except Exception as e:
            print(f"❌ Ollama streaming error: {e}")
            yield f"Error: {str(e)}"


# Singleton instance
_chat_client = None

def get_ollama_chat_client() -> OllamaChatClient:
    """Get or create the Ollama chat client singleton."""
    global _chat_client
    if _chat_client is None:
        _chat_client = OllamaChatClient()
    return _chat_client

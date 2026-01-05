"""
Ollama API Client
Handles chat and embedding operations using Ollama models.
"""
from typing import List, Dict, Optional
import requests
import json
import time

from config import OLLAMA_API_URL, OLLAMA_CHAT_MODEL


class OllamaChatClient:
    """Client for Q&A using Ollama models with hybrid search."""
    
    def __init__(self):
        """Initialize Ollama chat client."""
        self.api_url = OLLAMA_API_URL
        self.model_name = OLLAMA_CHAT_MODEL
        print(f"✅ Ollama Chat Client configured with model: {self.model_name}")
        print(f"   API URL: {self.api_url}")
    
    def _build_prompt(self, question: str, retrieved_chunks: List[Dict], conversation_history: Optional[List[Dict]] = None) -> str:
        """Build the prompt for Ollama."""
        # Build conversation context if provided
        history_text = ""
        if conversation_history:
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in conversation_history[-5:]  # Last 5 messages
            ])
        
        # Format retrieved chunks
        context_text = ""
        for i, chunk in enumerate(retrieved_chunks):
            context_text += f"\n[Source {i+1}] {chunk['podcast_name']} - {chunk['episode_title']}\n"
            context_text += f"Speaker: {chunk['speaker']} | Timestamp: {chunk['timestamp']}\n"
            context_text += f"{chunk['text']}\n"
        
        # Build prompt with optional conversation history
        if history_text:
            history_section = f"CONVERSATION HISTORY:\n{history_text}\n\n"
        else:
            history_section = ""
        
        return f"""You are a helpful AI assistant answering questions about podcast content.
{history_section}RETRIEVED RELEVANT EXCERPTS:
{context_text}
USER QUESTION: {question}
Please provide a comprehensive answer based on the excerpts above. Reference specific sources, speakers, and episodes when relevant. If the excerpts don't fully answer the question, acknowledge this clearly.
"""

    def answer_with_retrieved_chunks(
        self,
        question: str,
        retrieved_chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Answer a question using retrieved chunks from hybrid search.
        
        Args:
            question: User's question
            retrieved_chunks: List of relevant chunks from hybrid retrieval
            conversation_history: Optional previous messages for context
            
        Returns:
            Dict with answer and metadata
        """
        if not retrieved_chunks:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "processing_time_ms": 0,
                "context_method": "hybrid_retrieval",
                "model": self.model_name
            }
        
        prompt = self._build_prompt(question, retrieved_chunks, conversation_history)
        
        try:
            start_time = time.time()
            
            # Call Ollama API
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120
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
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Ollama API error during Q&A: {e}")
            return {
                "answer": f"I encountered an error while processing your question: {str(e)}. Please ensure Ollama is running.",
                "processing_time_ms": 0,
                "context_method": "error",
                "model": self.model_name
            }
        except Exception as e:
            print(f"❌ Unexpected error during Q&A: {e}")
            return {
                "answer": f"I encountered an unexpected error: {str(e)}",
                "processing_time_ms": 0,
                "context_method": "error",
                "model": self.model_name
            }

    def generate_answer_stream(
        self,
        question: str,
        retrieved_chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ):
        """
        Yield answer chunks from Ollama as they are generated.
        """
        if not retrieved_chunks:
            yield json.dumps({"answer": "I couldn't find any relevant information to answer your question."})
            return
            
        prompt = self._build_prompt(question, retrieved_chunks, conversation_history)
        
        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": True
                },
                stream=True,
                timeout=120
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if not chunk.get("done", False):
                        yield chunk.get("response", "")
                    else:
                        # Signal completion with potential final stats if needed
                        pass
        
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

"""
Gemini API Clients
Separate clients for summarization and Q&A tasks.
"""
from typing import List, Dict, Optional
import google.generativeai as genai
import time

from config import GEMINI_API_KEY


class GeminiSummaryClient:
    """Client for generating podcast summaries."""
    
    def __init__(self):
        """Initialize Gemini summary client."""
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        print("✅ Gemini Summary Client configured")
    
    def summarize_transcript(
        self,
        transcript_text: str,
        episode_title: str,
        podcast_name: str
    ) -> Dict:
        """
        Generate a comprehensive summary of a podcast transcript.
        
        Args:
            transcript_text: Full transcript text
            episode_title: Episode title
            podcast_name: Podcast name
            
        Returns:
            Dict with summary, key topics, and insights
        """
        prompt = f"""You are analyzing a podcast transcript. Please provide a comprehensive summary.

Podcast: {podcast_name}
Episode: {episode_title}

TRANSCRIPT:
{transcript_text[:50000]}  # Use more of the transcript for better summaries

Please provide:
1. A concise summary (2-3 paragraphs)
2. Key topics discussed (bullet points)
3. Main insights or takeaways (bullet points)
4. Notable quotes (if any)

Format your response as JSON with keys: "summary", "key_topics" (array), "insights" (array), "quotes" (array)
"""
        
        try:
            start_time = time.time()
            response = self.model.generate_content(prompt)
            processing_time = (time.time() - start_time) * 1000
            
            # Parse response (assuming JSON format)
            import json
            try:
                result = json.loads(response.text)
            except json.JSONDecodeError:
                # Fallback if model doesn't return perfect JSON
                result = {
                    "summary": response.text,
                    "key_topics": [],
                    "insights": [],
                    "quotes": []
                }
            
            result["processing_time_ms"] = processing_time
            return result
        
        except Exception as e:
            print(f"❌ Gemini API error during summarization: {e}")
            return {
                "summary": f"Error generating summary: {str(e)}",
                "key_topics": [],
                "insights": [],
                "quotes": [],
                "processing_time_ms": 0
            }


class GeminiChatClient:
    """Client for Q&A with full transcript context stuffing."""
    
    def __init__(self):
        """Initialize Gemini chat client."""
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        print("✅ Gemini Chat Client configured")
    
    def answer_with_full_transcript(
        self,
        question: str,
        transcript_text: str,
        episode_title: str,
        podcast_name: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Answer a question using full transcript context (no chunking).
        
        Args:
            question: User's question
            transcript_text: Full transcript text
            episode_title: Episode title
            podcast_name: Podcast name
            conversation_history: Optional previous messages for context
            
        Returns:
            Dict with answer and metadata
        """
        # Build conversation context if provided
        history_text = ""
        if conversation_history:
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in conversation_history[-5:]  # Last 5 messages
            ])
        
        prompt = f"""You are a helpful AI assistant answering questions about a specific podcast episode.

Podcast: {podcast_name}
Episode: {episode_title}

{f"CONVERSATION HISTORY:\n{history_text}\n" if history_text else ""}
FULL TRANSCRIPT:
{transcript_text[:100000]}  # Use as much context as possible

USER QUESTION: {question}

Please provide a comprehensive answer based on the full transcript above. Reference specific parts of the conversation, speakers, and timestamps when relevant. If the question cannot be answered from the transcript, acknowledge this clearly.
"""
        
        try:
            start_time = time.time()
            response = self.model.generate_content(prompt)
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "answer": response.text,
                "processing_time_ms": processing_time,
                "context_method": "full_transcript_stuffing"
            }
        
        except Exception as e:
            print(f"❌ Gemini API error during Q&A: {e}")
            return {
                "answer": f"I encountered an error while processing your question: {str(e)}",
                "processing_time_ms": 0,
                "context_method": "error"
            }


# Singleton instances
_summary_client = None
_chat_client = None

def get_summary_client() -> GeminiSummaryClient:
    """Get or create the Gemini summary client singleton."""
    global _summary_client
    if _summary_client is None:
        _summary_client = GeminiSummaryClient()
    return _summary_client

def get_chat_client() -> GeminiChatClient:
    """Get or create the Gemini chat client singleton."""
    global _chat_client
    if _chat_client is None:
        _chat_client = GeminiChatClient()
    return _chat_client

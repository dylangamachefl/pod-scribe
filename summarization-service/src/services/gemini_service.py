"""
Gemini API Client for Summarization
Generates comprehensive summaries using configurable Gemini models.
"""
from typing import Dict
import google.generativeai as genai
import time
import json

from config import GEMINI_API_KEY, SUMMARIZATION_MODEL


class GeminiSummarizationService:
    """Client for generating podcast summaries with Gemini."""
    
    def __init__(self):
        """Initialize Gemini summarization client with configurable model."""
        genai.configure(api_key=GEMINI_API_KEY)
        self.model_name = SUMMARIZATION_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        print(f"✅ Gemini Summarization Service configured with model: {self.model_name}")
    
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
            Dict with summary, key topics, insights, and quotes
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


# Singleton instance
_gemini_service = None

def get_gemini_service() -> GeminiSummarizationService:
    """Get or create the Gemini summarization service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiSummarizationService()
    return _gemini_service

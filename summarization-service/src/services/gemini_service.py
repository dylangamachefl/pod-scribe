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
        prompt = f"""Role: You are an expert synthesizer and content strategist. Your goal is to distill the provided podcast transcript into a clear, high-value summary that captures the essence, actionable advice, and nuance of the conversation.

Podcast: {podcast_name}
Episode: {episode_title}

TRANSCRIPT:
{transcript_text[:50000]}

Please analyze the transcript and generate a structured summary using the following format:

1. The One-Sentence Hook
   A single, compelling sentence that summarizes the core theme or "big idea" of the episode.

2. Top 3 Key Takeaways
   The three most critical insights or arguments presented.
   Format: Bold the concept, then explain it in 1-2 sentences.

3. Actionable Advice / "How-To"
   Extract specific steps, tools, tactics, or frameworks mentioned.
   Use bullet points. If no specific advice was given, summarize the practical implications of the discussion.

4. Notable Quotes
   Pull 2-3 verbatim quotes that are particularly insightful, controversial, or memorable.

5. Key Concepts & Definitions
   Briefly define any specific terms, books, mental models, or jargon introduced in the episode.

6. Summary of Perspectives
   Briefly outline the host's stance vs. the guest's stance (if applicable). Did they agree, disagree, or build upon each other?

Tone: Professional, concise, and objective. Avoid fluff.
Formatting: Use Markdown (Headers, bolding, bullet points) to make it scannable.

Format your response as JSON with keys:
- "hook" (string): The one-sentence hook
- "key_takeaways" (array of objects): Each with "concept" and "explanation"
- "actionable_advice" (array of strings): Bullet points of actionable advice
- "quotes" (array of strings): Notable verbatim quotes
- "concepts" (array of objects): Each with "term" and "definition"
- "perspectives" (string): Summary of different perspectives
- "summary" (string): A brief 2-3 paragraph overview for backward compatibility
- "key_topics" (array of strings): Main topics discussed for backward compatibility
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

"""
Gemini API Client for Two-Stage Summarization
Stage 1: Generates high-fidelity unstructured summaries
Stage 2: Extracts structured data using Instructor for guaranteed validation
"""
from typing import Dict
from pathlib import Path
import google.generativeai as genai
import instructor
import time
import yaml

from config import (
    GEMINI_API_KEY, 
    STAGE1_MODEL, 
    STAGE2_MODEL,
    STAGE1_MAX_RETRIES,
    STAGE1_BASE_DELAY,
    STAGE2_MAX_RETRIES,
    STAGE2_BASE_DELAY
)
from structured_models_v2 import RawSummary, StructuredSummaryV2


class GeminiSummarizationService:
    """Two-stage summarization client using Gemini and Instructor."""
    
    def __init__(self):
        """Initialize two-stage Gemini summarization client."""
        # Load prompts from YAML
        prompts_path = Path(__file__).parent.parent.parent / "config" / "prompts.yaml"
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                self.prompts = yaml.safe_load(f)
            print(f"✅ Loaded prompts from {prompts_path.name}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Prompts file not found: {prompts_path}. "
                "Please ensure config/prompts.yaml exists."
            )
        except yaml.YAMLError as e:
            raise RuntimeError(f"Invalid YAML in prompts file: {e}")
        
        # Configure API key
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Stage 1: Standard Gemini client for raw summarization (The Thinker)
        self.stage1_model_name = STAGE1_MODEL
        self.stage1_model = genai.GenerativeModel(self.stage1_model_name)
        self.stage1_max_retries = STAGE1_MAX_RETRIES
        self.stage1_base_delay = STAGE1_BASE_DELAY
        
        # Stage 2: Instructor-wrapped client for structure extraction (The Structurer)
        self.stage2_model_name = STAGE2_MODEL
        self.stage2_client = instructor.from_gemini(
            client=genai.GenerativeModel(self.stage2_model_name),
            mode=instructor.Mode.GEMINI_JSON
        )
        self.stage2_max_retries = STAGE2_MAX_RETRIES
        self.stage2_base_delay = STAGE2_BASE_DELAY
        
        print(f"✅ Two-Stage Summarization Service Initialized:")
        print(f"   Stage 1 (Thinker): {self.stage1_model_name}")
        print(f"   Stage 2 (Structurer): {self.stage2_model_name}")
    
    def _stage1_generate_raw_summary(
        self,
        transcript_text: str,
        episode_title: str,
        podcast_name: str
    ) -> RawSummary:
        """
        Stage 1: Generate high-fidelity unstructured summary.
        
        This stage focuses purely on comprehension and analysis without
        any JSON formatting constraints. The model can express ideas naturally
        in markdown/text format.
        
        Args:
            transcript_text: Full transcript text
            episode_title: Episode title
            podcast_name: Podcast name
            
        Returns:
            RawSummary with unstructured content
        """
        # Load prompt template and format with actual values
        prompt = self.prompts['stage1_prompt_template'].format(
            podcast_name=podcast_name,
            episode_title=episode_title,
            transcript_text=transcript_text[:50000]  # Limit to 50k chars
        )
        
        # Retry logic with exponential backoff for Stage 1
        for attempt in range(self.stage1_max_retries):
            try:
                start_time = time.time()
                response = self.stage1_model.generate_content(prompt)
                processing_time = (time.time() - start_time) * 1000
                
                print(f"✅ Stage 1 complete ({processing_time:.0f}ms)")
                
                return RawSummary(content=response.text)
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a quota error (429)
                if "429" in error_str or "quota" in error_str.lower():
                    if attempt < self.stage1_max_retries - 1:
                        delay = self.stage1_base_delay * (2 ** attempt)
                        print(f"⚠️  Stage 1 quota error. Retrying in {delay}s... (Attempt {attempt + 1}/{self.stage1_max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"❌ Stage 1 quota error persists after {self.stage1_max_retries} attempts")
                        raise
                
                # For other errors, raise immediately
                print(f"❌ Stage 1 error: {e}")
                raise
        
        # Should not reach here
        raise Exception("Stage 1: Maximum retries exceeded")
    
    def _stage2_extract_structure(
        self,
        raw_summary: RawSummary,
        episode_title: str,
        podcast_name: str
    ) -> StructuredSummaryV2:
        """
        Stage 2: Extract structured data using Instructor.
        
        Instructor wraps the Gemini API and enforces strict Pydantic validation.
        If the model outputs invalid data, Instructor automatically retries with
        the validation error, forcing the model to fix it.
        
        Args:
            raw_summary: Output from Stage 1
            episode_title: Episode title
            podcast_name: Podcast name
            
        Returns:
            StructuredSummaryV2 with validated structured fields
        """
        # Load prompt template and format with actual values
        prompt = self.prompts['stage2_prompt_template'].format(
            podcast_name=podcast_name,
            episode_title=episode_title,
            raw_summary_content=raw_summary.content
        )
        
        # Retry logic with exponential backoff for Stage 2
        for attempt in range(self.stage2_max_retries):
            try:
                start_time = time.time()
                
                # Instructor handles validation automatically
                # If Gemini returns invalid JSON, Instructor re-prompts with the error
                structured_data = self.stage2_client.chat.completions.create(
                    response_model=StructuredSummaryV2,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_retries=2  # Instructor's internal retry for validation errors
                )
                
                processing_time = (time.time() - start_time) * 1000
                print(f"✅ Stage 2 complete ({processing_time:.0f}ms)")
                
                return structured_data
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a quota error (429)
                if "429" in error_str or "quota" in error_str.lower():
                    if attempt < self.stage2_max_retries - 1:
                        delay = self.stage2_base_delay * (2 ** attempt)
                        print(f"⚠️  Stage 2 quota error. Retrying in {delay}s... (Attempt {attempt + 1}/{self.stage2_max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"❌ Stage 2 quota error persists after {self.stage2_max_retries} attempts")
                        raise
                
                # For other errors, raise immediately
                print(f"❌ Stage 2 error: {e}")
                raise
        
        # Should not reach here
        raise Exception("Stage 2: Maximum retries exceeded")
    
    def summarize_transcript(
        self,
        transcript_text: str,
        episode_title: str,
        podcast_name: str
    ) -> StructuredSummaryV2:
        """
        Orchestrate two-stage summarization pipeline.
        
        Stage 1: Generate high-fidelity unstructured summary (The Thinker)
        Stage 2: Extract validated structured data (The Structurer)
        
        Args:
            transcript_text: Full transcript text
            episode_title: Episode title
            podcast_name: Podcast name
            
        Returns:
            StructuredSummaryV2 with validated structured fields and timing metadata
        """
        total_start_time = time.time()
        
        try:
            # Stage 1: Generate raw summary (focus on quality)
            print(f"🧠 Stage 1: Generating raw summary for '{episode_title}'...")
            stage1_start = time.time()
            raw_summary = self._stage1_generate_raw_summary(
                transcript_text=transcript_text,
                episode_title=episode_title,
                podcast_name=podcast_name
            )
            stage1_time = (time.time() - stage1_start) * 1000
            
            # Stage 2: Extract structure (focus on validation)
            print(f"📋 Stage 2: Extracting structure for '{episode_title}'...")
            stage2_start = time.time()
            structured_summary = self._stage2_extract_structure(
                raw_summary=raw_summary,
                episode_title=episode_title,
                podcast_name=podcast_name
            )
            stage2_time = (time.time() - stage2_start) * 1000
            
            # Add timing metadata
            total_time = (time.time() - total_start_time) * 1000
            structured_summary.stage1_processing_time_ms = stage1_time
            structured_summary.stage2_processing_time_ms = stage2_time
            structured_summary.total_processing_time_ms = total_time
            
            print(f"✅ Two-stage pipeline complete: {total_time:.0f}ms (Stage 1: {stage1_time:.0f}ms, Stage 2: {stage2_time:.0f}ms)")
            
            return structured_summary
            
        except Exception as e:
            print(f"❌ Two-stage pipeline failed: {e}")
            raise


# Singleton instance
_gemini_service = None

def get_gemini_service() -> GeminiSummarizationService:
    """Get or create the Gemini summarization service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiSummarizationService()
    return _gemini_service

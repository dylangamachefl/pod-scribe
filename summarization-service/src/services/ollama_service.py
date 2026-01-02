"""
Ollama API Client for Two-Stage Summarization
Stage 1: Generates high-fidelity unstructured summaries
Stage 2: Extracts structured data using Instructor for guaranteed validation
"""
import instructor
import requests
from typing import Dict, List
from pathlib import Path
import time
import yaml

from config import (
    OLLAMA_API_URL,
    OLLAMA_SUMMARIZER_MODEL,
    STAGE1_MAX_RETRIES,
    STAGE1_BASE_DELAY,
    STAGE2_MAX_RETRIES,
    STAGE2_BASE_DELAY
)
from structured_models_v2 import RawSummary, StructuredSummaryV2


class OllamaClient:
    """Wrapper for Ollama API that mimics genai.GenerativeModel interface."""
    
    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name
    
    def generate_content(self, prompt: str) -> 'OllamaResponse':
        """Generate content using Ollama API."""
        response = requests.post(
            f"{self.api_url}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=300  # 5 minutes for long summarization
        )
        response.raise_for_status()
        result = response.json()
        return OllamaResponse(result.get("response", ""))


class OllamaResponse:
    """Response wrapper for Ollama API."""
    
    def __init__(self, text: str):
        self.text = text


class OllamaSummarizationService:
    """Two-stage summarization client using Ollama and Instructor."""
    
    def __init__(self):
        """Initialize two-stage Ollama summarization client."""
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
        
        # Stage 1: Ollama client for raw summarization (The Thinker)
        self.stage1_model_name = OLLAMA_SUMMARIZER_MODEL
        self.stage1_model = OllamaClient(OLLAMA_API_URL, self.stage1_model_name)
        self.stage1_max_retries = STAGE1_MAX_RETRIES
        self.stage1_base_delay = STAGE1_BASE_DELAY
        
        # Stage 2: Instructor-wrapped client for structure extraction (The Structurer)
        self.stage2_model_name = OLLAMA_SUMMARIZER_MODEL
        # Create Ollama client wrapper for Instructor
        ollama_client = OllamaClient(OLLAMA_API_URL, self.stage2_model_name)
        
        # Wrap with Instructor - using OpenAI-compatible mode
        # Instructor supports Ollama through the OpenAI-compatible API
        try:
            from openai import OpenAI
            # Create OpenAI client pointing to Ollama's OpenAI-compatible endpoint
            openai_client = OpenAI(
                base_url=f"{OLLAMA_API_URL}/v1",
                api_key="ollama"  # Ollama doesn't require a real key
            )
            self.stage2_client = instructor.from_openai(openai_client)
        except ImportError:
            raise RuntimeError(
                "OpenAI library required for Instructor integration. "
                "Install with: pip install openai"
            )
        
        self.stage2_max_retries = STAGE2_MAX_RETRIES
        self.stage2_base_delay = STAGE2_BASE_DELAY
        
        print(f"✅ Two-Stage Summarization Service Initialized:")
        print(f"   Stage 1 (Thinker): {self.stage1_model_name}")
        print(f"   Stage 2 (Structurer): {self.stage2_model_name}")
        print(f"   Ollama API: {OLLAMA_API_URL}")
    
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
                
            except requests.exceptions.RequestException as e:
                error_str = str(e)
                
                # Check if it's a connection or timeout error
                if attempt < self.stage1_max_retries - 1:
                    delay = self.stage1_base_delay * (2 ** attempt)
                    print(f"⚠️  Stage 1 Ollama error. Retrying in {delay}s... (Attempt {attempt + 1}/{self.stage1_max_retries})")
                    print(f"    Error: {error_str}")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Stage 1 Ollama error persists after {self.stage1_max_retries} attempts")
                    raise
            except Exception as e:
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
        
        Instructor wraps the Ollama API and enforces strict Pydantic validation.
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
                # If Ollama returns invalid JSON, Instructor re-prompts with the error
                # We use List[StructuredSummaryV2] to handle models that might return multiple tool calls
                structured_data_list = self.stage2_client.chat.completions.create(
                    model=self.stage2_model_name,
                    response_model=List[StructuredSummaryV2],
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_retries=2  # Instructor's internal retry for validation errors
                )
                
                if not structured_data_list:
                    raise ValueError("Stage 2: Model returned an empty list of structured data")
                
                # Take the first one (most reliable)
                structured_data = structured_data_list[0]
                
                if len(structured_data_list) > 1:
                    print(f"⚠️  Stage 2: Model returned {len(structured_data_list)} items, using the first one.")
                
                processing_time = (time.time() - start_time) * 1000
                print(f"✅ Stage 2 complete ({processing_time:.0f}ms)")
                
                return structured_data
                
            except requests.exceptions.RequestException as e:
                error_str = str(e)
                
                # Check if it's a connection or timeout error
                if attempt < self.stage2_max_retries - 1:
                    delay = self.stage2_base_delay * (2 ** attempt)
                    print(f"⚠️  Stage 2 Ollama error. Retrying in {delay}s... (Attempt {attempt + 1}/{self.stage2_max_retries})")
                    print(f"    Error: {error_str}")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Stage 2 Ollama error persists after {self.stage2_max_retries} attempts")
                    raise
            except Exception as e:
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
_ollama_service = None

def get_ollama_service() -> OllamaSummarizationService:
    """Get or create the Ollama summarization service singleton."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaSummarizationService()
    return _ollama_service

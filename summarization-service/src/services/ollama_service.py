"""
Ollama API Client for Two-Stage Summarization
Stage 1: Generates high-fidelity unstructured summaries
Stage 2: Extracts structured data using Instructor for guaranteed validation
"""
import asyncio
import httpx
import instructor
from typing import Dict, List, Optional
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
from podcast_transcriber_shared.gpu_lock import get_gpu_lock


class OllamaClient:
    """Async wrapper for Ollama API."""
    
    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=600)
        return self._client

    async def generate_content(self, prompt: str) -> 'OllamaResponse':
        """Generate content using Ollama API asynchronously."""
        client = await self._get_client()
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
        return OllamaResponse(result.get("response", ""))


class OllamaResponse:
    """Response wrapper for Ollama API."""
    
    def __init__(self, text: str):
        self.text = text


class OllamaSummarizationService:
    """Two-stage async summarization client using Ollama and Instructor."""
    
    def __init__(self):
        """Initialize two-stage Ollama summarization client."""
        # Load prompts from YAML
        prompts_path = Path(__file__).parent.parent.parent / "config" / "prompts.yaml"
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                self.prompts = yaml.safe_load(f)
            print(f"✅ Loaded prompts from {prompts_path.name}")
        except Exception as e:
            raise RuntimeError(f"Failed to load prompts: {e}")
        
        # Stage 1: Ollama client for raw summarization
        self.stage1_model_name = OLLAMA_SUMMARIZER_MODEL
        self.stage1_model = OllamaClient(OLLAMA_API_URL, self.stage1_model_name)
        self.stage1_max_retries = STAGE1_MAX_RETRIES
        self.stage1_base_delay = STAGE1_BASE_DELAY
        
        # Stage 2: Instructor-wrapped client
        self.stage2_model_name = OLLAMA_SUMMARIZER_MODEL
        try:
            from openai import AsyncOpenAI
            openai_client = AsyncOpenAI(
                base_url=f"{OLLAMA_API_URL}/v1",
                api_key="ollama"
            )
            self.stage2_client = instructor.from_openai(openai_client)
        except ImportError:
            raise RuntimeError("AsyncOpenAI library required for Instructor integration.")
        
        self.stage2_max_retries = STAGE2_MAX_RETRIES
        self.stage2_base_delay = STAGE2_BASE_DELAY
        
        print(f"✅ Async Two-Stage Summarization Service Initialized")
    
    async def _stage1_generate_raw_summary(
        self,
        transcript_text: str,
        episode_title: str,
        podcast_name: str
    ) -> RawSummary:
        """Stage 1: Generate high-fidelity unstructured summary."""
        prompt = self.prompts['stage1_prompt_template'].format(
            podcast_name=podcast_name,
            episode_title=episode_title,
            transcript_text=transcript_text[:50000]
        )
        
        for attempt in range(self.stage1_max_retries):
            try:
                start_time = time.time()
                async with get_gpu_lock().acquire():
                    response = await self.stage1_model.generate_content(prompt)
                print(f"✅ Stage 1 complete ({(time.time() - start_time)*1000:.0f}ms)")
                return RawSummary(content=response.text)
                
            except httpx.HTTPError as e:
                if attempt < self.stage1_max_retries - 1:
                    delay = self.stage1_base_delay * (2 ** attempt)
                    print(f"⚠️  Stage 1 retry {attempt + 1} in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(f"Stage 1 failed after {self.stage1_max_retries} attempts: {e}")
    
    async def _stage2_extract_structure(
        self,
        raw_summary: RawSummary,
        episode_title: str,
        podcast_name: str
    ) -> StructuredSummaryV2:
        """Stage 2: Extract structured data using Instructor."""
        prompt = self.prompts['stage2_prompt_template'].format(
            podcast_name=podcast_name,
            episode_title=episode_title,
            raw_summary_content=raw_summary.content
        )
        
        for attempt in range(self.stage2_max_retries):
            try:
                start_time = time.time()
                async with get_gpu_lock().acquire():
                    structured_data_list = await self.stage2_client.chat.completions.create(
                        model=self.stage2_model_name,
                        response_model=List[StructuredSummaryV2],
                        messages=[{"role": "user", "content": prompt}],
                        max_retries=2
                    )
                
                if not structured_data_list:
                    raise ValueError("Stage 2: Empty results")
                
                print(f"✅ Stage 2 complete ({(time.time() - start_time)*1000:.0f}ms)")
                return structured_data_list[0]
                
            except Exception as e:
                if attempt < self.stage2_max_retries - 1:
                    delay = self.stage2_base_delay * (2 ** attempt)
                    print(f"⚠️  Stage 2 retry {attempt + 1} in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(f"Stage 2 failed: {e}")
    
    async def summarize_transcript(
        self,
        transcript_text: str,
        episode_title: str,
        podcast_name: str
    ) -> StructuredSummaryV2:
        """Orchestrate two-stage summarization pipeline asynchronously."""
        total_start_time = time.time()
        
        # Stage 1: Think
        print(f"🧠 Stage 1: Processing '{episode_title}'...")
        stage1_start = time.time()
        raw_summary = await self._stage1_generate_raw_summary(
            transcript_text, episode_title, podcast_name
        )
        stage1_time = (time.time() - stage1_start) * 1000
        
        # Stage 2: Structure
        print(f"📋 Stage 2: Structuring '{episode_title}'...")
        stage2_start = time.time()
        structured_summary = await self._stage2_extract_structure(
            raw_summary, episode_title, podcast_name
        )
        stage2_time = (time.time() - stage2_start) * 1000
        
        # Metadata
        total_time = (time.time() - total_start_time) * 1000
        structured_summary.stage1_processing_time_ms = stage1_time
        structured_summary.stage2_processing_time_ms = stage2_time
        structured_summary.total_processing_time_ms = total_time
        
        print(f"✅ Summarization complete: {total_time:.0f}ms")
        return structured_summary


# Singleton instance
_ollama_service = None

def get_ollama_service() -> OllamaSummarizationService:
    """Get or create the Ollama summarization service singleton."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaSummarizationService()
    return _ollama_service

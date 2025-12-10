"""
Two-Stage Summarization Models
Stage 1: Raw summary output (unstructured)
Stage 2: Structured extraction (Instructor-validated)
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class RawSummary(BaseModel):
    """
    Stage 1 output: Unstructured, high-fidelity summary.
    This is markdown/text without JSON constraints.
    """
    content: str = Field(
        ..., 
        description="Comprehensive summary in markdown format with all key information"
    )


class KeyTakeaway(BaseModel):
    """A key takeaway with concept and explanation."""
    concept: str = Field(..., description="Bold concept name")
    explanation: str = Field(..., description="1-2 sentence explanation")


class Concept(BaseModel):
    """A concept or term with its definition."""
    term: str = Field(..., description="The term or concept")
    definition: str = Field(..., description="Brief definition")


class StructuredSummaryV2(BaseModel):
    """
    Stage 2 output: Structured summary extracted via Instructor.
    This represents the UI contract that the frontend expects.
    Instructor will enforce validation and retry if the model output doesn't match.
    """
    hook: str = Field(
        ..., 
        description="A punchy, compelling single sentence capturing the core theme"
    )
    key_takeaways: List[KeyTakeaway] = Field(
        ..., 
        min_length=3,
        max_length=5,
        description="Top 3-5 critical insights with concept and explanation"
    )
    actionable_advice: List[str] = Field(
        ..., 
        min_length=3,
        description="Specific steps, tools, tactics, or frameworks mentioned"
    )
    quotes: List[str] = Field(
        ..., 
        min_length=2,
        max_length=5,
        description="2-5 verbatim memorable quotes from the episode"
    )
    concepts: List[Concept] = Field(
        default_factory=list, 
        description="Terms, books, mental models with definitions"
    )
    perspectives: str = Field(
        ..., 
        description="Summary of how host and guest interacted (agreement, debate, etc.)"
    )
    summary: str = Field(
        ..., 
        min_length=200,
        description="A comprehensive 2-3 paragraph overview of the entire episode"
    )
    key_topics: List[str] = Field(
        ..., 
        min_length=3,
        description="Main topics discussed in the episode"
    )
    
    # Metadata
    stage1_processing_time_ms: Optional[float] = Field(
        None,
        description="Processing time for Stage 1 (raw summarization)"
    )
    stage2_processing_time_ms: Optional[float] = Field(
        None,
        description="Processing time for Stage 2 (structure extraction)"
    )
    total_processing_time_ms: Optional[float] = Field(
        None,
        description="Total processing time for both stages"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "hook": "Effective communication hinges on authenticity, connection, and mindful presence.",
                "key_takeaways": [
                    {
                        "concept": "Avoid Memorization, Embrace Structure",
                        "explanation": "Memorizing speeches burdens cognitive load. Use a roadmap instead."
                    },
                    {
                        "concept": "Lead with Questions",
                        "explanation": "Questions draw out the other person and create genuine dialogue."
                    },
                    {
                        "concept": "Reframe Anxiety as Excitement",
                        "explanation": "Both emotions are physiologically similar; reframing reduces stress."
                    }
                ],
                "actionable_advice": [
                    "Lead with questions to draw out the other person",
                    "Use the phrase 'tell me more' to encourage deeper conversation",
                    "Practice reframing anxiety as excitement before speaking"
                ],
                "quotes": [
                    "The magic of communication happens in the moment and not what's happening in your head before.",
                    "Dare to be dull. Give yourself permission to not be perfect."
                ],
                "concepts": [
                    {
                        "term": "Cognitive Load",
                        "definition": "The amount of working memory resources required to process information."
                    }
                ],
                "perspectives": "Both agreed on the importance of presence over performance in communication.",
                "summary": "This episode features communication expert Matt Abrahams discussing strategies for clear, confident speaking. He emphasizes the importance of being present rather than perfect, and provides actionable frameworks for reducing anxiety and improving spontaneous communication.",
                "key_topics": ["Public speaking", "Authenticity", "Communication strategies", "Anxiety management"]
            }
        }

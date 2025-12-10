"""
Pydantic models for structured summaries from Gemini API.
These models match the JSON structure Gemini returns based on our prompt.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class KeyTakeaway(BaseModel):
    """A key takeaway with concept and explanation."""
    concept: str = Field(..., description="Bold concept name")
    explanation: str = Field(..., description="1-2 sentence explanation")


class Concept(BaseModel):
    """A concept or term with its definition."""
    term: str = Field(..., description="The term or concept")
    definition: str = Field(..., description="Brief definition")


class StructuredSummary(BaseModel):
    """
    Structured summary matching Gemini's prompt output.
    This represents the rich, formatted content that Gemini generates.
    """
    hook: str = Field(..., description="One-sentence hook summarizing the episode")
    key_takeaways: List[KeyTakeaway] = Field(
        default_factory=list, 
        description="Top 3 critical insights with concept and explanation"
    )
    actionable_advice: List[str] = Field(
        default_factory=list, 
        description="Specific steps, tools, tactics, or frameworks"
    )
    quotes: List[str] = Field(
        default_factory=list, 
        description="2-3 verbatim memorable quotes from the episode"
    )
    concepts: List[Concept] = Field(
        default_factory=list, 
        description="Terms, books, mental models with definitions"
    )
    perspectives: str = Field(
        ..., 
        description="Summary of different viewpoints (host vs guest)"
    )
    summary: str = Field(
        ..., 
        description="2-3 paragraph overview for backward compatibility"
    )
    key_topics: List[str] = Field(
        default_factory=list, 
        description="Main topics discussed for backward compatibility"
    )
    
    # Optional metadata that may be added during processing
    processing_time_ms: Optional[float] = Field(
        None, 
        description="Time taken to generate the summary"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "hook": "Effective communication hinges on authenticity, connection, and mindful presence.",
                "key_takeaways": [
                    {
                        "concept": "Avoid Memorization, Embrace Structure",
                        "explanation": "Memorizing speeches burdens cognitive load. Use a roadmap instead."
                    }
                ],
                "actionable_advice": [
                    "Lead with questions to draw out the other person",
                    "Use the phrase 'tell me more' to encourage deeper conversation"
                ],
                "quotes": [
                    "The magic of communication happens in the moment and not what's happening in your head before."
                ],
                "concepts": [
                    {
                        "term": "Cognitive Load",
                        "definition": "The amount of working memory resources required to process information."
                    }
                ],
                "perspectives": "Both agreed on the importance of presence over performance.",
                "summary": "This episode features communication expert Matt Abrahams...",
                "key_topics": ["Public speaking", "Authenticity", "Communication strategies"]
            }
        }

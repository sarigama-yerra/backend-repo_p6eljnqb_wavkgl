"""
Database Schemas for Potongin.com

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl

class User(BaseModel):
    name: str
    email: str
    preferences: dict = Field(default_factory=lambda: {
        "text_size": "md",
        "high_contrast": False,
        "language": "auto"
    })

class Video(BaseModel):
    source_url: HttpUrl = Field(..., description="Original YouTube URL")
    title: Optional[str] = None
    channel: Optional[str] = None
    duration: Optional[float] = Field(None, description="Duration in seconds")
    thumbnail: Optional[str] = None
    languages: List[str] = Field(default_factory=list)

class TranscriptSegment(BaseModel):
    video_id: str
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    sentence_index: Optional[int] = None

class Clip(BaseModel):
    video_id: str
    user_id: Optional[str] = None
    start: float
    end: float
    title: Optional[str] = None
    transcript_snippet: Optional[str] = None
    export_status: str = Field("draft", description="draft, rendering, ready, failed")
    share_url: Optional[str] = None

class ClipBook(BaseModel):
    user_id: str
    title: str
    clip_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

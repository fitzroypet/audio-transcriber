from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum


class TranscriptionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionConfig(BaseModel):
    """Configuration for transcription processing."""
    enable_word_timestamps: str = "auto"  # auto, true, false
    word_timestamp_max_duration: int = 30  # minutes
    audio_chunk_length_minutes: int = 10
    chunk_overlap_seconds: int = 5


class TranscriptionRequest(BaseModel):
    filename: str
    file_size: int


class TranscriptionResponse(BaseModel):
    job_id: str
    status: TranscriptionStatus
    message: str


class TranscriptionStatusResponse(BaseModel):
    job_id: str
    status: TranscriptionStatus
    progress: Optional[float] = None
    error_message: Optional[str] = None
    transcription: Optional[Dict[str, Any]] = None


class TranscriptionResult(BaseModel):
    text: str
    segments: List[Dict[str, Any]]
    language: Optional[str] = None
    duration: Optional[float] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

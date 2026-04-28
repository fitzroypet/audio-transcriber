import asyncio
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class LiveTranscriptionSession:
    def __init__(self, transcriber, language_mode: str = 'en'):
        self.transcriber = transcriber
        self.language: Optional[str] = 'en' if language_mode == 'en' else None
        self.accumulated_segments: List[Dict] = []
        self.offset_seconds: float = 0.0

    async def handle_audio_chunk(self, data: bytes) -> List[Dict]:
        loop = asyncio.get_event_loop()
        segments, chunk_duration = await loop.run_in_executor(
            None,
            self.transcriber.transcribe_chunk,
            data,
            self.offset_seconds,
            self.language,
        )
        self.accumulated_segments.extend(segments)
        self.offset_seconds += chunk_duration
        return segments

    def get_full_text(self) -> str:
        return ' '.join(s['text'] for s in self.accumulated_segments if s.get('text'))

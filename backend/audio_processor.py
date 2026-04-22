import os
import uuid
import subprocess
import tempfile
import shutil
from typing import Optional, Tuple, List
import logging

try:
    from pydub import AudioSegment
    from pydub.utils import which
    PYDUB_AVAILABLE = True
except ImportError as e:
    logging.warning(f"pydub not available: {e}. Audio processing will be limited.")
    PYDUB_AVAILABLE = False
    AudioSegment = None
    which = None

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self, upload_dir: str = "uploads", max_size_mb: int = 500):
        self.upload_dir = upload_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.supported_formats = {
            '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma'
        }
        
        # Check if pydub is available
        if not PYDUB_AVAILABLE:
            logger.warning("pydub not available. Audio processing will be limited.")
        
        # Ensure ffmpeg is available (required for chunking)
        if not self._check_ffmpeg():
            raise RuntimeError("ffmpeg is required but not found. Please install ffmpeg.")
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_audio_duration(self, file_path: str) -> float:
        """Get audio duration in seconds without loading into memory."""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "csv=p=0", file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Error getting audio duration for {file_path}: {str(e)}")
            return 0.0
    
    def split_audio_into_chunks(
        self, 
        file_path: str, 
        chunk_length_minutes: int = 10, 
        overlap_seconds: int = 5
    ) -> List[Tuple[str, float, float]]:
        """
        Split audio file into chunks using ffmpeg.
        
        Returns:
            List of tuples: (chunk_file_path, start_time, end_time)
        """
        duration = self.get_audio_duration(file_path)
        if duration <= 0:
            raise ValueError(f"Could not determine duration of {file_path}")
        
        chunk_length_seconds = chunk_length_minutes * 60
        chunks = []
        
        # Create temporary directory for chunks
        temp_dir = tempfile.mkdtemp(prefix="audio_chunks_")
        
        start_time = 0
        chunk_index = 0
        
        while start_time < duration:
            end_time = min(start_time + chunk_length_seconds, duration)
            
            # Create chunk filename
            chunk_filename = f"chunk_{chunk_index:04d}.wav"
            chunk_path = os.path.join(temp_dir, chunk_filename)
            
            # Extract chunk using ffmpeg, transcoding to PCM WAV for Whisper compatibility
            cmd = [
                "ffmpeg", "-i", file_path,
                "-ss", str(start_time),
                "-t", str(end_time - start_time),
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                chunk_path
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                chunks.append((chunk_path, start_time, end_time))
                logger.info(f"Created chunk {chunk_index}: {start_time:.1f}s - {end_time:.1f}s")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error creating chunk {chunk_index}: {str(e)}")
                # Clean up partial chunks
                for chunk_path, _, _ in chunks:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise
            
            if end_time >= duration:
                break

            # Move to the next chunk while guaranteeing forward progress.
            next_start = end_time - overlap_seconds
            if next_start <= start_time:
                next_start = end_time

            start_time = next_start
            chunk_index += 1
        
        logger.info(f"Split audio into {len(chunks)} chunks")
        return chunks
    
    def cleanup_chunks(self, chunk_paths: List[str]):
        """Clean up temporary chunk files."""
        for chunk_path in chunk_paths:
            try:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup chunk {chunk_path}: {str(e)}")
        
        # Try to remove the temp directory
        try:
            temp_dir = os.path.dirname(chunk_paths[0]) if chunk_paths else None
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")
    
    def validate_file(self, filename: str, file_size: Optional[int]) -> Tuple[bool, Optional[str]]:
        """Validate uploaded audio file."""
        # Check file extension
        ext = os.path.splitext(filename.lower())[1]
        if ext not in self.supported_formats:
            return False, f"Unsupported format: {ext}. Supported formats: {', '.join(self.supported_formats)}"

        # Check file size (file_size may be None when Content-Length is not forwarded by proxy)
        if file_size is not None and file_size > self.max_size_bytes:
            return False, f"File too large. Maximum size: {self.max_size_bytes // (1024*1024)}MB"

        return True, None
    
    def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """Save uploaded file and return the file path."""
        # Generate unique filename to avoid conflicts
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        safe_filename = f"{file_id}{ext}"
        
        file_path = os.path.join(self.upload_dir, safe_filename)
        
        # Ensure upload directory exists
        os.makedirs(self.upload_dir, exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return file_path
    
    async def save_uploaded_file_streaming(self, file) -> str:
        """Save uploaded file using streaming to avoid loading into memory."""
        # Generate unique filename to avoid conflicts
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        safe_filename = f"{file_id}{ext}"
        
        file_path = os.path.join(self.upload_dir, safe_filename)
        
        # Ensure upload directory exists
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # Stream file content to disk
        with open(file_path, "wb") as f:
            while chunk := await file.read(8192):  # Read in 8KB chunks
                f.write(chunk)
        
        return file_path
    
    def convert_to_wav(self, input_path: str, output_path: Optional[str] = None) -> str:
        """Convert audio file to WAV format for Whisper processing."""
        if not PYDUB_AVAILABLE:
            # If pydub is not available, just return the original file
            # Whisper can handle most formats directly
            logger.warning("pydub not available, using original file format")
            return input_path
            
        if output_path is None:
            output_path = input_path.rsplit('.', 1)[0] + '.wav'
        
        try:
            # Load audio file
            audio = AudioSegment.from_file(input_path)
            
            # Convert to WAV format (16kHz, mono for better Whisper performance)
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Export as WAV
            audio.export(output_path, format="wav")
            
            logger.info(f"Converted {input_path} to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error converting audio file {input_path}: {str(e)}")
            # Fallback: return original file if conversion fails
            logger.warning("Conversion failed, using original file")
            return input_path
    
    def get_audio_info(self, file_path: str) -> dict:
        """Get basic information about the audio file."""
        if not PYDUB_AVAILABLE:
            return {
                "duration": None,
                "channels": None,
                "frame_rate": None,
                "sample_width": None,
                "note": "Audio info not available without pydub"
            }
            
        try:
            audio = AudioSegment.from_file(file_path)
            return {
                "duration": len(audio) / 1000.0,  # Duration in seconds
                "channels": audio.channels,
                "frame_rate": audio.frame_rate,
                "sample_width": audio.sample_width
            }
        except Exception as e:
            logger.error(f"Error getting audio info for {file_path}: {str(e)}")
            return {
                "duration": None,
                "channels": None,
                "frame_rate": None,
                "sample_width": None,
                "error": str(e)
            }
    
    def cleanup_file(self, file_path: str) -> None:
        """Remove temporary file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {str(e)}")

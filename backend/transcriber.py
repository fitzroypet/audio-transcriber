import os
import json
import uuid
import threading
import shutil
from typing import Dict, Any, Optional, List, Tuple
from faster_whisper import WhisperModel
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TranscriptionJob:
    def __init__(
        self,
        job_id: str,
        file_path: str,
        model_name: str = "base",
        config: Optional[Dict] = None,
        cleanup_paths: Optional[List[str]] = None
    ):
        self.job_id = job_id
        self.file_path = file_path
        self.model_name = model_name
        self.config = config or {}
        self.cleanup_paths = cleanup_paths or []
        self.status = "pending"
        self.progress = 0.0
        self.error_message = None
        self.result = None
        self.created_at = datetime.now()
        self.completed_at = None
        self.chunks = []  # For chunked processing
        self.chunk_results = []  # Store results from each chunk
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class WhisperTranscriber:
    def __init__(self, model_name: str = "base", results_dir: str = "results", config: Optional[Dict] = None):
        self.model_name = model_name
        self.results_dir = results_dir
        self.config = config or {}
        self.model = None
        self.jobs: Dict[str, TranscriptionJob] = {}
        self._model_lock = threading.Lock()
        
        # Ensure results directory exists
        os.makedirs(results_dir, exist_ok=True)
    
    def load_model(self):
        """Load the Whisper model (lazy loading)."""
        if self.model is not None:
            return

        with self._model_lock:
            if self.model is None:
                logger.info(f"Loading Whisper model: {self.model_name}")
                self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
                logger.info("Whisper model loaded successfully")
    
    def start_transcription(
        self,
        file_path: str,
        config: Optional[Dict] = None,
        cleanup_paths: Optional[List[str]] = None
    ) -> str:
        """Start a new transcription job and return job ID."""
        job_id = str(uuid.uuid4())
        job_config = {**self.config, **(config or {})}
        job = TranscriptionJob(
            job_id,
            file_path,
            self.model_name,
            job_config,
            cleanup_paths=cleanup_paths
        )
        self.jobs[job_id] = job
        
        # Run the Whisper work in a background thread so /upload can respond immediately.
        worker = threading.Thread(
            target=self._transcribe_job,
            args=(job_id,),
            daemon=True
        )
        worker.start()
        
        return job_id
    
    def _transcribe_job(self, job_id: str):
        """Run transcription work in a background thread."""
        job = self.jobs[job_id]
        
        try:
            job.status = "processing"
            job.progress = 0.1
            
            # Load model if not already loaded
            self.load_model()
            job.progress = 0.2
            
            # Check if we need to use chunked processing
            from .audio_processor import AudioProcessor
            audio_processor = AudioProcessor()
            duration = audio_processor.get_audio_duration(job.file_path)

            if duration <= 0:
                raise ValueError(
                    "Could not read audio data from the file. "
                    "The file may be corrupted or in an unsupported encoding."
                )

            # Determine if we should use word timestamps
            use_word_timestamps = self._should_use_word_timestamps(duration, job.config)
            
            if self._should_use_chunking(duration, job.config):
                logger.info(f"Using chunked processing for {duration:.1f}s audio file")
                result = self._transcribe_chunked(job, use_word_timestamps)
            else:
                logger.info(f"Using standard processing for {duration:.1f}s audio file")
                transcribe_kwargs = dict(
                    word_timestamps=use_word_timestamps,
                    temperature=job.config.get("temperature", 0),
                    beam_size=job.config.get("beam_size", 5),
                )
                if job.config.get("language"):
                    transcribe_kwargs["language"] = job.config["language"]
                segments, info = self.model.transcribe(job.file_path, **transcribe_kwargs)
                result = self._fw_to_dict(segments, info)
            
            job.progress = 0.9
            
            # Process and store result
            processed_result = self._process_transcription_result(result)
            job.result = processed_result
            job.status = "completed"
            job.progress = 1.0
            job.completed_at = datetime.now()
            
            # Save result to file
            self._save_result(job_id, processed_result)
            
            logger.info(f"Transcription completed for job {job_id}")
            
        except Exception as e:
            logger.error(f"Transcription failed for job {job_id}: {str(e)}")
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now()
        finally:
            for cleanup_path in set(job.cleanup_paths):
                if cleanup_path and os.path.exists(cleanup_path):
                    try:
                        os.remove(cleanup_path)
                    except OSError as e:
                        logger.warning(f"Failed to cleanup file {cleanup_path}: {str(e)}")
    
    def _fw_to_dict(self, segments_gen, info) -> Dict[str, Any]:
        """Convert faster-whisper (generator, info) output to the openai-whisper dict shape."""
        segments, text_parts = [], []
        for seg in segments_gen:
            text_parts.append(seg.text)
            seg_dict = {"start": seg.start, "end": seg.end, "text": seg.text}
            if seg.words:
                seg_dict["words"] = [
                    {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                    for w in seg.words
                ]
            segments.append(seg_dict)
        return {"text": "".join(text_parts), "language": info.language, "segments": segments}

    def _should_use_word_timestamps(self, duration: float, config: Dict) -> bool:
        """Determine if word timestamps should be used based on duration and config."""
        enable_word_timestamps = config.get("enable_word_timestamps", "auto")
        
        if enable_word_timestamps == "true":
            return True
        elif enable_word_timestamps == "false":
            return False
        else:  # auto
            max_duration = config.get("word_timestamp_max_duration", 30) * 60  # Convert to seconds
            return duration <= max_duration
    
    def _should_use_chunking(self, duration: float, config: Dict) -> bool:
        """Determine if chunking should be used based on duration and config."""
        chunk_length = config.get("audio_chunk_length_minutes", 10) * 60  # Convert to seconds
        # Use chunking if file is longer than chunk length
        return duration > chunk_length
    
    def _transcribe_chunked(self, job: TranscriptionJob, use_word_timestamps: bool) -> Dict[str, Any]:
        """Transcribe audio file in chunks and merge results."""
        from .audio_processor import AudioProcessor
        
        audio_processor = AudioProcessor()
        chunk_length = job.config.get("audio_chunk_length_minutes", 10)
        overlap = job.config.get("chunk_overlap_seconds", 5)
        
        # Split audio into chunks
        chunks = audio_processor.split_audio_into_chunks(
            job.file_path, 
            chunk_length, 
            overlap
        )
        
        job.chunks = chunks
        total_chunks = len(chunks)
        chunk_results = []
        
        try:
            # Process each chunk
            for i, (chunk_path, start_time, end_time) in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{total_chunks}: {start_time:.1f}s - {end_time:.1f}s")
                
                # Update progress
                job.progress = 0.2 + (0.6 * i / total_chunks)
                
                # Transcribe chunk
                transcribe_kwargs = dict(
                    word_timestamps=use_word_timestamps,
                    temperature=job.config.get("temperature", 0),
                    beam_size=job.config.get("beam_size", 5),
                )
                if job.config.get("language"):
                    transcribe_kwargs["language"] = job.config["language"]
                segments, info = self.model.transcribe(chunk_path, **transcribe_kwargs)
                chunk_result = self._fw_to_dict(segments, info)
                
                # Store chunk result with timing info
                chunk_results.append({
                    "chunk_index": i,
                    "start_time": start_time,
                    "end_time": end_time,
                    "result": chunk_result
                })
                
                # Clean up chunk file immediately
                try:
                    os.remove(chunk_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup chunk {chunk_path}: {str(e)}")
            
            # Clean up temp directory
            if chunks:
                temp_dir = os.path.dirname(chunks[0][0])
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Merge chunk results
            merged_result = self._merge_chunk_results(chunk_results, overlap)
            return merged_result
            
        except Exception as e:
            # Clean up any remaining chunks
            audio_processor.cleanup_chunks([chunk_path for chunk_path, _, _ in chunks])
            raise e
    
    def _merge_chunk_results(self, chunk_results: List[Dict], overlap_seconds: int) -> Dict[str, Any]:
        """Merge transcription results from multiple chunks."""
        if not chunk_results:
            return {"text": "", "language": "unknown", "segments": []}
        
        # Sort by chunk index
        chunk_results.sort(key=lambda x: x["chunk_index"])
        
        merged_text = ""
        merged_segments = []
        merged_words = []
        
        for i, chunk_data in enumerate(chunk_results):
            chunk_result = chunk_data["result"]
            chunk_start = chunk_data["start_time"]
            
            # Add text
            chunk_text = chunk_result["text"].strip()
            if i > 0 and chunk_text:
                # Add space between chunks
                merged_text += " " + chunk_text
            else:
                merged_text += chunk_text
            
            # Process segments
            if "segments" in chunk_result:
                for segment in chunk_result["segments"]:
                    # Adjust timestamps
                    adjusted_segment = {
                        "start": segment["start"] + chunk_start,
                        "end": segment["end"] + chunk_start,
                        "text": segment["text"].strip()
                    }
                    
                    # Add word timestamps if available
                    if "words" in segment:
                        adjusted_words = []
                        for word in segment["words"]:
                            adjusted_words.append({
                                "word": word["word"],
                                "start": word["start"] + chunk_start,
                                "end": word["end"] + chunk_start,
                                "probability": word.get("probability", 0.0)
                            })
                        adjusted_segment["words"] = adjusted_words
                    
                    merged_segments.append(adjusted_segment)
        
        # Handle overlap regions by removing duplicate text
        merged_segments = self._remove_overlap_duplicates(merged_segments, overlap_seconds)
        
        return {
            "text": merged_text.strip(),
            "language": chunk_results[0]["result"].get("language", "unknown"),
            "segments": merged_segments
        }
    
    def _remove_overlap_duplicates(self, segments: List[Dict], overlap_seconds: int) -> List[Dict]:
        """Remove duplicate text in overlap regions between segments."""
        if len(segments) <= 1:
            return segments
        
        cleaned_segments = []
        
        for i, segment in enumerate(segments):
            if i == 0:
                cleaned_segments.append(segment)
                continue
            
            prev_segment = cleaned_segments[-1]
            
            # Check if there's overlap
            if segment["start"] < prev_segment["end"]:
                # Calculate overlap duration
                overlap_duration = prev_segment["end"] - segment["start"]
                
                # If overlap is significant, trim the beginning of current segment
                if overlap_duration > 0.5:  # More than 0.5 seconds overlap
                    # Find where to start the current segment
                    trim_start = prev_segment["end"] - (overlap_seconds / 2)
                    segment["start"] = max(segment["start"], trim_start)
                    
                    # Trim text if needed (rough approximation)
                    if "words" in segment:
                        # Remove words that fall in the overlap region
                        segment["words"] = [
                            word for word in segment["words"] 
                            if word["start"] >= segment["start"]
                        ]
            
            cleaned_segments.append(segment)
        
        return cleaned_segments
    
    def _process_transcription_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process Whisper result into our standard format."""
        processed = {
            "text": result["text"].strip(),
            "language": result.get("language", "unknown"),
            "duration": None,
            "segments": []
        }
        
        # Calculate total duration from segments
        if result.get("segments"):
            processed["duration"] = result["segments"][-1]["end"]
            
            for segment in result["segments"]:
                processed_segment = {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "words": []
                }
                
                # Add word-level timestamps if available
                if "words" in segment:
                    for word in segment["words"]:
                        processed_segment["words"].append({
                            "word": word["word"],
                            "start": word["start"],
                            "end": word["end"],
                            "probability": word.get("probability", 0.0)
                        })
                
                processed["segments"].append(processed_segment)
        
        return processed
    
    def _save_result(self, job_id: str, result: Dict[str, Any]):
        """Save transcription result to file."""
        result_file = os.path.join(self.results_dir, f"{job_id}.json")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a transcription job."""
        job = self.jobs.get(job_id)
        if job is None:
            return None
        
        return job.to_dict()
    
    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the transcription result for a completed job."""
        job = self.jobs.get(job_id)
        if job is None or job.status != "completed":
            return None
        
        return job.result
    
    def cleanup_job(self, job_id: str):
        """Clean up job data after download."""
        if job_id in self.jobs:
            del self.jobs[job_id]

        # Remove result file
        result_file = os.path.join(self.results_dir, f"{job_id}.json")
        if os.path.exists(result_file):
            os.remove(result_file)

    def transcribe_chunk(
        self,
        audio_bytes: bytes,
        offset_seconds: float = 0.0,
        language: Optional[str] = None
    ) -> tuple:
        """Transcribe a raw audio chunk (from live recording) synchronously.

        Returns (segments, chunk_duration) where segments have timestamps
        adjusted by offset_seconds.
        """
        import tempfile
        self.load_model()

        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            temperature = 0.0 if language == 'en' else 0.2
            kwargs = dict(
                word_timestamps=False,
                temperature=temperature,
                beam_size=5,
            )
            if language:
                kwargs['language'] = language

            segments_gen, info = self.model.transcribe(tmp_path, **kwargs)
            segments = []
            for seg in segments_gen:
                text = seg.text.strip()
                if text:
                    segments.append({
                        'start': round(seg.start + offset_seconds, 2),
                        'end': round(seg.end + offset_seconds, 2),
                        'text': text,
                    })
            return segments, info.duration
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

import os
import json
import logging
from typing import Optional
from fastapi import FastAPI, File, Query, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .models import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionStatusResponse,
    TranscriptionStatus,
    ErrorResponse
)
from .audio_processor import AudioProcessor
from .transcriber import WhisperTranscriber
from .exporters import ExportManager
from .websocket_handler import LiveTranscriptionSession
from .gdrive import extract_file_id, download_gdrive_file

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Audio Transcriber API",
    description="Web-based audio transcription using OpenAI Whisper",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
RESULTS_DIR = os.getenv("RESULTS_DIR", "results")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "500"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Initialize components
audio_processor = AudioProcessor(
    upload_dir=UPLOAD_DIR,
    max_size_mb=MAX_FILE_SIZE_MB
)

transcriber = WhisperTranscriber(
    model_name=WHISPER_MODEL,
    results_dir=RESULTS_DIR
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web interface."""
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Audio Transcriber</h1><p>Frontend files not found. Please ensure frontend/index.html exists.</p>")


@app.post("/upload", response_model=TranscriptionResponse)
async def upload_file(
    file: UploadFile = File(...),
    language_mode: str = Query("en"),
):
    """Upload an audio file and start transcription."""
    try:
        logger.info(f"Upload request: filename={file.filename!r}, size={file.size}, content_type={file.content_type}")
        # Validate file
        is_valid, error_msg = audio_processor.validate_file(file.filename, file.size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Stream file to disk instead of loading into memory
        file_path = await audio_processor.save_uploaded_file_streaming(file)

        # Convert to WAV if needed
        wav_path = audio_processor.convert_to_wav(file_path)

        # English-only mode: deterministic decode, no language confusion.
        # Auto mode: slight temperature for multilingual flexibility.
        if language_mode == "en":
            language = "en"
            temperature = 0.0
        else:
            language = None  # Whisper auto-detects
            temperature = 0.2

        # Get configuration for transcription
        config = {
            "enable_word_timestamps": os.getenv("ENABLE_WORD_TIMESTAMPS", "auto"),
            "word_timestamp_max_duration": int(os.getenv("WORD_TIMESTAMP_MAX_DURATION", "30")),
            "audio_chunk_length_minutes": int(os.getenv("AUDIO_CHUNK_LENGTH_MINUTES", "10")),
            "chunk_overlap_seconds": int(os.getenv("CHUNK_OVERLAP_SECONDS", "5")),
            "language": language,
            "temperature": temperature,
            "beam_size": int(os.getenv("WHISPER_BEAM_SIZE", "5")),
        }
        
        # Start transcription with config
        cleanup_paths = [file_path]
        if wav_path != file_path:
            cleanup_paths.append(wav_path)

        job_id = transcriber.start_transcription(
            wav_path,
            config,
            cleanup_paths=cleanup_paths,
            original_filename=file.filename,
        )

        return TranscriptionResponse(
            job_id=job_id,
            status=TranscriptionStatus.PENDING,
            message="File uploaded and transcription started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/status/{job_id}", response_model=TranscriptionStatusResponse)
async def get_transcription_status(job_id: str):
    """Get the status of a transcription job."""
    job_status = transcriber.get_job_status(job_id)

    if job_status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return TranscriptionStatusResponse(
        job_id=job_id,
        status=job_status["status"],
        progress=job_status["progress"],
        error_message=job_status["error_message"],
        transcription=job_status["result"],
        original_filename=job_status.get("original_filename"),
    )


@app.get("/download/{job_id}")
async def download_transcription(job_id: str, format: str = "json"):
    """Download transcription result in specified format."""
    result = transcriber.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Transcription not found or not completed")

    try:
        exported_content = ExportManager.export(result, format)

        # Build filename from the original audio filename when available
        job_status = transcriber.get_job_status(job_id)
        original = (job_status or {}).get("original_filename") or ""
        stem = os.path.splitext(original)[0].strip() if original else ""
        filename = f"{stem}.{format}" if stem else f"transcription_{job_id}.{format}"
        
        # For large files, use streaming response
        if len(exported_content) > 10 * 1024 * 1024:  # 10MB threshold
            from fastapi.responses import StreamingResponse
            import io
            
            # Create a streaming response
            def generate():
                yield exported_content
            
            return StreamingResponse(
                io.BytesIO(exported_content.encode('utf-8') if isinstance(exported_content, str) else exported_content),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            # For smaller files, use temporary file approach
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=f'.{format}', delete=False, encoding='utf-8')
            temp_file.write(exported_content)
            temp_file.close()
            
            # Schedule cleanup of temp file
            import atexit
            atexit.register(lambda: os.unlink(temp_file.name) if os.path.exists(temp_file.name) else None)
            
            # Return as downloadable file
            return FileResponse(
                path=temp_file.name,
                filename=filename,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Download failed")


@app.post("/transcribe-gdrive", response_model=TranscriptionResponse)
async def transcribe_gdrive(
    gdrive_url: str = Query(..., description="Google Drive sharing URL"),
    language_mode: str = Query("en"),
):
    """Download a publicly-shared Google Drive audio file and start transcription."""
    file_id = extract_file_id(gdrive_url)
    if not file_id:
        raise HTTPException(
            status_code=400,
            detail="Could not recognise a Google Drive file ID in that URL. "
                   "Paste a 'drive.google.com/file/d/…' sharing link."
        )

    try:
        loop = __import__('asyncio').get_event_loop()
        file_path, original_filename = await loop.run_in_executor(
            None, download_gdrive_file, file_id, UPLOAD_DIR
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Google Drive download failed: {e}")
        raise HTTPException(status_code=422, detail=f"Download failed: {e}")

    wav_path = audio_processor.convert_to_wav(file_path)

    if language_mode == "en":
        language, temperature = "en", 0.0
    else:
        language, temperature = None, 0.2

    config = {
        "enable_word_timestamps": os.getenv("ENABLE_WORD_TIMESTAMPS", "auto"),
        "word_timestamp_max_duration": int(os.getenv("WORD_TIMESTAMP_MAX_DURATION", "30")),
        "audio_chunk_length_minutes": int(os.getenv("AUDIO_CHUNK_LENGTH_MINUTES", "10")),
        "chunk_overlap_seconds": int(os.getenv("CHUNK_OVERLAP_SECONDS", "5")),
        "language": language,
        "temperature": temperature,
        "beam_size": int(os.getenv("WHISPER_BEAM_SIZE", "5")),
    }

    cleanup_paths = [file_path]
    if wav_path != file_path:
        cleanup_paths.append(wav_path)

    job_id = transcriber.start_transcription(
        wav_path,
        config,
        cleanup_paths=cleanup_paths,
        original_filename=original_filename,
    )

    return TranscriptionResponse(
        job_id=job_id,
        status=TranscriptionStatus.PENDING,
        message=f"Downloading and transcribing: {original_filename}",
    )


@app.get("/formats")
async def get_supported_formats():
    """Get list of supported export formats."""
    return {
        "export_formats": ExportManager.get_supported_formats(),
        "audio_formats": list(audio_processor.supported_formats),
        "max_file_size_mb": MAX_FILE_SIZE_MB
    }


@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket, language_mode: str = "en"):
    """Live transcription via WebSocket.

    Protocol:
      - Client sends binary frames (complete audio blobs, ~5s each from MediaRecorder).
      - Server responds with JSON: {"segments": [...], "is_final": false, "full_text": "..."}
      - Client sends JSON {"type": "done"} when recording stops.
      - Server responds with JSON: {"is_final": true, "full_text": "...", "segments": [...]}
    """
    await websocket.accept()
    session = LiveTranscriptionSession(transcriber, language_mode)
    logger.info(f"Live transcription session started (language_mode={language_mode})")

    try:
        while True:
            msg = await websocket.receive()
            if msg.get('bytes'):
                segments = await session.handle_audio_chunk(msg['bytes'])
                await websocket.send_json({
                    "segments": segments,
                    "is_final": False,
                    "full_text": session.get_full_text(),
                })
            elif msg.get('text'):
                data = json.loads(msg['text'])
                if data.get('type') == 'done':
                    await websocket.send_json({
                        "is_final": True,
                        "full_text": session.get_full_text(),
                        "segments": session.accumulated_segments,
                    })
                    await websocket.close()
                    break
    except WebSocketDisconnect:
        logger.info("Live transcription WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e), "is_final": True})
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    timeout = int(os.getenv("UVICORN_TIMEOUT", "0"))
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        timeout_keep_alive=timeout if timeout > 0 else None,
        timeout_graceful_shutdown=30
    )

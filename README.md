# Audio Transcriber Application

A web-based audio transcription application using OpenAI Whisper for local, private transcription of audio files.

## Features

- Support for multiple audio formats (MP3, WAV, M4A, AAC, OGG, FLAC, WMA)
- **Handles audio files of any duration** (1+ hours supported via intelligent chunking)
- **Configurable word-level timestamps** (auto-disabled for long files to save memory)
- **Memory-efficient processing** using audio chunking and streaming uploads
- Multiple export formats (TXT, JSON, SRT)
- Real-time transcription progress
- Modern web interface with drag-and-drop upload
- **Configurable chunking settings** for optimal performance

## Setup

### Option 1: Quick Start (if no dependency conflicts)
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install ffmpeg (required for audio processing):
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

3. Run the application:
```bash
python run.py
```

4. Open your browser to `http://127.0.0.1:8000`

### Option 2: Virtual Environment (Recommended)
If you encounter dependency conflicts:

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install ffmpeg (see above)

4. Run the application:
```bash
python run.py
```

**Note for Python 3.13 users**: You may see warnings about `pydub` not being fully available due to the removal of the `audioop` module in Python 3.13. The application will still work, but audio format conversion will be limited. Whisper can handle most audio formats directly, so this shouldn't affect functionality significantly.

For detailed setup instructions, see [SETUP.md](SETUP.md).

## Configuration

The application supports various configuration options via environment variables. Copy `env.example` to `.env` and modify as needed:

```bash
cp env.example .env
```

### Key Configuration Options

- **`ENABLE_WORD_TIMESTAMPS`**: Control word-level timestamps (`auto`, `true`, `false`)
  - `auto`: Automatically disable for files longer than `WORD_TIMESTAMP_MAX_DURATION`
  - `true`: Always include word timestamps (uses more memory)
  - `false`: Never include word timestamps (saves memory)

- **`WORD_TIMESTAMP_MAX_DURATION`**: Maximum duration in minutes to use word timestamps (default: 30)

- **`AUDIO_CHUNK_LENGTH_MINUTES`**: Length of audio chunks for long files (default: 10)

- **`CHUNK_OVERLAP_SECONDS`**: Overlap between chunks to prevent word cutoff (default: 5)

- **`MAX_FILE_SIZE_MB`**: Maximum file size limit (default: 500)

- **`UVICORN_TIMEOUT`**: Server timeout in seconds (0 = unlimited, default: 0)

## Apple Notes Integration

To transcribe audio from Apple Notes:

1. Open Apple Notes and select the note with your recording
2. Tap the recording → Share → Save to Files
3. Upload the saved file using the web interface
4. Download your transcription in your preferred format

## API Endpoints

- `POST /upload` - Upload audio file
- `POST /transcribe` - Start transcription job
- `GET /status/{job_id}` - Check transcription progress
- `GET /download/{job_id}` - Download transcription results

## Configuration

Edit `.env` to customize:
- Maximum file size
- Whisper model size (affects speed vs accuracy)
- Upload and results directories

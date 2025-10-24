# Audio Transcriber Setup Guide

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install ffmpeg** (required for audio processing)
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

3. **Run the Application**
   ```bash
   python run.py
   ```

4. **Open in Browser**
   Navigate to `http://127.0.0.1:8000`

## Virtual Environment (Recommended)

If you encounter dependency conflicts:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

## Apple Notes Integration

1. Open Apple Notes and find your recording
2. Tap the recording → Share → Save to Files
3. Upload the saved file using the web interface
4. Download your transcription in your preferred format

## Supported Formats

- **Audio**: MP3, WAV, M4A, AAC, OGG, FLAC, WMA
- **Export**: TXT, JSON, SRT
- **Max file size**: 500MB (configurable)

## Troubleshooting

### pydub Import Error (Python 3.13)
If you see warnings about `pydub` not being available, this is expected on Python 3.13 due to the removal of the `audioop` module. The application will still work fine:

- Audio transcription will work normally
- Whisper can handle most audio formats directly
- Only advanced audio processing features will be limited

If you need full audio processing capabilities, consider using Python 3.11 or 3.12.

### ffmpeg Required
Make sure ffmpeg is installed for full audio processing:
```bash
brew install ffmpeg  # macOS
```

### Permission Errors
Make sure the `uploads` and `results` directories are writable:
```bash
chmod 755 uploads results
```

### Port Already in Use
If port 8000 is busy, edit the `.env` file and change the PORT value.

## Configuration

Edit `.env` to customize:
- `MAX_FILE_SIZE_MB`: Maximum file size (default: 500)
- `WHISPER_MODEL`: Model size - tiny, base, small, medium, large (default: base)
- `HOST`: Server host (default: 127.0.0.1)
- `PORT`: Server port (default: 8000)

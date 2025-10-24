#!/usr/bin/env python3
"""
Audio Transcriber Application Startup Script
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import whisper
        print("✅ Core dependencies (FastAPI, Whisper) are installed")
        
        # Check pydub separately since it may have compatibility issues
        try:
            import pydub
            print("✅ pydub is available")
        except ImportError as e:
            if "pyaudioop" in str(e):
                print("⚠️  pydub has limited functionality (expected on Python 3.13)")
                print("   The application will still work, but audio processing may be limited")
            else:
                print(f"⚠️  pydub issue: {e}")
                print("   The application will still work")
        
        return True
    except ImportError as e:
        print(f"❌ Missing critical dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False

def check_ffmpeg():
    """Check if ffmpeg is installed."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✅ ffmpeg is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg is not installed")
        print("Please install ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu/Debian: sudo apt install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        return False

def setup_environment():
    """Setup environment configuration."""
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if not env_file.exists() and env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
    
    # Ensure directories exist
    Path("uploads").mkdir(exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    print("✅ Created required directories")

def main():
    """Main startup function."""
    print("🎵 Audio Transcriber Application")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    if not check_ffmpeg():
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    print("\n🚀 Starting Audio Transcriber...")
    print("The application will open in your browser at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop the server")
    
    # Open browser
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except:
        pass
    
    # Start the server
    try:
        os.chdir(Path(__file__).parent)
        
        # Get timeout configuration
        timeout = os.getenv("UVICORN_TIMEOUT", "0")
        timeout_args = []
        if timeout != "0":
            timeout_args.extend(["--timeout-keep-alive", timeout])
        
        # Use virtual environment Python
        venv_python = Path("venv/bin/python")
        if venv_python.exists():
            subprocess.run([
                str(venv_python), "-m", "uvicorn", 
                "backend.main:app", 
                "--reload", 
                "--host", "127.0.0.1", 
                "--port", "8000",
                "--timeout-graceful-shutdown", "30"
            ] + timeout_args)
        else:
            subprocess.run([
                sys.executable, "-m", "uvicorn", 
                "backend.main:app", 
                "--reload", 
                "--host", "127.0.0.1", 
                "--port", "8000",
                "--timeout-graceful-shutdown", "30"
            ] + timeout_args)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simple test script to verify the Audio Transcriber application components.
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test individual imports
        import faster_whisper
        import fastapi
        print("✅ Core dependencies imported successfully")
        
        # Test our modules
        from models import TranscriptionRequest, TranscriptionResponse
        from audio_processor import AudioProcessor
        from transcriber import WhisperTranscriber
        from exporters import ExportManager
        print("✅ All backend modules imported successfully")

        globals()['AudioProcessor'] = AudioProcessor
        globals()['ExportManager'] = ExportManager
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_audio_processor():
    """Test AudioProcessor functionality."""
    print("\nTesting AudioProcessor...")
    
    try:
        processor = AudioProcessor()
        
        # Test validation
        valid, error = processor.validate_file("test.mp3", 1024)
        if valid:
            print("✅ File validation works")
        else:
            print(f"❌ File validation failed: {error}")
            return False
        
        # Test unsupported format
        valid, error = processor.validate_file("test.xyz", 1024)
        if not valid and "Unsupported format" in error:
            print("✅ Unsupported format detection works")
        else:
            print("❌ Unsupported format detection failed")
            return False
        
        return True
    except Exception as e:
        print(f"❌ AudioProcessor test failed: {e}")
        return False

def test_export_manager():
    """Test ExportManager functionality."""
    print("\nTesting ExportManager...")
    
    try:
        sample_data = {
            "text": "Hello world",
            "language": "en",
            "duration": 2.5,
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "text": "Hello world",
                    "words": []
                }
            ]
        }
        
        # Test TXT export
        txt_result = ExportManager.export(sample_data, "txt")
        if txt_result == "Hello world":
            print("✅ TXT export works")
        else:
            print("❌ TXT export failed")
            return False
        
        # Test JSON export
        json_result = ExportManager.export(sample_data, "json")
        parsed = json.loads(json_result)
        if parsed["text"] == "Hello world":
            print("✅ JSON export works")
        else:
            print("❌ JSON export failed")
            return False
        
        # Test SRT export
        srt_result = ExportManager.export(sample_data, "srt")
        if "Hello world" in srt_result and "00:00:00,000" in srt_result:
            print("✅ SRT export works")
        else:
            print("❌ SRT export failed")
            return False
        
        return True
    except Exception as e:
        print(f"❌ ExportManager test failed: {e}")
        return False

def test_directories():
    """Test that required directories exist."""
    print("\nTesting directory structure...")
    
    required_dirs = ["backend", "frontend", "uploads", "results"]
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✅ {dir_name}/ directory exists")
        else:
            print(f"❌ {dir_name}/ directory missing")
            return False
    
    required_files = [
        "backend/main.py",
        "backend/models.py", 
        "backend/audio_processor.py",
        "backend/transcriber.py",
        "backend/exporters.py",
        "frontend/index.html",
        "frontend/styles.css",
        "frontend/app.js",
        "requirements.txt",
        "README.md"
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            return False
    
    return True

def main():
    """Run all tests."""
    print("🧪 Audio Transcriber Application Tests")
    print("=" * 50)
    
    tests = [
        test_directories,
        test_imports,
        test_audio_processor,
        test_export_manager
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            break
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application is ready to run.")
        print("\nTo start the application:")
        print("  python run.py")
    else:
        print("❌ Some tests failed. Please check the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()

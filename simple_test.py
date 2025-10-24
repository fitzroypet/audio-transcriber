#!/usr/bin/env python3
"""
Simple test to verify the application can start.
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_basic_imports():
    """Test basic imports without pydub dependency."""
    print("Testing basic imports...")
    
    try:
        import fastapi
        print("✅ FastAPI imported successfully")
        
        import whisper
        print("✅ Whisper imported successfully")
        
        from models import TranscriptionRequest, TranscriptionResponse
        print("✅ Models imported successfully")
        
        from exporters import ExportManager
        print("✅ Exporters imported successfully")
        
        # Store ExportManager globally for later use
        globals()['ExportManager'] = ExportManager
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
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
        import json
        json_result = ExportManager.export(sample_data, "json")
        parsed = json.loads(json_result)
        if parsed["text"] == "Hello world":
            print("✅ JSON export works")
        else:
            print("❌ JSON export failed")
            return False
        
        return True
    except Exception as e:
        print(f"❌ ExportManager test failed: {e}")
        return False

def main():
    """Run basic tests."""
    print("🧪 Audio Transcriber Basic Tests")
    print("=" * 40)
    
    tests = [
        test_basic_imports,
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
        print("🎉 Basic tests passed! The application should work.")
        print("\nNote: Audio processing features require ffmpeg and pydub.")
        print("To start the application:")
        print("  python run.py")
    else:
        print("❌ Some tests failed. Please check the issues above.")

if __name__ == "__main__":
    main()

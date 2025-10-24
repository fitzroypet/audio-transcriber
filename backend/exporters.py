import json
from typing import Dict, Any
from datetime import timedelta


class ExportFormat:
    """Base class for export formats."""
    
    @staticmethod
    def export(data: Dict[str, Any]) -> str:
        raise NotImplementedError


class TXTExporter(ExportFormat):
    """Export transcription as plain text."""
    
    @staticmethod
    def export(data: Dict[str, Any]) -> str:
        return data.get("text", "").strip()


class JSONExporter(ExportFormat):
    """Export transcription as JSON with full metadata."""
    
    @staticmethod
    def export(data: Dict[str, Any]) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False)


class SRTExporter(ExportFormat):
    """Export transcription as SRT subtitle format."""
    
    @staticmethod
    def export(data: Dict[str, Any]) -> str:
        if not data.get("segments"):
            return ""
        
        srt_content = []
        
        for i, segment in enumerate(data["segments"], 1):
            start_time = SRTExporter._format_timestamp(segment["start"])
            end_time = SRTExporter._format_timestamp(segment["end"])
            text = segment["text"].strip()
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(text)
            srt_content.append("")  # Empty line between subtitles
        
        return "\n".join(srt_content)
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        td = timedelta(seconds=seconds)
        hours, remainder = divmod(td.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"


class ExportManager:
    """Manages different export formats."""
    
    EXPORTERS = {
        "txt": TXTExporter,
        "json": JSONExporter,
        "srt": SRTExporter
    }
    
    @classmethod
    def export(cls, data: Dict[str, Any], format_type: str) -> str:
        """Export data in the specified format."""
        exporter = cls.EXPORTERS.get(format_type.lower())
        if not exporter:
            raise ValueError(f"Unsupported export format: {format_type}")
        
        return exporter.export(data)
    
    @classmethod
    def get_supported_formats(cls) -> list:
        """Get list of supported export formats."""
        return list(cls.EXPORTERS.keys())

'use client';

// Drop this component anywhere in thepatna.org.
// Replace TRANSCRIBER_URL with your deployed Railway/Render URL.
const TRANSCRIBER_URL = 'https://YOUR_APP.railway.app?embed=true';

export default function TranscribeButton({ label = 'Transcribe Recording' }) {
  function openTranscriber() {
    window.open(
      TRANSCRIBER_URL,
      'audio-transcriber',
      'width=540,height=740,scrollbars=yes,resizable=yes'
    );
  }

  return (
    <button onClick={openTranscriber} className="transcribe-btn">
      🎵 {label}
    </button>
  );
}

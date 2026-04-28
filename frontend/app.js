class AudioTranscriber {
    constructor() {
        this.allowedTypes = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma'];
        this.maxFileSizeMb = 500;
        this.maxFileSizeBytes = this.maxFileSizeMb * 1024 * 1024;
        this.currentJobId = null;
        this.pollInterval = null;
        this.initializeElements();
        this.setupEventListeners();
        this.loadServerConfig();
    }

    initializeElements() {
        // Upload elements
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfo = document.getElementById('fileInfo');
        this.fileName = document.getElementById('fileName');
        this.fileSize = document.getElementById('fileSize');
        this.startTranscriptionBtn = document.getElementById('startTranscription');

        // Progress elements
        this.progressSection = document.getElementById('progressSection');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.progressPercent = document.getElementById('progressPercent');

        // Results elements
        this.resultsSection = document.getElementById('resultsSection');
        this.transcriptionPreview = document.getElementById('transcriptionPreview');
        this.newTranscriptionBtn = document.getElementById('newTranscription');

        // Error elements
        this.errorSection = document.getElementById('errorSection');
        this.errorMessage = document.getElementById('errorMessage');
        this.tryAgainBtn = document.getElementById('tryAgain');

        // Sections
        this.uploadSection = document.getElementById('uploadSection');
    }

    setupEventListeners() {
        // File upload events
        this.uploadArea.addEventListener('click', () => this.fileInput.click());
        this.uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        this.uploadArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
        this.uploadArea.addEventListener('drop', this.handleDrop.bind(this));
        this.fileInput.addEventListener('change', this.handleFileSelect.bind(this));

        // Button events
        this.startTranscriptionBtn.addEventListener('click', this.startTranscription.bind(this));
        this.newTranscriptionBtn.addEventListener('click', this.resetApp.bind(this));
        this.tryAgainBtn.addEventListener('click', this.resetApp.bind(this));

        // Language toggle hint
        document.querySelectorAll('input[name="languageMode"]').forEach(radio => {
            radio.addEventListener('change', () => {
                const hint = document.getElementById('toggleHint');
                if (hint) {
                    hint.textContent = radio.value === 'en'
                        ? 'Best accuracy for English-language meetings'
                        : 'Use when speakers switch between languages';
                }
            });
        });

        // Download button events
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-download')) {
                this.downloadResult(e.target.dataset.format);
            }
        });

        // Google Drive transcription
        document.getElementById('gdriveTranscribe').addEventListener('click', () => this.startGdriveTranscription());
        document.getElementById('gdriveUrl').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.startGdriveTranscription();
        });
    }

    async loadServerConfig() {
        try {
            const response = await fetch('/formats');
            if (!response.ok) return;

            const config = await response.json();

            if (Array.isArray(config.audio_formats) && config.audio_formats.length > 0) {
                this.allowedTypes = config.audio_formats.map((format) => format.toLowerCase());
                this.fileInput.accept = this.allowedTypes.join(',');
            }

            if (Number.isFinite(config.max_file_size_mb) && config.max_file_size_mb > 0) {
                this.maxFileSizeMb = config.max_file_size_mb;
                this.maxFileSizeBytes = this.maxFileSizeMb * 1024 * 1024;
            }
        } catch (error) {
            console.warn('Failed to load server config', error);
        }
    }

    handleDragOver(e) {
        e.preventDefault();
        this.uploadArea.classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');
    }

    handleDrop(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processFile(file);
        }
    }

    processFile(file) {
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();

        if (!this.allowedTypes.includes(fileExt)) {
            this.showError(`Unsupported file type: ${fileExt}. Supported formats: ${this.allowedTypes.join(', ')}`);
            return;
        }

        if (file.size > this.maxFileSizeBytes) {
            this.showError(`File too large. Maximum size is ${this.maxFileSizeMb}MB.`);
            return;
        }

        // Show file info
        this.fileName.textContent = file.name;
        this.fileSize.textContent = this.formatFileSize(file.size);
        this.fileInfo.style.display = 'block';
        this.selectedFile = file;

        // Hide error if showing
        this.hideError();
    }

    async startTranscription() {
        if (!this.selectedFile) return;

        try {
            this.showProgress('Uploading file...');

            // Create form data
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            const selectedMode = document.querySelector('input[name="languageMode"]:checked');
            const languageMode = selectedMode ? selectedMode.value : 'en';

            // Upload file
            const response = await fetch(`/upload?language_mode=${languageMode}`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let detail = `Server error ${response.status}`;
                try {
                    const error = await response.json();
                    detail = error.detail || error.message || error.error || JSON.stringify(error);
                } catch (_) {
                    detail = await response.text().catch(() => detail);
                }
                throw new Error(detail);
            }

            const result = await response.json();
            this.currentJobId = result.job_id;

            this.showProgress('Transcription started...');
            this.startPolling();

        } catch (error) {
            this.showError(`Upload failed: ${error.message}`);
        }
    }

    startPolling() {
        this.pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${this.currentJobId}`);
                const status = await response.json();

                if (status.status === 'processing') {
                    const progress = Math.round(status.progress * 100);
                    this.updateProgress(progress, 'Transcribing audio...');
                } else if (status.status === 'completed') {
                    this.showResults(status.transcription, status.original_filename);
                    this.stopPolling();
                } else if (status.status === 'failed') {
                    this.showError(`Transcription failed: ${status.error_message}`);
                    this.stopPolling();
                }

            } catch (error) {
                this.showError(`Failed to check status: ${error.message}`);
                this.stopPolling();
            }
        }, 2000); // Poll every 2 seconds
    }

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    showProgress(message) {
        this.hideAllSections();
        this.progressSection.style.display = 'block';
        this.progressText.textContent = message;
        this.progressFill.style.width = '0%';
        this.progressPercent.textContent = '0%';
    }

    updateProgress(percent, message) {
        this.progressFill.style.width = `${percent}%`;
        this.progressPercent.textContent = `${percent}%`;
        this.progressText.textContent = message;
    }

    async startGdriveTranscription() {
        const urlInput = document.getElementById('gdriveUrl');
        const url = urlInput.value.trim();
        if (!url) return;

        const selectedMode = document.querySelector('input[name="languageMode"]:checked');
        const languageMode = selectedMode ? selectedMode.value : 'en';

        try {
            this.showProgress('Fetching file from Google Drive...');
            const response = await fetch(
                `/transcribe-gdrive?gdrive_url=${encodeURIComponent(url)}&language_mode=${languageMode}`,
                { method: 'POST' }
            );

            if (!response.ok) {
                let detail = `Server error ${response.status}`;
                try { detail = (await response.json()).detail || detail; } catch (_) {}
                throw new Error(detail);
            }

            const result = await response.json();
            this.currentJobId = result.job_id;
            this.showProgress('File received, transcribing...');
            this.startPolling();
        } catch (error) {
            this.showError(`Google Drive error: ${error.message}`);
        }
    }

    showResults(transcription, originalFilename) {
        this.hideAllSections();
        this.resultsSection.style.display = 'block';
        this.transcriptionPreview.textContent = transcription.text;
        this.currentTranscription = transcription;

        const heading = this.resultsSection.querySelector('h3');
        if (originalFilename) {
            const stem = originalFilename.replace(/\.[^.]+$/, '');
            heading.textContent = `✅ ${stem}`;
        } else {
            heading.textContent = 'Transcription Complete!';
        }
    }

    async downloadResult(format) {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(`/download/${this.currentJobId}?format=${format}`);

            if (!response.ok) {
                throw new Error('Download failed');
            }

            // Get filename from response headers or create default
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `transcription.${format}`;

            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }

            // Create download link
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

        } catch (error) {
            this.showError(`Download failed: ${error.message}`);
        }
    }

    showError(message) {
        this.hideAllSections();
        this.errorSection.style.display = 'block';
        this.errorMessage.textContent = message;
        this.stopPolling();
    }

    hideError() {
        this.errorSection.style.display = 'none';
    }

    hideAllSections() {
        this.uploadSection.style.display = 'none';
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'none';
        this.errorSection.style.display = 'none';
    }

    resetApp() {
        this.hideAllSections();
        this.uploadSection.style.display = 'block';
        this.fileInfo.style.display = 'none';
        this.fileInput.value = '';
        const gdriveInput = document.getElementById('gdriveUrl');
        if (gdriveInput) gdriveInput.value = '';
        this.selectedFile = null;
        this.currentJobId = null;
        this.currentTranscription = null;
        this.stopPolling();
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}


// ── Live Recorder ──────────────────────────────────────────────────────────────

class LiveRecorder {
    constructor(onSegments, onFinal, onError) {
        this.onSegments = onSegments;
        this.onFinal = onFinal;
        this.onError = onError;
        this.isRecording = false;
        this.ws = null;
        this.stream = null;
        this.audioContext = null;
        this.recordStream = null;
        this.mediaRecorder = null;
        this.chunks = [];
        this.chunkIntervalMs = 5000;
        this.chunkTimer = null;
    }

    async start(languageMode = 'en', gainValue = 1.0) {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Route through a GainNode so quiet sources (e.g. Zoom via laptop speaker)
        // are amplified before MediaRecorder encodes them.
        if (gainValue !== 1.0) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(this.stream);
            const gainNode = this.audioContext.createGain();
            gainNode.gain.value = gainValue;
            const dest = this.audioContext.createMediaStreamDestination();
            source.connect(gainNode);
            gainNode.connect(dest);
            this.recordStream = dest.stream;
        } else {
            this.recordStream = this.stream;
        }

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${proto}//${location.host}/ws/transcribe?language_mode=${languageMode}`;
        this.ws = new WebSocket(wsUrl);

        await new Promise((resolve, reject) => {
            this.ws.onopen = resolve;
            this.ws.onerror = () => reject(new Error('WebSocket connection failed'));
        });

        this.ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.error) {
                    this.onError(data.error);
                } else if (data.is_final) {
                    this.onFinal(data);
                } else {
                    this.onSegments(data);
                }
            } catch (err) {
                console.error('WebSocket message parse error', err);
            }
        };

        this.ws.onerror = () => this.onError('WebSocket error — connection lost');

        this.isRecording = true;
        this._startChunk();
    }

    _startChunk() {
        if (!this.isRecording || !this.stream) return;

        this.chunks = [];
        this.mediaRecorder = new MediaRecorder(this.recordStream);

        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) this.chunks.push(e.data);
        };

        this.mediaRecorder.onstop = async () => {
            if (this.chunks.length > 0) {
                const blob = new Blob(this.chunks, { type: this.mediaRecorder.mimeType });
                const buf = await blob.arrayBuffer();
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(buf);
                }
            }
            if (this.isRecording) {
                this._startChunk();
            }
        };

        this.mediaRecorder.start();
        this.chunkTimer = setTimeout(() => {
            if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                this.mediaRecorder.stop();
            }
        }, this.chunkIntervalMs);
    }

    stop() {
        this.isRecording = false;

        if (this.chunkTimer) {
            clearTimeout(this.chunkTimer);
            this.chunkTimer = null;
        }

        const sendDone = async () => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'done' }));
            }
            if (this.stream) {
                this.stream.getTracks().forEach(t => t.stop());
                this.stream = null;
            }
        };

        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            const origStop = this.mediaRecorder.onstop;
            this.mediaRecorder.onstop = async () => {
                // Send the final chunk first
                if (this.chunks.length > 0) {
                    const blob = new Blob(this.chunks, { type: this.mediaRecorder.mimeType });
                    const buf = await blob.arrayBuffer();
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(buf);
                    }
                }
                await sendDone();
            };
            this.mediaRecorder.stop();
        } else {
            sendDone();
        }
    }

    cleanup() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        this.recordStream = null;
    }
}


// ── Live Transcriber UI ────────────────────────────────────────────────────────

class LiveTranscriberUI {
    constructor() {
        this.recorder = null;
        this.accumulatedSegments = [];
        this.timerInterval = null;
        this.elapsedSeconds = 0;
        this.initElements();
        this.setupEventListeners();
    }

    initElements() {
        this.recordControls = document.getElementById('recordControls');
        this.startRecordBtn = document.getElementById('startRecord');
        this.stopRecordBtn = document.getElementById('stopRecord');
        this.recordingStatus = document.getElementById('recordingStatus');
        this.recordTimer = document.getElementById('recordTimer');
        this.liveTranscript = document.getElementById('liveTranscript');
        this.liveTranscriptText = document.getElementById('liveTranscriptText');
        this.liveHint = document.getElementById('liveHint');
        this.liveResults = document.getElementById('liveResults');
        this.liveTranscriptionPreview = document.getElementById('liveTranscriptionPreview');
        this.newRecordingBtn = document.getElementById('newRecording');
        this.liveErrorSection = document.getElementById('liveErrorSection');
        this.liveErrorMessage = document.getElementById('liveErrorMessage');
        this.liveTryAgainBtn = document.getElementById('liveTryAgain');
    }

    setupEventListeners() {
        this.startRecordBtn.addEventListener('click', () => this.startRecording());
        this.stopRecordBtn.addEventListener('click', () => this.stopRecording());
        this.newRecordingBtn.addEventListener('click', () => this.resetLive());
        this.liveTryAgainBtn.addEventListener('click', () => this.resetLive());

        const boostInput = document.getElementById('boostLevel');
        const boostLabel = document.getElementById('boostLabel');
        if (boostInput && boostLabel) {
            boostInput.addEventListener('input', () => {
                boostLabel.textContent = `${boostInput.value}×`;
            });
        }

        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-download-live')) {
                this.downloadLiveResult(e.target.dataset.format);
            }
        });
    }

    async startRecording() {
        const selectedMode = document.querySelector('input[name="liveLanguageMode"]:checked');
        const languageMode = selectedMode ? selectedMode.value : 'en';
        const boostEl = document.getElementById('boostLevel');
        const gainValue = boostEl ? parseFloat(boostEl.value) : 1.0;

        this.accumulatedSegments = [];
        this.liveTranscriptText.textContent = '';
        this.liveHint.style.display = 'block';

        this.recorder = new LiveRecorder(
            (data) => this.onSegments(data),
            (data) => this.onFinal(data),
            (err) => this.onError(err)
        );

        try {
            await this.recorder.start(languageMode, gainValue);
        } catch (err) {
            this.showLiveError(err.message || 'Microphone access denied or not available');
            return;
        }

        // Show recording UI
        this.startRecordBtn.style.display = 'none';
        this.recordingStatus.style.display = 'flex';
        this.liveTranscript.style.display = 'block';
        this.liveResults.style.display = 'none';

        // Start timer
        this.elapsedSeconds = 0;
        this.timerInterval = setInterval(() => {
            this.elapsedSeconds++;
            const m = Math.floor(this.elapsedSeconds / 60);
            const s = this.elapsedSeconds % 60;
            this.recordTimer.textContent = `${m}:${String(s).padStart(2, '0')}`;
        }, 1000);
    }

    stopRecording() {
        if (this.recorder) {
            // Show "processing last chunk" state
            this.stopRecordBtn.disabled = true;
            this.stopRecordBtn.textContent = 'Finishing...';
            this.recorder.stop();
        }
        this._stopTimer();
    }

    onSegments(data) {
        if (data.segments && data.segments.length > 0) {
            this.accumulatedSegments.push(...data.segments);
            this.liveTranscriptText.textContent = data.full_text;
            this.liveHint.style.display = 'none';
            // Auto-scroll
            this.liveTranscript.scrollTop = this.liveTranscript.scrollHeight;
        }
    }

    onFinal(data) {
        this.accumulatedSegments = data.segments || this.accumulatedSegments;
        const fullText = data.full_text || '';

        // Hide recording UI, show results
        this.recordingStatus.style.display = 'none';
        this.liveTranscript.style.display = 'none';
        this.liveResults.style.display = 'block';
        this.liveTranscriptionPreview.textContent = fullText || '(No speech detected)';

        if (this.recorder) {
            this.recorder.cleanup();
            this.recorder = null;
        }
    }

    onError(message) {
        this._stopTimer();
        if (this.recorder) {
            this.recorder.cleanup();
            this.recorder = null;
        }
        this.recordingStatus.style.display = 'none';
        this.startRecordBtn.style.display = 'inline-flex';
        this.liveTranscript.style.display = 'none';
        this.showLiveError(message);
    }

    showLiveError(message) {
        this.liveErrorMessage.textContent = message;
        this.liveErrorSection.style.display = 'block';
    }

    resetLive() {
        this._stopTimer();
        if (this.recorder) {
            this.recorder.cleanup();
            this.recorder = null;
        }
        this.accumulatedSegments = [];
        this.liveTranscriptText.textContent = '';
        this.liveHint.style.display = 'block';
        this.startRecordBtn.style.display = 'inline-flex';
        this.startRecordBtn.disabled = false;
        this.stopRecordBtn.disabled = false;
        this.stopRecordBtn.textContent = 'Stop';
        this.recordingStatus.style.display = 'none';
        this.liveTranscript.style.display = 'none';
        this.liveResults.style.display = 'none';
        this.liveErrorSection.style.display = 'none';
    }

    _stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    downloadLiveResult(format) {
        const fullText = this.accumulatedSegments.map(s => s.text).join(' ');
        let content, filename, mimeType;

        if (format === 'txt') {
            content = fullText;
            filename = 'live-transcription.txt';
            mimeType = 'text/plain';
        } else if (format === 'srt') {
            content = this._segmentsToSRT(this.accumulatedSegments);
            filename = 'live-transcription.srt';
            mimeType = 'text/plain';
        } else {
            return;
        }

        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    _segmentsToSRT(segments) {
        return segments.map((seg, i) => {
            return `${i + 1}\n${this._srtTime(seg.start)} --> ${this._srtTime(seg.end)}\n${seg.text}\n`;
        }).join('\n');
    }

    _srtTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        const ms = Math.round((seconds % 1) * 1000);
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
    }
}


// ── Mode Tab Controller ────────────────────────────────────────────────────────

class ModeController {
    constructor(uploader, liveUI) {
        this.uploader = uploader;
        this.liveUI = liveUI;
        this.tabUpload = document.getElementById('tabUpload');
        this.tabLive = document.getElementById('tabLive');
        this.panelUpload = document.getElementById('panelUpload');
        this.panelLive = document.getElementById('panelLive');

        this.tabUpload.addEventListener('click', () => this.switchTo('upload'));
        this.tabLive.addEventListener('click', () => this.switchTo('live'));
    }

    switchTo(mode) {
        if (mode === 'upload') {
            // Stop any live recording before switching
            if (this.liveUI.recorder) {
                this.liveUI.recorder.cleanup();
                this.liveUI.recorder = null;
                this.liveUI._stopTimer();
            }
            this.tabUpload.classList.add('active');
            this.tabLive.classList.remove('active');
            this.panelUpload.style.display = 'block';
            this.panelLive.style.display = 'none';
        } else {
            this.tabUpload.classList.remove('active');
            this.tabLive.classList.add('active');
            this.panelUpload.style.display = 'none';
            this.panelLive.style.display = 'block';
        }
    }
}


// ── Init ───────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    if (new URLSearchParams(window.location.search).get('embed') === 'true') {
        document.body.classList.add('embed-mode');
    }
    const uploader = new AudioTranscriber();
    const liveUI = new LiveTranscriberUI();
    new ModeController(uploader, liveUI);
});

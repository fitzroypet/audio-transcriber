class AudioTranscriber {
    constructor() {
        this.currentJobId = null;
        this.pollInterval = null;
        this.initializeElements();
        this.setupEventListeners();
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

        // Download button events
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-download')) {
                this.downloadResult(e.target.dataset.format);
            }
        });
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
        // Validate file type
        const allowedTypes = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma'];
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExt)) {
            this.showError(`Unsupported file type: ${fileExt}. Supported formats: ${allowedTypes.join(', ')}`);
            return;
        }

        // Validate file size (500MB limit)
        const maxSize = 500 * 1024 * 1024; // 500MB in bytes
        if (file.size > maxSize) {
            this.showError('File too large. Maximum size is 500MB.');
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

            // Upload file
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
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
                    this.showResults(status.transcription);
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
    }

    updateProgress(percent, message) {
        this.progressFill.style.width = `${percent}%`;
        this.progressText.textContent = message;
    }

    showResults(transcription) {
        this.hideAllSections();
        this.resultsSection.style.display = 'block';
        this.transcriptionPreview.textContent = transcription.text;
        this.currentTranscription = transcription;
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

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new AudioTranscriber();
});

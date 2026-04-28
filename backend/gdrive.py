import os
import re
import uuid
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Regex patterns to extract Google Drive file IDs from various URL formats
_GDRIVE_PATTERNS = [
    r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
    r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
    r'drive\.google\.com/uc\?[^"]*id=([a-zA-Z0-9_-]+)',
    r'docs\.google\.com/[^/]+/d/([a-zA-Z0-9_-]+)',
]

_EXT_BY_MIME = {
    'audio/mpeg': '.mp3',
    'audio/mp4': '.m4a',
    'audio/x-m4a': '.m4a',
    'audio/wav': '.wav',
    'audio/x-wav': '.wav',
    'audio/ogg': '.ogg',
    'audio/flac': '.flac',
    'audio/aac': '.aac',
    'audio/x-ms-wma': '.wma',
    'video/mp4': '.mp4',
    'video/webm': '.webm',
}


def extract_file_id(url: str) -> Optional[str]:
    """Return the Google Drive file ID from a sharing URL, or None if not recognised."""
    for pattern in _GDRIVE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def download_gdrive_file(file_id: str, dest_dir: str) -> Tuple[str, str]:
    """Download a publicly-shared Google Drive file to dest_dir.

    Returns (saved_file_path, original_filename).
    Raises ValueError with a user-friendly message if the download fails.
    """
    import requests  # available via python-jose / direct dep

    os.makedirs(dest_dir, exist_ok=True)
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    # Try the usercontent endpoint first — more reliable for large files
    urls_to_try = [
        f'https://drive.usercontent.google.com/u/0/uc?id={file_id}&export=download&confirm=t',
        f'https://drive.google.com/uc?export=download&id={file_id}&confirm=t',
    ]

    response = None
    for url in urls_to_try:
        try:
            r = session.get(url, stream=True, timeout=60, allow_redirects=True)
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                response = r
                break
            logger.debug(f"Got HTML response from {url}, trying next URL")
        except requests.RequestException as exc:
            logger.debug(f"Request failed for {url}: {exc}")
            continue

    if response is None:
        raise ValueError(
            "Could not download the file from Google Drive. "
            "Make sure the file is shared as 'Anyone with the link can view'."
        )

    # Determine original filename from Content-Disposition
    cd = response.headers.get('Content-Disposition', '')
    original_filename = _parse_cd_filename(cd)

    if not original_filename:
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        ext = _EXT_BY_MIME.get(content_type, '.audio')
        original_filename = f'recording{ext}'

    original_filename = _sanitize_filename(original_filename)

    # Save with a unique prefix so concurrent downloads don't collide
    prefix = uuid.uuid4().hex[:8]
    save_path = os.path.join(dest_dir, f'{prefix}_{original_filename}')

    total = 0
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                total += len(chunk)

    if total == 0:
        os.remove(save_path)
        raise ValueError("Downloaded file is empty. The file may not be publicly accessible.")

    logger.info(f"Downloaded Google Drive file {file_id} → {save_path} ({total} bytes)")
    return save_path, original_filename


def _parse_cd_filename(cd: str) -> Optional[str]:
    """Extract filename from a Content-Disposition header."""
    if not cd:
        return None
    # Prefer filename* (RFC 5987) over filename
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1))
    m = re.search(r'filename="([^"]+)"', cd)
    if m:
        return m.group(1)
    m = re.search(r"filename=([^;]+)", cd)
    if m:
        return m.group(1).strip()
    return None


def _sanitize_filename(name: str) -> str:
    """Strip path separators and control characters from a filename."""
    name = os.path.basename(name)
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip('. ')
    return name or 'recording'

import io
import os
import zipfile
import logging
from pathlib import Path
from typing import Tuple
from tracemind.config import IGNORED_DIRECTORIES, IGNORED_EXTENSIONS

logger = logging.getLogger(__name__)

MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_ZIP_ENTRIES = 10000

def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    try:
        base = os.path.abspath(str(base_dir))
        target = os.path.abspath(str(target_path))
        return os.path.commonpath([base, target]) == base
    except Exception:
        return False

def safe_extract_zip(zip_content: bytes, destination_dir: str) -> str:
    """
    Safely extracts a ZIP archive into destination_dir while:
    1. Preventing ZIP-slip / path traversal vulnerabilities.
    2. Enforcing uncompressed size limits to prevent zip bombs.
    3. Skipping ignored directories (.git, node_modules, etc.) during extraction.
    4. Automatically identifying root project directory.
    """
    dest_path = Path(destination_dir).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            infolist = zf.infolist()
            if not infolist:
                raise ValueError("The uploaded ZIP archive is empty.")

            if len(infolist) > MAX_ZIP_ENTRIES:
                raise ValueError(f"ZIP archive contains too many entries ({len(infolist)} > {MAX_ZIP_ENTRIES}).")

            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError(f"Uncompressed archive size exceeds limit ({total_uncompressed / (1024*1024):.1f} MB > 200 MB).")

            extracted_count = 0
            for info in infolist:
                norm_name = info.filename.replace('\\', '/').strip('/')
                if not norm_name:
                    continue

                segments = norm_name.split('/')
                # Disallow path traversal
                if '..' in segments:
                    raise ValueError(f"Potentially malicious ZIP entry detected: {info.filename}")

                # Skip ignored directories (.git, node_modules, __pycache__, etc.)
                if any(seg in IGNORED_DIRECTORIES or seg.startswith('.') for seg in segments[:-1]):
                    continue
                if segments[-1] in IGNORED_DIRECTORIES or segments[-1].startswith('.'):
                    continue

                # Skip ignored extensions
                ext = Path(norm_name).suffix.lower()
                if ext in IGNORED_EXTENSIONS:
                    continue

                target_file_path = dest_path / norm_name
                if not is_safe_path(dest_path, target_file_path):
                    raise ValueError(f"Invalid extraction path outside workspace: {info.filename}")

                if info.is_dir():
                    target_file_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_file_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target_file_path, 'wb') as dst:
                        dst.write(src.read())
                    extracted_count += 1

            if extracted_count == 0:
                raise ValueError("No supported source files found in the uploaded ZIP archive.")

    except zipfile.BadZipFile:
        raise ValueError("Invalid or corrupted ZIP archive format.")

    # Check if archive extracted into a single wrapper folder
    top_items = [p for p in dest_path.iterdir() if p.is_dir() and not p.name.startswith('.')]
    top_files = [p for p in dest_path.iterdir() if p.is_file() and not p.name.startswith('.')]
    if len(top_items) == 1 and len(top_files) == 0:
        return str(top_items[0])

    return str(dest_path)


import os
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

from tracemind.config import (
    IGNORED_DIRECTORIES,
    IGNORED_EXTENSIONS,
    LANGUAGE_BY_EXTENSION,
    MAX_FILE_SIZE_BYTES,
)

logger = logging.getLogger(__name__)

@dataclass
class ScannedFile:
    path: str
    relative_path: str
    name: str
    language: str
    size_bytes: int
    file_hash: str
    line_count: int
    content: Optional[str] = None

class CodebaseScanner:
    def __init__(
        self,
        ignored_dirs: Optional[Set[str]] = None,
        ignored_exts: Optional[Set[str]] = None,
        max_file_size: int = MAX_FILE_SIZE_BYTES
    ):
        self.ignored_dirs = ignored_dirs or IGNORED_DIRECTORIES
        self.ignored_exts = ignored_exts or IGNORED_EXTENSIONS
        self.max_file_size = max_file_size

    def should_ignore_dir(self, dir_name: str) -> bool:
        return dir_name in self.ignored_dirs or dir_name.startswith(".")

    def detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_BY_EXTENSION.get(ext, "unknown")

    def read_file_safely(self, file_path: str) -> Optional[str]:
        # Try UTF-8-sig first to strip BOM, then UTF-8, then fallback to latin-1
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                    return content.lstrip("\ufeff")
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning("Failed reading %s: %s", file_path, e)
                return None
        return None

    def compute_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def scan_directory(self, repo_dir: str, load_content: bool = True) -> List[ScannedFile]:
        root_path = Path(repo_dir).resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Repository directory does not exist or is not a directory: {repo_dir}")

        scanned_files: List[ScannedFile] = []

        for current_root, dirs, files in os.walk(root_path):
            # Prune ignored directories in-place so os.walk does not descend into them
            dirs[:] = [d for d in dirs if not self.should_ignore_dir(d)]

            for file_name in files:
                file_path = Path(current_root) / file_name
                ext = file_path.suffix.lower()

                if ext in self.ignored_exts:
                    continue

                language = self.detect_language(str(file_path))
                if language == "unknown":
                    continue

                try:
                    file_size = file_path.stat().st_size
                except OSError as e:
                    logger.warning("Could not stat file %s: %s", file_path, e)
                    continue

                if file_size > self.max_file_size:
                    logger.info("Skipping file %s: size %d exceeds limit %d", file_path, file_size, self.max_file_size)
                    continue

                content = None
                if load_content:
                    content = self.read_file_safely(str(file_path))
                    if content is None:
                        continue
                    file_hash = self.compute_sha256(content)
                    line_count = len(content.splitlines())
                else:
                    file_hash = ""
                    line_count = 0

                rel_path = file_path.relative_to(root_path).as_posix()

                scanned_files.append(ScannedFile(
                    path=str(file_path),
                    relative_path=rel_path,
                    name=file_name,
                    language=language,
                    size_bytes=file_size,
                    file_hash=file_hash,
                    line_count=line_count,
                    content=content
                ))

        logger.info("Scanned %d source files from %s", len(scanned_files), repo_dir)
        return scanned_files

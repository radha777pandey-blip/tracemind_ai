import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACES_DIR = BASE_DIR / "data" / "workspaces"
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "tracemind.db"))

# Server configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# AI & LLM Providers
def get_gemini_api_key() -> str:
    load_dotenv(override=True)
    return os.getenv("GEMINI_API_KEY", "").strip()

GEMINI_API_KEY = get_gemini_api_key()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini" if GEMINI_API_KEY else "local")

# Scanner thresholds
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", str(1 * 1024 * 1024)))  # 1 MB

# Directories ignored during ingestion
IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    ".vscode",
    ".idea",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    "coverage",
    ".next",
    ".nuxt",
    "out",
}

# Ignored file extensions
IGNORED_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".docx", ".xlsx",
    ".db", ".sqlite", ".sqlite3"
}

# Supported languages mapping
LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
}

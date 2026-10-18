import sqlite3
import os
from contextlib import contextmanager
from typing import Generator
from tracemind.config import DATABASE_PATH

def get_db_path() -> str:
    return os.getenv("DATABASE_PATH", DATABASE_PATH)

def init_connection(db_path: str | None = None) -> sqlite3.Connection:
    target_path = db_path or get_db_path()
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency & foreign keys
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

@contextmanager
def get_db(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    conn = init_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

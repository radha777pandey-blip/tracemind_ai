import sqlite3
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    hash TEXT NOT NULL,
    line_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, relative_path)
);

CREATE TABLE IF NOT EXISTS code_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL, -- function, class, method, variable
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT,
    docstring TEXT,
    parent_entity_id INTEGER,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_entity_id) REFERENCES code_entities(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    source_type TEXT NOT NULL, -- file, entity
    source_id INTEGER NOT NULL, -- file_id or entity_id
    target_type TEXT NOT NULL, -- file, entity, external
    target_id INTEGER,         -- file_id or entity_id if resolved
    target_name TEXT NOT NULL, -- name of imported module/function
    relation_type TEXT NOT NULL, -- imports, calls, inherits, references
    line_number INTEGER,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS code_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    entity_id INTEGER,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    embedding BLOB,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES code_entities(id) ON DELETE SET NULL
);

-- Indexes for blazing fast graph traversal and search
CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo_id);
CREATE INDEX IF NOT EXISTS idx_files_relpath ON files(repo_id, relative_path);

CREATE INDEX IF NOT EXISTS idx_entities_repo ON code_entities(repo_id);
CREATE INDEX IF NOT EXISTS idx_entities_file ON code_entities(file_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON code_entities(repo_id, name);
CREATE INDEX IF NOT EXISTS idx_entities_qname ON code_entities(repo_id, qualified_name);

CREATE INDEX IF NOT EXISTS idx_deps_repo ON dependencies(repo_id);
CREATE INDEX IF NOT EXISTS idx_deps_source ON dependencies(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_deps_target ON dependencies(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_deps_target_name ON dependencies(repo_id, target_name);

CREATE INDEX IF NOT EXISTS idx_chunks_file ON code_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_entity ON code_chunks(entity_id);
"""

def init_db(conn: sqlite3.Connection) -> None:
    """Initializes the database schema if tables do not exist."""
    logger.info("Initializing database schema...")
    conn.executescript(CREATE_TABLES_SQL)
    conn.commit()


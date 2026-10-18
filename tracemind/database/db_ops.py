import sqlite3
from typing import Optional, Dict, Any, List

def create_or_get_repository(conn: sqlite3.Connection, name: str, path: str) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO repositories (name, path, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(path) DO UPDATE SET
            name = excluded.name,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id;
    """, (name, path))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("SELECT id FROM repositories WHERE path = ?", (path,))
    return cursor.fetchone()[0]

def update_repo_counts(conn: sqlite3.Connection, repo_id: int) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE repositories
        SET file_count = (SELECT COUNT(*) FROM files WHERE repo_id = ?),
            entity_count = (SELECT COUNT(*) FROM code_entities WHERE repo_id = ?)
        WHERE id = ?;
    """, (repo_id, repo_id, repo_id))

def insert_file(
    conn: sqlite3.Connection,
    repo_id: int,
    path: str,
    relative_path: str,
    language: str,
    size_bytes: int,
    file_hash: str,
    line_count: int
) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO files (repo_id, path, relative_path, language, size_bytes, hash, line_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_id, relative_path) DO UPDATE SET
            path = excluded.path,
            language = excluded.language,
            size_bytes = excluded.size_bytes,
            hash = excluded.hash,
            line_count = excluded.line_count
        RETURNING id;
    """, (repo_id, path, relative_path, language, size_bytes, file_hash, line_count))
    row = cursor.fetchone()
    return row[0]

def insert_code_entity(
    conn: sqlite3.Connection,
    repo_id: int,
    file_id: int,
    entity_type: str,
    name: str,
    qualified_name: str,
    start_line: int,
    end_line: int,
    signature: Optional[str] = None,
    docstring: Optional[str] = None,
    parent_entity_id: Optional[int] = None
) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO code_entities (
            repo_id, file_id, entity_type, name, qualified_name,
            start_line, end_line, signature, docstring, parent_entity_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
    """, (
        repo_id, file_id, entity_type, name, qualified_name,
        start_line, end_line, signature, docstring, parent_entity_id
    ))
    return cursor.fetchone()[0]

def insert_dependency(
    conn: sqlite3.Connection,
    repo_id: int,
    source_type: str,
    source_id: int,
    target_type: str,
    target_id: Optional[int],
    target_name: str,
    relation_type: str,
    line_number: Optional[int] = None
) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dependencies (
            repo_id, source_type, source_id, target_type, target_id,
            target_name, relation_type, line_number
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
    """, (
        repo_id, source_type, source_id, target_type, target_id,
        target_name, relation_type, line_number
    ))
    return cursor.fetchone()[0]

def insert_code_chunk(
    conn: sqlite3.Connection,
    repo_id: int,
    file_id: int,
    entity_id: Optional[int],
    chunk_index: int,
    content: str,
    start_line: int,
    end_line: int,
    embedding: Optional[bytes] = None
) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO code_chunks (
            repo_id, file_id, entity_id, chunk_index, content,
            start_line, end_line, embedding
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id;
    """, (
        repo_id, file_id, entity_id, chunk_index, content,
        start_line, end_line, embedding
    ))
    return cursor.fetchone()[0]

def get_repository(conn: sqlite3.Connection, repo_id: int) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
    row = cursor.fetchone()
    return dict(row) if row else None

def list_repositories(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repositories ORDER BY updated_at DESC")
    return [dict(row) for row in cursor.fetchall()]

def get_repository_files(conn: sqlite3.Connection, repo_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE repo_id = ? ORDER BY relative_path ASC", (repo_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_repository_entities(conn: sqlite3.Connection, repo_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, f.relative_path as file_path
        FROM code_entities e
        JOIN files f ON e.file_id = f.id
        WHERE e.repo_id = ?
        ORDER BY f.relative_path, e.start_line
    """, (repo_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_repository_dependencies(conn: sqlite3.Connection, repo_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.*, 
               CASE WHEN d.source_type = 'file' THEN f.relative_path
                    ELSE e.qualified_name END as source_name
        FROM dependencies d
        LEFT JOIN files f ON d.source_type = 'file' AND d.source_id = f.id
        LEFT JOIN code_entities e ON d.source_type = 'entity' AND d.source_id = e.id
        WHERE d.repo_id = ?
    """, (repo_id,))
    return [dict(row) for row in cursor.fetchall()]

def clear_repo_data(conn: sqlite3.Connection, repo_id: int) -> None:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM files WHERE repo_id = ?", (repo_id,))
    cursor.execute("DELETE FROM code_entities WHERE repo_id = ?", (repo_id,))
    cursor.execute("DELETE FROM dependencies WHERE repo_id = ?", (repo_id,))
    cursor.execute("DELETE FROM code_chunks WHERE repo_id = ?", (repo_id,))


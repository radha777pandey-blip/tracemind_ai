import pytest
import sqlite3
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.database.db_ops import (
    create_or_get_repository,
    insert_file,
    insert_code_entity,
    insert_dependency,
    insert_code_chunk,
    get_repository,
    get_repository_files,
    get_repository_entities,
    get_repository_dependencies,
    update_repo_counts
)

@pytest.fixture
def db_conn():
    conn = init_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()

def test_database_initialization(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "repositories" in tables
    assert "files" in tables
    assert "code_entities" in tables
    assert "dependencies" in tables
    assert "code_chunks" in tables

def test_crud_flow(db_conn):
    repo_id = create_or_get_repository(db_conn, "test_repo", "/path/to/test_repo")
    assert repo_id > 0

    file_id = insert_file(
        db_conn,
        repo_id=repo_id,
        path="/path/to/test_repo/auth.py",
        relative_path="auth.py",
        language="python",
        size_bytes=1024,
        file_hash="hash123",
        line_count=45
    )
    assert file_id > 0

    entity_id = insert_code_entity(
        db_conn,
        repo_id=repo_id,
        file_id=file_id,
        entity_type="function",
        name="get_user",
        qualified_name="auth.get_user",
        start_line=10,
        end_line=20,
        signature="def get_user(user_id: int)",
        docstring="Fetch user by ID"
    )
    assert entity_id > 0

    dep_id = insert_dependency(
        db_conn,
        repo_id=repo_id,
        source_type="file",
        source_id=file_id,
        target_type="file",
        target_id=None,
        target_name="database",
        relation_type="imports",
        line_number=1
    )
    assert dep_id > 0

    chunk_id = insert_code_chunk(
        db_conn,
        repo_id=repo_id,
        file_id=file_id,
        entity_id=entity_id,
        chunk_index=0,
        content="def get_user(user_id: int):\n    return db.query(user_id)",
        start_line=10,
        end_line=20
    )
    assert chunk_id > 0

    update_repo_counts(db_conn, repo_id)
    repo = get_repository(db_conn, repo_id)
    assert repo["file_count"] == 1
    assert repo["entity_count"] == 1

    files = get_repository_files(db_conn, repo_id)
    assert len(files) == 1
    assert files[0]["relative_path"] == "auth.py"

    entities = get_repository_entities(db_conn, repo_id)
    assert len(entities) == 1
    assert entities[0]["name"] == "get_user"

    deps = get_repository_dependencies(db_conn, repo_id)
    assert len(deps) == 1
    assert deps[0]["target_name"] == "database"

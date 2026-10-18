import pytest
import numpy as np
from tracemind.ai.embeddings import EmbeddingEngine
from tracemind.ai.vector_store import LocalVectorStore
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.database.db_ops import create_or_get_repository, insert_file, insert_code_chunk

def test_embeddings_and_search():
    engine = EmbeddingEngine()
    vec1 = engine.embed_text('def authenticate_user(token: str): verify_jwt(token)')
    vec2 = engine.embed_text('def login(username, password): check_credentials()')
    vec3 = engine.embed_text('def calculate_shipping(weight: float): return weight * 1.5')

    # Normalized vectors
    assert np.isclose(np.linalg.norm(vec1), 1.0)
    assert np.isclose(np.linalg.norm(vec2), 1.0)
    assert np.isclose(np.linalg.norm(vec3), 1.0)

    # Database integration
    conn = init_connection(':memory:')
    init_db(conn)
    repo_id = create_or_get_repository(conn, 'repo', '/repo')
    f_id = insert_file(conn, repo_id, '/repo/auth.py', 'auth.py', 'python', 100, 'h1', 10)
    f_shipping = insert_file(conn, repo_id, '/repo/ship.py', 'ship.py', 'python', 100, 'h2', 10)

    insert_code_chunk(conn, repo_id, f_id, None, 0, 'def authenticate_user(token: str): verify_jwt(token)', 1, 5)
    insert_code_chunk(conn, repo_id, f_shipping, None, 0, 'def calculate_shipping(weight: float): return weight * 1.5', 1, 5)

    store = LocalVectorStore()
    count = store.load_from_db(conn, repo_id, engine)
    assert count == 2

    # Query about authentication
    query_vec = engine.embed_text('how does user authentication and token verification work?')
    results = store.search(query_vec, top_k=2)

    assert len(results) == 2
    # The auth chunk should score higher than the shipping chunk
    assert results[0].file_path == 'auth.py'
    assert 'authenticate_user' in results[0].content
    assert results[0].score > results[1].score

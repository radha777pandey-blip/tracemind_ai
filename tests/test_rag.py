import pytest
from pathlib import Path
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.ingestion.pipeline import IngestionPipeline
from tracemind.ai.rag_service import CodebaseQAService

def test_rag_service_on_sample_repo(tmp_path):
    sample_dir = str(Path(__file__).resolve().parent.parent / 'samples' / 'ecommerce')
    db_path = str(tmp_path / 'rag_test.db')

    # Initialize & Ingest
    conn = init_connection(db_path)
    init_db(conn)
    conn.close()

    pipeline = IngestionPipeline(db_path=db_path)
    res = pipeline.ingest(sample_dir, 'Ecommerce_QA_Test')

    # Query RAG
    conn = init_connection(db_path)
    qa_service = CodebaseQAService(conn, res.repo_id)

    # 1. Ask about authentication
    response_auth = qa_service.query('Where is user authentication and token verification implemented?')
    assert len(response_auth.citations) > 0
    citation_files = [c.file_path for c in response_auth.citations]
    assert 'auth.py' in citation_files
    assert 'auth.py' in response_auth.answer

    # 2. Ask about payment processing
    response_payment = qa_service.query('How does payment processing work and what handles card transactions?')
    assert len(response_payment.citations) > 0
    citation_files_pay = [c.file_path for c in response_payment.citations]
    assert 'payment.py' in citation_files_pay

    conn.close()

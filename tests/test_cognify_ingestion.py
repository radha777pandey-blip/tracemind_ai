import os
import pytest
from pathlib import Path
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.database.db_ops import get_repository_entities, get_repository_dependencies, get_repository_files
from tracemind.ingestion.pipeline import IngestionPipeline
from tracemind.graph.graph_engine import DependencyGraph
from tracemind.graph.impact_engine import ImpactAnalysisEngine
from tracemind.ai.rag_service import CodebaseQAService

COGNIFY_EXTRACTED = Path(__file__).resolve().parent.parent / 'data' / 'workspaces' / 'test_cognify' / 'Cognify'

@pytest.mark.skipif(not COGNIFY_EXTRACTED.exists(), reason="Cognify test workspace not present")
def test_cognify_end_to_end(tmp_path):
    db_path = str(tmp_path / "cognify_test.db")
    conn = init_connection(db_path)
    init_db(conn)
    conn.close()

    # 1. Pipeline Ingest
    pipeline = IngestionPipeline(db_path=db_path)
    result = pipeline.ingest(str(COGNIFY_EXTRACTED), "Cognify_Test")

    assert result.repo_id > 0
    assert result.files_count > 0
    assert result.entities_count > 0
    assert "javascript" in result.languages

    # 2. Database validation
    conn = init_connection(db_path)
    files = get_repository_files(conn, result.repo_id)
    entities = get_repository_entities(conn, result.repo_id)
    deps = get_repository_dependencies(conn, result.repo_id)

    assert len(files) == result.files_count
    assert len(entities) == result.entities_count
    assert len(deps) > 0

    # 3. Dependency Graph validation
    graph = DependencyGraph.build_from_db(conn, result.repo_id)
    raw_graph = graph.to_dict()
    assert len(raw_graph["nodes"]) > 0
    assert len(raw_graph["edges"]) > 0

    # 4. Change-Impact Analysis validation
    impact_engine = ImpactAnalysisEngine(graph)
    # Pick first entity to test impact
    first_entity = entities[0]
    impact_report = impact_engine.analyze_impact(
        file_path=first_entity["file_path"],
        entity_name=first_entity["name"],
        max_depth=3
    )
    assert impact_report.target["name"] == first_entity["name"]
    assert impact_report.summary_text is not None
    assert impact_report.highest_risk in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    # 5. RAG / Semantic Q&A validation
    qa_service = CodebaseQAService(conn, result.repo_id)
    qa_response = qa_service.query("How does the server or database connection work?", top_k=3)
    assert qa_response.answer is not None
    assert len(qa_response.answer) > 0
    assert qa_response.mode in ["gemini_generation", "local_synthesis"]

    conn.close()

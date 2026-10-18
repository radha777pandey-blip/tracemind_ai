import os
import pytest
from pathlib import Path
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.ingestion.pipeline import IngestionPipeline
from tracemind.graph.graph_engine import DependencyGraph
from tracemind.graph.impact_engine import ImpactAnalysisEngine

def test_full_ingestion_and_impact_on_sample():
    # Use in-memory SQLite or temp database for clean isolation
    sample_dir = str(Path(__file__).resolve().parent.parent / 'samples' / 'ecommerce')
    test_db_path = str(Path(__file__).resolve().parent.parent / 'test_pipeline.db')
    
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # 1. Initialize DB
    conn = init_connection(test_db_path)
    init_db(conn)
    conn.close()

    # 2. Run Ingestion Pipeline
    pipeline = IngestionPipeline(db_path=test_db_path)
    result = pipeline.ingest(sample_dir, repo_name='Ecommerce_Demo')

    assert result.files_count == 6  # config, database, auth, payment, orders, main
    assert result.entities_count >= 10
    assert result.dependencies_count > 0
    assert result.chunks_count >= 6
    assert result.languages.get('python') == 6

    # 3. Build Dependency Graph
    conn = init_connection(test_db_path)
    graph = DependencyGraph.build_from_db(conn, result.repo_id)

    # 4. Perform Impact Analysis on get_current_user
    engine = ImpactAnalysisEngine(graph)
    report = engine.analyze_impact(file_path='auth.py', entity_name='get_current_user', max_depth=3)

    assert report.target['name'] == 'get_current_user'
    assert report.highest_risk == 'HIGH'
    assert report.total_affected_files >= 2  # orders.py and main.py

    affected_names = {item.name: item for item in report.affected_items}

    # create_order in orders.py directly calls get_current_user
    assert 'create_order' in affected_names
    assert affected_names['create_order'].depth == 1
    assert affected_names['create_order'].impact_level == 'HIGH'

    # handle_checkout_request in main.py calls create_order
    assert 'handle_checkout_request' in affected_names
    assert affected_names['handle_checkout_request'].depth == 2
    assert affected_names['handle_checkout_request'].impact_level == 'MEDIUM'

    conn.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

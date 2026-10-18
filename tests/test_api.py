import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from tracemind.api.app import app
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db

client = TestClient(app)

@pytest.fixture(scope='module', autouse=True)
def setup_test_environment():
    test_db = str(Path(__file__).resolve().parent.parent / 'test_api.db')
    os.environ['DATABASE_PATH'] = test_db
    conn = init_connection(test_db)
    init_db(conn)
    conn.close()

    yield

    if os.path.exists(test_db):
        os.remove(test_db)

def test_health_check():
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'healthy'
    assert data['system'] == 'TraceMind AI'

def test_dashboard_html():
    res = client.get('/')
    assert res.status_code == 200
    assert 'TraceMind AI' in res.text

def test_ingestion_and_full_api_workflow():
    sample_dir = str(Path(__file__).resolve().parent.parent / 'samples' / 'ecommerce')

    # 1. Ingest
    ingest_res = client.post('/api/repositories/ingest', json={
        'path': sample_dir,
        'name': 'API_Test_Repo'
    })
    assert ingest_res.status_code == 200
    ingest_data = ingest_res.json()
    repo_id = ingest_data['repo_id']
    assert repo_id > 0
    assert ingest_data['files_count'] == 6
    assert ingest_data['entities_count'] >= 10

    # 2. Get Repositories
    repos_res = client.get('/api/repositories')
    assert repos_res.status_code == 200
    repos = repos_res.json()
    assert any(r['id'] == repo_id for r in repos)

    # 3. Get Specific Repo
    repo_detail = client.get(f'/api/repositories/{repo_id}')
    assert repo_detail.status_code == 200
    assert repo_detail.json()['name'] == 'API_Test_Repo'

    # 4. Get Files
    files_res = client.get(f'/api/repositories/{repo_id}/files')
    assert files_res.status_code == 200
    files = files_res.json()
    assert len(files) == 6

    # 5. Get Entities
    entities_res = client.get(f'/api/repositories/{repo_id}/entities')
    assert entities_res.status_code == 200
    entities = entities_res.json()
    assert len(entities) >= 10
    entity_names = {e['name'] for e in entities}
    assert 'get_current_user' in entity_names
    assert 'create_order' in entity_names

    # 6. Get Dependencies
    deps_res = client.get(f'/api/repositories/{repo_id}/dependencies')
    assert deps_res.status_code == 200
    deps = deps_res.json()
    assert len(deps) > 0

    # 7. Get Graph
    graph_res = client.get(f'/api/repositories/{repo_id}/graph')
    assert graph_res.status_code == 200
    graph_data = graph_res.json()
    assert 'nodes' in graph_data
    assert 'edges' in graph_data
    assert len(graph_data['nodes']) > 0

    # 8. Impact Analysis (Critical Feature)
    impact_res = client.post(f'/api/repositories/{repo_id}/impact-analysis', json={
        'file_path': 'auth.py',
        'entity_name': 'get_current_user',
        'max_depth': 3
    })
    assert impact_res.status_code == 200
    impact_data = impact_res.json()
    assert impact_data['target']['name'] == 'get_current_user'
    assert impact_data['highest_risk'] == 'HIGH'
    assert impact_data['total_affected_files'] >= 2
    
    affected = {item['name']: item for item in impact_data['affected_items']}
    assert 'create_order' in affected
    assert affected['create_order']['depth'] == 1
    assert affected['create_order']['impact_level'] == 'HIGH'
    assert 'handle_checkout_request' in affected
    assert affected['handle_checkout_request']['depth'] == 2

    # 9. Query / RAG
    query_res = client.post(f'/api/repositories/{repo_id}/query', json={
        'query': 'Where is authentication handled?',
        'top_k': 3
    })
    assert query_res.status_code == 200
    query_data = query_res.json()
    assert len(query_data['citations']) > 0
    assert 'auth.py' in [c['file_path'] for c in query_data['citations']]
    assert len(query_data['answer']) > 0

def test_upload_zip_api():
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('app/server.js', 'const express = require("express");\nfunction start() {}\n')
        zf.writestr('app/routes.js', 'const s = require("./server");\nfunction handleReq() { start(); }\n')

    buf.seek(0)
    res = client.post(
        '/api/repositories/upload-zip',
        files={'file': ('test_app.zip', buf, 'application/zip')},
        data={'name': 'Uploaded_Zip_App'}
    )
    assert res.status_code == 200
    data = res.json()
    assert data['repo_id'] > 0
    assert data['name'] == 'Uploaded_Zip_App'
    assert data['files_count'] == 2
    assert data['entities_count'] >= 2


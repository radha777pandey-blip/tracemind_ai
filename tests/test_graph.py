import pytest
from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.database.db_ops import (
    create_or_get_repository,
    insert_file,
    insert_code_entity,
    insert_dependency
)
from tracemind.graph.graph_engine import DependencyGraph
from tracemind.graph.impact_engine import ImpactAnalysisEngine

@pytest.fixture
def sample_graph_db():
    conn = init_connection(":memory:")
    init_db(conn)

    repo_id = create_or_get_repository(conn, "test_repo", "/test")

    # File 1: database.py
    f1 = insert_file(conn, repo_id, "/test/database.py", "database.py", "python", 200, "h1", 20)
    e_get_db = insert_code_entity(conn, repo_id, f1, "function", "get_db", "database.get_db", 5, 10, "def get_db()")

    # File 2: auth.py (imports database, defines get_user)
    f2 = insert_file(conn, repo_id, "/test/auth.py", "auth.py", "python", 400, "h2", 30)
    e_get_user = insert_code_entity(conn, repo_id, f2, "function", "get_user", "auth.get_user", 10, 20, "def get_user(id)")
    insert_dependency(conn, repo_id, "file", f2, "file", f1, "database", "imports", 1)
    insert_dependency(conn, repo_id, "entity", e_get_user, "entity", e_get_db, "get_db", "calls", 15)

    # File 3: orders.py (calls get_user)
    f3 = insert_file(conn, repo_id, "/test/orders.py", "orders.py", "python", 500, "h3", 40)
    e_checkout = insert_code_entity(conn, repo_id, f3, "function", "checkout", "orders.checkout", 12, 25, "def checkout()")
    insert_dependency(conn, repo_id, "file", f3, "file", f2, "auth", "imports", 2)
    insert_dependency(conn, repo_id, "entity", e_checkout, "entity", e_get_user, "get_user", "calls", 18)

    # File 4: main.py (calls checkout)
    f4 = insert_file(conn, repo_id, "/test/main.py", "main.py", "python", 300, "h4", 25)
    e_run = insert_code_entity(conn, repo_id, f4, "function", "run_app", "main.run_app", 5, 15, "def run_app()")
    insert_dependency(conn, repo_id, "file", f4, "file", f3, "orders", "imports", 1)
    insert_dependency(conn, repo_id, "entity", e_run, "entity", e_checkout, "checkout", "calls", 10)

    yield conn, repo_id
    conn.close()

def test_dependency_graph_building(sample_graph_db):
    conn, repo_id = sample_graph_db
    graph = DependencyGraph.build_from_db(conn, repo_id)

    # Nodes: 4 files + 4 entities = 8 nodes
    assert len(graph.nodes) == 8

    # Verify containment
    auth_file_node = graph.nodes["file:auth.py"]
    outgoing = graph.get_outgoing("file:auth.py")
    out_targets = {e.target for e in outgoing}
    assert "entity:auth.get_user" in out_targets
    assert "file:database.py" in out_targets

    # Serialization
    data = graph.to_dict()
    assert len(data["nodes"]) == 8
    assert len(data["edges"]) > 0

def test_impact_analysis_direct_and_transitive(sample_graph_db):
    conn, repo_id = sample_graph_db
    graph = DependencyGraph.build_from_db(conn, repo_id)
    engine = ImpactAnalysisEngine(graph)

    # Case 1: Change get_user in auth.py
    report = engine.analyze_impact(file_path="auth.py", entity_name="get_user", max_depth=3)
    
    assert report.target["name"] == "get_user"
    assert report.highest_risk == "HIGH"
    
    affected_names = {item.name: item for item in report.affected_items}
    # checkout in orders.py directly calls get_user -> Depth 1 (HIGH)
    assert "checkout" in affected_names
    assert affected_names["checkout"].depth == 1
    assert affected_names["checkout"].impact_level == "HIGH"
    assert "Directly calls" in affected_names["checkout"].reason

    # run_app in main.py calls checkout which calls get_user -> Depth 2 (MEDIUM)
    assert "run_app" in affected_names
    assert affected_names["run_app"].depth == 2
    assert affected_names["run_app"].impact_level == "MEDIUM"

def test_impact_analysis_file_level(sample_graph_db):
    conn, repo_id = sample_graph_db
    graph = DependencyGraph.build_from_db(conn, repo_id)
    engine = ImpactAnalysisEngine(graph)

    # Case 2: Change database.py file entirely
    report = engine.analyze_impact(file_path="database.py", max_depth=3)
    assert report.target["name"] == "database.py"
    
    # auth.py directly imports database.py
    affected_files = {item.file_path for item in report.affected_items}
    assert "auth.py" in affected_files

import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tracemind.database.connection import init_connection
from tracemind.database.schema import init_db
from tracemind.ingestion.pipeline import IngestionPipeline
from tracemind.graph.graph_engine import DependencyGraph
from tracemind.graph.impact_engine import ImpactAnalysisEngine
from tracemind.ai.rag_service import CodebaseQAService

def print_separator(title: str):
    print("\n" + "="*70)
    print(f"  {title.upper()}")
    print("="*70)

def run_demo():
    print_separator("TraceMind AI: End-to-End System Demonstration")
    print("Initializing TraceMind AI Engine & Local SQLite Database...")

    db_path = "tracemind.db"
    conn = init_connection(db_path)
    init_db(conn)

    sample_dir = os.path.abspath("samples/ecommerce")
    print(f"\n[1] Ingesting Codebase: {sample_dir}")

    pipeline = IngestionPipeline(db_path=db_path)
    result = pipeline.ingest(sample_dir, repo_name="Ecommerce Microservice")

    print(f"    [+] Ingestion Status: SUCCESS")
    print(f"    [+] Repository ID: {result.repo_id}")
    print(f"    [+] Scanned Files: {result.files_count}")
    print(f"    [+] Extracted Entities: {result.entities_count}")
    print(f"    [+] Dependencies/Calls Mapped: {result.dependencies_count}")
    print(f"    [+] Code Chunks Created: {result.chunks_count}")

    print_separator("[2] Discovered Files & Code Entities")
    cursor = conn.cursor()
    cursor.execute("SELECT relative_path, language, line_count FROM files WHERE repo_id = ?", (result.repo_id,))
    for f in cursor.fetchall():
        print(f"  * {f[0]:<20} | Language: {f[1]:<10} | Lines: {f[2]}")

    print("\n  Sample Detected AST Entities (Functions & Classes):")
    cursor.execute("SELECT qualified_name, entity_type, start_line, end_line FROM code_entities WHERE repo_id = ? LIMIT 8", (result.repo_id,))
    for e in cursor.fetchall():
        print(f"    - [{e[1]:<8}] {e[0]} (lines {e[2]}-{e[3]})")

    print_separator("[3] Dependency & Call Graph Mapping")
    graph = DependencyGraph.build_from_db(conn, result.repo_id)
    print(f"  Total Graph Nodes: {len(graph.nodes)}")
    print(f"  Total Graph Edges: {sum(len(v) for v in graph.forward_edges.values())}")
    
    print("\n  Sample Direct Dependencies:")
    for edge in list(graph.get_outgoing("file:orders.py"))[:4]:
        target_name = graph.nodes[edge.target].name if edge.target in graph.nodes else edge.target
        print(f"    orders.py --[{edge.relation}]--> {target_name}")

    print_separator("[4] Change-Impact Analysis (Differentiating Feature)")
    print("Scenario: Developer wants to refactor or change 'get_current_user' in 'auth.py'")
    print("Question: Which components will break or be affected, and WHY?")

    impact_engine = ImpactAnalysisEngine(graph)
    report = impact_engine.analyze_impact(file_path="auth.py", entity_name="get_current_user", max_depth=3)

    print(f"\n  TARGET ENTITY: {report.target['name']} ({report.target['kind']}) in {report.target['file_path']}")
    print(f"  BLAST RADIUS:  {report.total_affected_files} files, {report.total_affected_entities} entities affected")
    print(f"  SEVERITY:      {report.highest_risk} RISK\n")
    print(f"  Summary: {report.summary_text}\n")

    print("  Detailed Impact Trace & Reasoning:")
    for i, item in enumerate(report.affected_items, 1):
        badge = f"[{item.impact_level}] (Depth {item.depth})"
        print(f"  {i}. {badge:<22} {item.name} in {item.file_path}:{item.line_number}")
        print(f"     Reason: {item.reason}")
        print(f"     Trail:  {' -> '.join(item.relation_trail)}")

    print_separator("[5] Semantic Codebase Q&A (RAG)")
    user_query = "How does the checkout and order flow work?"
    print(f"User Query: '{user_query}'\n")

    qa_service = CodebaseQAService(conn, result.repo_id)
    qa_res = qa_service.query(user_query, top_k=3)

    print(f"Engine Mode: {qa_res.mode}")
    print(f"Answer:\n{qa_res.answer}\n")
    print("Source Citations:")
    for c in qa_res.citations:
        print(f"  * {c.file_path} (Lines {c.start_line}-{c.end_line}) [{c.entity_name or 'block'}]")

    print_separator("Demonstration Completed Successfully")
    print("Start the web UI / API server with:")
    print("  uvicorn tracemind.api.app:app --reload")
    print("Then visit http://127.0.0.1:8000 in your browser.")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_demo()


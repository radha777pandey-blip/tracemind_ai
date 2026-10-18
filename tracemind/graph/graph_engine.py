import sqlite3
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class GraphNode:
    node_id: str
    name: str
    kind: str  # 'file', 'class', 'function', 'method'
    file_path: str
    line_number: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None

@dataclass
class GraphEdge:
    source: str  # node_id
    target: str  # node_id
    relation: str  # 'imports', 'calls', 'inherits', 'contains', 'references'
    line: Optional[int] = None

class DependencyGraph:
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        # Forward edges: source -> list of (target, edge) [source depends on target]
        self.forward_edges: Dict[str, List[GraphEdge]] = defaultdict(list)
        # Reverse edges: target -> list of (source, edge) [source depends on target, so target affects source]
        self.reverse_edges: Dict[str, List[GraphEdge]] = defaultdict(list)
        # Fast lookup by entity/file name
        self.name_to_node_ids: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.node_id] = node
        self.name_to_node_ids[node.name].add(node.node_id)
        if node.kind != 'file':
            # Also index by qualified name
            self.name_to_node_ids[node.node_id.replace("entity:", "")].add(node.node_id)

    def add_edge(self, edge: GraphEdge) -> None:
        self.forward_edges[edge.source].append(edge)
        self.reverse_edges[edge.target].append(edge)

    @classmethod
    def build_from_db(cls, conn: sqlite3.Connection, repo_id: int) -> 'DependencyGraph':
        graph = cls()
        cursor = conn.cursor()

        # 1. Load Files
        cursor.execute("SELECT id, path, relative_path, language FROM files WHERE repo_id = ?", (repo_id,))
        files_by_id = {}
        files_by_relpath = {}
        files_by_module = {}  # e.g. "auth.service" -> relative_path

        for row in cursor.fetchall():
            f_id, f_path, rel_path, lang = row[0], row[1], row[2], row[3]
            files_by_id[f_id] = rel_path
            files_by_relpath[rel_path] = f_id

            # Map Python module path to relative path
            clean_rel = rel_path.replace("\\", "/")
            if clean_rel.endswith(".py"):
                clean_rel = clean_rel[:-3]
            if clean_rel.endswith("/__init__"):
                clean_rel = clean_rel[:-9]
            mod_name = clean_rel.replace("/", ".")
            files_by_module[mod_name] = rel_path
            # Also just filename without ext
            base_name = clean_rel.split("/")[-1]
            files_by_module[base_name] = rel_path

            file_node_id = f"file:{rel_path}"
            graph.add_node(GraphNode(
                node_id=file_node_id,
                name=rel_path,
                kind="file",
                file_path=rel_path,
                line_number=1
            ))

        # 2. Load Entities
        cursor.execute("""
            SELECT e.id, e.file_id, e.entity_type, e.name, e.qualified_name,
                   e.start_line, e.signature, e.docstring, f.relative_path
            FROM code_entities e
            JOIN files f ON e.file_id = f.id
            WHERE e.repo_id = ?
        """, (repo_id,))

        entities_by_id = {}
        entities_by_qname = {}
        entities_by_simple_name = defaultdict(list)

        for row in cursor.fetchall():
            e_id, f_id, e_type, name, qname, s_line, sig, doc, rel_path = row
            entity_node_id = f"entity:{qname}"
            entities_by_id[e_id] = entity_node_id
            entities_by_qname[qname] = entity_node_id
            entities_by_simple_name[name].append(entity_node_id)

            graph.add_node(GraphNode(
                node_id=entity_node_id,
                name=name,
                kind=e_type,
                file_path=rel_path,
                line_number=s_line,
                signature=sig,
                docstring=doc
            ))

            # Containment edge: file contains entity
            file_node_id = f"file:{rel_path}"
            graph.add_edge(GraphEdge(
                source=file_node_id,
                target=entity_node_id,
                relation="contains",
                line=s_line
            ))

        # 3. Load Dependencies and Resolve Targets
        cursor.execute("""
            SELECT d.source_type, d.source_id, d.target_type, d.target_id,
                   d.target_name, d.relation_type, d.line_number,
                   f.relative_path as file_path, e.qualified_name as entity_qname
            FROM dependencies d
            LEFT JOIN files f ON d.source_type = 'file' AND d.source_id = f.id
            LEFT JOIN code_entities e ON d.source_type = 'entity' AND d.source_id = e.id
            WHERE d.repo_id = ?
        """, (repo_id,))

        for row in cursor.fetchall():
            s_type, s_id, t_type, t_id, t_name, rel_type, line, f_path, e_qname = row

            # Source Node ID
            if s_type == 'file' and f_path:
                source_node_id = f"file:{f_path}"
                source_file = f_path
            elif s_type == 'entity' and e_qname:
                source_node_id = f"entity:{e_qname}"
                source_file = graph.nodes[source_node_id].file_path if source_node_id in graph.nodes else ""
            else:
                continue

            # Target Node Resolution
            target_node_id = None
            clean_t_name = t_name.strip("'\"")

            # 1. Direct file match
            if clean_t_name in files_by_relpath:
                target_node_id = f"file:{clean_t_name}"
            # 2. Relative import resolution (e.g. './connection', '../models/user')
            elif clean_t_name.startswith('.') and source_file:
                import posixpath
                src_dir = posixpath.dirname(source_file.replace('\\', '/'))
                base_cand = posixpath.normpath(posixpath.join(src_dir, clean_t_name))
                for ext in ('', '.js', '.ts', '.jsx', '.json', '/index.js', '/index.ts', '.py'):
                    test_cand = base_cand + ext
                    if test_cand in files_by_relpath:
                        target_node_id = f"file:{test_cand}"
                        break
            # 3. Known module or filename with extension
            elif clean_t_name in files_by_module:
                target_node_id = f"file:{files_by_module[clean_t_name]}"
            elif f"{clean_t_name}.py" in files_by_relpath:
                target_node_id = f"file:{clean_t_name}.py"
            elif f"{clean_t_name}.js" in files_by_relpath:
                target_node_id = f"file:{clean_t_name}.js"
            elif f"{clean_t_name}.ts" in files_by_relpath:
                target_node_id = f"file:{clean_t_name}.ts"
            # 4. Qualified entity name
            elif clean_t_name in entities_by_qname:
                target_node_id = entities_by_qname[clean_t_name]
            # 5. Simple function or class name (e.g. 'get_user', 'getConnection')
            elif clean_t_name in entities_by_simple_name:
                candidates = entities_by_simple_name[clean_t_name]
                valid_candidates = [c for c in candidates if c != source_node_id]
                if valid_candidates:
                    target_node_id = valid_candidates[0]
            # 6. Method call fallback (e.g. 'db.query' -> 'query')
            elif '.' in clean_t_name:
                method_name = clean_t_name.split('.')[-1]
                if method_name in entities_by_simple_name:
                    candidates = entities_by_simple_name[method_name]
                    valid_candidates = [c for c in candidates if c != source_node_id]
                    if valid_candidates:
                        target_node_id = valid_candidates[0]

            if target_node_id and target_node_id != source_node_id:
                graph.add_edge(GraphEdge(
                    source=source_node_id,
                    target=target_node_id,
                    relation=rel_type,
                    line=line
                ))

        logger.info("Built DependencyGraph with %d nodes and %d edges", len(graph.nodes), sum(len(e) for e in graph.forward_edges.values()))
        return graph

    def get_outgoing(self, node_id: str) -> List[GraphEdge]:
        """Entities or files that node_id depends on (calls, imports)."""
        return self.forward_edges.get(node_id, [])

    def get_incoming(self, node_id: str) -> List[GraphEdge]:
        """Entities or files that depend on node_id (callers, importers)."""
        return self.reverse_edges.get(node_id, [])

    def find_nodes_by_name(self, name: str) -> List[GraphNode]:
        node_ids = self.name_to_node_ids.get(name, set())
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the graph into nodes and links for frontend or API."""
        node_list = [
            {
                "id": n.node_id,
                "name": n.name,
                "kind": n.kind,
                "file_path": n.file_path,
                "line_number": n.line_number,
                "signature": n.signature
            }
            for n in self.nodes.values()
        ]
        edge_list = []
        for src, edges in self.forward_edges.items():
            for e in edges:
                edge_list.append({
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "line": e.line
                })
        return {"nodes": node_list, "edges": edge_list}

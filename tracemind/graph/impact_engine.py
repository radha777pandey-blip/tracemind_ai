import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import deque

from tracemind.graph.graph_engine import DependencyGraph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)

@dataclass
class ImpactedItem:
    node_id: str
    name: str
    kind: str  # file, function, method, class
    file_path: str
    line_number: Optional[int]
    depth: int
    impact_level: str  # HIGH, MEDIUM, LOW
    relation_trail: List[str]
    reason: str

@dataclass
class ImpactReport:
    target: Dict[str, Any]
    total_affected_files: int
    total_affected_entities: int
    highest_risk: str
    summary_text: str
    affected_items: List[ImpactedItem]

class ImpactAnalysisEngine:
    def __init__(self, graph: DependencyGraph):
        self.graph = graph

    def resolve_target_node(
        self,
        file_path: Optional[str] = None,
        entity_name: Optional[str] = None
    ) -> Optional[GraphNode]:
        if not file_path and not entity_name:
            return None

        # Clean file path separators
        norm_file = file_path.replace("\\", "/") if file_path else None

        # Case 1: Specific entity requested
        if entity_name:
            candidates = self.graph.find_nodes_by_name(entity_name)
            if norm_file:
                # Filter candidates by file
                matching = [c for c in candidates if c.file_path == norm_file or c.file_path.endswith(norm_file)]
                if matching:
                    return matching[0]
            if candidates:
                return candidates[0]

        # Case 2: Only file requested
        if norm_file:
            file_node_id = f"file:{norm_file}"
            if file_node_id in self.graph.nodes:
                return self.graph.nodes[file_node_id]
            # Try partial match on filename
            for nid, node in self.graph.nodes.items():
                if node.kind == "file" and (node.file_path == norm_file or node.file_path.endswith(norm_file)):
                    return node

        return None

    def analyze_impact(
        self,
        file_path: Optional[str] = None,
        entity_name: Optional[str] = None,
        max_depth: int = 3
    ) -> ImpactReport:
        target_node = self.resolve_target_node(file_path, entity_name)
        if not target_node:
            raise ValueError(f"Target entity or file not found in dependency graph (file='{file_path}', entity='{entity_name}')")

        # Initial seed nodes to start reverse traversal
        # If target is a file, also seed all entities contained within that file
        seeds = [target_node.node_id]
        if target_node.kind == "file":
            for edge in self.graph.get_outgoing(target_node.node_id):
                if edge.relation == "contains":
                    seeds.append(edge.target)

        # BFS queue: (current_node_id, depth, path_of_edges)
        visited = set(seeds)
        queue = deque([(seed_id, 0, []) for seed_id in seeds])

        impacted_items: List[ImpactedItem] = []
        affected_files: Set[str] = set()
        affected_entities: Set[str] = set()

        while queue:
            curr_id, curr_depth, trail = queue.popleft()

            if curr_depth >= max_depth:
                continue

            # Incoming edges: who depends on curr_id?
            incoming_edges = self.graph.get_incoming(curr_id)

            for edge in incoming_edges:
                dependent_id = edge.source

                # Skip containment if moving from entity to parent file (already tracked)
                if edge.relation == "contains":
                    continue

                new_trail = trail + [f"{edge.source} [{edge.relation}] -> {edge.target}"]
                new_depth = curr_depth + 1

                if dependent_id not in visited:
                    visited.add(dependent_id)
                    dep_node = self.graph.nodes.get(dependent_id)
                    if not dep_node:
                        continue

                    # Determine impact level based on depth
                    if new_depth == 1:
                        impact_level = "HIGH"
                    elif new_depth == 2:
                        impact_level = "MEDIUM"
                    else:
                        impact_level = "LOW"

                    # Generate human-readable reason
                    target_display = f"{target_node.name} ({target_node.kind} in {target_node.file_path})"
                    if new_depth == 1:
                        reason = f"Directly {edge.relation} {target_display} at line {edge.line or 'unknown'}."
                    else:
                        upstream = self.graph.nodes.get(edge.target)
                        upstream_name = upstream.name if upstream else edge.target
                        reason = f"Indirectly affected (depth {new_depth}): {edge.relation} '{upstream_name}', which depends on {target_display}."

                    item = ImpactedItem(
                        node_id=dep_node.node_id,
                        name=dep_node.name,
                        kind=dep_node.kind,
                        file_path=dep_node.file_path,
                        line_number=dep_node.line_number,
                        depth=new_depth,
                        impact_level=impact_level,
                        relation_trail=new_trail,
                        reason=reason
                    )
                    impacted_items.append(item)

                    affected_files.add(dep_node.file_path)
                    if dep_node.kind != "file":
                        affected_entities.add(dep_node.node_id)

                    queue.append((dependent_id, new_depth, new_trail))

        # Determine overall severity
        if any(item.impact_level == "HIGH" for item in impacted_items):
            highest_risk = "HIGH"
        elif any(item.impact_level == "MEDIUM" for item in impacted_items):
            highest_risk = "MEDIUM"
        elif impacted_items:
            highest_risk = "LOW"
        else:
            highest_risk = "NONE"

        # Summary text
        summary_text = (
            f"Modifying '{target_node.name}' ({target_node.kind} in {target_node.file_path}) "
            f"has a {highest_risk} risk profile. "
            f"It potentially impacts {len(affected_files)} file(s) and {len(affected_entities)} entity/entities across the codebase."
        )

        return ImpactReport(
            target={
                "node_id": target_node.node_id,
                "name": target_node.name,
                "kind": target_node.kind,
                "file_path": target_node.file_path,
                "line_number": target_node.line_number,
                "signature": target_node.signature
            },
            total_affected_files=len(affected_files),
            total_affected_entities=len(affected_entities),
            highest_risk=highest_risk,
            summary_text=summary_text,
            affected_items=impacted_items
        )

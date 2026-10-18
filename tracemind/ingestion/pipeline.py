import os
import sqlite3
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

from tracemind.database.connection import get_db
from tracemind.database.db_ops import (
    create_or_get_repository,
    clear_repo_data,
    insert_file,
    insert_code_entity,
    insert_dependency,
    insert_code_chunk,
    update_repo_counts
)
from tracemind.ingestion.scanner import CodebaseScanner
from tracemind.ingestion.parser import CodeParser
from tracemind.ingestion.chunker import StructureAwareChunker
from tracemind.graph.graph_engine import DependencyGraph

logger = logging.getLogger(__name__)

@dataclass
class IngestionResult:
    repo_id: int
    name: str
    path: str
    files_count: int
    entities_count: int
    dependencies_count: int
    chunks_count: int
    languages: Dict[str, int]

class IngestionPipeline:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.scanner = CodebaseScanner()
        self.chunker = StructureAwareChunker()

    def ingest(self, repo_dir: str, repo_name: Optional[str] = None) -> IngestionResult:
        abs_path = os.path.abspath(repo_dir)
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            raise ValueError(f"Invalid repository directory: {repo_dir}")

        name = repo_name or os.path.basename(abs_path) or "repository"
        logger.info("Starting ingestion for '%s' at %s", name, abs_path)

        with get_db(self.db_path) as conn:
            # 1. Create or get repo record
            repo_id = create_or_get_repository(conn, name, abs_path)
            # Clear previous indexed data for this repo to allow clean re-indexing
            clear_repo_data(conn, repo_id)

            # 2. Scan directory
            scanned_files = self.scanner.scan_directory(abs_path, load_content=True)

            total_entities = 0
            total_deps = 0
            total_chunks = 0
            lang_counts: Dict[str, int] = {}

            # First pass: insert all files
            file_ids: Dict[str, int] = {}
            for sf in scanned_files:
                lang_counts[sf.language] = lang_counts.get(sf.language, 0) + 1
                f_id = insert_file(
                    conn=conn,
                    repo_id=repo_id,
                    path=sf.path,
                    relative_path=sf.relative_path,
                    language=sf.language,
                    size_bytes=sf.size_bytes,
                    file_hash=sf.file_hash,
                    line_count=sf.line_count
                )
                file_ids[sf.relative_path] = f_id

            # Second pass: parse entities, dependencies, and chunks
            for sf in scanned_files:
                if not sf.content:
                    continue

                f_id = file_ids[sf.relative_path]
                parse_result = CodeParser.parse_file(sf.relative_path, sf.content, sf.language)

                # Store Entities
                entity_map: Dict[str, int] = {}
                for entity in parse_result.entities:
                    e_id = insert_code_entity(
                        conn=conn,
                        repo_id=repo_id,
                        file_id=f_id,
                        entity_type=entity.entity_type,
                        name=entity.name,
                        qualified_name=entity.qualified_name,
                        start_line=entity.start_line,
                        end_line=entity.end_line,
                        signature=entity.signature,
                        docstring=entity.docstring,
                        parent_entity_id=None
                    )
                    entity_map[entity.qualified_name] = e_id
                    entity_map[entity.name] = e_id
                    total_entities += 1

                # Store Dependencies
                for dep in parse_result.dependencies:
                    # Check if source is entity or file
                    if dep.source_name in entity_map:
                        s_type = "entity"
                        s_id = entity_map[dep.source_name]
                    else:
                        s_type = "file"
                        s_id = f_id

                    insert_dependency(
                        conn=conn,
                        repo_id=repo_id,
                        source_type=s_type,
                        source_id=s_id,
                        target_type="unresolved",
                        target_id=None,
                        target_name=dep.target_name,
                        relation_type=dep.relation_type,
                        line_number=dep.line_number
                    )
                    total_deps += 1

                # Chunking
                chunks = self.chunker.chunk_file(sf.relative_path, sf.content, parse_result.entities)
                for chunk in chunks:
                    matched_entity_id = entity_map.get(chunk.entity_name) if chunk.entity_name else None
                    insert_code_chunk(
                        conn=conn,
                        repo_id=repo_id,
                        file_id=f_id,
                        entity_id=matched_entity_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line
                    )
                    total_chunks += 1

            # Update repository metadata counts
            update_repo_counts(conn, repo_id)

        logger.info(
            "Ingestion complete for repo_id=%d: %d files, %d entities, %d dependencies, %d chunks",
            repo_id, len(scanned_files), total_entities, total_deps, total_chunks
        )

        return IngestionResult(
            repo_id=repo_id,
            name=name,
            path=abs_path,
            files_count=len(scanned_files),
            entities_count=total_entities,
            dependencies_count=total_deps,
            chunks_count=total_chunks,
            languages=lang_counts
        )

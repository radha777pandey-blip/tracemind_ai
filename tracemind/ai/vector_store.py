import sqlite3
import logging
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from tracemind.ai.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    chunk_id: int
    repo_id: int
    file_id: int
    file_path: str
    entity_name: Optional[str]
    content: str
    start_line: int
    end_line: int
    score: float

class LocalVectorStore:
    def __init__(self):
        self.chunk_ids: List[int] = []
        self.metadata: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None  # Shape (N, D)

    def load_from_db(self, conn: sqlite3.Connection, repo_id: int, embedding_engine: EmbeddingEngine) -> int:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.repo_id, c.file_id, c.entity_id, c.chunk_index,
                   c.content, c.start_line, c.end_line, c.embedding,
                   f.relative_path, e.name as entity_name
            FROM code_chunks c
            JOIN files f ON c.file_id = f.id
            LEFT JOIN code_entities e ON c.entity_id = e.id
            WHERE c.repo_id = ?
            ORDER BY c.id ASC
        """, (repo_id,))

        rows = cursor.fetchall()
        if not rows:
            return 0

        vector_list = []
        self.chunk_ids = []
        self.metadata = []

        updates_to_save = []

        for row in rows:
            c_id, r_id, f_id, e_id, idx, content, s_line, e_line, emb_blob, rel_path, ent_name = row
            
            vec = None
            if emb_blob:
                try:
                    loaded_vec = np.frombuffer(emb_blob, dtype=np.float32)
                    if loaded_vec.shape == (embedding_engine.dimension,):
                        vec = loaded_vec
                except Exception:
                    vec = None

            if vec is None:
                vec = embedding_engine.embed_text(content)
                updates_to_save.append((vec.tobytes(), c_id))

            vector_list.append(vec)
            self.chunk_ids.append(c_id)
            self.metadata.append({
                "chunk_id": c_id,
                "repo_id": r_id,
                "file_id": f_id,
                "file_path": rel_path,
                "entity_name": ent_name,
                "content": content,
                "start_line": s_line,
                "end_line": e_line
            })

        if updates_to_save:
            cursor.executemany("UPDATE code_chunks SET embedding = ? WHERE id = ?", updates_to_save)
            conn.commit()
            logger.info("Re-indexed/updated %d chunks with %d-dim embeddings", len(updates_to_save), embedding_engine.dimension)

        self.vectors = np.vstack(vector_list) if vector_list else None
        logger.info("Loaded %d vectors into LocalVectorStore for repo_id=%d", len(self.chunk_ids), repo_id)
        return len(self.chunk_ids)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        if self.vectors is None or len(self.chunk_ids) == 0:
            return []

        if query_vec.shape[0] != self.vectors.shape[1]:
            logger.warning(
                "Query vector dimension %d does not match index vector dimension %d. Returning empty results.",
                query_vec.shape[0], self.vectors.shape[1]
            )
            return []

        scores = np.dot(self.vectors, query_vec)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            meta = self.metadata[idx]
            results.append(SearchResult(
                chunk_id=meta["chunk_id"],
                repo_id=meta["repo_id"],
                file_id=meta["file_id"],
                file_path=meta["file_path"],
                entity_name=meta["entity_name"],
                content=meta["content"],
                start_line=meta["start_line"],
                end_line=meta["end_line"],
                score=float(scores[idx])
            ))
        return results

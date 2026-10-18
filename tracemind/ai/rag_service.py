import os
import sqlite3
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from tracemind.config import get_gemini_api_key
from tracemind.ai.embeddings import EmbeddingEngine
from tracemind.ai.vector_store import LocalVectorStore, SearchResult
from tracemind.graph.graph_engine import DependencyGraph
from tracemind.graph.impact_engine import ImpactAnalysisEngine

logger = logging.getLogger(__name__)

@dataclass
class SourceCitation:
    file_path: str
    entity_name: Optional[str]
    start_line: int
    end_line: int
    snippet: str

@dataclass
class QAResponse:
    query: str
    answer: str
    citations: List[SourceCitation]
    mode: str  # 'gemini_generation', 'local_synthesis', or 'no_results'

class CodebaseQAService:
    def __init__(self, db_conn: sqlite3.Connection, repo_id: int):
        self.conn = db_conn
        self.repo_id = repo_id
        self.embedding_engine = EmbeddingEngine()
        self.vector_store = LocalVectorStore()
        self.vector_store.load_from_db(self.conn, self.repo_id, self.embedding_engine)
        self.graph = DependencyGraph.build_from_db(self.conn, self.repo_id)

    def _local_synthesize_answer(self, query: str, retrieved_chunks: List[SearchResult]) -> str:
        """Deterministic, grounded synthesis when no external LLM key is configured or Gemini fails."""
        if not retrieved_chunks:
            return f"No relevant code components found in this repository for query: '{query}'."

        files_found = list(dict.fromkeys([c.file_path for c in retrieved_chunks]))
        entities_found = list(dict.fromkeys([c.entity_name for c in retrieved_chunks if c.entity_name]))

        lines = [
            f"Based on local codebase analysis for query: '{query}':\n",
            f"### Primary Relevant Files:",
        ]
        for f in files_found:
            lines.append(f"- `{f}`")

        if entities_found:
            lines.append(f"\n### Relevant Code Entities:")
            for e in entities_found:
                lines.append(f"- `{e}`")

        lines.append(f"\n### Grounded Evidence Snippets:")
        for i, chunk in enumerate(retrieved_chunks[:4], 1):
            entity_label = f" (in `{chunk.entity_name}`)" if chunk.entity_name else ""
            lines.append(f"\n**{i}. `{chunk.file_path}` (Lines {chunk.start_line}-{chunk.end_line}){entity_label}:**")
            code_preview = "\n".join(chunk.content.splitlines()[:12])
            lines.append(f"```\n{code_preview}\n```")

        lines.append("\n> *Response generated via local semantic retrieval & synthesis (Gemini API not used).*")
        return "\n".join(lines)

    def query(self, user_question: str, top_k: int = 4) -> QAResponse:
        # 1. Embed and retrieve relevant chunks
        query_vec = self.embedding_engine.embed_text(user_question)
        chunks = self.vector_store.search(query_vec, top_k=top_k)

        if not chunks:
            return QAResponse(
                query=user_question,
                answer=f"No relevant code components found in this repository for query: '{user_question}'. Try querying for specific functions, files, or concepts existing in the codebase.",
                citations=[],
                mode="no_results"
            )

        # 2. Build citations
        citations = [
            SourceCitation(
                file_path=c.file_path,
                entity_name=c.entity_name,
                start_line=c.start_line,
                end_line=c.end_line,
                snippet=c.content[:200] + ("..." if len(c.content) > 200 else "")
            )
            for c in chunks
        ]

        # 3. Check if Gemini API is available
        api_key = get_gemini_api_key()
        client = self.embedding_engine.client
        if not client and api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
            except Exception as ex:
                logger.warning("Could not initialize genai.Client for Q&A: %s", ex)

        if client and api_key:
            try:
                context_blocks = []
                for c in chunks:
                    context_blocks.append(
                        f"File: {c.file_path} (lines {c.start_line}-{c.end_line})\n"
                        f"Entity: {c.entity_name or 'N/A'}\n"
                        f"Code:\n{c.content}\n"
                    )
                context_str = "\n---\n".join(context_blocks)

                system_prompt = (
                    "You are TraceMind AI, an expert codebase understanding assistant. "
                    "Answer the user's question about the codebase based STRICTLY on the provided code context. "
                    "Reference specific files, line numbers, and function/class names in your explanation. "
                    "If the answer cannot be determined from the context, clearly say so."
                )

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"{system_prompt}\n\nContext:\n{context_str}\n\nQuestion: {user_question}"
                )

                if response and response.text:
                    return QAResponse(
                        query=user_question,
                        answer=response.text.strip(),
                        citations=citations,
                        mode="gemini_generation"
                    )
            except Exception as e:
                logger.warning("Gemini generation call failed (%s), falling back to grounded synthesizer.", e)

        # Fallback to local grounded synthesis
        answer = self._local_synthesize_answer(user_question, chunks)
        return QAResponse(
            query=user_question,
            answer=answer,
            citations=citations,
            mode="local_synthesis"
        )


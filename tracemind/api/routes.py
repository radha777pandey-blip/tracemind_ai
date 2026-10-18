import os
import re
import uuid
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from tracemind.config import WORKSPACES_DIR
from tracemind.ingestion.zip_handler import safe_extract_zip
from tracemind.database.connection import get_db
from tracemind.database.db_ops import (
    get_repository,
    list_repositories,
    get_repository_files,
    get_repository_entities,
    get_repository_dependencies
)
from tracemind.ingestion.pipeline import IngestionPipeline
from tracemind.graph.graph_engine import DependencyGraph
from tracemind.graph.impact_engine import ImpactAnalysisEngine
from tracemind.ai.rag_service import CodebaseQAService
from tracemind.api.schemas import (
    IngestRequest,
    IngestResponse,
    RepositoryResponse,
    FileItemResponse,
    EntityItemResponse,
    DependencyItemResponse,
    ImpactRequest,
    ImpactResponse,
    ImpactedItemResponse,
    QueryRequest,
    QueryResponse,
    CitationResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["TraceMind"])

@router.post("/repositories/upload-zip", response_model=IngestResponse)
async def upload_zip_repository(
    file: UploadFile = File(..., description="ZIP archive of the codebase"),
    name: Optional[str] = Form(None, description="Optional name for the repository")
):
    """Safely extracts a multipart ZIP archive and indexes it into TraceMind."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip archive files are supported.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Uploaded ZIP file exceeds 100MB limit.")

    clean_base_name = Path(file.filename).stem
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', clean_base_name) or "project"
    repo_name = name or clean_base_name

    unique_folder = f"{safe_name}_{uuid.uuid4().hex[:8]}"
    dest_workspace = WORKSPACES_DIR / unique_folder

    try:
        effective_dir = safe_extract_zip(contents, str(dest_workspace))
        pipeline = IngestionPipeline()
        result = pipeline.ingest(effective_dir, repo_name)
        return IngestResponse(
            repo_id=result.repo_id,
            name=result.name,
            path=result.path,
            files_count=result.files_count,
            entities_count=result.entities_count,
            dependencies_count=result.dependencies_count,
            chunks_count=result.chunks_count,
            languages=result.languages
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Failed processing ZIP archive upload: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed processing ZIP archive: {str(e)}")

@router.post("/repositories/ingest", response_model=IngestResponse)
def ingest_repository(req: IngestRequest):
    """Scans, parses, chunks, and indexes a local codebase directory."""
    if not os.path.exists(req.path):
        raise HTTPException(status_code=400, detail=f"Directory not found: {req.path}")

    try:
        pipeline = IngestionPipeline()
        result = pipeline.ingest(req.path, req.name)
        return IngestResponse(
            repo_id=result.repo_id,
            name=result.name,
            path=result.path,
            files_count=result.files_count,
            entities_count=result.entities_count,
            dependencies_count=result.dependencies_count,
            chunks_count=result.chunks_count,
            languages=result.languages
        )
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories", response_model=List[RepositoryResponse])
def get_repositories():
    """Lists all ingested repositories."""
    with get_db() as conn:
        repos = list_repositories(conn)
        return [
            RepositoryResponse(
                id=r["id"],
                name=r["name"],
                path=r["path"],
                file_count=r["file_count"] or 0,
                entity_count=r["entity_count"] or 0,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"])
            )
            for r in repos
        ]

@router.get("/repositories/{repo_id}", response_model=RepositoryResponse)
def get_repository_details(repo_id: int):
    """Fetches metadata for a specific repository."""
    with get_db() as conn:
        r = get_repository(conn, repo_id)
        if not r:
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        return RepositoryResponse(
            id=r["id"],
            name=r["name"],
            path=r["path"],
            file_count=r["file_count"] or 0,
            entity_count=r["entity_count"] or 0,
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"])
        )

@router.get("/repositories/{repo_id}/files", response_model=List[FileItemResponse])
def get_files(repo_id: int):
    """Lists all parsed source files in the repository."""
    with get_db() as conn:
        if not get_repository(conn, repo_id):
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        files = get_repository_files(conn, repo_id)
        return [
            FileItemResponse(
                id=f["id"],
                relative_path=f["relative_path"],
                language=f["language"],
                size_bytes=f["size_bytes"],
                line_count=f["line_count"]
            )
            for f in files
        ]

@router.get("/repositories/{repo_id}/entities", response_model=List[EntityItemResponse])
def get_entities(repo_id: int):
    """Lists all detected code entities (functions, classes, methods)."""
    with get_db() as conn:
        if not get_repository(conn, repo_id):
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        entities = get_repository_entities(conn, repo_id)
        return [
            EntityItemResponse(
                id=e["id"],
                name=e["name"],
                qualified_name=e["qualified_name"],
                entity_type=e["entity_type"],
                file_path=e["file_path"],
                start_line=e["start_line"],
                end_line=e["end_line"],
                signature=e["signature"],
                docstring=e["docstring"]
            )
            for e in entities
        ]

@router.get("/repositories/{repo_id}/dependencies", response_model=List[DependencyItemResponse])
def get_dependencies(repo_id: int):
    """Lists all extracted relationships (imports, calls, inherits)."""
    with get_db() as conn:
        if not get_repository(conn, repo_id):
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        deps = get_repository_dependencies(conn, repo_id)
        return [
            DependencyItemResponse(
                id=d["id"],
                source_type=d["source_type"],
                source_name=d["source_name"],
                target_name=d["target_name"],
                relation_type=d["relation_type"],
                line_number=d["line_number"]
            )
            for d in deps
        ]

@router.get("/repositories/{repo_id}/graph")
def get_graph(repo_id: int):
    """Returns node-link graph data formatted for visualization."""
    with get_db() as conn:
        if not get_repository(conn, repo_id):
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        graph = DependencyGraph.build_from_db(conn, repo_id)
        return graph.to_dict()

@router.post("/repositories/{repo_id}/impact-analysis", response_model=ImpactResponse)
def run_impact_analysis(repo_id: int, req: ImpactRequest):
    """Computes blast radius and explanation trail for a modified file or entity."""
    with get_db() as conn:
        if not get_repository(conn, repo_id):
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        graph = DependencyGraph.build_from_db(conn, repo_id)

    engine = ImpactAnalysisEngine(graph)
    try:
        report = engine.analyze_impact(
            file_path=req.file_path,
            entity_name=req.entity_name,
            max_depth=req.max_depth
        )
        return ImpactResponse(
            target=report.target,
            total_affected_files=report.total_affected_files,
            total_affected_entities=report.total_affected_entities,
            highest_risk=report.highest_risk,
            summary_text=report.summary_text,
            affected_items=[
                ImpactedItemResponse(
                    node_id=item.node_id,
                    name=item.name,
                    kind=item.kind,
                    file_path=item.file_path,
                    line_number=item.line_number,
                    depth=item.depth,
                    impact_level=item.impact_level,
                    relation_trail=item.relation_trail,
                    reason=item.reason
                )
                for item in report.affected_items
            ]
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Impact analysis error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/repositories/{repo_id}/query", response_model=QueryResponse)
def query_codebase(repo_id: int, req: QueryRequest):
    """Grounded semantic QA over codebase with citations."""
    with get_db() as conn:
        if not get_repository(conn, repo_id):
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        qa_service = CodebaseQAService(conn, repo_id)

    try:
        res = qa_service.query(req.query, top_k=req.top_k)
        return QueryResponse(
            query=res.query,
            answer=res.answer,
            citations=[
                CitationResponse(
                    file_path=c.file_path,
                    entity_name=c.entity_name,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    snippet=c.snippet
                )
                for c in res.citations
            ],
            mode=res.mode
        )
    except Exception as e:
        logger.exception("QA query error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


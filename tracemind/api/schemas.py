from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class IngestRequest(BaseModel):
    path: str = Field(..., description="Local directory path of the codebase to ingest")
    name: Optional[str] = Field(None, description="Optional name for the repository")

class IngestResponse(BaseModel):
    repo_id: int
    name: str
    path: str
    files_count: int
    entities_count: int
    dependencies_count: int
    chunks_count: int
    languages: Dict[str, int]

class RepositoryResponse(BaseModel):
    id: int
    name: str
    path: str
    file_count: int
    entity_count: int
    created_at: str
    updated_at: str

class FileItemResponse(BaseModel):
    id: int
    relative_path: str
    language: str
    size_bytes: int
    line_count: int

class EntityItemResponse(BaseModel):
    id: int
    name: str
    qualified_name: str
    entity_type: str
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None

class DependencyItemResponse(BaseModel):
    id: int
    source_type: str
    source_name: Optional[str] = None
    target_name: str
    relation_type: str
    line_number: Optional[int] = None

class ImpactRequest(BaseModel):
    file_path: Optional[str] = Field(None, description="Path of modified file (e.g. auth.py)")
    entity_name: Optional[str] = Field(None, description="Name of modified function or class (e.g. get_user)")
    max_depth: int = Field(3, ge=1, le=5, description="Graph traversal depth")

class ImpactedItemResponse(BaseModel):
    node_id: str
    name: str
    kind: str
    file_path: str
    line_number: Optional[int]
    depth: int
    impact_level: str
    relation_trail: List[str]
    reason: str

class ImpactResponse(BaseModel):
    target: Dict[str, Any]
    total_affected_files: int
    total_affected_entities: int
    highest_risk: str
    summary_text: str
    affected_items: List[ImpactedItemResponse]

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Question about the codebase")
    top_k: int = Field(4, ge=1, le=10, description="Number of relevant code chunks to retrieve")

class CitationResponse(BaseModel):
    file_path: str
    entity_name: Optional[str] = None
    start_line: int
    end_line: int
    snippet: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationResponse]
    mode: str

# TraceMind AI

> **AI-Powered Codebase Understanding & Change-Impact Analysis Engine**
> Final-Year Computer Science & Engineering Capstone Project

---

## Overview

When developers work on non-trivial codebases, understanding interconnected components becomes difficult:
- Which files depend on each other?
- Where is a specific function or class called?
- What is the blast radius when modifying an existing function or class?
- What parts of the codebase will break if a contract changes, and **why**?

**TraceMind AI** solves this problem by combining:
1. **AST-Based Code Analysis**: Real Abstract Syntax Tree parsing extracting functions, classes, methods, docstrings, imports, and call sites.
2. **Deterministic Dependency Graph**: Directed multigraph representing file imports, containment, function calls, and class inheritance.
3. **Change-Impact Analysis Engine**: Breadth-First Search (BFS) reverse graph traversal calculating blast radius, impact severity (HIGH, MEDIUM, LOW), and step-by-step reasoning trails.
4. **Local Vector Store & Semantic RAG**: Lightweight NumPy-backed vector store for cosine similarity code chunk retrieval, with verified line-level source citations.
5. **Interactive UI & REST API**: Clean FastAPI backend with an embedded web dashboard and interactive OpenAPI documentation.

---

## Architecture

`
[Local Codebase]
       │
       ▼
[1. File Scanner] ──(Recursive traversal, filters .git, venv, node_modules)
       │
       ▼
[2. AST Code Parser] ──(Python standard library st + JS/TS extractor)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[3. Logical Chunker]            [4. Dependency Graph Engine]
(Function & class boundaries)     (Nodes: Files & Entities; Edges: Imports & Calls)
       │                                 │
       ▼                                 ▼
[5. Local Vector Store]         [6. Impact Analysis Engine]
(NumPy float32 + SQLite)         (Reverse BFS blast radius & reasoning)
       │                                 │
       └──────────────┬──────────────────┘
                      ▼
            [7. FastAPI REST Layer]
             GET /  •  /api/repositories/*
`

---

## Project Structure

`
tracemind/
├── requirements.txt            # Python dependencies (FastAPI, NumPy, Uvicorn, etc.)
├── .env.example                # Environment variables template
├── demo.py                     # Standalone viva/interview demonstration script
├── tracemind.db                # SQLite database (WAL mode)
├── tracemind/
│   ├── config.py               # Central configuration & thresholds
│   ├── database/
│   │   ├── connection.py       # SQLite connection with foreign keys & WAL
│   │   ├── schema.py           # Relational schema (repositories, files, entities, deps, chunks)
│   │   └── db_ops.py           # High-performance CRUD operations
│   ├── ingestion/
│   │   ├── scanner.py          # Directory scanner, language detector, BOM stripper
│   │   ├── parser.py           # Python AST parser & JS/TS symbol extractor
│   │   ├── chunker.py          # Structure-aware logical chunker
│   │   └── pipeline.py         # End-to-end ingestion orchestrator
│   ├── graph/
│   │   ├── graph_engine.py     # Directed dependency & call graph
│   │   └── impact_engine.py    # Change-impact blast radius & explanation generator
│   ├── ai/
│   │   ├── embeddings.py       # Normalized embedding engine (Gemini API + local fallback)
│   │   ├── vector_store.py     # Local NumPy vector database with cosine similarity
│   │   └── rag_service.py      # Grounded Q&A service with verified source citations
│   └── api/
│       ├── schemas.py          # Pydantic request/response models
│       ├── routes.py           # REST endpoints
│       └── app.py              # FastAPI application & web dashboard
├── samples/
│   └── ecommerce/              # Realistic multi-file sample microservice
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       ├── payment.py
│       ├── orders.py
│       └── main.py
└── tests/
    ├── test_database.py        # SQLite schema & CRUD tests
    ├── test_scanner.py         # Directory scanning & ignore rule tests
    ├── test_parser.py          # AST & JS symbol extraction tests
    ├── test_chunker.py         # Structure-aware chunking tests
    ├── test_graph.py           # Dependency graph & impact traversal tests
    ├── test_vector_store.py    # Vector similarity search tests
    ├── test_rag.py             # Grounded RAG Q&A tests
    ├── test_pipeline.py        # Ingestion integration tests
    └── test_api.py             # FastAPI REST endpoint tests
`

---

## Quick Start Guide

### 1. Installation

`ash
# Clone or navigate to the repository
cd tracemind

# Install dependencies
pip install -r requirements.txt
`

### 2. Run All Automated Tests

Run the full test suite (17 automated unit and integration tests):
`ash
python -m pytest -v
`

### 3. Run the Standalone Viva / CLI Demo

Execute the 10-step end-to-end demonstration:
`ash
python demo.py
`

### 4. Start the Web Dashboard & API Server

`ash
uvicorn tracemind.api.app:app --reload --host 127.0.0.1 --port 8000
`
- Open **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/repositories/ingest | Scans, parses AST, chunks, and indexes a local codebase directory |
| GET | /api/repositories | Lists all ingested repositories |
| GET | /api/repositories/{id} | Fetches repository details & file/entity statistics |
| GET | /api/repositories/{id}/files | Lists all indexed files with line counts |
| GET | /api/repositories/{id}/entities | Lists all detected functions, classes, and methods |
| GET | /api/repositories/{id}/dependencies | Lists all extracted import, call, and inheritance relationships |
| GET | /api/repositories/{id}/graph | Returns complete node-link graph data for visualization |
| POST | /api/repositories/{id}/impact-analysis | **Core Feature**: Computes blast radius and explanation trail for a modified file or entity |
| POST | /api/repositories/{id}/query | Semantic Q&A with grounded citations |
| GET | /api/health | Health check endpoint |

---

## Viva / Interview Explanation Guide

1. **Why AST over regex for code understanding?**
   Regex fails on nested blocks, multi-line arguments, comments, and scope. Python's st module builds a syntax tree that guarantees 100% precision for class definitions, function signatures, and call expressions.
2. **How does Change-Impact Analysis work?**
   When an entity E is changed, the engine queries the reverse call/dependency graph using BFS up to depth $. Direct callers/importers receive HIGH risk (depth 1), callers-of-callers receive MEDIUM risk (depth 2), and transitive callers receive LOW risk (depth 3+), retaining the exact chain of calls as evidence.
3. **Why local NumPy vector store instead of Chroma/Pinecone?**
   Eliminates external database dependencies, avoids platform-specific binary wheel compilation issues, and computes cosine similarity in $<1$ ms for codebases with thousands of chunks.


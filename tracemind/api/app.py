import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from tracemind.database.connection import get_db
from tracemind.database.schema import init_db
from tracemind.api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('tracemind')

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database schema is created
    logger.info('Ensuring TraceMind database schema is initialized...')
    with get_db() as conn:
        init_db(conn)
    yield
    logger.info('Shutting down TraceMind API.')

app = FastAPI(
    title='TraceMind AI API',
    description='AI-Powered Codebase Understanding & Change-Impact Analysis Engine',
    version='1.0.0',
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(api_router)

@app.get('/api/health')
def health_check():
    return {'status': 'healthy', 'system': 'TraceMind AI', 'version': '1.0.0'}

@app.get('/', response_class=HTMLResponse)
def index():
    if INDEX_HTML_PATH.exists():
        return HTMLResponse(content=INDEX_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>TraceMind AI</h1><p>index.html not found</p>")

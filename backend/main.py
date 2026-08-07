"""
backend/main.py
─────────────────────────────────────────────────────────────
FastAPI application entry point for the Enterprise Multi-Agent
Knowledge Assistant backend.

Module 3: Document Upload & Management API
Module 4: Processing pipeline (text extraction, chunking,
          Local embedding, FAISS indexing)
Module 5: Groq LLM Integration (Llama 3.3 70B Versatile direct chat, health, config)
Module 6: RAG – Retrieval-Augmented Generation (FAISS search + Groq Llama 3.3 70B)
Module 7+: LangGraph multi-agent workflows
─────────────────────────────────────────────────────────────
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.documents import router as documents_router
from api.processing import router as processing_router
from api.chat import router as chat_router       # Module 5/6
from api.rag import router as rag_router         # Module 6

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Enterprise AI Assistant Backend starting (Modules 4, 5 & 6)")
    logger.info("=" * 60)

    # Pre-load FAISS index
    try:
        from processing.vector_store import get_vector_store
        vs = get_vector_store()
        stats = vs.get_stats()
        logger.info(
            "FAISS index loaded: %d vectors across %d documents",
            stats["total_vectors"], stats["total_documents"],
        )
    except Exception as exc:
        logger.warning("FAISS pre-load failed (will init on first request): %s", exc)

    # Validate Groq API key
    if not os.getenv("GROQ_API_KEY"):
        logger.warning(
            "⚠️  GROQ_API_KEY is not set. "
            "LLM generation will fail until configured in backend/.env"
        )
    else:
        logger.info("✅ GROQ_API_KEY detected — Groq LLM (llama-3.3-70b-versatile) ready")

    # Pre-warm LLM service singleton (Module 5)
    try:
        from services.llm_service import get_llm_service
        get_llm_service()
        logger.info(
            "✅ Groq LLM service ready: model=%s",
            os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        )
    except Exception as exc:
        logger.warning("LLM service pre-warm failed (will init on first request): %s", exc)

    # Pre-warm Retriever Service (Module 6)
    try:
        from services.retriever_service import get_retriever_service
        rs = get_retriever_service()
        logger.info(
            "✅ Retriever service ready: embedder=%s | index_vectors=%d",
            rs._embedder._model_name if hasattr(rs._embedder, '_model_name') else 'local',
            rs._vector_store.get_stats()["total_vectors"],
        )
    except Exception as exc:
        logger.warning("Retriever service pre-warm failed (will init on first request): %s", exc)

    logger.info("✅ Backend ready — docs at http://localhost:8000/docs")
    yield

    # Shutdown
    logger.info("🛑 Backend shutting down...")


# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="Enterprise Multi-Agent Knowledge Assistant API",
    description=(
        "**Module 3**: Document Upload & Management\n\n"
        "**Module 4**: AI Processing Pipeline "
        "(Text Extraction → Chunking → Local Embeddings → FAISS Index)\n\n"
        "**Module 5**: Groq LLM Integration (Llama 3.3 70B) — `POST /api/chat`\n\n"
        "**Module 6**: RAG — `POST /api/rag/chat`, `POST /api/rag/search`, "
        "`GET /api/rag/health`\n\n"
        "**Module 7+**: LangGraph Multi-Agent Workflows"
    ),
    version="0.7.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    "http://localhost:5173",    # Vite dev server
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",    # Alternative dev
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────

app.include_router(documents_router, prefix="/api")
app.include_router(processing_router, prefix="/api")   # Module 4
app.include_router(chat_router,       prefix="/api")   # Module 5/6
app.include_router(rag_router,        prefix="/api")   # Module 6

# ── Health check ──────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "version": app.version, "modules": ["3", "4", "5", "6"]}


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

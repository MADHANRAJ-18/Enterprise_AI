import os

import logging

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from api.documents import router as documents_router

from api.processing import router as processing_router

from api.chat import router as chat_router

from api.rag import router as rag_router

from api.conversations import router as conversations_router

from api.agent import router as agent_router
from api.notifications import router as notifications_router

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",

    datefmt="%H:%M:%S",

)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Enterprise AI Assistant Backend starting (Modules 4-9)")
    logger.info("=" * 60)

    # Run heavy pre-warming in background task without blocking incoming HTTP requests
    async def _async_prewarm():
        try:
            from processing.vector_store import get_vector_store
            vs = get_vector_store()
            stats = vs.get_stats()
            logger.info("FAISS index loaded: %d vectors across %d documents", stats["total_vectors"], stats["total_documents"])
        except Exception as exc:
            logger.warning("FAISS pre-load: %s", exc)

        try:
            from services.llm_service import get_llm_service
            get_llm_service()
            logger.info("✅ LLM service ready")
        except Exception as exc:
            logger.warning("LLM service pre-warm: %s", exc)

        try:
            from services.retriever_service import get_retriever_service
            get_retriever_service()
            logger.info("✅ Retriever service ready")
        except Exception as exc:
            logger.warning("Retriever service pre-warm: %s", exc)

    import asyncio
    asyncio.create_task(_async_prewarm())

    logger.info("✅ Backend ready — docs at http://localhost:8000/docs")
    yield
    logger.info("🛑 Backend shutting down...")

app = FastAPI(

    title="Enterprise Multi-Agent Knowledge Assistant API",

    description=(

        "**Module 3**: Document Upload & Management\n\n"

        "**Module 4**: AI Processing Pipeline "

        "(Text Extraction → Chunking → Embeddings → FAISS Index)\n\n"

        "**Module 5**: Gemini LLM Integration — `POST /api/chat`\n\n"

        "**Module 6**: RAG — `POST /api/rag/chat`, `POST /api/rag/search`, "

        "`GET /api/rag/health`\n\n"

        "**Module 7**: LangGraph Multi-Agent Orchestration — `POST /api/agent/chat`\n\n"

        "Workflow: Coordinator → Retrieval → [Summarizer×3 parallel] → "

        "[Comparison/Gap Analysis] → Citation → Answer\n\n"

        "Intents: `question_answering` | `summarization` | `comparison` | `gap_analysis`"

    ),

    version="0.9.0",

    lifespan=lifespan,

    docs_url="/docs",

    redoc_url="/redoc",

)

ALLOWED_ORIGINS = [

    "http://localhost:5173",

    "http://localhost:5174",

    "http://localhost:5175",

    "http://localhost:3000",

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

app.include_router(documents_router,     prefix="/api")

app.include_router(processing_router,    prefix="/api")

app.include_router(chat_router,          prefix="/api")

app.include_router(rag_router,           prefix="/api")

app.include_router(conversations_router, prefix="/api")

app.include_router(agent_router,         prefix="/api")

app.include_router(notifications_router, prefix="/api")

@app.get("/health", tags=["Health"])

async def health_check():
    return {"status": "ok", "version": app.version, "modules": ["3", "4", "5", "6", "7"]}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

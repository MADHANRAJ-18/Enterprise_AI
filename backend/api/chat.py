from __future__ import annotations

import os

import logging

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, UploadFile, File

from models.chat import (

    ChatRequest,

    ChatResponse,

    ChatErrorResponse,

    LLMHealthResponse,

    ChatParseFileResponse,

)

from models.rag import DocumentChunk

from services.llm_service import get_llm_service

from services.prompt_builder import get_prompt_builder

from services.citation_service import optimize_citations

from processing.loaders import load_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat – Module 5/6"])

@router.post(

    "/parse-file",

    response_model=ChatParseFileResponse,

    summary="Extract text transiently from a file uploaded directly in AI Chat",

    description="Extract text from PDF, DOCX, TXT, CSV, or MD without persisting to database or vector store.",

)

async def parse_chat_file(file: UploadFile = File(...)) -> ChatParseFileResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    ext = os.path.splitext(file.filename)[1].lstrip(".").upper()

    if not ext:
        ext = "TXT"

    if ext in ("PDF", "DOCX"):
        file_type_loader = ext

    else:
        file_type_loader = "TXT"

    try:
        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        doc = load_document(content, file_type_loader)

        return ChatParseFileResponse(

            filename=file.filename,

            file_type=ext,

            char_count=len(doc.full_text),

            page_count=doc.page_count,

            text=doc.full_text,

        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        logger.error("Failed to parse chat attachment: %s", exc)

        raise HTTPException(status_code=500, detail=f"Failed to process file: {exc}")

GREETING_RESPONSES = {
    "hi": "Hello! How can I assist you with your company documents and knowledge base today?",
    "hello": "Hello! How can I help you today? Feel free to ask about company policies, documents, or tasks.",
    "hey": "Hey there! How can I assist you today?",
    "heya": "Hello! How can I help you today?",
    "hi there": "Hello! What can I help you find today?",
    "hello there": "Hello! How can I assist you today?",
    "good morning": "Good morning! How can I help you today?",
    "good afternoon": "Good afternoon! How can I help you today?",
    "good evening": "Good evening! How can I help you today?",
    "howdy": "Howdy! How can I assist you today?",
    "thanks": "You're very welcome! Let me know if you need anything else.",
    "thank you": "You're welcome! Feel free to ask if you have more questions.",
    "who are you": "I am your Enterprise AI Knowledge Assistant. I help you search, summarize, and understand uploaded company documents and policies.",
    "what can you do": "I can answer questions based on your company documents, summarize reports, compare policies, perform gap analysis, and provide precise citations.",
    "help": "You can ask me questions about your uploaded documents, search company policies, request summaries, or ask for document comparisons. How can I help?",
}

@router.post(

    "",

    response_model=ChatResponse,

    responses={

        400: {"model": ChatErrorResponse, "description": "Invalid request"},

        429: {"model": ChatErrorResponse, "description": "Rate limit hit"},

        500: {"model": ChatErrorResponse, "description": "LLM or server error"},

        503: {"model": ChatErrorResponse, "description": "LLM service unavailable"},

    },

    summary="Send a message and receive an LLM response (Gemini / Groq)",

    description=(

        "**Module 5** — Direct LLM generation.\n\n"

        "Send `message` and get a response from configured LLM (Google Gemini / Groq).\n\n"

        "**Module 6** prepends retrieved document context when `use_rag=true`."

    ),

)
async def chat(request: ChatRequest) -> ChatResponse:
    num_atts = len(request.attachments) if request.attachments else 0

    norm_q = request.message.strip().lower().strip("!?.,")
    if norm_q in GREETING_RESPONSES and not request.attachments and not request.document_ids:
        fast_answer = GREETING_RESPONSES[norm_q]
        return ChatResponse(
            message=request.message,
            response=fast_answer,
            model="Enterprise AI (Fast Greeting)",
            status="success",
            timestamp=datetime.now(timezone.utc).isoformat(),
            processing_time=0.001,
            retrieval_time=0.0,
            citations=[],
            prompt_tokens=len(request.message),
            completion_tokens=len(fast_answer.split()),
        )

    logger.info("Chat request: %d chars | attachments=%d | use_rag=%s", len(request.message), num_atts, request.use_rag)

    context: str | None = None

    retrieval_time: float = 0.0

    retrieved_raw_chunks: list = []

    if request.use_rag:
        try:
            from services.retriever_service import get_retriever_service

            retriever = get_retriever_service()

            retrieval = await retriever.retrieve(

                query=request.message,

                top_k=5,

                similarity_threshold=0.3,

                document_ids=request.document_ids,

                scope=getattr(request, "scope", "company"),

                user_id=getattr(request, "user_id", None),

                company_id=getattr(request, "company_id", None),

            )

            builder = get_prompt_builder()

            context, system_prompt_override = builder.build(

                chunks=retrieval.chunks,

                query=request.message,

            )

            retrieval_time = retrieval.retrieval_time
            retrieved_raw_chunks = retrieval.chunks

            if not request.system_prompt:
                request.system_prompt = system_prompt_override

            logger.info(

                "RAG via /chat: retrieved %d chunks (fallback=%s)",

                len(retrieval.chunks), retrieval.used_fallback,

            )

        except Exception as exc:
            logger.warning(

                "RAG retrieval failed (falling back to direct LLM): %s", exc

            )

            context = None

    history = []

    if request.conversation_history:
        history = [

            {"role": turn.role, "parts": [turn.content]}

            for turn in request.conversation_history

        ]

    try:
        llm = get_llm_service()

        result = await llm.generate(

            user_prompt=request.message,

            context=context,

            system_prompt=request.system_prompt,

            conversation_history=history,

            attachments=request.attachments,

        )

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    except TimeoutError as exc:
        raise HTTPException(

            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

            detail=f"LLM API timed out: {exc}",

        )

    except RuntimeError as exc:
        err_str = str(exc).lower()

        if "rate limit" in err_str or "quota" in err_str or "429" in err_str:
            raise HTTPException(

                status_code=status.HTTP_429_TOO_MANY_REQUESTS,

                detail="LLM API rate limit reached. Please wait and retry.",

            )

        if "api_key" in err_str or "authentication" in err_str or "403" in err_str:
            raise HTTPException(

                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                detail="LLM authentication failed. Check API key.",

            )

        logger.exception("Unexpected LLM error")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"LLM generation failed: {exc}",

        )

    citations = optimize_citations(result.content, retrieved_raw_chunks) if retrieved_raw_chunks else []

    return ChatResponse(

        message=request.message,

        response=result.content,

        model=result.model,

        status="success",

        timestamp=result.timestamp,

        processing_time=result.processing_time,

        retrieval_time=retrieval_time,

        prompt_tokens=result.prompt_tokens,

        completion_tokens=result.completion_tokens,

        finish_reason=result.finish_reason,

        sources_used=len(citations) if citations else None,

        citations=citations,

    )

@router.get(

    "/health",

    response_model=LLMHealthResponse,

    summary="Check LLM connectivity",

)

async def chat_health() -> LLMHealthResponse:
    try:
        llm    = get_llm_service()

        result = await llm.health_check()

        return LLMHealthResponse(

            status=result.get("status", "unhealthy"),

            model=result.get("model", "unknown"),

            latency_ms=result.get("latency_ms"),

            response=result.get("response"),

            error=result.get("error"),

            timestamp=datetime.now(timezone.utc).isoformat(),

        )

    except Exception as exc:
        logger.error("LLM health check failed: %s", exc)

        return LLMHealthResponse(

            status="unhealthy",

            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),

            error=str(exc),

            timestamp=datetime.now(timezone.utc).isoformat(),

        )

@router.get(

    "/config",

    summary="View current LLM configuration (non-sensitive)",

)

async def chat_config() -> dict:
    from services.llm_service import GeminiLLMService

    llm = get_llm_service()

    provider_name = "Google Gemini" if isinstance(llm, GeminiLLMService) else "Groq"

    model_name = getattr(llm, "_model_name", os.getenv("LLM_MODEL", "gemini-2.5-flash"))

    return {

        "model":                model_name,

        "provider":             provider_name,

        "temperature":          float(os.getenv("LLM_TEMPERATURE", "0.7")),

        "max_output_tokens":    int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192")),

        "timeout_seconds":      int(os.getenv("LLM_TIMEOUT_SECONDS", "45")),

        "rag_enabled":          True,

        "rag_top_k":            int(os.getenv("RAG_TOP_K", "5")),

        "rag_threshold":        float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3")),

        "module":               6,

    }

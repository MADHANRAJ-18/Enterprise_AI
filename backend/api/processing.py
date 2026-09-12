from __future__ import annotations

import os

import logging

from fastapi import APIRouter, Query, BackgroundTasks, status as http_status

from services.processing_service import (

    process_document,

    process_all_pending,

    deindex_document,

    get_indexing_stats,

)

from models.processing import (

    ProcessRequest,

    ProcessSingleResponse,

    ProcessAllResponse,

    IndexingStatsResponse,

    IndexHealthResponse,

    DeleteIndexResponse,

    DocumentProcessingResult,

)

from processing.vector_store import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/processing", tags=["Processing Pipeline"])

@router.post(

    "/process/{doc_id}",

    response_model=ProcessSingleResponse,

    summary="Process a single document",

)

async def process_single(

    doc_id: str,

    background_tasks: BackgroundTasks,

    user_id: str = Query(..., description="Authenticated user UUID"),

    force_reindex: bool = Query(

        False,

        description="Re-process even if the document is already Indexed",

    ),

):
    background_tasks.add_task(

        process_document,

        doc_id=doc_id,

        user_id=user_id,

        force_reindex=force_reindex,

    )

    return ProcessSingleResponse(

        success=True,

        result=DocumentProcessingResult(

            document_id=doc_id,

            file_name="",

            status="queued",

        ),

        message=(

            f"Document {doc_id} queued for processing. "

            "Check GET /api/processing/status for progress."

        ),

    )

@router.post(

    "/process-all",

    response_model=ProcessAllResponse,

    summary="Process all pending documents",

)

async def process_all(body: ProcessRequest):
    result = await process_all_pending(

        user_id=body.user_id,

        force_reindex=body.force_reindex,

    )

    return result

@router.get(

    "/status",

    response_model=IndexingStatsResponse,

    summary="Get indexing status for a user",

)

async def get_status(

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    stats = await get_indexing_stats(user_id)

    return IndexingStatsResponse(**stats)

@router.delete(

    "/index/{doc_id}",

    response_model=DeleteIndexResponse,

    summary="Remove a document from the FAISS index",

)

async def delete_index(

    doc_id: str,

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    vectors_removed, chunks_removed = await deindex_document(

        doc_id=doc_id,

        user_id=user_id,

    )

    return DeleteIndexResponse(

        success=True,

        document_id=doc_id,

        vectors_removed=vectors_removed,

        chunks_removed=chunks_removed,

        message=(

            f"Removed {vectors_removed} vectors and {chunks_removed} chunks. "

            "Document status reset to 'Uploaded'."

        ),

    )

@router.get(

    "/health",

    response_model=IndexHealthResponse,

    summary="Processing pipeline health check",

)

async def pipeline_health():
    embedder_ready = False

    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    embedding_dim = int(os.getenv("EMBEDDING_DIMENSION", "384"))

    try:
        from processing.embedder import get_embedder

        get_embedder()

        embedder_ready = True

    except Exception as exc:
        logger.warning("Embedder health check failed: %s", exc)

    faiss_ready = False

    faiss_vectors = 0

    faiss_docs = 0

    try:
        vs = get_vector_store()

        stats = vs.get_stats()

        faiss_ready = True

        faiss_vectors = stats["total_vectors"]

        faiss_docs = stats["total_documents"]

    except Exception as exc:
        logger.warning("FAISS health check failed: %s", exc)

    return IndexHealthResponse(

        embedder_ready=embedder_ready,

        faiss_ready=faiss_ready,

        faiss_total_vectors=faiss_vectors,

        faiss_total_documents=faiss_docs,

        embedding_model=embedding_model,

        embedding_dimension=embedding_dim,

    )

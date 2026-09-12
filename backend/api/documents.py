from typing import Optional

from fastapi import (

    APIRouter, UploadFile, File, Form, Query, BackgroundTasks,

    HTTPException, status as http_status

)

from services.document_service import (

    upload_document,

    list_documents,

    list_company_documents,

    get_document,

    delete_document,

    update_document_status,

    update_document_metadata,

)

from models.document import (

    DocumentCategory,

    DocumentScope,

    DocumentStatus,

    DocumentListResponse,

    UploadResponse,

    DeleteResponse,

    ErrorResponse,

    DocumentUpdateRequest,

    DocumentResponse,

)

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post(

    "/upload",

    response_model=UploadResponse,

    status_code=http_status.HTTP_201_CREATED,

    summary="Upload a document",

    responses={

        403: {"model": ErrorResponse, "description": "Insufficient role for company upload"},

        409: {"model": ErrorResponse, "description": "Duplicate file"},

        413: {"model": ErrorResponse, "description": "File too large"},

        415: {"model": ErrorResponse, "description": "Unsupported file type"},

    },

)

async def upload(

    background_tasks: BackgroundTasks,

    file:       UploadFile       = File(..., description="File to upload (PDF, DOCX, TXT, ≤ 20 MB)"),

    category:   DocumentCategory = Form(DocumentCategory.GENERAL),

    user_id:    str              = Form(..., description="Authenticated user UUID"),

    scope:      DocumentScope    = Form(DocumentScope.WORKSPACE, description="'company' or 'workspace'"),

    company_id: Optional[str]   = Form(None, description="Company UUID (resolved from profile if omitted)"),

):
    doc = await upload_document(

        file=file,

        category=category.value,

        user_id=user_id,

        background_tasks=background_tasks,

        scope=scope.value,

        company_id=company_id,

    )

    return UploadResponse(

        success=True,

        document=doc,

        message=f"'{file.filename}' uploaded successfully to {scope.value} scope.",

    )

@router.get(

    "",

    response_model=DocumentListResponse,

    summary="List documents for a user",

)

async def list_user_documents(

    user_id:    str            = Query(..., description="Authenticated user UUID"),

    page:       int            = Query(1, ge=1, description="Page number"),

    page_size:  int            = Query(50, ge=1, le=200, description="Items per page"),

    category:   Optional[str] = Query(None, description="Filter by category"),

    doc_status: Optional[str] = Query(None, alias="status", description="Filter by status"),

    scope:      Optional[str] = Query(None, description="Filter by scope: 'workspace' | 'company' | 'both'"),

):
    docs, total = await list_documents(

        user_id=user_id,

        page=page,

        page_size=page_size,

        category=category,

        status_filter=doc_status,

        scope=scope,

    )

    return DocumentListResponse(

        documents=docs,

        total=total,

        page=page,

        page_size=page_size,

    )

@router.get(

    "/company",

    response_model=DocumentListResponse,

    summary="List company documents by company_id",

)

async def list_company_docs(

    company_id: str            = Query(..., description="Company UUID"),

    page:       int            = Query(1, ge=1),

    page_size:  int            = Query(50, ge=1, le=200),

    category:   Optional[str] = Query(None),

    doc_status: Optional[str] = Query(None, alias="status"),

):
    docs, total = await list_company_documents(

        company_id=company_id,

        page=page,

        page_size=page_size,

        category=category,

        status_filter=doc_status,

    )

    return DocumentListResponse(

        documents=docs,

        total=total,

        page=page,

        page_size=page_size,

    )

@router.get(

    "/{doc_id}",

    summary="Get a single document",

    responses={404: {"model": ErrorResponse}},

)

async def get_single_document(
    doc_id:  str,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    doc = await get_document(doc_id=doc_id, user_id=user_id)
    return doc

@router.get(
    "/{doc_id}/signed-url",
    summary="Get temporary signed URL to view/render document",
)
async def get_doc_signed_url(
    doc_id:  str,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    from services.document_service import get_document_signed_url
    return await get_document_signed_url(doc_id=doc_id, user_id=user_id)

@router.get(
    "/{doc_id}/file",
    summary="Stream raw document bytes for authenticated PDF viewer",
)
async def get_doc_file_stream(
    doc_id:  str,
    user_id: str = Query(..., description="Authenticated user UUID"),
):
    from services.document_service import get_document_file_stream
    from fastapi.responses import Response
    content, filename, content_type = await get_document_file_stream(doc_id=doc_id, user_id=user_id)
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )

@router.patch(

    "/{doc_id}",

    response_model=DocumentResponse,

    summary="Update document metadata",

    responses={404: {"model": ErrorResponse}},

)

async def update_doc(

    doc_id: str,

    updates: DocumentUpdateRequest,

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    updates_dict = updates.model_dump(exclude_unset=True)

    doc = await update_document_metadata(

        doc_id=doc_id,

        user_id=user_id,

        updates=updates_dict

    )

    return doc

@router.post(

    "/{doc_id}/overwrite",

    response_model=UploadResponse,

    summary="Overwrite / replace document file content",

    responses={

        403: {"model": ErrorResponse},

        404: {"model": ErrorResponse},

        413: {"model": ErrorResponse},

        415: {"model": ErrorResponse},

    },

)

async def overwrite_file(

    doc_id: str,

    background_tasks: BackgroundTasks,

    file: UploadFile = File(..., description="Replacement file (PDF, DOCX, TXT, ≤ 20 MB)"),

    user_id: str = Form(..., description="Authenticated user UUID"),

):
    from services.document_service import overwrite_document

    doc = await overwrite_document(

        doc_id=doc_id,

        user_id=user_id,

        file=file,

        background_tasks=background_tasks,

    )

    return UploadResponse(

        success=True,

        document=doc,

        message=f"'{file.filename}' successfully overwritten & queued for AI indexing.",

    )

@router.delete(

    "/{doc_id}",

    response_model=DeleteResponse,

    summary="Delete a document",

    responses={404: {"model": ErrorResponse}},

)

async def delete(

    doc_id:  str,

    user_id: str = Query(..., description="Authenticated user UUID"),

):
    await delete_document(doc_id=doc_id, user_id=user_id)

    return DeleteResponse(success=True, message="Document deleted successfully.")

@router.patch(

    "/{doc_id}/status",

    summary="Update document processing status",

    responses={404: {"model": ErrorResponse}},

)

async def update_status(

    doc_id:     str,

    new_status: DocumentStatus,

    user_id:    str = Query(..., description="Authenticated user UUID"),

):
    await update_document_status(doc_id=doc_id, new_status=new_status)

    return {"success": True, "doc_id": doc_id, "status": new_status.value}

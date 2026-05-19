"""
Document management routes.

Routes:
  GET    /documents/           - health/root check
  POST   /documents/upload     - upload & process a document (auth required)
  GET    /documents/list       - list all documents for current org (auth required)
  DELETE /documents/{doc_id}   - delete a document and its vectors (auth required)
"""
import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, field_validator

from Backend.core.security import get_current_user
from Backend.Database.mongodb import mongodb
from Backend.Services.embedding_service import (
    delete_document_vectors,
    save_embeddings_to_qdrant,
    update_document_status_in_qdrant,
)
from Backend.Services.file_utils import save_file
from Backend.Services.text_processor import extract_text, split_text

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class DocumentMeta(BaseModel):
    document_id: str
    title: str
    file_name: str
    file_type: str
    file_size_mb: float
    chunk_count: int
    upload_date: str
    status: str
    tags: List[str] = []


class UploadResponse(BaseModel):
    message: str
    document_id: str
    chunk_count: int
    document: dict


class DocumentStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("public", "private"):
            raise ValueError("status must be 'public' or 'private'")
        return v


# ---------------------------------------------------------------------------
# GET / — lightweight root / health check for this router
# ---------------------------------------------------------------------------
@router.get("/", tags=["documents"])
def documents_root():
    """Documents router health check."""
    return {"message": "Documents API is running."}


# ---------------------------------------------------------------------------
# POST /upload — upload, process, embed, and store a document
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse, tags=["documents"])
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = "",
    description: str = "",
    tags: Optional[str] = None,  # comma-separated string for form-data compatibility
    version: int = 1,
    status: str = Form("private"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a document and run the full ingestion pipeline:
    1. Save raw file to disk
    2. Extract text (PDF / DOCX / PPTX / XLSX / CSV / TXT)
    3. Chunk the text
    4. Store chunks in MongoDB (text_chunks collection)
    5. Embed chunks and upsert vectors to Qdrant
    6. Save document metadata to MongoDB (documents collection)
    7. Increment organization document_count
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Only administrators are allowed to upload documents to the knowledge base.",
        )

    user_id = current_user.get("user_id")
    org_id = current_user.get("organization_id")

    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization.")

    if status not in ("public", "private"):
        raise HTTPException(
            status_code=400,
            detail="status must be 'public' or 'private'",
        )

    tag_list: List[str] = [t.strip() for t in tags.split(",")] if tags else []

    try:
        # Step 1 – save raw file
        file_path, original_name = save_file(file)
        doc_id = f"doc_{uuid.uuid4().hex}"

        # Step 2 – extract text
        text = extract_text(file_path)
        if not text.strip():
            raise ValueError("No text could be extracted from the uploaded file.")

        # Step 3 – chunk
        chunks = split_text(text)
        chunk_count = len(chunks)

        now_utc = datetime.utcnow().isoformat() + "Z"

        # Step 4 – persist chunks to MongoDB
        if chunks:
            chunk_docs = [
                {
                    "document_id": doc_id,
                    "organization_id": org_id,
                    "chunk_index": idx,
                    "text": chunk_text,
                    "created_at": now_utc,
                }
                for idx, chunk_text in enumerate(chunks, start=1)
            ]
            await mongodb.db.text_chunks.insert_many(chunk_docs)

        # Step 5 – generate embeddings and upsert into Qdrant
        embedding_model = request.app.state.embedding_model
        await save_embeddings_to_qdrant(
            chunks=chunks,
            metadata={
                "document_id": doc_id,
                "organization_id": org_id,
                "source_name": original_name,
                "file_type": file.filename.split(".")[-1].lower(),
                "upload_user_id": user_id,
                "status": status,
            },
            model=embedding_model,
        )

        # Step 6 – store document metadata
        file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 4)
        doc_meta = {
            "_id": doc_id,
            "document_id": doc_id,
            "organization_id": org_id,
            "title": title or original_name,
            "description": description,
            "file_name": original_name,
            "file_type": file.filename.split(".")[-1].lower(),
            "file_size_mb": file_size_mb,
            "file_size_bytes": os.path.getsize(file_path),
            "uploaded_by": user_id,
            "upload_date": now_utc,
            "uploaded_at": now_utc,
            "last_updated": now_utc,
            "processed": True,
            "status": status,
            "chunk_count": chunk_count,
            "tags": tag_list,
            "version": version,
        }
        await mongodb.db.documents.insert_one(doc_meta)

        # Step 7 – increment org document_count
        await mongodb.db.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {"$inc": {"document_count": 1}},
        )

        logger.info(
            "Document uploaded: id=%s chunks=%d org=%s user=%s",
            doc_id,
            chunk_count,
            org_id,
            user_id,
        )

        return UploadResponse(
            message="Document uploaded and processed successfully.",
            document_id=doc_id,
            chunk_count=chunk_count,
            document=doc_meta,
        )

    except ValueError as exc:
        logger.warning("Upload validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "Upload failed for file '%s'", getattr(file, "filename", "unknown")
        )
        raise HTTPException(
            status_code=500, detail="Internal server error during document upload."
        )


# ---------------------------------------------------------------------------
# GET /list — list all documents for current organization
# ---------------------------------------------------------------------------
@router.get("/list", response_model=List[DocumentMeta], tags=["documents"])
async def list_documents(
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    skip: int = 0,
):
    """Return all documents belonging to the current user's organization."""
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization.")

    try:
        cursor = (
            mongodb.db.documents.find({"organization_id": org_id})
            .sort("upload_date", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)

        return [
            DocumentMeta(
                document_id=str(d.get("_id", "")),
                title=d.get("title", d.get("file_name", "")),
                file_name=d.get("file_name", ""),
                file_type=d.get("file_type", ""),
                file_size_mb=d.get("file_size_mb", 0.0),
                chunk_count=d.get("chunk_count", 0),
                upload_date=d.get("upload_date", d.get("uploaded_at", "")),
                status=d.get("status", "private"),
                tags=d.get("tags", []),
            )
            for d in docs
        ]
    except Exception as exc:
        logger.error("Error listing documents for org '%s': %s", org_id, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve document list.")


# ---------------------------------------------------------------------------
# PATCH /{doc_id}/status — toggle document privacy (admin only)
# ---------------------------------------------------------------------------
@router.patch("/{doc_id}/status", tags=["documents"])
async def update_document_status(
    doc_id: str,
    body: DocumentStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Set a document's privacy status to public or private."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can change document visibility.",
        )

    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no associated organization.")

    try:
        doc = await mongodb.db.documents.find_one({"_id": doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        if doc.get("organization_id") != org_id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to modify this document.",
            )

        now_utc = datetime.utcnow().isoformat() + "Z"
        await mongodb.db.documents.update_one(
            {"_id": doc_id},
            {"$set": {"status": body.status, "last_updated": now_utc}},
        )

        try:
            update_document_status_in_qdrant(doc_id, body.status)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        logger.info(
            "Document status updated: id=%s status=%s org=%s",
            doc_id,
            body.status,
            org_id,
        )
        return {
            "message": "Document status updated successfully.",
            "document_id": doc_id,
            "status": body.status,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error updating document status '%s'", doc_id)
        raise HTTPException(status_code=500, detail="Failed to update document status.")


# ---------------------------------------------------------------------------
# DELETE /{doc_id} — remove document metadata and its Qdrant vectors
# ---------------------------------------------------------------------------
@router.delete("/{doc_id}", tags=["documents"])
async def delete_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a document:
    1. Verify the document belongs to the caller's organization
    2. Remove Qdrant vectors for this document
    3. Remove chunk records from MongoDB
    4. Remove document metadata from MongoDB
    5. Decrement organization document_count
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Only administrators are allowed to delete documents from the knowledge base.",
        )

    org_id = current_user.get("organization_id")

    try:
        # 1 – verify ownership
        doc = await mongodb.db.documents.find_one({"_id": doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        if doc.get("organization_id") != org_id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to delete this document.",
            )

        # 2 – delete vectors from Qdrant
        try:
            delete_document_vectors(doc_id)
        except Exception as exc:
            logger.warning(
                "Vector deletion failed for doc '%s' (continuing): %s", doc_id, exc
            )

        # 3 – delete text chunks from MongoDB
        await mongodb.db.text_chunks.delete_many({"document_id": doc_id})

        # 4 – delete document metadata
        await mongodb.db.documents.delete_one({"_id": doc_id})

        # 5 – decrement org document_count (floor at 0)
        await mongodb.db.organizations.update_one(
            {"_id": ObjectId(org_id), "document_count": {"$gt": 0}},
            {"$inc": {"document_count": -1}},
        )

        logger.info("Document deleted: id=%s org=%s", doc_id, org_id)
        return {"message": "Document deleted successfully.", "document_id": doc_id}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error deleting document '%s'", doc_id)
        raise HTTPException(status_code=500, detail="Failed to delete document.")

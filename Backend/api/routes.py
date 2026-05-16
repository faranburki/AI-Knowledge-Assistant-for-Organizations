from fastapi import APIRouter, UploadFile, File, Request
import os
import uuid
from datetime import datetime
from typing import List
from Backend.Database.mongodb import mongodb
from Backend.Services.text_processor import extract_text, split_text
from Backend.Services.file_utils import save_file
from Backend.Services.embedding_service import save_embeddings_to_qdrant

router = APIRouter()

@router.get("/")
def root():
    return {"message": "Hello World"}

@router.post("/upload-doc")
async def upload_doc(
    request: Request,
    file: UploadFile = File(...),
    organization_id: str = "",
    title: str = "",
    description: str = "",
    upload_user_id: str = "",
    tags: List[str]=[],
    version: int = 1
):
    # Step 1 : save file
    file_path, original_name = save_file(file)
    doc_id = f"doc_{uuid.uuid4()}"

    # Step 2 : Extract Text
    text = extract_text(file_path)
    if not text.strip():
        return {"error": "No Text extracted from file"}

    # Step 3 : Chunk text
    chunks = split_text(text)
    chunk_count = len(chunks)

    # Step 4 : Save chunks
    for idx, chunk_text in enumerate(chunks, start=1):
        await mongodb.db.text_chunks.insert_one({
            "document_id": doc_id,
            "chunk_index": idx,
            "text": chunk_text,
            "created_at": datetime.utcnow().isoformat() + "Z"
        })

    # Step 5 : Create embeddings in Qdrant
    await save_embeddings_to_qdrant(
        chunks=chunks,
        metadata={
            "document_id": doc_id,
            "organization_id": organization_id or "org_unknown",
            "source_name": original_name,
            "file_type": file.filename.split(".")[-1].lower(),
            "upload_user_id": upload_user_id or "user_unknown"
        },
        model=request.app.state.embedding_model
    )

    # Step 6 : Insert metadata according to desired schema
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    now_utc = datetime.utcnow().isoformat() + "Z"
    doc_meta = {
        "_id": doc_id,
        "organization_id": organization_id or "org_unknown",
        "title": title or original_name,
        "description": description,
        "file_name": original_name,
        "file_type": file.filename.split(".")[-1].lower(),
        "file_size_mb": round(file_size_mb, 3),
        "upload_user_id": upload_user_id or "user_unknown",
        "upload_date": now_utc,
        "processed": True,
        "chunk_count": chunk_count,
        "tags": tags,
        "last_updated": now_utc
    }
    await mongodb.db.documents.insert_one(doc_meta)

    return {
        "message": "Document uploaded and metadata stored",
        "document_id": doc_id,
        "chunk_count": chunk_count,
        "document": doc_meta
    }

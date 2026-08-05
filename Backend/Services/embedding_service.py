import asyncio
import logging
import uuid
from typing import Dict, List

from Backend.Database import chroma

logger = logging.getLogger(__name__)


def generate_embeddings(chunks: List[str], model) -> List[List[float]]:
    """Generate embeddings for a list of text chunks using the provided model."""
    if not chunks:
        return []

    try:
        embeddings = model.encode(chunks, show_progress_bar=False)
    except Exception as exc:
        logger.exception("Embedding model failed to encode chunks")
        raise ValueError("Failed to generate embeddings for the uploaded document.") from exc

    if hasattr(embeddings, "tolist"):
        embeddings = embeddings.tolist()

    return embeddings


async def save_embeddings_to_chroma(
    chunks: List[str],
    metadata: Dict[str, str],
    model,
    batch_size: int = 64,
) -> int:
    """Generate embeddings and save them to ChromaDB. Returns number of points saved."""
    if not chunks:
        return 0

    # Encode and explicitly normalize to length 1 for exact Cosine math
    def _encode():
        return model.encode(chunks, normalize_embeddings=True).tolist()
        
    embeddings = await asyncio.to_thread(_encode)
    
    doc_id = metadata.get("document_id", "")
    namespace = uuid.NAMESPACE_DNS
    
    ids = []
    metadatas = []
    
    for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings), start=1):
        point_id = str(uuid.uuid5(namespace, f"{doc_id}_chunk_{idx}"))
        ids.append(point_id)
        
        doc_status = metadata.get("status", "private")
        payload = {
            "document_id": doc_id,
            "organization_id": metadata.get("organization_id") or "",
            "source_name": metadata.get("source_name") or "",
            "file_type": metadata.get("file_type") or "",
            "upload_user_id": metadata.get("upload_user_id") or "",
            "status": doc_status,
            "is_public": doc_status == "public",
            "chunk_index": idx,
            "chunk_text": chunk_text,
            "page_estimate": max(1, (idx - 1) // 5 + 1),
        }
        metadatas.append(payload)

    try:
        # We can add in batches if the document is very large, but Chroma handles 
        # reasonably large adds efficiently. We'll implement batching just in case.
        def _add_batch(c_ids, c_embeds, c_metas, c_docs):
            chroma.collection.add(
                ids=c_ids,
                embeddings=c_embeds,
                metadatas=c_metas,
                documents=c_docs
            )

        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            await asyncio.to_thread(
                _add_batch,
                ids[start:end],
                embeddings[start:end],
                metadatas[start:end],
                chunks[start:end]
            )
        logger.info(
            "Saved %d embedding points for document '%s'",
            len(ids),
            doc_id,
        )
    except Exception as exc:
        logger.exception("Failed to upsert embeddings into ChromaDB")
        raise ValueError("Unable to save embeddings to the vector store.") from exc

    return len(ids)


async def update_document_status_in_chroma(document_id: str, status: str) -> None:
    """Update privacy status on all ChromaDB points for a document asynchronously."""
    if status not in ("public", "private"):
        raise ValueError("status must be 'public' or 'private'")

    def _update():
        # Fetch the points
        result = chroma.collection.get(
            where={"document_id": document_id},
            include=["metadatas"]
        )
        if not result or not result.get("ids"):
            return
        
        c_ids = result["ids"]
        c_metas = result["metadatas"]
        
        for meta in c_metas:
            meta["status"] = status
            meta["is_public"] = status == "public"
            
        chroma.collection.update(
            ids=c_ids,
            metadatas=c_metas
        )

    try:
        await asyncio.to_thread(_update)
        logger.info(
            "Updated ChromaDB payload status='%s' for document '%s'",
            status,
            document_id,
        )
    except Exception as exc:
        logger.exception(
            "Failed to update ChromaDB status for document '%s'", document_id
        )
        raise ValueError("Unable to update document visibility in the vector store.") from exc


async def delete_document_vectors(document_id: str) -> None:
    """Delete all ChromaDB vectors that belong to a given document asynchronously."""
    def _delete():
        chroma.collection.delete(
            where={"document_id": document_id}
        )
        
    try:
        await asyncio.to_thread(_delete)
        logger.info("Deleted ChromaDB vectors for document '%s'", document_id)
    except Exception as exc:
        logger.exception("Failed to delete vectors for document '%s'", document_id)
        raise ValueError("Unable to delete embeddings from the vector store.") from exc

import logging
import uuid
from typing import Dict, List

from qdrant_client.http.models import PointStruct

from Backend.Database import qdrant

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


def build_qdrant_points(
    chunks: List[str],
    embeddings: List[List[float]],
    metadata: Dict[str, str],
) -> List[PointStruct]:
    """Convert chunk text and embeddings into Qdrant PointStruct objects.

    Qdrant point IDs must be unsigned 64-bit integers or UUIDs.
    We generate a deterministic UUID v5 from (document_id + chunk_index)
    so that re-uploading the same document produces the same IDs (idempotent upsert).
    """
    doc_id = metadata.get("document_id", "")
    namespace = uuid.NAMESPACE_DNS  # arbitrary but stable namespace

    points: List[PointStruct] = []
    for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings), start=1):
        # Deterministic UUID per chunk — safe for Qdrant
        point_id = str(uuid.uuid5(namespace, f"{doc_id}_chunk_{idx}"))

        payload = {
            "document_id": doc_id,
            "organization_id": metadata.get("organization_id"),
            "source_name": metadata.get("source_name"),
            "file_type": metadata.get("file_type"),
            "upload_user_id": metadata.get("upload_user_id"),
            "chunk_index": idx,
            "chunk_text": chunk_text,
            "page_estimate": max(1, (idx - 1) // 5 + 1),  # ~5 chunks per page estimate
        }

        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )
        )

    return points


async def save_embeddings_to_qdrant(
    chunks: List[str],
    metadata: Dict[str, str],
    model,
    batch_size: int = 64,
) -> int:
    """Generate embeddings and save them to Qdrant. Returns number of points saved."""
    if not chunks:
        return 0

    embeddings = generate_embeddings(chunks, model)
    points = build_qdrant_points(chunks, embeddings, metadata)

    try:
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            qdrant.client.upsert(collection_name=qdrant.COLLECTION_NAME, points=batch)
        logger.info(
            "Saved %d embedding points for document '%s'",
            len(points),
            metadata.get("document_id"),
        )
    except Exception as exc:
        logger.exception("Failed to upsert embeddings into Qdrant")
        raise ValueError("Unable to save embeddings to the vector store.") from exc

    return len(points)


def delete_document_vectors(document_id: str) -> None:
    """Delete all Qdrant vectors that belong to a given document."""
    try:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        qdrant.client.delete(
            collection_name=qdrant.COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info("Deleted Qdrant vectors for document '%s'", document_id)
    except Exception as exc:
        logger.exception("Failed to delete vectors for document '%s'", document_id)
        raise ValueError("Unable to delete embeddings from the vector store.") from exc

import logging
from typing import Dict, List
from qdrant_client.http.models import PointStruct
from Backend.Database.qdrant import COLLECTION_NAME, client

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
    metadata: Dict[str, str]
) -> List[PointStruct]:
    """Convert chunk text and embeddings into Qdrant PointStruct objects."""
    points: List[PointStruct] = []

    for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings), start=1):
        point_id = f"{metadata.get('document_id')}_{idx}"
        payload = {
            "document_id": metadata.get("document_id"),
            "organization_id": metadata.get("organization_id"),
            "source_name": metadata.get("source_name"),
            "file_type": metadata.get("file_type"),
            "upload_user_id": metadata.get("upload_user_id"),
            "chunk_index": idx,
            "chunk_text": chunk_text,
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
    """Generate embeddings and save them to Qdrant."""
    if not chunks:
        return 0

    embeddings = generate_embeddings(chunks, model)
    points = build_qdrant_points(chunks, embeddings, metadata)

    try:
        for start in range(0, len(points), batch_size):
            batch_points = points[start : start + batch_size]
            client.upsert(collection_name=COLLECTION_NAME, points=batch_points)
    except Exception as exc:
        logger.exception("Failed to upsert embeddings into Qdrant")
        raise ValueError("Unable to save embeddings to the vector store.") from exc

    return len(points)

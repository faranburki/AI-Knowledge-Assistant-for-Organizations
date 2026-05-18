import logging
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType

load_dotenv()

logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents_chunks"
VECTOR_SIZE = 384

# Module-level client — populated by connect_to_qdrant() at app startup.
# Do NOT use before startup completes.
client: QdrantClient = None  # type: ignore[assignment]


def _get_qdrant_client() -> QdrantClient:
    """Create and return a connected QdrantClient using env vars."""
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    return QdrantClient(url=qdrant_url, api_key=qdrant_api_key)


def _ensure_collection(qdrant_client: QdrantClient) -> None:
    """Create the vector collection if it does not already exist."""
    try:
        existing = {c.name for c in qdrant_client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            logger.info("Creating Qdrant collection: %s", COLLECTION_NAME)
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Collection '%s' created successfully.", COLLECTION_NAME)
        else:
            logger.info("Collection '%s' already exists.", COLLECTION_NAME)
            
        # Ensure payload indexes exist for filtering
        logger.info("Creating payload indexes for collection '%s'", COLLECTION_NAME)
        try:
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="organization_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="document_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            qdrant_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="upload_user_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            logger.warning("Payload indexes may already exist or could not be created: %s", str(e))
            
    except Exception as exc:
        logger.exception("Failed to ensure Qdrant collection '%s'", COLLECTION_NAME)
        raise RuntimeError("Unable to initialize Qdrant collection.") from exc


async def connect_to_qdrant() -> None:
    """
    Called once at application startup.
    Creates the QdrantClient, verifies connectivity, and ensures the
    required collection exists.  Populates the module-level `client`.
    """
    global client  # noqa: PLW0603
    try:
        qdrant_client = _get_qdrant_client()
        # Verify connectivity with a lightweight call
        qdrant_client.get_collections()
        _ensure_collection(qdrant_client)
        client = qdrant_client
        logger.info("Qdrant initialized successfully.")
    except Exception as exc:
        logger.exception("Failed to connect to Qdrant")
        raise RuntimeError("Unable to connect to Qdrant.") from exc
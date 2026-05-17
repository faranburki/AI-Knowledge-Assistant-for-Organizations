import logging
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

load_dotenv()

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

try:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    client.get_collections()
    print("Qdrant connected successfully")
except Exception as exc:
    logger.exception("Failed to initialize Qdrant client")
    raise RuntimeError("Unable to connect to Qdrant.") from exc


COLLECTION_NAME = "documents _chunks"
VECTOR_SIZE = 384


def qdrant_init():
    try:
        collections = client.get_collections().collections
        existing_names = [c.name for c in collections]
        
        if COLLECTION_NAME not in existing_names:
            print(f"Creating collection: {COLLECTION_NAME}")

            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            )
        else:
            print(f"Collection already exists: {COLLECTION_NAME}")
    except Exception as exc:
        logger.exception("Failed to initialize Qdrant collection %s", COLLECTION_NAME)
        raise RuntimeError("Unable to initialize Qdrant collection.") from exc


async def connect_to_qdrant():
    """Initialize Qdrant connection and collections at startup"""
    qdrant_init()
    print("Qdrant initialized successfully")
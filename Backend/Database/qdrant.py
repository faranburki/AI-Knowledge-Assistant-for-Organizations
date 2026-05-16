import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

load_dotenv()

client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY")
)


try:
    client.get_collections()
    print("Qdrant connected successfully")
except Exception as e:
    print("Qdrant connection failed:", e)
    
COLLECTION_NAME="documents _chunks"
VECTOR_SIZE=384


def qdrant_init():
    collections = client.get_collections().collections
    existing_names=[c.name for c in collections]
    
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


async def connect_to_qdrant():
    """Initialize Qdrant connection and collections at startup"""
    qdrant_init()
    print("Qdrant initialized successfully")
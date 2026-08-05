import logging
import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

load_dotenv()

logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents_chunks"

# Module-level client — populated by connect_to_chroma() at app startup.
client = None  # type: ignore[assignment]
collection = None

def _get_chroma_client():
    """Create and return a connected Chroma client."""
    # We will use PersistentClient to save data locally in a directory.
    # If a remote server is needed, we could check for an env var like CHROMA_URL
    # and use chromadb.HttpClient. For now, local persistence is optimal and standard.
    persist_directory = os.getenv("CHROMA_PERSIST_DIR", "Backend/Database/chroma_db")
    
    # Ensure directory exists
    os.makedirs(persist_directory, exist_ok=True)
    
    logger.info("Initializing ChromaDB PersistentClient at %s", persist_directory)
    return chromadb.PersistentClient(path=persist_directory)

def _ensure_collection(chroma_client) -> None:
    """Create the vector collection if it does not already exist."""
    global collection
    try:
        logger.info("Ensuring ChromaDB collection '%s' exists", COLLECTION_NAME)
        # get_or_create_collection simplifies the logic
        # For cosine distance, we specify metadata={"hnsw:space": "cosine"}
        collection = chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("Collection '%s' is ready.", COLLECTION_NAME)
    except Exception as exc:
        logger.exception("Failed to ensure ChromaDB collection '%s'", COLLECTION_NAME)
        raise RuntimeError("Unable to initialize ChromaDB collection.") from exc

async def connect_to_chroma() -> None:
    """
    Called once at application startup.
    Creates the Chroma client and ensures the required collection exists.
    Populates the module-level `client` and `collection`.
    """
    global client
    try:
        chroma_client = _get_chroma_client()
        _ensure_collection(chroma_client)
        client = chroma_client
        logger.info("ChromaDB initialized successfully.")
    except Exception as exc:
        logger.exception("Failed to connect to ChromaDB")
        raise RuntimeError("Unable to connect to ChromaDB.") from exc

import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.db = None

    def get_db(self):
        if self.db is None:
            raise RuntimeError("MongoDB is not connected. Call connect_to_mongo first.")
        return self.db

mongodb = MongoDB()

async def connect_to_mongo():
    mongodb_url = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB", "Ai_assistant")

    if not mongodb_url:
        logger.error("MONGODB_URI environment variable is not set")
        raise ValueError("MONGODB_URI environment variable is not set.")

    if mongodb.client:
        mongodb.client.close()

    try:
        mongodb.client = AsyncIOMotorClient(mongodb_url)
        await mongodb.client.admin.command("ping")
        mongodb.db = mongodb.client[db_name]
        print(f"Connected to MongoDB database: {db_name}")
        await ensure_mongo_indexes()
    except Exception as exc:
        logger.exception("Failed to connect to MongoDB at %s", mongodb_url)
        raise RuntimeError("Unable to connect to MongoDB.") from exc


async def ensure_mongo_indexes():
    """Ensure database indexes exist in MongoDB for production performance."""
    if mongodb.db is None:
        logger.error("Cannot ensure MongoDB indexes: database connection is not open.")
        return

    logger.info("Verifying and creating MongoDB indexes...")
    try:
        # 1. Users collection indexes
        await mongodb.db.users.create_index("email", unique=True)
        await mongodb.db.users.create_index("subscribed_org_ids")
        logger.info("✅ Indexes on 'users' collection ensured.")
        
        # 2. Queries collection indexes
        # Compound index for user query history sorted by time
        await mongodb.db.queries.create_index([("user_id", 1), ("timestamp", -1)])
        await mongodb.db.queries.create_index("organization_id")
        await mongodb.db.queries.create_index("conversation_id")
        logger.info("✅ Indexes on 'queries' collection ensured.")

        # 3. Documents collection indexes
        await mongodb.db.documents.create_index("organization_id")
        await mongodb.db.documents.create_index("document_id", unique=True)
        logger.info("✅ Indexes on 'documents' collection ensured.")
        
        # 4. Voice Sessions collection indexes
        await mongodb.db.voice_sessions.create_index("session_id", unique=True)
        await mongodb.db.voice_sessions.create_index("user_id")
        await mongodb.db.voice_sessions.create_index("organization_id")
        logger.info("✅ Indexes on 'voice_sessions' collection ensured.")
        
    except Exception as exc:
        logger.warning("Failed to create MongoDB indexes: %s. Continuing startup...", str(exc))


async def close_mongo_connection():
    if mongodb.client:
        mongodb.client.close()
        mongodb.client = None
        mongodb.db = None
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
    except Exception as exc:
        logger.exception("Failed to connect to MongoDB at %s", mongodb_url)
        raise RuntimeError("Unable to connect to MongoDB.") from exc


async def close_mongo_connection():
    if mongodb.client:
        mongodb.client.close()
        mongodb.client = None
        mongodb.db = None
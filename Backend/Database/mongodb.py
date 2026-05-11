import os
from motor.motor_asyncio import AsyncIOMotorClient

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
    mongodb_url = os.getenv("MONGODB_URL")
    db_name = os.getenv("MONGODB_DB", "Ai_assistant")

    if not mongodb_url:
        raise ValueError("MONGODB_URL environment variable is not set")

    # close old connection if exists
    if mongodb.client:
        mongodb.client.close()

    mongodb.client = AsyncIOMotorClient(mongodb_url)

    # verify connection (important for Atlas)
    await mongodb.client.admin.command("ping")

    mongodb.db = mongodb.client[db_name]
    print(f"Connected to MongoDB database: {db_name}")


async def close_mongo_connection():
    if mongodb.client:
        mongodb.client.close()
        mongodb.client = None
        mongodb.db = None
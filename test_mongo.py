import asyncio
import os
import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

async def test_insert():
    uri = os.getenv("MONGODB_URI")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[os.getenv("MONGODB_DB", "knowledge_db")]
    
    try:
        org_result = await db.organizations.insert_one({
            "name": "Test's Organization",
            "slug": "test",
            "description": None,
            "document_count": 0,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        })
        print(f"Inserted org: {org_result.inserted_id}")
    except Exception as e:
        print(f"Error inserting org: {type(e)} - {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_insert())

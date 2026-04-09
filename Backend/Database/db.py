from pymongo import MongoClient

# Change to local MongoDB for testing
Client = MongoClient("mongodb://localhost:27017/ai_assistant")

db=Client["Ai_assistant"]
documents_collection=db["documents"]
text_chunks_collection=db["text_chunks"]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from Backend.api.routes import router
from Backend.Database.mongodb import connect_to_mongo, close_mongo_connection
from Backend.Database.qdrant import connect_to_qdrant

load_dotenv()

RAW_DIR="Backend/Database/raw"
PROCESSED_DIR="Backend/Database/processed"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Loading embedding model...")
    app.state.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    await connect_to_mongo()
    await connect_to_qdrant()
    
    print("Application startup complete")
    yield
    
    # Shutdown
    await close_mongo_connection()
    print("Application shutdown complete")


app = FastAPI(lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Router registration with prefixes
app.include_router(router, prefix="/documents")

# TODO: Add other routers when created
# app.include_router(auth_router, prefix="/auth")
# app.include_router(orgs_router, prefix="/orgs")
# app.include_router(query_router, prefix="/query")
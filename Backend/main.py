import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from starlette.exceptions import HTTPException as StarletteHTTPException

from Backend.api.routes import router as documents_router
from Backend.routers import auth, organizations, query
from Backend.Database.mongodb import connect_to_mongo, close_mongo_connection
from Backend.Database.qdrant import connect_to_qdrant

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

RAW_DIR = "Backend/Database/raw"
PROCESSED_DIR = "Backend/Database/processed"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Loading embedding model...")
    try:
        app.state.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded successfully")
    except Exception as e:
        logger.error("Failed to load embedding model: %s", str(e))
        raise
    
    logger.info("Connecting to MongoDB...")
    await connect_to_mongo()
    
    logger.info("Connecting to Qdrant...")
    await connect_to_qdrant()
    
    logger.info("Application startup complete")
    yield
    
    # Shutdown
    logger.info("Closing MongoDB connection...")
    await close_mongo_connection()
    logger.info("Application shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Knowledge Assistant API",
    description="RAG-based knowledge assistant with multi-tenancy support",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("HTTPException: %s", exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error: %s", exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Health check endpoint
@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Router registration with prefixes
app.include_router(documents_router, prefix="/documents", tags=["documents"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(organizations.router, prefix="/orgs", tags=["organizations"])
app.include_router(query.router, prefix="/query", tags=["query"])

logger.info("All routers registered")
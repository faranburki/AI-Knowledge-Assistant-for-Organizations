from fastapi import FastAPI
import os
from Backend.api.routes import router

app = FastAPI()

RAW_DIR="Backend/Database/raw"
PROCESSED_DIR="Backend/Database/processed"

os.makedirs(RAW_DIR,exist_ok=True)
os.makedirs(PROCESSED_DIR,exist_ok=True)

app.include_router(router)
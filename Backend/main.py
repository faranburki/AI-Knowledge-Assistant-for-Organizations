from fastapi import FastAPI
import os
from Backend.api.routes import router
from Backend.Database.mongodb import connect_to_mongo, close_mongo_connection

app = FastAPI()

RAW_DIR="Backend/Database/raw"
PROCESSED_DIR="Backend/Database/processed"

os.makedirs(RAW_DIR,exist_ok=True)
os.makedirs(PROCESSED_DIR,exist_ok=True)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()
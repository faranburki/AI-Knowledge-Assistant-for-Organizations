from fastapi import UploadFile
import logging
import os
import uuid
import shutil

logger = logging.getLogger(__name__)
RAW_DIR = "Backend/Database/raw"
os.makedirs(RAW_DIR, exist_ok=True)

def save_file(upload_file: UploadFile):
    if not upload_file or not upload_file.filename:
        logger.warning("Invalid upload_file provided to save_file")
        raise ValueError("Invalid uploaded file.")

    ext = upload_file.filename.split(".")[-1].lower()
    unique_name = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(RAW_DIR, unique_name)

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(upload_file.file, f)
    except Exception as exc:
        logger.exception("Failed to save uploaded file %s", upload_file.filename)
        raise ValueError("Unable to save the uploaded file.") from exc

    return file_path, upload_file.filename
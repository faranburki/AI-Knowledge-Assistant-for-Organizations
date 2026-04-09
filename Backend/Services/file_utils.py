from fastapi import UploadFile
import os, uuid, shutil

RAW_DIR = "Backend/Database/raw"
os.makedirs(RAW_DIR, exist_ok=True)

def save_file(upload_file: UploadFile):
    if not upload_file.filename:
        raise ValueError("Invalid file")

    ext = upload_file.filename.split(".")[-1].lower()
    unique_name = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(RAW_DIR, unique_name)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)

    return file_path, upload_file.filename
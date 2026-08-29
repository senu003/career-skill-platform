from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pypdf import PdfReader
import bcrypt
import os
import uuid

from .database import SessionLocal
from .models import User

router = APIRouter()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post("/users")
def create_user(
    name: str,
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    user = User(
        name=name,
        email=email,
        password_hash=hashed_password
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email
    }


@router.post("/cv/upload")
async def upload_cv(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    os.makedirs("uploads", exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = f"uploads/{file_id}.pdf"

    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return {
        "file_id": file_id,
        "filename": file.filename,
        "pages": len(reader.pages),
        "text_preview": text[:1000]
    }
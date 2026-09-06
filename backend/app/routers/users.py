from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import bcrypt
from datetime import timedelta

from ..database import SessionLocal
from ..models import User
from app.auth_deps import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user_required


router = APIRouter()


class UserCreate(BaseModel):
    name: str
    email: str
    password: str


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get("/users/me")
def get_me(current_user: User = Depends(get_current_user_required)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


@router.post("/users")
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):

    hashed_password = bcrypt.hashpw(
        user_data.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    user = User(
        name=user_data.name,
        email=user_data.email,
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


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not bcrypt.checkpw(form_data.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
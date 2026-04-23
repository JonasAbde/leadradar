from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from . import models
import os

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-32-chars-long!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(models.get_db)
) -> models.User:
    token = None
    
    # Check Authorization header
    if credentials:
        token = credentials.credentials
    else:
        # Check cookie
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(models.get_db)
) -> models.User | None:
    try:
        return get_current_user(request, credentials, db)
    except HTTPException:
        return None

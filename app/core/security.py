"""Security module for password hashing and JWT authentication."""

import os
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "myresumo-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Returns payload or raises exception."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token. Please login again.")


async def get_current_user(request: Request):
    """FastAPI dependency to get current logged-in user object from session cookie."""
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            
        from app.database.repositories.user_repository import UserRepository
        from app.database.models.user import UserResponse
        
        repo = UserRepository()
        user_data = await repo.get_user_by_id(user_id)
        if not user_data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            
        return UserResponse(
            id=user_data.get("id"),
            email=user_data.get("email"),
            name=user_data.get("name"),
            role=user_data.get("role", "student"),
            is_admin=user_data.get("is_admin", False) or user_data.get("role") == "admin",
            created_at=user_data.get("created_at")
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


async def get_current_user_optional(request: Request):
    """Get current user object or None if not logged in."""
    try:
        token = request.cookies.get("auth_token")
        if not token:
            return None
            
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
            
        from app.database.repositories.user_repository import UserRepository
        from app.database.models.user import UserResponse
        
        repo = UserRepository()
        user_data = await repo.get_user_by_id(user_id)
        if not user_data:
            return None
            
        return UserResponse(
            id=user_data.get("id"),
            email=user_data.get("email"),
            name=user_data.get("name"),
            role=user_data.get("role", "student"),
            is_admin=user_data.get("is_admin", False) or user_data.get("role") == "admin",
            created_at=user_data.get("created_at")
        )
    except Exception:
        return None


def require_login_redirect(request: Request) -> RedirectResponse | None:
    """Redirect to login if not authenticated (for web routes)."""
    token = request.cookies.get("auth_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    try:
        decode_access_token(token)
        return None
    except Exception:
        return RedirectResponse(url="/login", status_code=303)


async def require_admin(request: Request) -> bool:
    """Check if current user is an admin."""
    user_id = await get_current_user(request)
    from app.database.repositories.user_repository import UserRepository
    repo = UserRepository()
    user = await repo.get_user_by_id(user_id)
    if not user or (not user.get("is_admin", False) and user.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return True

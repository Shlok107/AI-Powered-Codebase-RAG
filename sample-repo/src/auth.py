"""
Authentication module.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from config.settings import settings


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password with salt.
    
    Args:
        password: Plain text password
        salt: Optional salt (generated if not provided)
        
    Returns:
        Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 with SHA-256
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return hashed.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify a password against its hash."""
    new_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(new_hash, hashed)


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User identifier
        expires_delta: Optional expiration time
        
    Returns:
        Encoded JWT token
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.jwt_expiry_hours)
    
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[str]:
    """
    Decode and validate a JWT token.
    
    Returns:
        User ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def authenticate_user(username: str, password: str) -> Optional[str]:
    """
    Authenticate a user and return access token.
    
    In a real application, this would query a database.
    For demo purposes, we use a hardcoded user.
    """
    # DEMO ONLY - In production, query database with parameterized query
    demo_user = "admin"
    demo_hash, demo_salt = hash_password("admin123")
    
    if username == demo_user and verify_password(password, demo_hash, demo_salt):
        return create_access_token(username)
    
    return None


def get_current_user(token: str) -> Optional[str]:
    """Get current user from token."""
    return decode_token(token)
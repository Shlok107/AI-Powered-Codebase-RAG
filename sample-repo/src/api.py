"""
API routes module.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from config.settings import Settings
from src.auth import authenticate_user, create_access_token, get_current_user
from src.database import init_db, close_pool, db_cursor


security = HTTPBearer()


# Request/Response Models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]


class ErrorResponse(BaseModel):
    detail: str


# Dependency
async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    user_id = get_current_user(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    close_pool()


def create_app(settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Codebase RAG Demo API",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "0.1.0"}
    
    @app.post("/auth/login", response_model=LoginResponse)
    async def login(request: LoginRequest):
        token = authenticate_user(request.username, request.password)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return LoginResponse(access_token=token)
    
    @app.get("/auth/me", response_model=UserResponse)
    async def get_me(user_id: str = Depends(get_current_user_id)):
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, username, email FROM users WHERE username = %s",
                (user_id,)
            )
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return UserResponse(id=user[0], username=user[1], email=user[2])
    
    @app.get("/users")
    async def list_users(user_id: str = Depends(get_current_user_id)):
        with db_cursor() as cur:
            cur.execute("SELECT id, username, email, created_at FROM users")
            users = cur.fetchall()
            return [
                {"id": u[0], "username": u[1], "email": u[2], "created_at": u[3].isoformat()}
                for u in users
            ]
    
    @app.get("/audit-logs")
    async def get_audit_logs(limit: int = 50, user_id: str = Depends(get_current_user_id)):
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, user_id, action, resource_type, resource_id, created_at "
                "FROM audit_log ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            logs = cur.fetchall()
            return [
                {
                    "id": l[0],
                    "user_id": l[1],
                    "action": l[2],
                    "resource_type": l[3],
                    "resource_id": l[4],
                    "created_at": l[5].isoformat(),
                }
                for l in logs
            ]
    
    return app
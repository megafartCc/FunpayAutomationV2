from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.auth_service import AuthService

router = APIRouter()

auth_service = AuthService()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)
    golden_key: str = Field(..., min_length=10, max_length=512)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    token = auth_service.login(payload.username, payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return AuthResponse(access_token=token)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> AuthResponse:
    token = auth_service.register(payload.username, payload.password, payload.golden_key)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    return AuthResponse(access_token=token)

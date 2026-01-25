from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from services.auth_service import AuthService
from services.session_service import SessionService
from services.remember_service import RememberService
from settings.config import settings

router = APIRouter()

auth_service = AuthService()
session_service = SessionService()
remember_service = RememberService()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)
    remember_me: bool = True


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)
    golden_key: str = Field(..., min_length=10, max_length=512)
    remember_me: bool = True


class AuthResponse(BaseModel):
    user_id: int
    username: str
    email: str | None = None


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _clear_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/")


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    user = auth_service.login(payload.username, payload.password)
    if user is None or user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    session_id = session_service.create_session(user.id)
    _set_cookie(response, settings.session_cookie_name, session_id, settings.session_ttl_seconds)
    if payload.remember_me:
        remember_token = remember_service.create_token(user.id, request.headers.get("user-agent"))
        _set_cookie(
            response,
            settings.remember_cookie_name,
            remember_token,
            settings.remember_days * 24 * 60 * 60,
        )
    return AuthResponse(user_id=user.id, username=user.username, email=user.email)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response) -> AuthResponse:
    user = auth_service.register(payload.username, payload.password, payload.golden_key)
    if user is None or user.id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    session_id = session_service.create_session(user.id)
    _set_cookie(response, settings.session_cookie_name, session_id, settings.session_ttl_seconds)
    if payload.remember_me:
        remember_token = remember_service.create_token(user.id, request.headers.get("user-agent"))
        _set_cookie(
            response,
            settings.remember_cookie_name,
            remember_token,
            settings.remember_days * 24 * 60 * 60,
        )
    return AuthResponse(user_id=user.id, username=user.username, email=user.email)


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        session_service.delete_session(session_id)
    remember_token = request.cookies.get(settings.remember_cookie_name)
    if remember_token:
        remember_service.revoke(remember_token)
    _clear_cookie(response, settings.session_cookie_name)
    _clear_cookie(response, settings.remember_cookie_name)
    return {"ok": True}


@router.get("/me", response_model=AuthResponse)
async def me(request: Request, response: Response) -> AuthResponse:
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        user_id = session_service.get_user_id(session_id)
        if user_id:
            user = auth_service.get_user(user_id)
            if user and user.id is not None:
                return AuthResponse(user_id=user.id, username=user.username, email=user.email)

    remember_token = request.cookies.get(settings.remember_cookie_name)
    if remember_token:
        rotated = remember_service.rotate_token(remember_token, request.headers.get("user-agent"))
        if rotated:
            new_token, user_id = rotated
            user = auth_service.get_user(user_id)
            if user and user.id is not None:
                session_id = session_service.create_session(user.id)
                _set_cookie(response, settings.session_cookie_name, session_id, settings.session_ttl_seconds)
                _set_cookie(
                    response,
                    settings.remember_cookie_name,
                    new_token,
                    settings.remember_days * 24 * 60 * 60,
                )
                return AuthResponse(user_id=user.id, username=user.username, email=user.email)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

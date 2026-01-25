from __future__ import annotations

from fastapi import HTTPException, Request, Response, status

from services.auth_service import AuthService
from services.remember_service import RememberService
from services.session_service import SessionService
from settings.config import settings


auth_service = AuthService()
session_service = SessionService()
remember_service = RememberService()


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


def get_current_user(request: Request, response: Response):
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        user_id = session_service.get_user_id(session_id)
        if user_id:
            user = auth_service.get_user(user_id)
            if user and user.id is not None:
                return user

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
                return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

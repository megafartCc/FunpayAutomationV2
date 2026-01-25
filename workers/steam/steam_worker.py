from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SteamHandler.deauthorize import logout_all_steam_sessions  # noqa: E402


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format=LOG_FORMAT,
)
logger = logging.getLogger("steam.worker")

app = FastAPI(title="SteamWorker")


class SteamDeauthorizeRequest(BaseModel):
    steam_login: str = Field(..., min_length=1, max_length=255)
    steam_password: str = Field(..., min_length=1, max_length=255)
    mafile_json: str = Field(..., min_length=2)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/steam/deauthorize")
async def steam_deauthorize(payload: SteamDeauthorizeRequest) -> dict:
    try:
        ok = await logout_all_steam_sessions(
            steam_login=payload.steam_login,
            steam_password=payload.steam_password,
            mafile_json=payload.mafile_json,
        )
    except Exception as exc:
        logger.exception("Steam deauthorize failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not ok:
        raise HTTPException(status_code=500, detail="Failed to deauthorize Steam sessions")
    return {"success": True}


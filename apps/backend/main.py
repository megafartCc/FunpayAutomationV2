import logging
from pathlib import Path
import sys
import types

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import router as auth_router
from api.accounts import router as accounts_router
from api.blacklist import router as blacklist_router
from api.chats import router as chats_router
from api.lots import router as lots_router
from api.orders import router as orders_router
from api.rentals import router as rentals_router
from api.notifications import router as notifications_router
from api.workspaces import router as workspaces_router
from db.mysql import ensure_schema
from settings.config import settings

app = FastAPI(title="FunpayAutomationV2 API")

logger = logging.getLogger("uvicorn.error")


def _load_auto_raise_router():
    path = Path(__file__).resolve().parent / "api" / "auto_raise_clean.py"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        logger.error("auto_raise_clean.py not found; auto-raise disabled")
        return None

    # Try decoding in a safe order; this tolerates accidental UTF-16 files.
    for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            source = data.decode(enc)
            break
        except UnicodeDecodeError:
            source = None
    if source is None:
        # Last resort: strip nulls and decode as UTF-8.
        source = data.replace(b"\x00", b"").decode("utf-8", errors="ignore")
        logger.warning("auto_raise_clean.py had invalid encoding; recovered with null-byte strip")

    if "\x00" in source:
        source = source.replace("\x00", "")
        logger.warning("auto_raise_clean.py contained null bytes; stripped at load")

    try:
        code = compile(source, str(path), "exec")
    except Exception as exc:
        logger.error("Auto-raise module failed to compile: %s", exc)
        return None

    module_name = "api.auto_raise_clean_runtime"
    mod = types.ModuleType(module_name)
    mod.__file__ = str(path)
    mod.__package__ = "api"
    sys.modules[module_name] = mod
    try:
        exec(code, mod.__dict__)
    except Exception as exc:
        logger.error("Auto-raise module failed to exec: %s", exc)
        return None

    router = getattr(mod, "router", None)
    if router is None:
        logger.error("Auto-raise router not found after load")
    return router


@app.on_event("startup")
def _startup() -> None:
    ensure_schema()

if settings.cors_origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(accounts_router, prefix="/api", tags=["accounts"])
app.include_router(blacklist_router, prefix="/api", tags=["blacklist"])
app.include_router(chats_router, prefix="/api", tags=["chats"])
app.include_router(lots_router, prefix="/api", tags=["lots"])
app.include_router(orders_router, prefix="/api", tags=["orders"])
app.include_router(rentals_router, prefix="/api", tags=["rentals"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
app.include_router(workspaces_router, prefix="/api", tags=["workspaces"])
auto_raise_router = _load_auto_raise_router()
if auto_raise_router is not None:
    app.include_router(auto_raise_router, prefix="/api", tags=["auto-raise"])

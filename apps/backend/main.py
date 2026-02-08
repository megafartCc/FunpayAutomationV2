import logging

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
from api.raise_categories import router as raise_categories_router
from api.auto_raise import router as auto_raise_router
from api.bot_customization import router as bot_customization_router
from api.steam_bridge import router as steam_bridge_router
from api.telegram import router as telegram_router
from api.internal import router as internal_router
from api.bonus import router as bonus_router
from api.workspaces import router as workspaces_router
from api.plugins import router as plugins_router, start_price_dumper_scheduler
from services.cleanup_service import start_cleanup_scheduler
from db.mysql import ensure_schema
from settings.config import settings

app = FastAPI(title="FunpayAutomationV2 API")

logger = logging.getLogger("uvicorn.error")


@app.on_event("startup")
def _startup() -> None:
    ensure_schema()
    start_price_dumper_scheduler()
    start_cleanup_scheduler()

if settings.cors_origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
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
app.include_router(raise_categories_router, prefix="/api", tags=["raise-categories"])
app.include_router(auto_raise_router, prefix="/api", tags=["auto-raise"])
app.include_router(bonus_router, prefix="/api", tags=["bonus"])
app.include_router(telegram_router, prefix="/api", tags=["telegram"])
app.include_router(workspaces_router, prefix="/api", tags=["workspaces"])
app.include_router(bot_customization_router, prefix="/api", tags=["bot-customization"])
app.include_router(steam_bridge_router, prefix="/api", tags=["steam-bridge"])
app.include_router(plugins_router, prefix="/api", tags=["plugins"])
app.include_router(internal_router, prefix="/api", tags=["internal"])

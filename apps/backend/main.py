from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.mysql import ensure_schema
from api.auth import router as auth_router
from api.accounts import router as accounts_router
from api.lots import router as lots_router
from settings.config import settings

app = FastAPI(title="FunpayAutomationV2 API")

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
app.include_router(lots_router, prefix="/api", tags=["lots"])


@app.on_event("startup")
def startup() -> None:
    ensure_schema()

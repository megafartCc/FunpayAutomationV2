from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Make backend package and shared libraries importable when launched from repo root or worker dir.
ROOT = Path(__file__).resolve().parents[3]
BACKEND_PATH = ROOT / "apps" / "backend"
SHARED_PATH = ROOT / "packages" / "shared"
for path in (BACKEND_PATH, SHARED_PATH):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Load environment variables from a local .env if present (useful for Railway/CLI).
load_dotenv(ROOT / ".env")
load_dotenv()

from backend.config import (  # noqa: E402
    STEAM_PRESENCE_ENABLED,
    STEAM_PRESENCE_IDENTITY_SECRET,
    STEAM_PRESENCE_LOGIN,
    STEAM_PRESENCE_PASSWORD,
    STEAM_PRESENCE_REFRESH_TOKEN,
    STEAM_PRESENCE_SHARED_SECRET,
)
from backend.logger import logger  # noqa: E402
from SteamHandler.presence_bot import init_presence_bot  # noqa: E402


def main() -> None:
    if not STEAM_PRESENCE_ENABLED:
        logger.warning("Steam presence worker disabled (set STEAM_PRESENCE_ENABLED=1 to run).")
        return

    logger.info("Starting Steam presence worker…")
    bot = init_presence_bot(
        enabled=True,
        login=STEAM_PRESENCE_LOGIN,
        password=STEAM_PRESENCE_PASSWORD,
        shared_secret=STEAM_PRESENCE_SHARED_SECRET or None,
        identity_secret=STEAM_PRESENCE_IDENTITY_SECRET or None,
        refresh_token=STEAM_PRESENCE_REFRESH_TOKEN or None,
    )
    if not bot:
        logger.error("Steam presence bot did not start (check credentials/secrets).")
        return

    bot.wait_ready(timeout=30)
    logger.info("Steam presence worker is running.")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Steam presence worker stopped by signal.")
        os._exit(0)


if __name__ == "__main__":
    main()

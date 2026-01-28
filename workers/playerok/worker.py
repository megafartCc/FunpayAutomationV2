import logging
import os
import time

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> logging.Logger:
    logging.basicConfig(level=os.getenv("PLAYEROK_LOG_LEVEL", "INFO"), format=LOG_FORMAT)
    return logging.getLogger("playerok.worker")


def load_cookies() -> str | None:
    # Either pass inline JSON or a path to a cookies file.
    inline = os.getenv("PLAYEROK_COOKIES_JSON")
    if inline and inline.strip():
        return inline.strip()
    path = os.getenv("PLAYEROK_COOKIES_PATH")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def main() -> None:
    logger = configure_logging()
    cookies = load_cookies()
    if not cookies:
        logger.error("Missing PlayerOk cookies. Set PLAYEROK_COOKIES_JSON or PLAYEROK_COOKIES_PATH.")
        raise SystemExit(1)

    poll_seconds = int(os.getenv("PLAYEROK_POLL_SECONDS", "10"))
    logger.info("PlayerOk worker starting. Poll interval: %ss", poll_seconds)

    # TODO: initialize API client + list accounts/lots/rentals.
    while True:
        # TODO: replace with real polling once API integration is wired.
        logger.debug("PlayerOk worker heartbeat")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()

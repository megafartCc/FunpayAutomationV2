from __future__ import annotations

import logging
import os

from .constants import LOG_FORMAT


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format=LOG_FORMAT,
    )
    if os.getenv("FUNPAY_DEBUG_OFFER_SAVE"):
        logging.getLogger("FunPayAPI").setLevel(logging.INFO)
    else:
        logging.getLogger("FunPayAPI").setLevel(logging.WARNING)
    return logging.getLogger("funpay.worker")

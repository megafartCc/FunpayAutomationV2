from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import re
import struct
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha1
from pathlib import Path
from urllib.parse import urlparse

# Allow running from repo root while importing FunPayAPI from this folder.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mysql.connector  # noqa: E402
from FunPayAPI.account import Account  # noqa: E402
from FunPayAPI.common import exceptions as fp_exceptions  # noqa: E402
from FunPayAPI.common.enums import EventTypes, MessageTypes, SubCategoryTypes  # noqa: E402
from FunPayAPI.common.utils import RegularExpressions  # noqa: E402
from FunPayAPI.updater.events import NewMessageEvent  # noqa: E402
from FunPayAPI.updater.runner import Runner  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
import requests  # noqa: E402
try:  # noqa: E402
    import redis  # type: ignore
except Exception:  # noqa: E402
    redis = None


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# Keep ASCII source while matching Cyrillic commands.
COMMAND_PREFIXES = (
    "!\u0441\u0442\u043e\u043a",
    "!\u0430\u043a\u043a",
    "!\u043a\u043e\u0434",
    "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c",
    "!\u043b\u043f\u0437\u0430\u043c\u0435\u043d\u0430",
    "!\u043e\u0442\u043c\u0435\u043d\u0430",
    "!\u0430\u0434\u043c\u0438\u043d",
    "!\u043f\u0430\u0443\u0437\u0430",
    "!\u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c",
)
STOCK_LIST_LIMIT = 8
STOCK_TITLE = "\u0421\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0435 \u043b\u043e\u0442\u044b:"
STOCK_EMPTY = "\u0421\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0445 \u043b\u043e\u0442\u043e\u0432 \u043d\u0435\u0442."
STOCK_DB_MISSING = (
    "\u0418\u043d\u0432\u0435\u043d\u0442\u0430\u0440\u044c \u043f\u043e\u043a\u0430 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d."
)
RENTALS_EMPTY = "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0430\u0440\u0435\u043d\u0434 \u043d\u0435\u0442."
ORDER_LOT_MISSING = (
    "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u0442\u044c \u043b\u043e\u0442. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u0430\u0434\u043c\u0438\u043d."
)
ORDER_LOT_UNMAPPED = (
    "\u041b\u043e\u0442 \u043d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d \u043a \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u0430\u0434\u043c\u0438\u043d."
)
ORDER_ACCOUNT_BUSY = (
    "\u041b\u043e\u0442 \u0443\u0436\u0435 \u0437\u0430\u043d\u044f\u0442 \u0434\u0440\u0443\u0433\u0438\u043c \u043f\u043e\u043a\u0443\u043f\u0430\u0442\u0435\u043b\u0435\u043c. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u0430\u0434\u043c\u0438\u043d."
)
ORDER_ACCOUNT_REPLACEMENT_PREFIX = (
    "\u041b\u043e\u0442 \u0443\u0436\u0435 \u0430\u0440\u0435\u043d\u0434\u043e\u0432\u0430\u043d \u0434\u0440\u0443\u0433\u0438\u043c \u043f\u043e\u043a\u0443\u043f\u0430\u0442\u0435\u043b\u0435\u043c. "
    "\u041c\u044b \u0432\u044b\u0434\u0430\u043b\u0438 \u0432\u0430\u043c \u0437\u0430\u043c\u0435\u043d\u0443, \u043f\u043e\u0442\u043e\u043c\u0443 \u0447\u0442\u043e \u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0439 \u043b\u043e\u0442 \u0431\u044b\u043b \u0437\u0430\u043d\u044f\u0442."
)
ACCOUNT_HEADER = "\u0412\u0430\u0448 \u0430\u043a\u043a\u0430\u0443\u043d\u0442:"
ACCOUNT_TIMER_NOTE = (
    "\u23f1\ufe0f \u041e\u0442\u0441\u0447\u0435\u0442 \u0430\u0440\u0435\u043d\u0434\u044b \u043d\u0430\u0447\u043d\u0435\u0442\u0441\u044f \u043f\u043e\u0441\u043b\u0435 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u043a\u043e\u0434\u0430 (!\u043a\u043e\u0434)."
)
COMMANDS_RU = (
    "\u041a\u043e\u043c\u0430\u043d\u0434\u044b:\n"
    "!\u0430\u043a\u043a \u2014 \u0434\u0430\u043d\u043d\u044b\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430\n"
    "!\u043a\u043e\u0434 \u2014 \u043a\u043e\u0434 Steam Guard\n"
    "!\u0441\u0442\u043e\u043a \u2014 \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u043e\u0432\n"
    "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c <\u0447\u0430\u0441\u044b> <ID_\u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430> \u2014 \u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u0430\u0440\u0435\u043d\u0434\u0443\n"
    "!\u043f\u0430\u0443\u0437\u0430 <ID> \u2014 \u043f\u0430\u0443\u0437\u0430 \u0430\u0440\u0435\u043d\u0434\u044b \u043d\u0430 1 \u0447\u0430\u0441\n"
    "!\u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c <ID> \u2014 \u0441\u043d\u044f\u0442\u044c \u043f\u0430\u0443\u0437\u0443 \u0440\u0430\u043d\u044c\u0448\u0435 \u0441\u0440\u043e\u043a\u0430\n"
    "!\u0430\u0434\u043c\u0438\u043d \u2014 \u0432\u044b\u0437\u0432\u0430\u0442\u044c \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u0430\n"
    "!\u043b\u043f\u0437\u0430\u043c\u0435\u043d\u0430 <ID> \u2014 \u0437\u0430\u043c\u0435\u043d\u0430 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 (10 \u043c\u0438\u043d\u0443\u0442 \u043f\u043e\u0441\u043b\u0435 !\u043a\u043e\u0434)\n"
    "!\u043e\u0442\u043c\u0435\u043d\u0430 <ID> \u2014 \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c \u0430\u0440\u0435\u043d\u0434\u0443"
)
RENTAL_FROZEN_MESSAGE = (
    "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440 \u0437\u0430\u043c\u043e\u0440\u043e\u0437\u0438\u043b \u0432\u0430\u0448\u0443 \u0430\u0440\u0435\u043d\u0434\u0443. \u0414\u043e\u0441\u0442\u0443\u043f \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d."
)
RENTAL_UNFROZEN_MESSAGE = (
    "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440 \u0440\u0430\u0437\u043c\u043e\u0440\u043e\u0437\u0438\u043b \u0432\u0430\u0448\u0443 \u0430\u0440\u0435\u043d\u0434\u0443. "
    "\u0414\u043e\u0441\u0442\u0443\u043f \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d. \u0427\u0442\u043e \u0431\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u043a\u043e\u0434 \u0435\u0449\u0435 \u0440\u0430\u0437 \u043f\u0440\u043e\u043f\u0438\u0448\u0438\u0442\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0443 !\u043a\u043e\u0434."
)
RENTAL_PAUSED_MESSAGE = (
    "\u23f8\ufe0f \u0412\u0430\u0448\u0430 \u0430\u0440\u0435\u043d\u0434\u0430 \u0437\u0430\u043c\u043e\u0440\u043e\u0436\u0435\u043d\u0430 \u043d\u0430 1 \u0447\u0430\u0441.\n"
    "\u0427\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u0440\u0430\u043d\u044c\u0448\u0435 \u0441\u0440\u043e\u043a\u0430, \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 !\u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"
)
RENTAL_PAUSE_ALREADY_USED_MESSAGE = (
    "\u23f8\ufe0f \u041f\u0430\u0443\u0437\u0430 \u0443\u0436\u0435 \u0431\u044b\u043b\u0430 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0430 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u0430\u0440\u0435\u043d\u0434\u044b."
)
RENTAL_ALREADY_PAUSED_MESSAGE = (
    "\u23f8\ufe0f \u0410\u0440\u0435\u043d\u0434\u0430 \u0443\u0436\u0435 \u043d\u0430 \u043f\u0430\u0443\u0437\u0435."
)
RENTAL_PAUSE_IN_MATCH_MESSAGE = (
    "\u26a0\ufe0f \u041d\u0435\u043b\u044c\u0437\u044f \u043f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0430\u0440\u0435\u043d\u0434\u0443 \u043d\u0430 \u043f\u0430\u0443\u0437\u0443 \u0432\u043e \u0432\u0440\u0435\u043c\u044f \u043c\u0430\u0442\u0447\u0430. "
    "\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u0435 \u043c\u0430\u0442\u0447 \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0441\u043d\u043e\u0432\u0430."
)
RENTAL_CODE_BLOCKED_MESSAGE = (
    "\u23f8\ufe0f \u0410\u0440\u0435\u043d\u0434\u0430 \u043d\u0430 \u043f\u0430\u0443\u0437\u0435, \u043a\u043e\u0434\u044b \u043d\u0430 \u0432\u0440\u0435\u043c\u044f \u043f\u0430\u0443\u0437\u044b \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b."
)
RENTAL_NOT_PAUSED_MESSAGE = (
    "\u25b6\ufe0f \u0410\u0440\u0435\u043d\u0434\u0430 \u043d\u0435 \u043d\u0430 \u043f\u0430\u0443\u0437\u0435."
)
RENTAL_RESUMED_MESSAGE = (
    "\u25b6\ufe0f \u041c\u044b \u0440\u0430\u0437\u043c\u043e\u0440\u043e\u0437\u0438\u043b\u0438 \u0432\u0430\u0448\u0443 \u0430\u0440\u0435\u043d\u0434\u0443. "
    "\u0414\u043e\u0441\u0442\u0443\u043f \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d. \u0427\u0442\u043e \u0431\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u043a\u043e\u0434 \u0435\u0449\u0435 \u0440\u0430\u0437 \u043f\u0440\u043e\u043f\u0438\u0448\u0438\u0442\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0443 !\u043a\u043e\u0434."
)
RENTAL_PAUSE_EXPIRED_MESSAGE = (
    "\u23f0 \u041f\u0430\u0443\u0437\u0430 \u0438\u0441\u0442\u0435\u043a\u043b\u0430 (\u043f\u0440\u043e\u0448\u043b\u043e 1 \u0447\u0430\u0441). \u0410\u0440\u0435\u043d\u0434\u0430 \u0432\u043e\u0437\u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0430."
)
RENTAL_EXPIRED_MESSAGE = "\u0410\u0440\u0435\u043d\u0434\u0430 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0430\u0441\u044c. \u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442."
RENTAL_EXPIRED_CONFIRM_MESSAGE = (
    "\u0417\u0430\u043a\u0430\u0437 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d. \u041f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u0437\u0430\u0439\u0434\u0438\u0442\u0435 \u0432 \u0440\u0430\u0437\u0434\u0435\u043b \u00ab\u041f\u043e\u043a\u0443\u043f\u043a\u0438\u00bb, \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0435\u0433\u043e \u0432 \u0441\u043f\u0438\u0441\u043a\u0435 \u0438 \u043d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 \u00ab\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435 \u0437\u0430\u043a\u0430\u0437\u0430\u00bb."
)
RENTAL_EXPIRE_DELAY_MESSAGE = (
    "\u0412\u0430\u0448\u0430 \u0430\u0440\u0435\u043d\u0434\u0430 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0430\u0441\u044c, \u043d\u043e \u043c\u044b \u0432\u0438\u0434\u0438\u043c, \u0447\u0442\u043e \u0432\u044b \u0432 \u043c\u0430\u0442\u0447\u0435.\n"
    "\u0423 \u0432\u0430\u0441 \u0435\u0441\u0442\u044c \u0432\u0440\u0435\u043c\u044f, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u0442\u044c \u043c\u0430\u0442\u0447. \u0427\u0435\u0440\u0435\u0437 1 \u043c\u0438\u043d\u0443\u0442\u0443 \u044f \u043f\u0440\u043e\u0432\u0435\u0440\u044e \u0441\u043d\u043e\u0432\u0430.\n"
    "\u0414\u043e\u0441\u0442\u0443\u043f \u0431\u0443\u0434\u0435\u0442 \u0437\u0430\u043a\u0440\u044b\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438, \u0435\u0441\u043b\u0438 \u043c\u0430\u0442\u0447 \u0443\u0436\u0435 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u0442\u0441\u044f.\n"
    "\u0415\u0441\u043b\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u2014 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0443:\n"
    "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c <\u0447\u0430\u0441\u044b> <ID \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430>"
)
LP_REPLACE_WINDOW_MINUTES = 10
LP_REPLACE_MMR_RANGE = 1000
LP_REPLACE_NO_CODE_MESSAGE = (
    "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u0435 \u043a\u043e\u0434 (!\u043a\u043e\u0434), "
    "\u0437\u0430\u0442\u0435\u043c \u043c\u043e\u0436\u043d\u043e \u0437\u0430\u043f\u0440\u043e\u0441\u0438\u0442\u044c \u0437\u0430\u043c\u0435\u043d\u0443."
)
LP_REPLACE_TOO_LATE_MESSAGE = (
    "\u0417\u0430\u043c\u0435\u043d\u0430 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u0432 \u0442\u0435\u0447\u0435\u043d\u0438\u0435 "
    "10 \u043c\u0438\u043d\u0443\u0442 \u043f\u043e\u0441\u043b\u0435 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u043a\u043e\u0434\u0430 (!\u043a\u043e\u0434)."
)
LP_REPLACE_NO_MMR_MESSAGE = (
    "\u0414\u043b\u044f \u0437\u0430\u043c\u0435\u043d\u044b \u043d\u0443\u0436\u0435\u043d MMR \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430. "
    "\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443."
)
LP_REPLACE_NO_MATCH_MESSAGE = (
    "\u041d\u0435\u0442 \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u043e\u0433\u043e \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 \u0434\u043b\u044f \u0437\u0430\u043c\u0435\u043d\u044b "
    "\u0432 \u043f\u0440\u0435\u0434\u0435\u043b\u0430\u0445 \u00b11000 MMR. \u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443."
)
LP_REPLACE_FAILED_MESSAGE = (
    "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0437\u0430\u043c\u0435\u043d\u0443. "
    "\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443."
)
LP_REPLACE_SUCCESS_PREFIX = "\u2705 \u0417\u0430\u043c\u0435\u043d\u0430 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0430. \u041d\u043e\u0432\u044b\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442:"
ORDER_ID_RE = RegularExpressions().ORDER_ID
LOT_NUMBER_RE = re.compile(r"(?:\u2116|#)\s*(\d+)")

_processed_orders: dict[str, set[str]] = {}
_processed_orders_lock = threading.Lock()
_redis_client = None
_chat_history_prefetch_seen: dict[tuple[int, int | None, int], float] = {}
_chat_history_prefetch_lock = threading.Lock()


@dataclass
class RentalMonitorState:
    last_check_ts: float = 0.0
    freeze_cache: dict[int, bool] = field(default_factory=dict)
    expire_delay_since: dict[int, datetime] = field(default_factory=dict)
    expire_delay_next_check: dict[int, datetime] = field(default_factory=dict)
    expire_delay_notified: set[int] = field(default_factory=set)
    expire_soon_notified: dict[int, int] = field(default_factory=dict)


@dataclass
class AutoRaiseSettings:
    enabled: bool = False
    categories: list[int] = field(default_factory=list)
    interval_hours: int = 1


def detect_command(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.strip().lower()
    if not cleaned.startswith("!"):
        return None
    for cmd in COMMAND_PREFIXES:
        if cleaned.startswith(cmd):
            return cmd
    return None


def parse_command(text: str | None) -> tuple[str | None, str]:
    if not text:
        return None, ""
    cleaned = text.strip()
    if not cleaned.startswith("!"):
        return None, ""
    parts = cleaned.split(maxsplit=1)
    command = parts[0].lower()
    if command not in COMMAND_PREFIXES:
        return None, ""
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def normalize_username(name: str | None) -> str:
    return (name or "").strip().lower()


def _orders_key(site_username: str | None, site_user_id: int | None, workspace_id: int | None) -> str:
    if site_user_id is not None:
        base = str(site_user_id)
    else:
        base = site_username or "single"
    if workspace_id is not None:
        return f"{base}:{workspace_id}"
    return base


def is_order_processed(
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    order_id: str,
) -> bool:
    key = _orders_key(site_username, site_user_id, workspace_id)
    with _processed_orders_lock:
        return order_id in _processed_orders.get(key, set())


def mark_order_processed(
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    order_id: str,
) -> None:
    key = _orders_key(site_username, site_user_id, workspace_id)
    with _processed_orders_lock:
        bucket = _processed_orders.setdefault(key, set())
        bucket.add(order_id)
        if len(bucket) > 5000:
            _processed_orders[key] = set(list(bucket)[-1000:])


def format_duration_minutes(total_minutes: int | None) -> str:
    minutes = int(total_minutes or 0)
    if minutes <= 0:
        return "0 \u043c\u0438\u043d"
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours} \u0447 {mins} \u043c\u0438\u043d"
    if hours:
        return f"{hours} \u0447"
    return f"{mins} \u043c\u0438\u043d"


def format_hours_label(hours: int) -> str:
    value = int(hours)
    if 11 <= (value % 100) <= 14:
        return "\u0447\u0430\u0441\u043e\u0432"
    last = value % 10
    if last == 1:
        return "\u0447\u0430\u0441"
    if 2 <= last <= 4:
        return "\u0447\u0430\u0441\u0430"
    return "\u0447\u0430\u0441\u043e\u0432"


def format_penalty_label(total_minutes: int | None) -> str:
    minutes = int(total_minutes or 0)
    if minutes > 0 and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} {format_hours_label(hours)}"
    return format_duration_minutes(minutes)


def normalize_owner_name(owner: str | None) -> str:
    return str(owner or "").strip().lower()


def format_time_left(seconds_left: int) -> str:
    total = max(0, int(seconds_left))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours:
        return f"{hours} \u0447 {minutes} \u043c\u0438\u043d {seconds} \u0441\u0435\u043a"
    if minutes:
        return f"{minutes} \u043c\u0438\u043d {seconds} \u0441\u0435\u043a"
    return f"{seconds} \u0441\u0435\u043a"


def build_expire_soon_message(account_row: dict, seconds_left: int) -> str:
    account_id = account_row.get("id")
    name = account_row.get("account_name") or account_row.get("login") or f"ID {account_id}"
    label = f"{name} (ID {account_id})" if account_id is not None else name
    time_left = format_time_left(seconds_left)
    lot_number = account_row.get("lot_number")
    lot_url = account_row.get("lot_url")
    if lot_number and lot_url:
        lot_label = f"\u041b\u043e\u0442 \u2116{lot_number}: {lot_url}"
    elif lot_number:
        lot_label = f"\u041b\u043e\u0442 \u2116{lot_number}"
    elif lot_url:
        lot_label = f"\u041b\u043e\u0442: {lot_url}"
    else:
        lot_label = "\u043b\u043e\u0442, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d \u043a \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443"

    return (
        f"\u23f3 \u0412\u0430\u0448\u0430 \u0430\u0440\u0435\u043d\u0434\u0430 {label} \u0441\u043a\u043e\u0440\u043e \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u0442\u0441\u044f.\n"
        f"\u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c: {time_left}.\n"
        f"\u0415\u0441\u043b\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u2014 \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430 \u043e\u043f\u043b\u0430\u0442\u0438\u0442\u0435 \u044d\u0442\u043e\u0442 {lot_label}."
    )


def parse_lot_number(text: str | None) -> int | None:
    if not text:
        return None
    match = LOT_NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def extract_order_id(text: str | None) -> str | None:
    if not text:
        return None
    match = ORDER_ID_RE.search(text)
    if not match:
        return None
    return match.group(0).lstrip("#")


def extract_lot_number_from_order(order: object) -> int | None:
    candidates = [
        getattr(order, "full_description", None),
        getattr(order, "short_description", None),
        getattr(order, "title", None),
        getattr(order, "html", None),
    ]
    for item in candidates:
        lot_number = parse_lot_number(item if isinstance(item, str) else None)
        if lot_number is not None:
            return lot_number
    return None


def parse_account_id_arg(args: str) -> int | None:
    if not args:
        return None
    token = args.strip().split(maxsplit=1)[0]
    if not token.isdigit():
        return None
    try:
        return int(token)
    except ValueError:
        return None


def build_rental_choice_message(accounts: list[dict], command: str) -> str:
    lines = [
        "\u0423 \u0432\u0430\u0441 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0430\u0440\u0435\u043d\u0434.",
        f"\u0423\u043a\u0430\u0436\u0438\u0442\u0435 ID \u0432 \u043a\u043e\u043c\u0430\u043d\u0434\u0435 {command} <ID>:",
        "",
    ]
    for acc in accounts:
        display = build_display_name(acc)
        lines.append(f"ID {acc.get('id')}: {display}")
    return "\n".join(lines)


def _calculate_resume_start(rental_start: object, frozen_at: object) -> datetime | None:
    start_dt = _parse_datetime(rental_start)
    frozen_dt = _parse_datetime(frozen_at)
    if not start_dt or not frozen_dt:
        return None
    delta = datetime.utcnow() - frozen_dt
    if delta.total_seconds() < 0:
        delta = timedelta(0)
    return start_dt + delta


def get_unit_minutes(account: dict) -> int:
    return 60


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


_CHAT_TIME_CLASS_KEYS = (
    "contact-item-time",
    "contact-item-date",
    "chat-msg-time",
    "chat-msg-date",
    "chat-msg-date-time",
)
_CHAT_TIME_ATTR_KEYS = (
    "data-time",
    "data-date",
    "data-timestamp",
    "data-last-message-time",
    "data-last-msg-time",
)
_CHAT_TIME_RE_YMD = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_DMY = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_DM = re.compile(r"\b(\d{1,2})[./](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CHAT_TIME_RE_RU_MONTH = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>[а-яё\.]+)\s*(?P<year>\d{4})?,?\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?\b",
    re.IGNORECASE,
)
_MSK_OFFSET = timedelta(hours=3)
_RU_MONTHS = {
    "января": 1,
    "январь": 1,
    "янв": 1,
    "февраля": 2,
    "февраль": 2,
    "фев": 2,
    "марта": 3,
    "март": 3,
    "мар": 3,
    "апреля": 4,
    "апрель": 4,
    "апр": 4,
    "мая": 5,
    "май": 5,
    "июня": 6,
    "июнь": 6,
    "июл": 7,
    "июля": 7,
    "июль": 7,
    "августа": 8,
    "август": 8,
    "авг": 8,
    "сентября": 9,
    "сентябрь": 9,
    "сен": 9,
    "сент": 9,
    "октября": 10,
    "октябрь": 10,
    "окт": 10,
    "ноября": 11,
    "ноябрь": 11,
    "ноя": 11,
    "декабря": 12,
    "декабрь": 12,
    "дек": 12,
}


def _msk_now() -> datetime:
    return datetime.utcnow() + _MSK_OFFSET


def _msk_to_utc(value: datetime) -> datetime:
    return value - _MSK_OFFSET


def _parse_funpay_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    raw = " ".join(str(text).strip().split())
    if not raw:
        return None

    if raw.isdigit():
        try:
            ts = int(raw)
        except ValueError:
            ts = 0
        if ts > 0:
            if ts > 10**12:
                ts = ts / 1000.0
            try:
                return datetime.utcfromtimestamp(float(ts))
            except Exception:
                return None

    match = _CHAT_TIME_RE_YMD.search(raw)
    if match:
        year, month, day, hour, minute, second = match.groups()
        dt_msk = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    match = _CHAT_TIME_RE_DMY.search(raw)
    if match:
        day, month, year, hour, minute, second = match.groups()
        year_val = int(year)
        if year_val < 100:
            year_val += 2000
        dt_msk = datetime(
            int(year_val),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    match = _CHAT_TIME_RE_DM.search(raw)
    if match:
        day, month, hour, minute, second = match.groups()
        now = _msk_now()
        dt_msk = datetime(
            now.year,
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    lowered = raw.lower()
    yesterday_flag = "\u0432\u0447\u0435\u0440\u0430" in lowered or "yesterday" in lowered
    match = _CHAT_TIME_RE_RU_MONTH.search(raw)
    if match:
        day = int(match.group("day"))
        month_raw = match.group("month") or ""
        month_key = re.sub(r"[^a-zA-Zа-яА-ЯёЁ]", "", month_raw).lower()
        month = _RU_MONTHS.get(month_key)
        if month:
            year_raw = match.group("year")
            now_msk = _msk_now()
            year_val = int(year_raw) if year_raw else now_msk.year
            dt_msk = datetime(
                year_val,
                month,
                day,
                int(match.group("hour")),
                int(match.group("minute")),
                int(match.group("second") or 0),
            )
            if not year_raw and dt_msk > now_msk + timedelta(days=1):
                dt_msk = dt_msk.replace(year=dt_msk.year - 1)
            return _msk_to_utc(dt_msk)

    match = _CHAT_TIME_RE_TIME.search(raw)
    if match:
        hour, minute, second = match.groups()
        base = _msk_now().date()
        if yesterday_flag:
            base = base - timedelta(days=1)
        dt_msk = datetime(
            base.year,
            base.month,
            base.day,
            int(hour),
            int(minute),
            int(second or 0),
        )
        return _msk_to_utc(dt_msk)

    return None


def _extract_datetime_from_html(html: str | None) -> datetime | None:
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return _parse_funpay_datetime(html)

    candidates: list[str] = []
    for attr in _CHAT_TIME_ATTR_KEYS:
        for el in soup.find_all(attrs={attr: True}):
            value = el.get(attr)
            if value:
                candidates.append(str(value))

    for el in soup.find_all("time"):
        text = el.get_text(" ", strip=True)
        if text:
            candidates.append(text)

    for el in soup.find_all(class_=True):
        classes = " ".join(el.get("class", []))
        class_lower = classes.lower()
        if any(key in classes for key in _CHAT_TIME_CLASS_KEYS) or (
            ("time" in class_lower or "date" in class_lower)
            and ("chat" in class_lower or "contact" in class_lower or "msg" in class_lower)
        ):
            title = el.get("title")
            if title:
                candidates.append(str(title))
            text = el.get_text(" ", strip=True)
            if text:
                candidates.append(text)

    for candidate in candidates:
        dt = _parse_funpay_datetime(candidate)
        if dt:
            return dt

    return None


def _fetch_latest_chat_times(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    chat_ids: list[int],
) -> dict[int, datetime]:
    if not chat_ids:
        return {}
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(chat_ids))
        params: list = [int(user_id)]
        workspace_clause = " AND workspace_id IS NULL"
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        params.extend([int(cid) for cid in chat_ids])
        cursor.execute(
            f"""
            SELECT chat_id, MAX(sent_time) AS last_time
            FROM chat_messages
            WHERE user_id = %s{workspace_clause} AND chat_id IN ({placeholders})
            GROUP BY chat_id
            """,
            tuple(params),
        )
        rows = cursor.fetchall() or []
        result: dict[int, datetime] = {}
        for row in rows:
            chat_id = row.get("chat_id")
            last_time = row.get("last_time")
            if chat_id is None or last_time is None:
                continue
            try:
                result[int(chat_id)] = last_time if isinstance(last_time, datetime) else datetime.fromisoformat(str(last_time))
            except Exception:
                continue
        return result
    finally:
        conn.close()


def _resolve_rental_minutes(account: dict) -> int:
    minutes = account.get("rental_duration_minutes")
    if minutes is None:
        try:
            minutes = int(account.get("rental_duration") or 0) * 60
        except Exception:
            minutes = 0
    try:
        return int(minutes or 0)
    except Exception:
        return 0


def get_remaining_label(account: dict, now: datetime) -> tuple[str | None, str]:
    rental_start = _parse_datetime(account.get("rental_start"))
    total_minutes = account.get("rental_duration_minutes")
    try:
        total_minutes_int = int(total_minutes or 0)
    except Exception:
        total_minutes_int = 0
    if not rental_start or total_minutes_int <= 0:
        return None, "\u043e\u0436\u0438\u0434\u0430\u0435\u043c !\u043a\u043e\u0434"
    expiry_time = rental_start + timedelta(minutes=total_minutes_int)
    remaining = expiry_time - now
    if remaining.total_seconds() < 0:
        remaining = timedelta(0)
    hours = int(remaining.total_seconds() // 3600)
    mins = int((remaining.total_seconds() % 3600) // 60)
    remaining_label = f"{hours} \u0447 {mins} \u043c\u0438\u043d"
    return expiry_time.strftime("%H:%M:%S"), remaining_label


def build_display_name(account: dict) -> str:
    # Prefer per-workspace override from lots.display_name, then fallback to account_name/login.
    name = (
        account.get("display_name")
        or account.get("account_name")
        or account.get("login")
        or ""
    ).strip()
    lot_number = account.get("lot_number")
    if lot_number and not name.startswith("\u2116"):
        prefix = f"\u2116{lot_number} "
        name = f"{prefix}{name}" if name else prefix.strip()
    return name or "\u0410\u043a\u043a\u0430\u0443\u043d\u0442"


def build_account_message(account: dict, duration_minutes: int, include_timer_note: bool) -> str:
    display_name = build_display_name(account)
    now = datetime.utcnow()
    expiry_str, remaining_str = get_remaining_label(account, now)
    lines = [
        ACCOUNT_HEADER,
        f"ID: {account.get('id')}",
        f"\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435: {display_name}",
        f"\u041b\u043e\u0433\u0438\u043d: {account.get('login')}",
        f"\u041f\u0430\u0440\u043e\u043b\u044c: {account.get('password')}",
    ]
    if expiry_str:
        lines.append(f"\u0418\u0441\u0442\u0435\u043a\u0430\u0435\u0442: {expiry_str} \u041c\u0421\u041a | \u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c: {remaining_str}")
    else:
        lines.append(f"\u0410\u0440\u0435\u043d\u0434\u0430: {format_duration_minutes(duration_minutes)}")
        if include_timer_note:
            lines.extend(["", ACCOUNT_TIMER_NOTE])
    lines.extend(["", COMMANDS_RU])
    return "\n".join(lines)


def get_query_time() -> int:
    try:
        import requests

        request = requests.post(
            "https://api.steampowered.com/ITwoFactorService/QueryTime/v0001",
            timeout=15,
        )
        json_data = request.json()
        server_time = int(json_data["response"]["server_time"]) - time.time()
        return int(server_time)
    except Exception:
        return 0


def get_guard_code(shared_secret: str) -> str:
    symbols = "23456789BCDFGHJKMNPQRTVWXY"
    timestamp = time.time() + get_query_time()
    digest = hmac.new(
        base64.b64decode(shared_secret),
        struct.pack(">Q", int(timestamp / 30)),
        sha1,
    ).digest()
    start = digest[19] & 0x0F
    value = struct.unpack(">I", digest[start : start + 4])[0] & 0x7FFFFFFF
    code = ""
    for _ in range(5):
        code += symbols[value % len(symbols)]
        value //= len(symbols)
    return code


def get_steam_guard_code(mafile_json: str | dict | None) -> tuple[bool, str]:
    if not mafile_json:
        return False, "\u041d\u0435\u0442 maFile"
    try:
        data = mafile_json if isinstance(mafile_json, dict) else json.loads(mafile_json)
        shared_secret = data.get("shared_secret")
        if not shared_secret:
            return False, "\u041d\u0435\u0442 shared_secret"
        return True, get_guard_code(shared_secret)
    except Exception as exc:
        return False, str(exc)


def send_chat_message(logger: logging.Logger, account: Account, chat_id: int, text: str) -> bool:
    try:
        account.send_message(chat_id, text)
        return True
    except Exception as exc:
        logger.warning("Failed to send chat message: %s", exc)
        return False


def send_message_by_owner(logger: logging.Logger, account: Account, owner: str | None, text: str) -> bool:
    if not owner:
        return False
    try:
        chat = account.get_chat_by_name(owner, True)
    except Exception as exc:
        logger.warning("Failed to resolve chat for %s: %s", owner, exc)
        return False
    chat_id = getattr(chat, "id", None)
    if not chat_id:
        logger.warning("Chat not found for %s.", owner)
        return False
    return send_chat_message(logger, account, int(chat_id), text)


def _steam_id_from_mafile(mafile_json: str | dict | None) -> str | None:
    if not mafile_json:
        return None
    try:
        data = mafile_json if isinstance(mafile_json, dict) else json.loads(mafile_json)
        steam_value = (data or {}).get("Session", {}).get("SteamID")
        if steam_value is None:
            steam_value = (data or {}).get("steamid") or (data or {}).get("SteamID")
        if steam_value is not None:
            return str(int(steam_value))
    except Exception:
        return None
    return None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if redis is None:
        _redis_client = None
        return None
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        _redis_client = None
        return None
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    except Exception:
        _redis_client = None
    return _redis_client


def _clear_lot_cache_on_start() -> None:
    """Best-effort cache bust for lot mappings so fresh display names are used after deploy."""
    cache = _get_redis()
    if not cache:
        return
    patterns = ["lot:*", "lot_mapping:*", "lot:list:*", "lot:stock:*"]
    for pattern in patterns:
        keys = list(cache.scan_iter(match=pattern))
        if keys:
            cache.delete(*keys)

def _presence_cache_key(steam_id: str) -> str:
    return f"presence:{steam_id}"


def _presence_cache_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_TTL_SECONDS", "15"))


def _presence_cache_empty_ttl_seconds() -> int:
    return int(os.getenv("PRESENCE_CACHE_EMPTY_TTL_SECONDS", "5"))


def _chat_history_prefetch_cooldown_seconds() -> int:
    return int(os.getenv("CHAT_HISTORY_PREFETCH_COOLDOWN_SECONDS", "600"))


def _should_prefetch_history(user_id: int, workspace_id: int | None, chat_id: int) -> bool:
    now = time.time()
    key = (int(user_id), int(workspace_id) if workspace_id is not None else -1, int(chat_id))
    cooldown = _chat_history_prefetch_cooldown_seconds()
    with _chat_history_prefetch_lock:
        last = _chat_history_prefetch_seen.get(key)
        if last is not None and now - last < cooldown:
            return False
        _chat_history_prefetch_seen[key] = now
    return True


def _chat_cache_workspace_key(workspace_id: int | None) -> str:
    return "none" if workspace_id is None else str(int(workspace_id))


def _chat_list_cache_pattern(user_id: int, workspace_id: int | None) -> str:
    return f"chat:list:{int(user_id)}:{_chat_cache_workspace_key(workspace_id)}:*"


def _chat_history_cache_pattern(user_id: int, workspace_id: int | None, chat_id: int) -> str:
    return f"chat:history:{int(user_id)}:{_chat_cache_workspace_key(workspace_id)}:{int(chat_id)}:*"


def invalidate_chat_cache(user_id: int, workspace_id: int | None, chat_id: int) -> None:
    cache = _get_redis()
    if not cache:
        return
    patterns = [
        _chat_list_cache_pattern(user_id, workspace_id),
        _chat_history_cache_pattern(user_id, workspace_id, chat_id),
    ]
    for pattern in patterns:
        try:
            batch: list[str] = []
            for key in cache.scan_iter(match=pattern):
                batch.append(str(key))
                if len(batch) >= 200:
                    cache.delete(*batch)
                    batch.clear()
            if batch:
                cache.delete(*batch)
        except Exception:
            continue


def _is_admin_command(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return "!админ" in lowered or "!admin" in lowered


def fetch_presence(steam_id: str | None) -> dict:
    if not steam_id:
        return {}
    cache = _get_redis()
    if cache:
        try:
            cached_raw = cache.get(_presence_cache_key(steam_id))
        except Exception:
            cached_raw = None
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except Exception:
                cached = None
            return cached if isinstance(cached, dict) else {}
    base = os.getenv("STEAM_PRESENCE_URL", "").strip() or os.getenv("STEAM_BRIDGE_URL", "").strip()
    if not base:
        return {}
    base = base.rstrip("/")
    if base.endswith("/presence"):
        url = f"{base}/{steam_id}"
    else:
        url = f"{base}/presence/{steam_id}"
    try:
        resp = requests.get(url, timeout=5)
    except requests.RequestException:
        return {}
    if not resp.ok:
        if cache:
            try:
                cache.set(_presence_cache_key(steam_id), "null", ex=_presence_cache_empty_ttl_seconds())
            except Exception:
                pass
        return {}
    try:
        data = resp.json()
    except Exception:
        if cache:
            try:
                cache.set(_presence_cache_key(steam_id), "null", ex=_presence_cache_empty_ttl_seconds())
            except Exception:
                pass
        return {}
    if not isinstance(data, dict):
        if cache:
            try:
                cache.set(_presence_cache_key(steam_id), "null", ex=_presence_cache_empty_ttl_seconds())
            except Exception:
                pass
        return {}
    if cache:
        try:
            cache.set(
                _presence_cache_key(steam_id),
                json.dumps(data, ensure_ascii=False),
                ex=_presence_cache_ttl_seconds(),
            )
        except Exception:
            pass
    return data


def fetch_active_rentals_for_monitor(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None = None,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_last_rented = column_exists(cursor, "accounts", "last_rented_workspace_id")
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_lots = table_exists(cursor, "lots")
        has_lot_number = has_lots and column_exists(cursor, "lots", "lot_number")
        has_lot_url = has_lots and column_exists(cursor, "lots", "lot_url")
        has_lot_user_id = has_lots and column_exists(cursor, "lots", "user_id")
        has_lot_workspace = has_lots and column_exists(cursor, "lots", "workspace_id")
        has_account_lot_url = column_exists(cursor, "accounts", "lot_url")

        workspace_expr = "a.workspace_id"
        if has_last_rented:
            workspace_expr = "COALESCE(a.last_rented_workspace_id, a.workspace_id)"

        params: list = [user_id]
        workspace_clause = ""
        if workspace_id is not None:
            workspace_clause = f" AND {workspace_expr} = %s"
            params.append(workspace_id)

        lot_join = ""
        lot_fields = ""
        if has_lots:
            lot_join = "LEFT JOIN lots l ON l.account_id = a.id"
            if has_lot_user_id:
                lot_join += " AND l.user_id = a.user_id"
            if has_lot_workspace:
                lot_join += f" AND l.workspace_id = {workspace_expr}"
            if has_lot_number:
                lot_fields += ", l.lot_number AS lot_number"
            if has_lot_url and has_account_lot_url:
                lot_fields += ", COALESCE(l.lot_url, a.lot_url) AS lot_url"
            elif has_lot_url:
                lot_fields += ", l.lot_url AS lot_url"
            elif has_account_lot_url:
                lot_fields += ", a.lot_url AS lot_url"
        elif has_account_lot_url:
            lot_fields += ", a.lot_url AS lot_url"
        cursor.execute(
            f"""
            SELECT a.id, a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_name, a.login, a.password, a.mafile_json, a.account_frozen, a.rental_frozen
                   {', rental_frozen_at' if has_frozen_at else ''}
                   {lot_fields}
            FROM accounts a
            {lot_join}
            WHERE a.user_id = %s AND a.owner IS NOT NULL AND a.owner != ''{workspace_clause}
            """,
            tuple(params),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def is_blacklisted(
    mysql_cfg: dict,
    owner: str | None,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist"):
            return False
        params: list = [owner_key, int(user_id)]
        workspace_clause = ""
        if workspace_id is not None:
            workspace_clause = " AND (workspace_id = %s OR workspace_id IS NULL)"
            params.append(int(workspace_id))
        cursor.execute(
            f"SELECT 1 FROM blacklist WHERE owner = %s AND user_id = %s{workspace_clause} LIMIT 1",
            tuple(params),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def log_blacklist_event(
    mysql_cfg: dict,
    *,
    owner: str,
    action: str,
    reason: str | None = None,
    details: str | None = None,
    amount: int | None = None,
    user_id: int,
    workspace_id: int | None = None,
) -> None:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist_logs"):
            return
        cursor.execute(
            """
            INSERT INTO blacklist_logs (owner, action, reason, details, amount, user_id, workspace_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_key,
                action,
                reason,
                details,
                int(amount) if amount is not None else None,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_chat_summary(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    name: str | None,
    last_message_text: str | None,
    unread: bool | None,
    last_message_time: datetime | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chats"):
            return
        cursor.execute(
            """
            INSERT INTO chats (
                chat_id, name, last_message_text, last_message_time, unread,
                admin_unread_count, admin_requested, user_id, workspace_id
            )
            VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                last_message_text = VALUES(last_message_text),
                last_message_time = CASE
                    WHEN VALUES(last_message_time) IS NULL THEN last_message_time
                    WHEN last_message_text IS NULL OR VALUES(last_message_text) <> last_message_text
                        THEN VALUES(last_message_time)
                    ELSE last_message_time
                END,
                unread = VALUES(unread)
            """,
            (
                int(chat_id),
                name.strip() if isinstance(name, str) and name.strip() else None,
                last_message_text.strip() if isinstance(last_message_text, str) and last_message_text.strip() else None,
                last_message_time,
                1 if unread else 0,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_chat_message(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_id: int,
    message_id: int,
    author: str | None,
    text: str | None,
    by_bot: bool,
    message_type: str | None,
    sent_time: datetime | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chat_messages"):
            return
        cursor.execute(
            """
            INSERT INTO chat_messages (
                message_id, chat_id, author, text, sent_time, by_bot, message_type, user_id, workspace_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id = id
            """,
            (
                int(message_id),
                int(chat_id),
                author.strip() if isinstance(author, str) and author.strip() else None,
                text if text is not None else None,
                sent_time,
                1 if by_bot else 0,
                message_type,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        inserted = cursor.rowcount == 1
        if inserted and _is_admin_command(text) and not by_bot:
            cursor.execute(
                """
                UPDATE chats
                SET admin_unread_count = admin_unread_count + 1,
                    admin_requested = 1
                WHERE user_id = %s AND workspace_id <=> %s AND chat_id = %s
                """,
                (
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                    int(chat_id),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    invalidate_chat_cache(int(user_id), workspace_id, int(chat_id))


def fetch_chat_outbox(
    mysql_cfg: dict,
    user_id: int,
    workspace_id: int | None,
    limit: int = 20,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "chat_outbox"):
            return []
        cursor.execute(
            """
            SELECT id, chat_id, text, attempts
            FROM chat_outbox
            WHERE status = 'pending' AND user_id = %s AND workspace_id <=> %s
            ORDER BY id ASC
            LIMIT %s
            """,
            (int(user_id), int(workspace_id) if workspace_id is not None else None, int(max(1, min(limit, 200)))),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def mark_outbox_sent(mysql_cfg: dict, outbox_id: int, workspace_id: int | None = None) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_outbox SET status='sent', sent_at=NOW() WHERE id = %s",
            (int(outbox_id),),
        )
        conn.commit()
    finally:
        conn.close()


def mark_outbox_failed(
    mysql_cfg: dict,
    outbox_id: int,
    error: str,
    attempts: int,
    max_attempts: int,
    workspace_id: int | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        status = "failed" if attempts >= max_attempts else "pending"
        cursor.execute(
            """
            UPDATE chat_outbox
            SET status=%s, attempts=%s, last_error=%s
            WHERE id = %s
            """,
            (status, int(attempts), error[:500], int(outbox_id)),
        )
        conn.commit()
    finally:
        conn.close()


def log_order_history(
    mysql_cfg: dict,
    *,
    order_id: str,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
    account_id: int | None = None,
    account_name: str | None = None,
    steam_id: str | None = None,
    rental_minutes: int | None = None,
    lot_number: int | None = None,
    amount: int | None = None,
    price: float | None = None,
    action: str = "purchase",
) -> None:
    order_key = str(order_id or "").strip()
    if order_key.startswith("#"):
        order_key = order_key[1:]
    owner_key = normalize_owner_name(owner)
    if not order_key or not owner_key:
        return
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return
        has_steam_id = column_exists(cursor, "order_history", "steam_id")
        if has_steam_id:
            cursor.execute(
                """
                INSERT INTO order_history (
                    order_id, owner, account_name, account_id, steam_id, rental_minutes,
                    lot_number, amount, price, action, user_id, workspace_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_key,
                    owner_key,
                    account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                    int(account_id) if account_id is not None else None,
                    steam_id.strip() if isinstance(steam_id, str) and steam_id.strip() else None,
                    int(rental_minutes) if rental_minutes is not None else None,
                    int(lot_number) if lot_number is not None else None,
                    int(amount) if amount is not None else None,
                    float(price) if price is not None else None,
                    action,
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO order_history (
                    order_id, owner, account_name, account_id, rental_minutes,
                    lot_number, amount, price, action, user_id, workspace_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_key,
                    owner_key,
                    account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                    int(account_id) if account_id is not None else None,
                    int(rental_minutes) if rental_minutes is not None else None,
                    int(lot_number) if lot_number is not None else None,
                    int(amount) if amount is not None else None,
                    float(price) if price is not None else None,
                    action,
                    int(user_id),
                    int(workspace_id) if workspace_id is not None else None,
                ),
            )
        conn.commit()
        log_notification_event(
            mysql_cfg,
            event_type="purchase",
            status="ok",
            title="Order activity",
            message=f"Order {order_key} action: {action}.",
            owner=owner_key,
            account_name=account_name,
            account_id=account_id,
            order_id=order_key,
            user_id=user_id,
            workspace_id=workspace_id,
        )
    finally:
        conn.close()


def fetch_latest_order_id_for_account(
    mysql_cfg: dict,
    *,
    account_id: int,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> str | None:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return None
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "order_history"):
            return None
        workspace_clause = ""
        params: list = [int(user_id), int(account_id), owner_key]
        if workspace_id is not None:
            workspace_clause = " AND workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT order_id
            FROM order_history
            WHERE user_id = %s AND account_id = %s AND owner = %s{workspace_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def log_notification_event(
    mysql_cfg: dict,
    *,
    event_type: str,
    status: str,
    title: str,
    user_id: int,
    workspace_id: int | None = None,
    message: str | None = None,
    owner: str | None = None,
    account_name: str | None = None,
    account_id: int | None = None,
    order_id: str | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "notification_logs"):
            return
        cursor.execute(
            """
            INSERT INTO notification_logs (
                event_type, status, title, message, owner, account_name,
                account_id, order_id, user_id, workspace_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_type,
                status,
                title,
                message,
                normalize_owner_name(owner) if owner else None,
                account_name.strip() if isinstance(account_name, str) and account_name.strip() else None,
                int(account_id) if account_id is not None else None,
                order_id.strip() if isinstance(order_id, str) and order_id.strip() else None,
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_blacklist_compensation_total(
    mysql_cfg: dict,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> int:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return 0
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist_logs"):
            return 0
        cursor.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0)
            FROM blacklist_logs
            WHERE owner = %s AND user_id = %s AND action = 'blacklist_comp'
            """,
            (owner_key, int(user_id)),
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def remove_blacklist_entry(
    mysql_cfg: dict,
    owner: str,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    owner_key = normalize_owner_name(owner)
    if not owner_key:
        return False
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "blacklist"):
            return False
        cursor.execute(
            "DELETE FROM blacklist WHERE owner = %s AND user_id = %s",
            (owner_key, int(user_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def fetch_lot_mapping(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> dict | None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "lots"):
            return None
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_mmr = column_exists(cursor, "accounts", "mmr")
        has_display_name = column_exists(cursor, "lots", "display_name")
        params: list = [int(user_id), int(lot_number)]
        where_workspace = ""
        order_clause = " ORDER BY a.id"
        has_workspace = column_exists(cursor, "lots", "workspace_id")
        if has_workspace and workspace_id is not None:
            where_workspace = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
            order_clause = " ORDER BY CASE WHEN l.workspace_id = %s THEN 0 ELSE 1 END, a.id"
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json, a.owner,
                   a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen
                   {', a.`low_priority` AS `low_priority`' if has_low_priority else ', 0 AS `low_priority`'}
                   {', a.mmr' if has_mmr else ', NULL AS mmr'},
                   l.lot_number, l.lot_url
                   {', l.display_name' if has_display_name else ', NULL AS display_name'}
            FROM lots l
            JOIN accounts a ON a.id = l.account_id
            WHERE l.user_id = %s AND l.lot_number = %s
                  {where_workspace}
            {order_clause}
            LIMIT 1
            """,
            tuple(params + ([int(workspace_id)] if has_workspace and workspace_id is not None else [])),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def fetch_chats_missing_history(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    chat_ids: list[int],
) -> list[int]:
    if not chat_ids:
        return []
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        if not table_exists(cursor, "chat_messages"):
            return list(chat_ids)
        placeholders = ", ".join(["%s"] * len(chat_ids))
        cursor.execute(
            f"""
            SELECT DISTINCT chat_id
            FROM chat_messages
            WHERE user_id = %s AND workspace_id <=> %s AND chat_id IN ({placeholders})
            """,
            tuple([int(user_id), int(workspace_id) if workspace_id is not None else None, *chat_ids]),
        )
        existing = {int(row[0]) for row in (cursor.fetchall() or [])}
        return [cid for cid in chat_ids if int(cid) not in existing]
    finally:
        conn.close()


def prefetch_chat_histories(
    logger: logging.Logger,
    mysql_cfg: dict,
    account: Account,
    *,
    user_id: int,
    workspace_id: int | None,
    chats: dict[int, str | None],
) -> None:
    if not env_bool("CHAT_HISTORY_PREFETCH_ENABLED", True):
        return
    max_chats = env_int("CHAT_HISTORY_PREFETCH_LIMIT", 8)
    if max_chats <= 0:
        return
    chat_ids = list(chats.keys())
    missing = fetch_chats_missing_history(
        mysql_cfg,
        user_id=int(user_id),
        workspace_id=workspace_id,
        chat_ids=chat_ids,
    )
    if not missing:
        return
    missing = [cid for cid in missing if _should_prefetch_history(int(user_id), workspace_id, cid)]
    if not missing:
        return
    missing = missing[:max_chats]
    batch_size = env_int("CHAT_HISTORY_PREFETCH_BATCH", 4)
    msg_limit = env_int("CHAT_HISTORY_PREFETCH_MESSAGES", 50)
    for idx in range(0, len(missing), max(1, batch_size)):
        chunk = missing[idx : idx + max(1, batch_size)]
        try:
            histories = account.get_chats_histories({cid: chats.get(cid) for cid in chunk}) or {}
        except Exception as exc:
            logger.debug("Chat history prefetch failed: %s", exc)
            continue
        for chat_id, messages in histories.items():
            if not messages:
                continue
            trimmed = messages[-msg_limit:] if msg_limit > 0 else messages
            for msg in trimmed:
                try:
                    sent_time = _extract_datetime_from_html(getattr(msg, "html", None))
                    insert_chat_message(
                        mysql_cfg,
                        user_id=int(user_id),
                        workspace_id=workspace_id,
                        chat_id=int(chat_id),
                        message_id=int(getattr(msg, "id", 0) or 0),
                        author=getattr(msg, "author", None) or getattr(msg, "chat_name", None),
                        text=getattr(msg, "text", None),
                        by_bot=bool(getattr(msg, "by_bot", False)),
                        message_type=getattr(getattr(msg, "type", None), "name", None),
                        sent_time=sent_time,
                    )
                except Exception:
                    continue


def sync_chats_list(
    mysql_cfg: dict,
    account: Account,
    *,
    user_id: int,
    workspace_id: int | None,
) -> None:
    try:
        chats_map = account.get_chats(update=True) or {}
    except Exception:
        return
    chat_ids = [int(chat.id) for chat in chats_map.values() if getattr(chat, "id", None) is not None]
    history_times = _fetch_latest_chat_times(mysql_cfg, int(user_id), workspace_id, chat_ids)
    chat_names: dict[int, str | None] = {}
    for chat in chats_map.values():
        try:
            chat_id = int(chat.id)
            chat_time = _extract_datetime_from_html(getattr(chat, "html", None)) or history_times.get(chat_id)
            upsert_chat_summary(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
                chat_id=chat_id,
                name=chat.name,
                last_message_text=getattr(chat, "last_message_text", None),
                unread=bool(getattr(chat, "unread", False)),
                last_message_time=chat_time,
            )
            chat_names[chat_id] = getattr(chat, "name", None)
        except Exception:
            continue
    if chat_names:
        prefetch_chat_histories(
            logging.getLogger("funpay.worker"),
            mysql_cfg,
            account,
            user_id=int(user_id),
            workspace_id=workspace_id,
            chats=chat_names,
        )


def process_chat_outbox(
    logger: logging.Logger,
    mysql_cfg: dict,
    account: Account,
    *,
    user_id: int,
    workspace_id: int | None,
) -> None:
    pending = fetch_chat_outbox(mysql_cfg, int(user_id), workspace_id, limit=20)
    if not pending:
        return
    max_attempts = env_int("CHAT_OUTBOX_MAX_ATTEMPTS", 3)
    for item in pending:
        outbox_id = int(item.get("id") or 0)
        chat_id = int(item.get("chat_id") or 0)
        text = str(item.get("text") or "")
        attempts = int(item.get("attempts") or 0) + 1
        if not outbox_id or not chat_id or not text:
            continue
        try:
            message = account.send_message(chat_id, text)
            message_id = int(getattr(message, "id", 0) or 0)
            if message_id <= 0:
                message_id = -outbox_id
            insert_chat_message(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
                chat_id=chat_id,
                message_id=message_id,
                author=account.username or "you",
                text=text,
                by_bot=True,
                message_type="manual",
                sent_time=datetime.utcnow(),
            )
            upsert_chat_summary(
                mysql_cfg,
                user_id=int(user_id),
                workspace_id=workspace_id,
                chat_id=chat_id,
                name=None,
                last_message_text=text,
                unread=False,
                last_message_time=datetime.utcnow(),
            )
            mark_outbox_sent(mysql_cfg, outbox_id, workspace_id=workspace_id)
        except Exception as exc:
            logger.warning("Chat send failed: %s", exc)
            mark_outbox_failed(
                mysql_cfg,
                outbox_id,
                str(exc),
                attempts,
                max_attempts,
                workspace_id=workspace_id,
            )


def release_account_in_db(
    mysql_cfg: dict,
    account_id: int,
    user_id: int,
    workspace_id: int | None = None,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_last_rented = column_exists(cursor, "accounts", "last_rented_workspace_id")
        updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
        if has_frozen_at:
            updates.append("rental_frozen_at = NULL")
        workspace_clause = ""
        params: list = [account_id, user_id]
        if workspace_id is not None and has_last_rented:
            workspace_clause = " AND last_rented_workspace_id = %s"
            params.append(workspace_id)
        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = %s AND user_id = %s{workspace_clause}",
            tuple(params),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_rental_freeze_state(
    mysql_cfg: dict,
    *,
    account_id: int,
    user_id: int,
    owner: str | None,
    workspace_id: int | None,
    frozen: bool,
    rental_start: datetime | None = None,
    frozen_at: datetime | None = None,
    clear_frozen_at: bool = False,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_last_rented = column_exists(cursor, "accounts", "last_rented_workspace_id")
        updates = ["rental_frozen = %s"]
        params: list = [1 if frozen else 0]
        if has_frozen_at and (frozen or frozen_at is not None or clear_frozen_at):
            updates.append("rental_frozen_at = %s")
            params.append(frozen_at.strftime("%Y-%m-%d %H:%M:%S") if frozen_at else None)
        if rental_start is not None:
            updates.append("rental_start = %s")
            params.append(rental_start.strftime("%Y-%m-%d %H:%M:%S"))
        params.extend([account_id, user_id])
        where_clause = " WHERE id = %s AND user_id = %s"
        if owner:
            where_clause += " AND LOWER(owner) = %s"
            params.append(normalize_username(owner))
        if workspace_id is not None and has_last_rented:
            where_clause += " AND last_rented_workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)}{where_clause}",
            tuple(params),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def deauthorize_account_sessions(
    logger: logging.Logger,
    account_row: dict,
) -> bool:
    base = os.getenv("STEAM_WORKER_URL", "").strip()
    if not base:
        return False
    login = account_row.get("login") or account_row.get("account_name")
    password = account_row.get("password") or ""
    mafile_json = account_row.get("mafile_json")
    if not login or not password or not mafile_json:
        return False
    url = f"{base.rstrip('/')}/api/steam/deauthorize"
    timeout = env_int("STEAM_WORKER_TIMEOUT", 90)
    payload = {
        "steam_login": login,
        "steam_password": password,
        "mafile_json": mafile_json,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Steam worker request failed: %s", exc)
        return False
    if resp.ok:
        return True
    logger.warning("Steam worker error (status %s).", resp.status_code)
    return False


def _clear_expire_delay_state(state: RentalMonitorState, account_id: int) -> None:
    state.expire_delay_since.pop(account_id, None)
    state.expire_delay_next_check.pop(account_id, None)
    state.expire_delay_notified.discard(account_id)


def _should_delay_expire(
    logger: logging.Logger,
    account: Account,
    owner: str,
    account_row: dict,
    state: RentalMonitorState,
    now: datetime,
) -> bool:
    if not env_bool("DOTA_MATCH_DELAY_EXPIRE", True):
        return False
    account_id = int(account_row.get("id"))
    next_check = state.expire_delay_next_check.get(account_id)
    if next_check and now < next_check:
        return True

    steam_id = _steam_id_from_mafile(account_row.get("mafile_json"))
    presence = fetch_presence(steam_id)
    in_match = bool(presence.get("in_match"))
    if not in_match:
        _clear_expire_delay_state(state, account_id)
        return False

    since = state.expire_delay_since.get(account_id)
    if since is None:
        state.expire_delay_since[account_id] = now
        since = now

    grace_minutes = env_int("DOTA_MATCH_GRACE_MINUTES", 90)
    if now - since >= timedelta(minutes=grace_minutes):
        _clear_expire_delay_state(state, account_id)
        return False

    state.expire_delay_next_check[account_id] = now + timedelta(minutes=1)
    if account_id not in state.expire_delay_notified:
        extra = ""
        display = presence.get("presence_display") or presence.get("presence_state")
        if display:
            extra = f"\n\u0421\u0442\u0430\u0442\u0443\u0441: {display}"
        send_message_by_owner(logger, account, owner, f"{RENTAL_EXPIRE_DELAY_MESSAGE}{extra}")
        state.expire_delay_notified.add(account_id)
    return True


def process_rental_monitor(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    state: RentalMonitorState,
) -> None:
    interval = env_int("FUNPAY_RENTAL_CHECK_SECONDS", 30)
    now_ts = time.time()
    if now_ts - state.last_check_ts < interval:
        return
    state.last_check_ts = now_ts

    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        return

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            return
    if user_id is None:
        return

    rentals = fetch_active_rentals_for_monitor(mysql_cfg, int(user_id), workspace_id)
    now = datetime.utcnow()
    active_ids = {int(row.get("id")) for row in rentals}
    if state.freeze_cache:
        state.freeze_cache = {k: v for k, v in state.freeze_cache.items() if k in active_ids}
    if state.expire_delay_since:
        state.expire_delay_since = {k: v for k, v in state.expire_delay_since.items() if k in active_ids}
    if state.expire_delay_next_check:
        state.expire_delay_next_check = {
            k: v for k, v in state.expire_delay_next_check.items() if k in active_ids
        }
    if state.expire_delay_notified:
        state.expire_delay_notified = {k for k in state.expire_delay_notified if k in active_ids}
    if state.expire_soon_notified:
        state.expire_soon_notified = {
            k: v for k, v in state.expire_soon_notified.items() if k in active_ids
        }

    for row in rentals:
        account_id = int(row.get("id"))
        owner = row.get("owner")
        frozen = bool(row.get("rental_frozen"))
        frozen_at = _parse_datetime(row.get("rental_frozen_at"))
        if frozen and frozen_at and now >= frozen_at + timedelta(hours=1):
            new_start = _calculate_resume_start(row.get("rental_start"), frozen_at)
            unfrozen = update_rental_freeze_state(
                mysql_cfg,
                account_id=account_id,
                user_id=int(user_id),
                owner=owner,
                workspace_id=workspace_id,
                frozen=False,
                rental_start=new_start,
            )
            if unfrozen:
                frozen = False
                row["rental_frozen"] = 0
                send_message_by_owner(logger, account, owner, RENTAL_PAUSE_EXPIRED_MESSAGE)
                state.freeze_cache[account_id] = False
                continue
        prev = state.freeze_cache.get(account_id)
        if prev is None:
            state.freeze_cache[account_id] = frozen
        elif prev != frozen:
            state.freeze_cache[account_id] = frozen
            message = RENTAL_FROZEN_MESSAGE if frozen else RENTAL_UNFROZEN_MESSAGE
            send_message_by_owner(logger, account, owner, message)

    for row in rentals:
        account_id = int(row.get("id"))
        owner = row.get("owner")
        if not owner:
            _clear_expire_delay_state(state, account_id)
            state.expire_soon_notified.pop(account_id, None)
            continue
        if row.get("rental_frozen"):
            state.expire_soon_notified.pop(account_id, None)
            continue
        started = _parse_datetime(row.get("rental_start"))
        total_minutes = row.get("rental_duration_minutes")
        if total_minutes is None:
            total_minutes = int(row.get("rental_duration") or 0) * 60
        try:
            total_minutes_int = int(total_minutes or 0)
        except Exception:
            total_minutes_int = 0
        if not started or total_minutes_int <= 0:
            _clear_expire_delay_state(state, account_id)
            state.expire_soon_notified.pop(account_id, None)
            continue
        expiry_time = started + timedelta(minutes=total_minutes_int)
        if now < expiry_time:
            _clear_expire_delay_state(state, account_id)
            remind_minutes = env_int("RENTAL_EXPIRE_REMIND_MINUTES", 10)
            if remind_minutes > 0:
                seconds_left = int((expiry_time - now).total_seconds())
                expiry_ts = int(expiry_time.timestamp())
                if 0 < seconds_left <= remind_minutes * 60:
                    if state.expire_soon_notified.get(account_id) != expiry_ts:
                        message = build_expire_soon_message(row, seconds_left)
                        send_message_by_owner(logger, account, owner, message)
                        state.expire_soon_notified[account_id] = expiry_ts
                else:
                    state.expire_soon_notified.pop(account_id, None)
            continue
        if _should_delay_expire(logger, account, owner, row, state, now):
            continue

        if env_bool("AUTO_STEAM_DEAUTHORIZE_ON_EXPIRE", True):
            deauth_ok = deauthorize_account_sessions(logger, row)
            log_notification_event(
                mysql_cfg,
                event_type="deauthorize",
                status="ok" if deauth_ok else "failed",
                title="Steam deauthorize on expiry",
                message="Auto deauthorize triggered by rental expiration.",
                owner=owner,
                account_name=row.get("account_name") or row.get("login"),
                account_id=account_id,
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
        released = release_account_in_db(mysql_cfg, account_id, int(user_id), workspace_id)
        log_notification_event(
            mysql_cfg,
            event_type="rental_expired",
            status="ok" if released else "failed",
            title="Rental expired",
            message="Rental expired and account was released." if released else "Rental expired but release failed.",
            owner=owner,
            account_name=row.get("account_name") or row.get("login"),
            account_id=account_id,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        if released:
            send_message_by_owner(logger, account, owner, RENTAL_EXPIRED_MESSAGE)
            order_id = fetch_latest_order_id_for_account(
                mysql_cfg,
                account_id=account_id,
                owner=owner,
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
            if order_id:
                confirm_message = (
                    f"{RENTAL_EXPIRED_CONFIRM_MESSAGE}\n\n"
                    f"\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0442\u0443\u0442 -> https://funpay.com/orders/{order_id}/"
                )
            else:
                confirm_message = RENTAL_EXPIRED_CONFIRM_MESSAGE
            send_message_by_owner(logger, account, owner, confirm_message)
        _clear_expire_delay_state(state, account_id)


def get_user_id_by_username(mysql_cfg: dict, username: str) -> int | None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE username = %s LIMIT 1",
            (username.lower().strip(),),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


def table_exists(cursor: mysql.connector.cursor.MySQLCursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
        (table,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor: mysql.connector.cursor.MySQLCursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s LIMIT 1",
        (table, column),
    )
    return cursor.fetchone() is not None


def fetch_available_lot_accounts(
    mysql_cfg: dict,
    user_id: int | None,
    workspace_id: int | None = None,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        if not table_exists(cursor, "accounts"):
            return []
        has_lots = table_exists(cursor, "lots")
        has_account_user_id = column_exists(cursor, "accounts", "user_id")
        has_lot_user_id = has_lots and column_exists(cursor, "lots", "user_id")
        has_account_workspace = column_exists(cursor, "accounts", "workspace_id")
        has_lot_workspace = has_lots and column_exists(cursor, "lots", "workspace_id")
        has_account_lot_url = column_exists(cursor, "accounts", "lot_url")
        has_account_lot_number = column_exists(cursor, "accounts", "lot_number")
        has_account_frozen = column_exists(cursor, "accounts", "account_frozen")
        has_rental_frozen = column_exists(cursor, "accounts", "rental_frozen")
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_display_name = has_lots and column_exists(cursor, "lots", "display_name")

        select_fields = [
            "a.ID AS id",
            "a.account_name AS account_name",
            "a.login AS login",
            "a.password AS password",
            "a.owner AS owner",
            "a.rental_start AS rental_start",
            "a.rental_duration AS rental_duration",
            "a.rental_duration_minutes AS rental_duration_minutes",
            "a.mmr AS mmr",
            "a.workspace_id AS workspace_id",
        ]
        if has_low_priority:
            select_fields.append("a.`low_priority` AS `low_priority`")
        else:
            select_fields.append("0 AS `low_priority`")
        if has_lots:
            select_fields.extend(["l.lot_number AS lot_number", "l.lot_url AS lot_url"])
            if has_display_name:
                select_fields.append("l.display_name AS display_name")
            else:
                select_fields.append("NULL AS display_name")
        else:
            select_fields.append(
                "a.lot_number AS lot_number" if has_account_lot_number else "NULL AS lot_number"
            )
            select_fields.append("a.lot_url AS lot_url" if has_account_lot_url else "NULL AS lot_url")
            select_fields.append("NULL AS display_name")

        from_clause = "FROM accounts a"
        if has_lots:
            join_clause = " LEFT JOIN lots l ON l.account_id = a.ID"
            from_clause += join_clause

        where_clauses = ["a.owner IS NULL"]
        params: list = []
        if has_account_frozen:
            where_clauses.append("(a.account_frozen = 0 OR a.account_frozen IS NULL)")
        if has_rental_frozen:
            where_clauses.append("(a.rental_frozen = 0 OR a.rental_frozen IS NULL)")
        if has_low_priority:
            where_clauses.append("(a.`low_priority` = 0 OR a.`low_priority` IS NULL)")
        if has_lots:
            where_clauses.append("l.lot_number IS NOT NULL")
            if has_account_workspace and has_lot_workspace and workspace_id is not None:
                where_clauses.append("(l.workspace_id = %s OR l.workspace_id IS NULL)")
                params.append(int(workspace_id))

        if user_id is not None:
            if has_account_user_id:
                where_clauses.append("a.user_id = %s")
                params.append(user_id)
            elif has_lot_user_id:
                where_clauses.append("l.user_id = %s")
                params.append(user_id)
        if has_lots:
            order_clause = "ORDER BY (l.lot_number IS NULL), l.lot_number"
        elif has_account_lot_number:
            order_clause = "ORDER BY (a.lot_number IS NULL), a.lot_number"
        else:
            order_clause = "ORDER BY a.ID"

        query = f"SELECT {', '.join(select_fields)} {from_clause} WHERE {' AND '.join(where_clauses)} {order_clause}"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return list(rows or [])
    finally:
        conn.close()


def fetch_lot_account(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> dict | None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_mmr = column_exists(cursor, "accounts", "mmr")
        has_display_name = column_exists(cursor, "lots", "display_name")
        params: list = [user_id, lot_number]
        join_clause = "JOIN accounts a ON a.id = l.account_id"
        where_workspace = ""
        has_workspace = column_exists(cursor, "lots", "workspace_id")
        order_clause = " ORDER BY a.id"
        if has_workspace and workspace_id is not None:
            where_workspace = " AND (l.workspace_id = %s OR l.workspace_id IS NULL)"
            params.append(int(workspace_id))
            order_clause = " ORDER BY CASE WHEN l.workspace_id = %s THEN 0 ELSE 1 END, a.id"
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen
                   {', a.`low_priority` AS `low_priority`' if has_low_priority else ', 0 AS `low_priority`'}
                   {', a.mmr' if has_mmr else ', NULL AS mmr'},
                   l.lot_number, l.lot_url
                   {', l.display_name' if has_display_name else ', NULL AS display_name'}
            FROM lots l
            {join_clause}
            WHERE l.user_id = %s AND l.lot_number = %s
                  {where_workspace}
                  AND (a.owner IS NULL OR a.owner = '')
                  AND (a.account_frozen = 0 OR a.account_frozen IS NULL)
                  AND (a.rental_frozen = 0 OR a.rental_frozen IS NULL)
                  {"AND (a.`low_priority` = 0 OR a.`low_priority` IS NULL)" if has_low_priority else ""}
            {order_clause}
            LIMIT 1
            """,
            tuple(params + ([int(workspace_id)] if has_workspace and workspace_id is not None else [])),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def find_replacement_account_for_lot(
    mysql_cfg: dict,
    user_id: int,
    lot_number: int,
    workspace_id: int | None = None,
) -> dict | None:
    try:
        available = fetch_available_lot_accounts(mysql_cfg, user_id, workspace_id=workspace_id)
    except mysql.connector.Error:
        return None
    if not available:
        return None
    return available[0]


def assign_account_to_buyer(
    mysql_cfg: dict,
    *,
    account_id: int,
    user_id: int,
    buyer: str,
    units: int,
    total_minutes: int,
    workspace_id: int | None = None,
) -> None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        has_last_rented = column_exists(cursor, "accounts", "last_rented_workspace_id")
        updates = [
            "owner = %s",
            "rental_duration = %s",
            "rental_duration_minutes = %s",
            "rental_start = NULL",
        ]
        params: list = [buyer, int(units), int(total_minutes)]
        if workspace_id is not None and has_last_rented:
            updates.append("last_rented_workspace_id = %s")
            params.append(int(workspace_id))
        params.extend([int(account_id), int(user_id)])
        cursor.execute(
            f"""
            UPDATE accounts
            SET {', '.join(updates)}
            WHERE id = %s AND user_id = %s
            """,
            tuple(params),
        )
        conn.commit()
    finally:
        conn.close()


def replace_rental_account(
    mysql_cfg: dict,
    *,
    old_account_id: int,
    new_account_id: int,
    user_id: int,
    owner: str,
    workspace_id: int | None,
    rental_start: datetime,
    rental_duration: int,
    rental_duration_minutes: int,
) -> bool:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        has_last_rented = column_exists(cursor, "accounts", "last_rented_workspace_id")
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_account_frozen = column_exists(cursor, "accounts", "account_frozen")
        has_rental_frozen = column_exists(cursor, "accounts", "rental_frozen")
        rental_start_str = rental_start.strftime("%Y-%m-%d %H:%M:%S")

        try:
            conn.start_transaction()
        except Exception:
            pass

        updates = [
            "owner = %s",
            "rental_duration = %s",
            "rental_duration_minutes = %s",
            "rental_start = %s",
            "rental_frozen = 0",
        ]
        params: list = [owner, int(rental_duration), int(rental_duration_minutes), rental_start_str]
        if has_frozen_at:
            updates.append("rental_frozen_at = NULL")
        if workspace_id is not None and has_last_rented:
            updates.append("last_rented_workspace_id = %s")
            params.append(int(workspace_id))
        params.extend([int(new_account_id), int(user_id)])
        where_clauses = ["id = %s", "user_id = %s", "(owner IS NULL OR owner = '')"]
        if has_account_frozen:
            where_clauses.append("(account_frozen = 0 OR account_frozen IS NULL)")
        if has_rental_frozen:
            where_clauses.append("(rental_frozen = 0 OR rental_frozen IS NULL)")
        if has_low_priority:
            where_clauses.append("(`low_priority` = 0 OR `low_priority` IS NULL)")
        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE {' AND '.join(where_clauses)}",
            tuple(params),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False

        old_updates = ["owner = NULL", "rental_start = NULL", "rental_frozen = 0"]
        if has_frozen_at:
            old_updates.append("rental_frozen_at = NULL")
        if has_low_priority:
            old_updates.append("`low_priority` = 1")
        old_params: list = [int(old_account_id), int(user_id)]
        old_where = "id = %s AND user_id = %s"
        if owner:
            old_where += " AND LOWER(owner) = %s"
            old_params.append(normalize_username(owner))
        if workspace_id is not None and has_last_rented:
            old_where += " AND last_rented_workspace_id = %s"
            old_params.append(int(workspace_id))
        cursor.execute(
            f"UPDATE accounts SET {', '.join(old_updates)} WHERE {old_where}",
            tuple(old_params),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False

        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def extend_rental_for_buyer(
    mysql_cfg: dict,
    *,
    account_id: int,
    user_id: int,
    buyer: str,
    add_units: int,
    add_minutes: int,
    workspace_id: int | None = None,
) -> dict | None:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_last_rented = column_exists(cursor, "accounts", "last_rented_workspace_id")
        has_lot_workspace = column_exists(cursor, "lots", "workspace_id")
        workspace_clause = ""
        base_params: list = [account_id, user_id, normalize_username(buyer)]
        if workspace_id is not None and has_last_rented:
            workspace_clause = " AND last_rented_workspace_id = %s"
            base_params.append(int(workspace_id))

        lot_number_query = "SELECT lot_number FROM lots WHERE lots.account_id = accounts.id"
        lot_url_query = "SELECT lot_url FROM lots WHERE lots.account_id = accounts.id"
        lot_params: list = []
        if workspace_id is not None and has_lot_workspace:
            lot_number_query += " AND lots.workspace_id = %s"
            lot_url_query += " AND lots.workspace_id = %s"
            lot_params = [int(workspace_id), int(workspace_id)]
        params = lot_params + base_params
        cursor.execute(
            f"""
            SELECT id, account_name, login, password, mafile_json,
                   owner, rental_start, rental_duration, rental_duration_minutes,
                   account_frozen, rental_frozen,
                   ({lot_number_query} LIMIT 1) AS lot_number,
                   ({lot_url_query} LIMIT 1) AS lot_url
            FROM accounts
            WHERE id = %s AND user_id = %s AND LOWER(owner) = %s{workspace_clause}
            LIMIT 1
            """,
            tuple(params),
        )
        current = cursor.fetchone()
        if not current:
            return None

        base_minutes = current.get("rental_duration_minutes")
        if base_minutes is None:
            base_minutes = int(current.get("rental_duration") or 0) * 60
        try:
            base_minutes_int = int(base_minutes or 0)
        except Exception:
            base_minutes_int = 0

        new_minutes = base_minutes_int + int(add_minutes)
        try:
            base_units = int(current.get("rental_duration") or 0)
        except Exception:
            base_units = 0
        new_units = base_units + int(add_units)

        cursor = conn.cursor()
        update_workspace_clause = ""
        update_params: list = [new_units, new_minutes, account_id, user_id]
        if workspace_id is not None and has_last_rented:
            update_workspace_clause = " AND last_rented_workspace_id = %s"
            update_params.append(int(workspace_id))
        cursor.execute(
            f"""
            UPDATE accounts
            SET rental_duration = %s,
                rental_duration_minutes = %s
            WHERE id = %s AND user_id = %s{update_workspace_clause}
            """,
            tuple(update_params),
        )
        conn.commit()

        cursor = conn.cursor(dictionary=True)
        join_clause = "LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id"
        join_params: list = []
        if workspace_id is not None and has_lot_workspace:
            join_clause += " AND l.workspace_id = %s"
            join_params.append(int(workspace_id))
        final_workspace_clause = ""
        final_params: list = [account_id, user_id]
        if workspace_id is not None and has_last_rented:
            final_workspace_clause = " AND a.last_rented_workspace_id = %s"
            final_params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen,
                   l.lot_number, l.lot_url
            FROM accounts a
            {join_clause}
            WHERE a.id = %s AND a.user_id = %s{final_workspace_clause}
            LIMIT 1
            """,
            tuple(join_params + final_params),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def fetch_owner_accounts(
    mysql_cfg: dict,
    user_id: int,
    owner: str,
    workspace_id: int | None = None,
) -> list[dict]:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        has_lot_workspace = column_exists(cursor, "lots", "workspace_id")
        has_frozen_at = column_exists(cursor, "accounts", "rental_frozen_at")
        has_low_priority = column_exists(cursor, "accounts", "low_priority")
        has_mmr = column_exists(cursor, "accounts", "mmr")
        join_clause = "LEFT JOIN lots l ON l.account_id = a.id AND l.user_id = a.user_id"
        join_params: list = []
        if workspace_id is not None and has_lot_workspace:
            join_clause += " AND l.workspace_id = %s"
            join_params.append(int(workspace_id))
        workspace_clause = ""
        params: list = [user_id, normalize_username(owner)]
        if workspace_id is not None and column_exists(cursor, "accounts", "last_rented_workspace_id"):
            workspace_clause = " AND a.last_rented_workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            SELECT a.id, a.account_name, a.login, a.password, a.mafile_json,
                   a.owner, a.rental_start, a.rental_duration, a.rental_duration_minutes,
                   a.account_frozen, a.rental_frozen{', a.rental_frozen_at' if has_frozen_at else ''}
                   {', a.`low_priority` AS `low_priority`' if has_low_priority else ', 0 AS `low_priority`'}
                   {', a.mmr' if has_mmr else ', NULL AS mmr'},
                   l.lot_number, l.lot_url
            FROM accounts a
            {join_clause}
            WHERE a.user_id = %s AND LOWER(a.owner) = %s{workspace_clause}
            ORDER BY a.id
            """,
            tuple(join_params + params),
        )
        return list(cursor.fetchall() or [])
    finally:
        conn.close()


def start_rental_for_owner(
    mysql_cfg: dict,
    user_id: int,
    owner: str,
    workspace_id: int | None = None,
) -> int:
    cfg = resolve_workspace_mysql_cfg(mysql_cfg, workspace_id)
    conn = mysql.connector.connect(**cfg)
    try:
        cursor = conn.cursor()
        workspace_clause = ""
        params: list = [user_id, normalize_username(owner)]
        if workspace_id is not None and column_exists(cursor, "accounts", "last_rented_workspace_id"):
            workspace_clause = " AND last_rented_workspace_id = %s"
            params.append(int(workspace_id))
        cursor.execute(
            f"""
            UPDATE accounts
            SET rental_start = NOW()
            WHERE user_id = %s AND LOWER(owner) = %s AND rental_start IS NULL{workspace_clause}
            """,
            tuple(params),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def build_stock_messages(accounts: list[dict]) -> list[str]:
    if not accounts:
        return [STOCK_EMPTY]
    lines: list[str] = []
    for account in accounts:
        lot_url = account.get("lot_url")
        display_name = build_display_name(account)
        line = f"{display_name} - {lot_url}" if lot_url else display_name
        lines.append(line)

    batches: list[str] = []
    for i in range(0, len(lines), STOCK_LIST_LIMIT):
        chunk = lines[i : i + STOCK_LIST_LIMIT]
        if i == 0:
            batches.append("\n".join([STOCK_TITLE, *chunk]))
        else:
            batches.append("\n".join(chunk))
    return batches


def handle_stock_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Stock command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Stock command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
        return True

    try:
        accounts = fetch_available_lot_accounts(mysql_cfg, user_id, workspace_id=workspace_id)

    except mysql.connector.Error as exc:
        logger.warning("Stock query failed: %s", exc)
        send_chat_message(logger, account, chat_id, STOCK_DB_MISSING)
        return True

    for message in build_stock_messages(accounts):
        send_chat_message(logger, account, chat_id, message)
    return True


def handle_account_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Account command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Account command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    for acc in accounts:
        total_minutes = acc.get("rental_duration_minutes")
        if total_minutes is None:
            total_minutes = get_unit_minutes(acc)
        message = build_account_message(acc, int(total_minutes or 0), include_timer_note=True)
        send_chat_message(logger, account, chat_id, message)
    return True


def handle_code_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Code command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Code command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    active_accounts = [acc for acc in accounts if not acc.get("rental_frozen")]
    if not active_accounts:
        send_chat_message(logger, account, chat_id, RENTAL_CODE_BLOCKED_MESSAGE)
        return True

    lines = ["\u041a\u043e\u0434\u044b Steam Guard:"]
    started_now = False
    for acc in active_accounts:
        display_name = build_display_name(acc)
        ok, code = get_steam_guard_code(acc.get("mafile_json"))
        login = acc.get("login") or "-"
        if ok:
            lines.append(f"{display_name} ({login}): {code}")
        else:
            lines.append(f"{display_name} ({login}): \u043e\u0448\u0438\u0431\u043a\u0430 {code}")
        if acc.get("rental_start") is None:
            started_now = True

    if started_now:
        start_rental_for_owner(mysql_cfg, user_id, sender_username, workspace_id)
        lines.extend(
            [
                "",
                "\u23f1\ufe0f \u0410\u0440\u0435\u043d\u0434\u0430 \u043d\u0430\u0447\u0430\u043b\u0430\u0441\u044c \u0441\u0435\u0439\u0447\u0430\u0441 (\u0441 \u043c\u043e\u043c\u0435\u043d\u0442\u0430 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u043a\u043e\u0434\u0430).",
            ]
        )

    send_chat_message(logger, account, chat_id, "\n".join(lines))
    return True


def handle_low_priority_replace_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Low priority replace command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Low priority replace command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command)
    if not selected:
        return True

    rental_start = _parse_datetime(selected.get("rental_start"))
    if rental_start is None:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_CODE_MESSAGE)
        return True
    if datetime.utcnow() - rental_start > timedelta(minutes=LP_REPLACE_WINDOW_MINUTES):
        send_chat_message(logger, account, chat_id, LP_REPLACE_TOO_LATE_MESSAGE)
        return True

    raw_mmr = selected.get("mmr")
    try:
        target_mmr = int(raw_mmr)
    except Exception:
        target_mmr = None
    if target_mmr is None:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_MMR_MESSAGE)
        return True

    try:
        available = fetch_available_lot_accounts(mysql_cfg, user_id, workspace_id=workspace_id)
    except mysql.connector.Error as exc:
        logger.warning("Low priority replace lookup failed: %s", exc)
        send_chat_message(logger, account, chat_id, LP_REPLACE_FAILED_MESSAGE)
        return True

    replacement = _select_replacement_account(
        available,
        target_mmr=target_mmr,
        exclude_id=int(selected.get("id") or 0),
        max_delta=LP_REPLACE_MMR_RANGE,
    )
    if not replacement:
        send_chat_message(logger, account, chat_id, LP_REPLACE_NO_MATCH_MESSAGE)
        return True

    rental_minutes = _resolve_rental_minutes(selected)
    try:
        rental_units = int(selected.get("rental_duration") or 0)
    except Exception:
        rental_units = 0
    if rental_units <= 0 and rental_minutes > 0:
        rental_units = max(1, (rental_minutes + 59) // 60)

    ok = replace_rental_account(
        mysql_cfg,
        old_account_id=int(selected.get("id") or 0),
        new_account_id=int(replacement.get("id") or 0),
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        rental_start=rental_start,
        rental_duration=rental_units,
        rental_duration_minutes=rental_minutes,
    )
    if not ok:
        send_chat_message(logger, account, chat_id, LP_REPLACE_FAILED_MESSAGE)
        return True

    replacement_info = dict(replacement)
    replacement_info["owner"] = sender_username
    replacement_info["rental_start"] = rental_start
    replacement_info["rental_duration"] = rental_units
    replacement_info["rental_duration_minutes"] = rental_minutes
    replacement_info["account_frozen"] = 0
    replacement_info["rental_frozen"] = 0
    message = f"{LP_REPLACE_SUCCESS_PREFIX}\n{build_account_message(replacement_info, rental_minutes, False)}"
    send_chat_message(logger, account, chat_id, message)
    return True


def _select_account_for_command(
    logger: logging.Logger,
    account: Account,
    chat_id: int,
    accounts: list[dict],
    args: str,
    command: str,
) -> dict | None:
    if not accounts:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return None
    account_id = parse_account_id_arg(args)
    if account_id is None:
        if len(accounts) == 1:
            return accounts[0]
        send_chat_message(logger, account, chat_id, build_rental_choice_message(accounts, command))
        return None
    for acc in accounts:
        if int(acc.get("id")) == account_id:
            return acc
    send_chat_message(logger, account, chat_id, build_rental_choice_message(accounts, command))
    return None


def _select_replacement_account(
    available: list[dict],
    *,
    target_mmr: int,
    exclude_id: int,
    max_delta: int = LP_REPLACE_MMR_RANGE,
) -> dict | None:
    candidates: list[tuple[int, int, dict]] = []
    for acc in available:
        if int(acc.get("id") or 0) == exclude_id:
            continue
        raw_mmr = acc.get("mmr")
        if raw_mmr is None:
            continue
        try:
            mmr = int(raw_mmr)
        except Exception:
            continue
        diff = abs(mmr - target_mmr)
        if diff > max_delta:
            continue
        candidates.append((diff, mmr, acc))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], int(item[2].get("id") or 0)))
    return candidates[0][2]


def handle_pause_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Pause command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Pause command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command)
    if not selected:
        return True

    if selected.get("rental_frozen"):
        send_chat_message(logger, account, chat_id, RENTAL_ALREADY_PAUSED_MESSAGE)
        return True

    frozen_at = selected.get("rental_frozen_at")
    if frozen_at:
        send_chat_message(logger, account, chat_id, RENTAL_PAUSE_ALREADY_USED_MESSAGE)
        return True

    steam_id = _steam_id_from_mafile(selected.get("mafile_json"))
    if steam_id:
        presence = fetch_presence(steam_id)
        if presence.get("in_match"):
            send_chat_message(logger, account, chat_id, RENTAL_PAUSE_IN_MATCH_MESSAGE)
            return True

    now = datetime.utcnow()
    ok = update_rental_freeze_state(
        mysql_cfg,
        account_id=int(selected["id"]),
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        frozen=True,
        frozen_at=now,
    )
    if not ok:
        send_chat_message(logger, account, chat_id, "\u274c \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0430\u0440\u0435\u043d\u0434\u0443 \u043d\u0430 \u043f\u0430\u0443\u0437\u0443.")
        return True

    deauthorize_account_sessions(logger, selected)

    pause_message = RENTAL_PAUSED_MESSAGE
    if len(accounts) > 1:
        pause_message = f"{pause_message} (ID {selected.get('id')})"
    send_chat_message(logger, account, chat_id, pause_message)
    return True


def handle_resume_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    if chat_id is None:
        logger.warning("Resume command ignored (missing chat_id).")
        return False
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Resume command skipped: %s", exc)
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
            return True

    if user_id is None:
        send_chat_message(logger, account, chat_id, RENTALS_EMPTY)
        return True

    accounts = fetch_owner_accounts(mysql_cfg, user_id, sender_username, workspace_id)
    selected = _select_account_for_command(logger, account, chat_id, accounts, args, command)
    if not selected:
        return True

    if not selected.get("rental_frozen"):
        send_chat_message(logger, account, chat_id, RENTAL_NOT_PAUSED_MESSAGE)
        return True

    new_start = _calculate_resume_start(selected.get("rental_start"), selected.get("rental_frozen_at"))
    ok = update_rental_freeze_state(
        mysql_cfg,
        account_id=int(selected["id"]),
        user_id=int(user_id),
        owner=sender_username,
        workspace_id=workspace_id,
        frozen=False,
        rental_start=new_start,
    )
    if not ok:
        send_chat_message(logger, account, chat_id, "\u274c \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043d\u044f\u0442\u044c \u043f\u0430\u0443\u0437\u0443.")
        return True

    resume_message = RENTAL_RESUMED_MESSAGE
    if len(accounts) > 1:
        resume_message = f"{resume_message} (ID {selected.get('id')})"
    send_chat_message(logger, account, chat_id, resume_message)
    return True


def handle_order_purchased(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    msg: object,
) -> None:
    order_id = extract_order_id(getattr(msg, "text", None) or "")
    if not order_id:
        return
    if is_order_processed(site_username, site_user_id, workspace_id, order_id):
        return

    try:
        order = account.get_order(order_id)
    except Exception as exc:
        logger.warning("Failed to fetch order %s: %s", order_id, exc)
        return

    buyer = str(getattr(order, "buyer_username", "") or "")
    if not buyer:
        logger.warning("Order %s missing buyer username.", order_id)
        return

    chat_id = getattr(order, "chat_id", None)
    if isinstance(chat_id, str) and chat_id.isdigit():
        chat_id = int(chat_id)
    if chat_id is None:
        try:
            chat = account.get_chat_by_name(buyer, True)
            chat_id = getattr(chat, "id", None)
        except Exception:
            chat_id = None
    if chat_id is None:
        logger.warning("Skipping order %s: chat id not found.", order_id)
        return

    lot_number = extract_lot_number_from_order(order)
    if lot_number is None:
        send_chat_message(logger, account, chat_id, ORDER_LOT_MISSING)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError as exc:
        logger.warning("Order %s skipped: %s", order_id, exc)
        return

    user_id = site_user_id
    if user_id is None and site_username:
        try:
            user_id = get_user_id_by_username(mysql_cfg, site_username)
        except mysql.connector.Error as exc:
            logger.warning("Failed to resolve user id for %s: %s", site_username, exc)
            return

    if user_id is None:
        logger.warning("Order %s skipped: user id missing.", order_id)
        return

    try:
        amount = int(getattr(order, "amount", None) or 1)
    except Exception:
        amount = 1
    if amount <= 0:
        amount = 1
    price_value = None
    raw_price = getattr(order, "sum", None)
    if raw_price is None:
        raw_price = getattr(order, "price", None)
    try:
        if raw_price is not None:
            price_value = float(raw_price)
    except Exception:
        price_value = None

    lot_mapping = fetch_lot_mapping(mysql_cfg, int(user_id), int(lot_number), workspace_id)
    steam_id = _steam_id_from_mafile(lot_mapping.get("mafile_json")) if lot_mapping else None

    if is_blacklisted(mysql_cfg, buyer, int(user_id), workspace_id):
        comp_threshold_minutes = env_int("BLACKLIST_COMP_MINUTES", 0)
        comp_hours = env_int("BLACKLIST_COMP_HOURS", 5)
        comp_threshold_minutes = max(comp_threshold_minutes, comp_hours * 60, 5 * 60)
        unit_minutes_default = env_int("BLACKLIST_COMP_UNIT_MINUTES", 60)
        unit_minutes = get_unit_minutes(lot_mapping) if lot_mapping else unit_minutes_default
        paid_minutes = max(0, int(unit_minutes) * int(amount))
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=lot_mapping.get("id") if lot_mapping else None,
            account_name=lot_mapping.get("account_name") if lot_mapping else None,
            steam_id=steam_id,
            rental_minutes=paid_minutes,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="blacklist_comp",
        )
        log_blacklist_event(
            mysql_cfg,
            owner=buyer,
            action="blacklist_comp",
            details=f"order={order_id}; lot={lot_number}; amount={amount}",
            amount=paid_minutes,
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        total_paid = get_blacklist_compensation_total(mysql_cfg, buyer, int(user_id), workspace_id)
        if total_paid >= comp_threshold_minutes:
            removed = remove_blacklist_entry(mysql_cfg, buyer, int(user_id), workspace_id)
            log_blacklist_event(
                mysql_cfg,
                owner=buyer,
                action="auto_unblacklist",
                details=f"total_minutes={total_paid}/{comp_threshold_minutes}; order={order_id}; lot={lot_number}",
                user_id=int(user_id),
                workspace_id=workspace_id,
            )
            if removed:
                send_chat_message(
                    logger,
                    account,
                    chat_id,
                    f"\u041e\u043f\u043b\u0430\u0442\u0430 \u0448\u0442\u0440\u0430\u0444\u0430 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0430 ({format_duration_minutes(total_paid)}). \u0414\u043e\u0441\u0442\u0443\u043f \u0440\u0430\u0437\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d.",
                )
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

        remaining = max(comp_threshold_minutes - total_paid, 0)
        lot_url = lot_mapping.get("lot_url") if lot_mapping else None
        lot_label = f"\u043b\u043e\u0442 \u2116{lot_number}"
        if lot_url:
            lot_label = f"\u043b\u043e\u0442 {lot_url}"
        send_chat_message(
            logger,
            account,
            chat_id,
            "\u0412\u044b \u0432 \u0447\u0435\u0440\u043d\u043e\u043c \u0441\u043f\u0438\u0441\u043a\u0435.\n"
            f"\u041e\u043f\u043b\u0430\u0442\u0438\u0442\u0435 \u0448\u0442\u0440\u0430\u0444 {format_penalty_label(comp_threshold_minutes)}, "
            "\u0447\u0442\u043e\u0431\u044b \u0440\u0430\u0437\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f.\n"
            f"\u041e\u043f\u043b\u0430\u0447\u0435\u043d\u043e: {format_duration_minutes(total_paid)}. "
            f"\u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c: {format_duration_minutes(remaining)}.\n"
            f"\u0415\u0441\u043b\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u2014 \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430 \u043e\u043f\u043b\u0430\u0442\u0438\u0442\u0435 \u044d\u0442\u043e\u0442 {lot_label}.",
        )
        log_blacklist_event(
            mysql_cfg,
            owner=buyer,
            action="blocked_order",
            details=f"order={order_id}; lot={lot_number}; amount={amount}; paid={total_paid}; remaining={remaining}",
            user_id=int(user_id),
            workspace_id=workspace_id,
        )
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    mapping = lot_mapping
    if mapping:
        try:
            owner_accounts = fetch_owner_accounts(mysql_cfg, int(user_id), buyer, workspace_id)
        except mysql.connector.Error:
            owner_accounts = []
        for account_row in owner_accounts:
            account_lot = account_row.get("lot_number")
            if account_lot is None:
                continue
            try:
                account_lot_number = int(account_lot)
            except Exception:
                continue
            if account_lot_number == int(lot_number):
                mapping = account_row
                break
    if not mapping:
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="unmapped",
        )
        send_chat_message(logger, account, chat_id, ORDER_LOT_UNMAPPED)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    if mapping.get("account_frozen") or mapping.get("rental_frozen") or mapping.get("low_priority"):
        replacement = find_replacement_account_for_lot(
            mysql_cfg, int(user_id), int(lot_number), workspace_id
        )
        if replacement:
            unit_minutes = get_unit_minutes(replacement)
            total_minutes = unit_minutes * amount
            assign_account_to_buyer(
                mysql_cfg,
                account_id=int(replacement["id"]),
                user_id=user_id,
                buyer=buyer,
                units=amount,
                total_minutes=total_minutes,
                workspace_id=workspace_id,
            )
            log_order_history(
                mysql_cfg,
                order_id=order_id,
                owner=buyer,
                user_id=int(user_id),
                workspace_id=workspace_id,
                account_id=replacement.get("id"),
                account_name=replacement.get("account_name"),
                steam_id=steam_id,
                rental_minutes=total_minutes,
                lot_number=lot_number,
                amount=amount,
                price=price_value,
                action="replace_assign",
            )
            replacement_info = dict(replacement)
            replacement_info["owner"] = buyer
            replacement_info["rental_duration"] = amount
            replacement_info["rental_duration_minutes"] = total_minutes
            replacement_info["account_frozen"] = 0
            replacement_info["rental_frozen"] = 0
            message = f"{ORDER_ACCOUNT_REPLACEMENT_PREFIX}\n{build_account_message(replacement_info, total_minutes, True)}"
            send_chat_message(logger, account, chat_id, message)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="busy",
        )
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    owner = mapping.get("owner")
    if owner and normalize_username(owner) != normalize_username(buyer):
        replacement = find_replacement_account_for_lot(
            mysql_cfg, int(user_id), int(lot_number), workspace_id
        )
        if replacement:
            unit_minutes = get_unit_minutes(replacement)
            total_minutes = unit_minutes * amount
            assign_account_to_buyer(
                mysql_cfg,
                account_id=int(replacement["id"]),
                user_id=user_id,
                buyer=buyer,
                units=amount,
                total_minutes=total_minutes,
                workspace_id=workspace_id,
            )
            log_order_history(
                mysql_cfg,
                order_id=order_id,
                owner=buyer,
                user_id=int(user_id),
                workspace_id=workspace_id,
                account_id=replacement.get("id"),
                account_name=replacement.get("account_name"),
                steam_id=steam_id,
                rental_minutes=total_minutes,
                lot_number=lot_number,
                amount=amount,
                price=price_value,
                action="replace_assign",
            )
            replacement_info = dict(replacement)
            replacement_info["owner"] = buyer
            replacement_info["rental_duration"] = amount
            replacement_info["rental_duration_minutes"] = total_minutes
            replacement_info["account_frozen"] = 0
            replacement_info["rental_frozen"] = 0
            message = f"{ORDER_ACCOUNT_REPLACEMENT_PREFIX}\n{build_account_message(replacement_info, total_minutes, True)}"
            send_chat_message(logger, account, chat_id, message)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return

        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="busy",
        )
        send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
        mark_order_processed(site_username, site_user_id, workspace_id, order_id)
        return

    unit_minutes = get_unit_minutes(mapping)
    total_minutes = unit_minutes * amount

    updated_account = mapping
    if not owner:
        assign_account_to_buyer(
            mysql_cfg,
            account_id=int(mapping["id"]),
            user_id=user_id,
            buyer=buyer,
            units=amount,
            total_minutes=total_minutes,
            workspace_id=workspace_id,
        )
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            rental_minutes=total_minutes,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="assign",
        )
    else:
        updated_account = extend_rental_for_buyer(
            mysql_cfg,
            account_id=int(mapping["id"]),
            user_id=user_id,
            buyer=buyer,
            add_units=amount,
            add_minutes=total_minutes,
            workspace_id=workspace_id,
        )
        if not updated_account:
            log_order_history(
                mysql_cfg,
                order_id=order_id,
                owner=buyer,
                user_id=int(user_id),
                workspace_id=workspace_id,
                account_id=mapping.get("id"),
                account_name=mapping.get("account_name"),
                steam_id=steam_id,
                lot_number=lot_number,
                amount=amount,
                price=price_value,
                action="busy",
            )
            send_chat_message(logger, account, chat_id, ORDER_ACCOUNT_BUSY)
            mark_order_processed(site_username, site_user_id, workspace_id, order_id)
            return
        log_order_history(
            mysql_cfg,
            order_id=order_id,
            owner=buyer,
            user_id=int(user_id),
            workspace_id=workspace_id,
            account_id=mapping.get("id"),
            account_name=mapping.get("account_name"),
            steam_id=steam_id,
            rental_minutes=total_minutes,
            lot_number=lot_number,
            amount=amount,
            price=price_value,
            action="extend",
        )

    message = build_account_message(updated_account or mapping, total_minutes, include_timer_note=True)
    send_chat_message(logger, account, chat_id, message)
    mark_order_processed(site_username, site_user_id, workspace_id, order_id)


def _log_command_stub(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
    action: str,
) -> bool:
    logger.info(
        "user=%s workspace=%s chat=%s author=%s command=%s args=%s action=%s url=%s",
        site_username or "-",
        workspace_id if workspace_id is not None else "-",
        chat_name,
        sender_username,
        command,
        args or "-",
        action,
        chat_url,
    )
    return True


def handle_command(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    chat_name: str,
    sender_username: str,
    chat_id: int | None,
    command: str,
    args: str,
    chat_url: str,
) -> bool:
    handlers = {
        "!\u0441\u0442\u043e\u043a": handle_stock_command,
        "!\u0430\u043a\u043a": handle_account_command,
        "!\u043a\u043e\u0434": handle_code_command,
        "!\u043f\u0440\u043e\u0434\u043b\u0438\u0442\u044c": lambda *a: _log_command_stub(*a, action="extend"),
        "!\u043b\u043f\u0437\u0430\u043c\u0435\u043d\u0430": handle_low_priority_replace_command,
        "!\u043e\u0442\u043c\u0435\u043d\u0430": lambda *a: _log_command_stub(*a, action="cancel"),
        "!\u0430\u0434\u043c\u0438\u043d": lambda *a: _log_command_stub(*a, action="admin"),
        "!\u043f\u0430\u0443\u0437\u0430": handle_pause_command,
        "!\u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c": handle_resume_command,
    }
    handler = handlers.get(command)
    if not handler:
        logger.info(
            "user=%s workspace=%s chat=%s author=%s command_unhandled=%s args=%s url=%s",
            site_username or "-",
            workspace_id if workspace_id is not None else "-",
            chat_name,
            sender_username,
            command,
            args or "-",
            chat_url,
        )
        return False
    return handler(
        logger,
        account,
        site_username,
        site_user_id,
        workspace_id,
        chat_name,
        sender_username,
        chat_id,
        command,
        args,
        chat_url,
    )


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def get_mysql_config() -> dict:
    url = os.getenv("MYSQL_URL", "").strip()
    host = os.getenv("MYSQLHOST", "").strip()
    port = os.getenv("MYSQLPORT", "").strip() or "3306"
    user = os.getenv("MYSQLUSER", "").strip()
    password = os.getenv("MYSQLPASSWORD", "").strip()
    database = os.getenv("MYSQLDATABASE", "").strip() or os.getenv("MYSQL_DATABASE", "").strip()

    if url:
        parsed = urlparse(url)
        host = parsed.hostname or host
        if parsed.port:
            port = str(parsed.port)
        user = parsed.username or user
        password = parsed.password or password
        if parsed.path and parsed.path != "/":
            database = parsed.path.lstrip("/")

    if not database:
        raise RuntimeError("MySQL database name missing. Set MYSQLDATABASE or MYSQL_DATABASE.")

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
    }


_WORKSPACE_DB_CACHE: dict[int, str] = {}


def get_workspace_db_name(mysql_cfg: dict, workspace_id: int) -> str | None:
    cached = _WORKSPACE_DB_CACHE.get(workspace_id)
    if cached:
        return cached
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT db_name FROM workspaces WHERE id = %s", (workspace_id,))
        row = cursor.fetchone()
        db_name = (row or {}).get("db_name") or ""
        if db_name:
            _WORKSPACE_DB_CACHE[workspace_id] = db_name
            return db_name
        return None
    finally:
        conn.close()


def resolve_workspace_mysql_cfg(mysql_cfg: dict, workspace_id: int | None) -> dict:
    return mysql_cfg


def normalize_proxy_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    return f"socks5://{value}"


def build_proxy_config(raw: str | None) -> dict | None:
    url = normalize_proxy_url(raw)
    if not url:
        return None
    return {"http": url, "https": url}


IPIFY_URL = "https://api.ipify.org"


def _fetch_public_ip(proxies: dict | None) -> str | None:
    try:
        resp = requests.get(IPIFY_URL, proxies=proxies, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None
    text = (resp.text or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = resp.json()
            text = str(data.get("ip") or "").strip()
        except Exception:
            return None
    return text or None


def ensure_proxy_isolated(
    logger: logging.Logger,
    proxy_url: str | None,
    label: str,
    *,
    fatal: bool = False,
) -> dict | None:
    if not proxy_url:
        msg = f"{label} Missing proxy_url, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    proxy_cfg = build_proxy_config(proxy_url)
    if not proxy_cfg:
        msg = f"{label} Invalid proxy_url, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    direct_ip = _fetch_public_ip({"http": None, "https": None})
    if not direct_ip:
        msg = f"{label} Direct IP check failed, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    proxy_ip = _fetch_public_ip(proxy_cfg)
    if not proxy_ip:
        msg = f"{label} Proxy IP check failed, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    if proxy_ip == direct_ip:
        msg = f"{label} Proxy IP matches direct IP, bot will not start."
        if fatal:
            logger.error(msg)
        else:
            logger.warning(msg)
        return None
    logger.info("%s Proxy check passed (direct/proxy IP differ).", label)
    return proxy_cfg


def fetch_workspaces(mysql_cfg: dict) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT w.id AS workspace_id, w.name AS workspace_name, w.golden_key, w.proxy_url,
                   w.user_id, u.username
            FROM workspaces w
            JOIN users u ON u.id = w.user_id
            WHERE w.platform = 'funpay'
              AND w.golden_key IS NOT NULL AND w.golden_key != ''
            ORDER BY w.user_id, w.id
            """
        )
        rows = cursor.fetchall()
        return list(rows or [])
    finally:
        conn.close()


def _parse_auto_raise_categories(raw: str | None) -> list[int]:
    if not raw:
        return []
    values: list[int] = []
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError:
            continue
    return values


def fetch_auto_raise_settings(mysql_cfg: dict, user_id: int) -> AutoRaiseSettings:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT enabled, categories, interval_hours
            FROM auto_raise_settings
            WHERE user_id = %s
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cursor.fetchone()
        if not row:
            return AutoRaiseSettings()
        interval_hours = int(row.get("interval_hours") or 1)
        categories = sorted(set(_parse_auto_raise_categories(row.get("categories"))))
        return AutoRaiseSettings(
            enabled=bool(row.get("enabled")),
            categories=categories,
            interval_hours=max(1, min(interval_hours, 6)),
        )
    finally:
        conn.close()


def log_auto_raise_history(
    mysql_cfg: dict,
    *,
    user_id: int,
    workspace_id: int | None,
    category_id: int | None,
    category_name: str | None,
    status: str,
    message: str | None,
) -> None:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO auto_raise_history (user_id, workspace_id, category_id, category_name, status, message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                int(user_id),
                int(workspace_id) if workspace_id is not None else None,
                int(category_id) if category_id is not None else None,
                category_name,
                status,
                message,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_funpay_workspaces_by_user(mysql_cfg: dict, user_id: int) -> list[dict]:
    conn = mysql.connector.connect(**mysql_cfg)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id AS workspace_id, name AS workspace_name, golden_key, proxy_url, user_id
            FROM workspaces
            WHERE platform = 'funpay'
              AND user_id = %s
              AND golden_key IS NOT NULL AND golden_key != ''
            ORDER BY id
            """,
            (int(user_id),),
        )
        rows = cursor.fetchall()
        return list(rows or [])
    finally:
        conn.close()


def _format_wait_time(seconds: int | None) -> str:
    if not seconds:
        return ""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins:
        return f"{hours}h {mins}m"
    return f"{hours}h"


def _sleep_with_stop(stop_event: threading.Event, seconds: float) -> None:
    remaining = float(seconds)
    step = 1.0 if remaining > 1 else remaining
    while remaining > 0 and not stop_event.is_set():
        time.sleep(step)
        remaining -= step
        step = 1.0 if remaining > 1 else remaining


def _build_raise_groups(account: Account, category_ids: list[int]) -> tuple[dict[int, dict], list[int]]:
    common_subcats = account.get_sorted_subcategories().get(SubCategoryTypes.COMMON, {})
    groups: dict[int, dict] = {}
    missing: list[int] = []
    for cid in category_ids:
        subcat = common_subcats.get(int(cid))
        if subcat:
            group = groups.setdefault(
                subcat.category.id,
                {"game": subcat.category.name, "subcats": [], "raise_all": False},
            )
            if subcat not in group["subcats"]:
                group["subcats"].append(subcat)
            continue
        category = account.get_category(int(cid))
        if category:
            group = groups.setdefault(
                category.id,
                {"game": category.name, "subcats": [], "raise_all": True},
            )
            group["raise_all"] = True
            continue
        missing.append(int(cid))
    return groups, missing


def run_auto_raise_for_workspace(
    logger: logging.Logger,
    mysql_cfg: dict,
    settings: AutoRaiseSettings,
    workspace: dict,
    user_id: int,
    user_agent: str | None,
    cooldowns: dict[tuple[int, int], float],
) -> None:
    workspace_id = int(workspace.get("workspace_id"))
    workspace_name = workspace.get("workspace_name") or str(workspace_id)
    golden_key = (workspace.get("golden_key") or "").strip()
    proxy_cfg = build_proxy_config(workspace.get("proxy_url"))
    label = f"[auto-raise {workspace_name}]"

    if not golden_key:
        return
    if not proxy_cfg:
        logger.warning("%s Missing proxy URL, skipping auto raise.", label)
        for cid in settings.categories:
            log_auto_raise_history(
                mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                category_id=cid,
                category_name=f"Category {cid}",
                status="failed",
                message="Proxy URL missing.",
            )
        return

    try:
        account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
        account.get()
    except Exception as exc:
        short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
        logger.warning("%s Account init failed: %s", label, short)
        for cid in settings.categories:
            log_auto_raise_history(
                mysql_cfg,
                user_id=user_id,
                workspace_id=workspace_id,
                category_id=cid,
                category_name=f"Category {cid}",
                status="failed",
                message=f"Account init failed: {short}",
            )
        return

    groups, missing = _build_raise_groups(account, settings.categories)
    for cid in missing:
        log_auto_raise_history(
            mysql_cfg,
            user_id=user_id,
            workspace_id=workspace_id,
            category_id=cid,
            category_name=f"Category {cid}",
            status="failed",
            message="Category not found in account.",
        )

    now = time.time()
    for game_id, info in groups.items():
        cooldown_key = (workspace_id, int(game_id))
        next_allowed = cooldowns.get(cooldown_key)
        if next_allowed and next_allowed > now:
            continue

        subcats = info.get("subcats") or []
        raise_all = bool(info.get("raise_all"))
        try:
            if raise_all or not subcats:
                account.raise_lots(int(game_id))
                log_auto_raise_history(
                    mysql_cfg,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    category_id=int(game_id),
                    category_name=str(info.get("game") or f"Category {game_id}"),
                    status="ok",
                    message=None,
                )
            else:
                account.raise_lots(int(game_id), subcategories=subcats)
                for subcat in subcats:
                    label = f"{subcat.category.name} - {subcat.name}"
                    log_auto_raise_history(
                        mysql_cfg,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        category_id=subcat.id,
                        category_name=label,
                        status="ok",
                        message=None,
                    )
        except fp_exceptions.RaiseError as exc:
            wait_time = exc.wait_time
            error_text = exc.error_message or "Raise failed."
            wait_label = _format_wait_time(wait_time)
            message = error_text
            if wait_label:
                message = f"{error_text} Next try in {wait_label}."
            if wait_time:
                cooldowns[cooldown_key] = time.time() + int(wait_time)
            targets = subcats if subcats else [None]
            for subcat in targets:
                category_id = subcat.id if subcat else int(game_id)
                category_name = (
                    f"{subcat.category.name} - {subcat.name}"
                    if subcat
                    else str(info.get("game") or f"Category {game_id}")
                )
                log_auto_raise_history(
                    mysql_cfg,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    category_id=category_id,
                    category_name=category_name,
                    status="failed",
                    message=message,
                )
        except Exception as exc:
            short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
            logger.warning("%s Auto raise failed: %s", label, short)
            targets = subcats if subcats else [None]
            for subcat in targets:
                category_id = subcat.id if subcat else int(game_id)
                category_name = (
                    f"{subcat.category.name} - {subcat.name}"
                    if subcat
                    else str(info.get("game") or f"Category {game_id}")
                )
                log_auto_raise_history(
                    mysql_cfg,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    category_id=category_id,
                    category_name=category_name,
                    status="failed",
                    message=short,
                )


def auto_raise_user_loop(
    logger: logging.Logger,
    mysql_cfg: dict,
    user_id: int,
    user_agent: str | None,
    stop_event: threading.Event,
) -> None:
    label = f"[auto-raise user {user_id}]"
    cooldowns: dict[tuple[int, int], float] = {}
    refresh_seconds = 30
    idle_seconds = 30
    last_refresh = 0.0
    settings = AutoRaiseSettings()

    logger.info("%s Auto raise loop started.", label)
    while not stop_event.is_set():
        if time.time() - last_refresh >= refresh_seconds:
            settings = fetch_auto_raise_settings(mysql_cfg, user_id)
            last_refresh = time.time()
        if not settings.enabled or not settings.categories:
            _sleep_with_stop(stop_event, idle_seconds)
            continue

        workspaces = fetch_funpay_workspaces_by_user(mysql_cfg, user_id)
        if not workspaces:
            _sleep_with_stop(stop_event, idle_seconds)
            continue

        interval_hours = max(1, min(int(settings.interval_hours or 1), 6))
        interval_seconds = interval_hours * 3600

        for workspace in workspaces:
            if stop_event.is_set():
                break
            if time.time() - last_refresh >= refresh_seconds:
                settings = fetch_auto_raise_settings(mysql_cfg, user_id)
                last_refresh = time.time()
            if not settings.enabled:
                break
            run_auto_raise_for_workspace(
                logger,
                mysql_cfg,
                settings,
                workspace,
                user_id,
                user_agent,
                cooldowns,
            )
            remaining = float(interval_seconds)
            while remaining > 0 and not stop_event.is_set():
                chunk = min(30.0, remaining)
                _sleep_with_stop(stop_event, chunk)
                remaining -= chunk
                if time.time() - last_refresh >= refresh_seconds:
                    settings = fetch_auto_raise_settings(mysql_cfg, user_id)
                    last_refresh = time.time()
                if not settings.enabled:
                    remaining = 0
                    break

    logger.info("%s Auto raise loop stopped.", label)


def refresh_session_loop(account: Account, interval_seconds: int = 3600, label: str | None = None) -> None:
    sleep_time = interval_seconds
    while True:
        time.sleep(sleep_time)
        try:
            account.get()
            logging.getLogger("funpay.worker").info("%sSession refreshed.", f"{label} " if label else "")
            sleep_time = interval_seconds
        except Exception:
            logging.getLogger("funpay.worker").exception(
                "%sSession refresh failed. Retrying in 60s.", f"{label} " if label else ""
            )
            sleep_time = 60


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format=LOG_FORMAT,
    )
    logging.getLogger("FunPayAPI").setLevel(logging.WARNING)
    return logging.getLogger("funpay.worker")


def log_message(
    logger: logging.Logger,
    account: Account,
    site_username: str | None,
    site_user_id: int | None,
    workspace_id: int | None,
    event: NewMessageEvent,
) -> str | None:
    if event.type is not EventTypes.NEW_MESSAGE:
        return None

    msg = event.message
    my_name = (account.username or "").strip()

    sender_username = None

    # 1) Try to parse explicit author from message HTML (matches FunPay UI).
    if getattr(msg, "html", None):
        try:
            soup = BeautifulSoup(msg.html, "lxml")
            link = soup.find("a", {"class": "chat-msg-author-link"})
            if link and link.text:
                sender_username = link.text.strip()
        except Exception:
            sender_username = None

    # 2) Use API-provided author.
    if not sender_username and msg.author:
        sender_username = msg.author
    # 3) Use chat_name.
    if not sender_username and msg.chat_name:
        sender_username = msg.chat_name
    # 4) Use IDs if available.
    if not sender_username and msg.author_id:
        sender_username = f"user_{msg.author_id}"
    if not sender_username and msg.interlocutor_id:
        sender_username = f"user_{msg.interlocutor_id}"
    # 5) Last resort: chat id placeholder.
    if not sender_username:
        sender_username = f"chat_{msg.chat_id}"

    message_text = msg.text
    command, command_args = parse_command(message_text)

    # If we don't have a chat name, it's likely not a private chat.
    if not sender_username or sender_username == "-":
        return None

    chat_id = msg.chat_id
    chat_url = f"https://funpay.com/chat/?node={chat_id}" if chat_id is not None else "-"

    is_system = bool(msg.type and msg.type is not MessageTypes.NON_SYSTEM)
    if msg.author_id == 0 or (sender_username and sender_username.lower() == "funpay"):
        is_system = True

    chat_name = msg.chat_name or msg.author or "-"
    logger.info(
        "user=%s workspace=%s chat=%s author=%s system=%s url=%s: %s",
        site_username or "-",
        workspace_id if workspace_id is not None else "-",
        chat_name,
        sender_username,
        is_system,
        chat_url,
        message_text,
    )
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None

    if mysql_cfg and chat_id is not None:
        user_id = site_user_id
        if user_id is None and site_username:
            try:
                user_id = get_user_id_by_username(mysql_cfg, site_username)
            except mysql.connector.Error:
                user_id = None
        if user_id is not None:
            try:
                msg_id = int(getattr(msg, "id", 0) or 0)
                if msg_id <= 0:
                    msg_id = int(time.time() * 1000)
                sent_time = _extract_datetime_from_html(getattr(msg, "html", None)) or datetime.utcnow()
                insert_chat_message(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=workspace_id,
                    chat_id=int(chat_id),
                    message_id=msg_id,
                    author=sender_username,
                    text=message_text,
                    by_bot=bool(getattr(msg, "by_bot", False)),
                    message_type=getattr(msg.type, "name", None),
                    sent_time=sent_time,
                )
                upsert_chat_summary(
                    mysql_cfg,
                    user_id=int(user_id),
                    workspace_id=workspace_id,
                    chat_id=int(chat_id),
                    name=chat_name,
                    last_message_text=message_text,
                    unread=not bool(getattr(msg, "by_bot", False)),
                    last_message_time=sent_time,
                )
            except Exception:
                pass
    if command:
        logger.info(
            "user=%s workspace=%s chat=%s author=%s command=%s args=%s url=%s",
            site_username or "-",
            workspace_id if workspace_id is not None else "-",
            chat_name,
            sender_username,
            command,
            command_args or "-",
            chat_url,
        )
        if not is_system:
            handle_command(
                logger,
                account,
                site_username,
                site_user_id,
                workspace_id,
                chat_name,
                sender_username,
                msg.chat_id,
                command,
                command_args,
                chat_url,
            )
    if is_system:
        logger.info(
            "user=%s workspace=%s system_event type=%s chat=%s url=%s raw=%s",
            site_username or "-",
            workspace_id if workspace_id is not None else "-",
            getattr(msg.type, "name", msg.type),
            chat_name,
            chat_url,
            (msg.text or "").strip(),
        )
        if msg.type == MessageTypes.ORDER_PURCHASED:
            handle_order_purchased(logger, account, site_username, site_user_id, workspace_id, msg)
    return None


def run_single_user(logger: logging.Logger) -> None:
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")
    if not golden_key:
        logger.error("FUNPAY_GOLDEN_KEY is required (set FUNPAY_MULTI_USER=1 for DB mode).")
        sys.exit(1)

    proxy_url = normalize_proxy_url(os.getenv("FUNPAY_PROXY_URL"))
    if not proxy_url:
        logger.error("FUNPAY_PROXY_URL is required to start the bot.")
        sys.exit(1)
    proxy_cfg = ensure_proxy_isolated(logger, proxy_url, "[single-user]", fatal=True)
    if not proxy_cfg:
        sys.exit(1)

    user_agent = os.getenv("FUNPAY_USER_AGENT")
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)

    logger.info("Initializing FunPay account...")
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    logger.info("Bot started for %s.", account.username or "unknown")

    threading.Thread(target=refresh_session_loop, args=(account, 3600, None), daemon=True).start()

    runner = Runner(account, disable_message_requests=False)
    logger.info("Listening for new messages...")
    state = RentalMonitorState()
    chat_sync_interval = env_int("CHAT_SYNC_SECONDS", 30)
    chat_sync_last = 0.0
    while True:
        updates = runner.get_updates()
        events = runner.parse_updates(updates)
        for event in events:
            if isinstance(event, NewMessageEvent):
                log_message(logger, account, account.username, None, None, event)
        process_rental_monitor(logger, account, account.username, None, None, state)
        try:
            mysql_cfg = get_mysql_config()
        except RuntimeError:
            mysql_cfg = None
        if mysql_cfg:
            if time.time() - chat_sync_last >= chat_sync_interval:
                user_id = get_user_id_by_username(mysql_cfg, account.username) if account.username else None
                if user_id is not None:
                    sync_chats_list(mysql_cfg, account, user_id=user_id, workspace_id=None)
                    chat_sync_last = time.time()
            if account.username:
                user_id = get_user_id_by_username(mysql_cfg, account.username)
                if user_id is not None:
                    process_chat_outbox(logger, mysql_cfg, account, user_id=user_id, workspace_id=None)
        time.sleep(poll_seconds)


def workspace_worker_loop(
    workspace: dict,
    user_agent: str | None,
    poll_seconds: int,
    stop_event: threading.Event,
) -> None:
    logger = logging.getLogger("funpay.worker")
    workspace_id = workspace.get("workspace_id")
    workspace_name = workspace.get("workspace_name") or f"Workspace {workspace_id}"
    user_id = workspace.get("user_id")
    site_username = workspace.get("username") or f"user-{user_id}"
    golden_key = workspace.get("golden_key")
    proxy_url = normalize_proxy_url(workspace.get("proxy_url"))
    label = f"[{workspace_name}]"

    state = RentalMonitorState()
    chat_sync_interval = env_int("CHAT_SYNC_SECONDS", 30)
    chat_sync_last = 0.0
    try:
        mysql_cfg = get_mysql_config()
    except RuntimeError:
        mysql_cfg = None
    while not stop_event.is_set():
        try:
            if not golden_key:
                logger.warning("%s Missing golden_key, skipping.", label)
                return
            proxy_cfg = ensure_proxy_isolated(logger, proxy_url, label)
            if not proxy_cfg:
                return

            account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
            account.get()
            logger.info("Bot started for %s (%s).", site_username, workspace_name)

            threading.Thread(
                target=refresh_session_loop,
                args=(account, 3600, label),
                daemon=True,
            ).start()

            runner = Runner(account, disable_message_requests=False)
            while not stop_event.is_set():
                updates = runner.get_updates()
                events = runner.parse_updates(updates)
                for event in events:
                    if stop_event.is_set():
                        break
                    if isinstance(event, NewMessageEvent):
                        log_message(logger, account, site_username, user_id, workspace_id, event)
                process_rental_monitor(logger, account, site_username, user_id, workspace_id, state)
                if mysql_cfg and user_id is not None:
                    if time.time() - chat_sync_last >= chat_sync_interval:
                        sync_chats_list(mysql_cfg, account, user_id=int(user_id), workspace_id=workspace_id)
                        chat_sync_last = time.time()
                    process_chat_outbox(logger, mysql_cfg, account, user_id=int(user_id), workspace_id=workspace_id)
                time.sleep(poll_seconds)
        except Exception as exc:
            # Avoid logging full HTML bodies from failed FunPay requests.
            short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
            logger.error("%s Worker error: %s. Restarting in 30s.", label, short)
            logger.debug("%s Traceback:", label, exc_info=True)
            time.sleep(30)
    logger.info("%s Worker stopped (key updated or removed).", label)


def run_multi_user(logger: logging.Logger) -> None:
    poll_seconds = env_int("FUNPAY_POLL_SECONDS", 6)
    sync_seconds = env_int("FUNPAY_USER_SYNC_SECONDS", 60)
    max_users = env_int("FUNPAY_MAX_USERS", 0)
    user_agent = os.getenv("FUNPAY_USER_AGENT")

    mysql_cfg = get_mysql_config()
    logger.info("Multi-user mode enabled. Sync interval: %ss.", sync_seconds)

    workers: dict[int, dict] = {}

    while True:
        try:
            workspaces = fetch_workspaces(mysql_cfg)
            if max_users > 0:
                workspaces = workspaces[:max_users]

            desired = {
                int(w["workspace_id"]): w
                for w in workspaces
                if w.get("golden_key") and str(w.get("golden_key")).strip()
            }

            # Auto-raise loops removed.

            # Stop removed workspaces.
            for workspace_id in list(workers.keys()):
                if workspace_id not in desired:
                    workers[workspace_id]["stop"].set()
                    workers[workspace_id]["thread"].join(timeout=5)
                    workers.pop(workspace_id, None)

            for workspace_id, workspace in desired.items():
                golden_key = (workspace.get("golden_key") or "").strip()
                proxy_url = normalize_proxy_url(workspace.get("proxy_url"))
                existing = workers.get(workspace_id)
                if (
                    existing
                    and existing.get("golden_key") == golden_key
                    and existing.get("proxy_url") == proxy_url
                ):
                    continue
                if existing:
                    existing["stop"].set()
                    existing["thread"].join(timeout=5)
                    workers.pop(workspace_id, None)

                if not proxy_url:
                    logger.warning(
                        "Workspace %s missing proxy_url, bot will not start.",
                        workspace.get("workspace_name") or workspace_id,
                    )
                    continue

                stop_event = threading.Event()
                thread = threading.Thread(
                    target=workspace_worker_loop,
                    args=(workspace, user_agent, poll_seconds, stop_event),
                    daemon=True,
                )
                workers[workspace_id] = {
                    "golden_key": golden_key,
                    "proxy_url": proxy_url,
                    "thread": thread,
                    "stop": stop_event,
                }
                thread.start()

            time.sleep(sync_seconds)
        except Exception as exc:
            short = exc.short_str() if hasattr(exc, "short_str") else str(exc)[:200]
            logger.error("User sync failed: %s. Retrying in 30s.", short)
            logger.debug("User sync traceback:", exc_info=True)
            time.sleep(30)


def main() -> None:
    logger = configure_logging()
    _clear_lot_cache_on_start()
    explicit_multi = os.getenv("FUNPAY_MULTI_USER")
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")

    # Auto-mode:
    # - If FUNPAY_MULTI_USER is explicitly set, respect it.
    # - Else if a single key is provided, run single-user.
    # - Else try multi-user (DB mode).
    if explicit_multi is not None:
        multi_user = env_bool("FUNPAY_MULTI_USER", False)
    else:
        multi_user = False if golden_key else True

    if multi_user:
        run_multi_user(logger)
    else:
        run_single_user(logger)


if __name__ == "__main__":
    main()

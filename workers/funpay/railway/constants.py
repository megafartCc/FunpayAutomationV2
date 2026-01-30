from __future__ import annotations

import re
import threading

from FunPayAPI.common.utils import RegularExpressions

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# Keep ASCII source while matching Cyrillic commands.
COMMAND_PREFIXES = (
    "!сток",
    "!акк",
    "!код",
    "!продлить",
    "!лпзамена",
    "!отмена",
    "!админ",
    "!пауза",
    "!продолжить",
)
STOCK_LIST_LIMIT = 8
STOCK_TITLE = "Свободные лоты:"
STOCK_EMPTY = "Свободных лотов нет."
STOCK_DB_MISSING = (
    "Инвентарь пока не настроен."
)
RENTALS_EMPTY = "Активных аренд нет."
ORDER_LOT_MISSING = (
    "Не удалось определить лот. Напишите !админ."
)
ORDER_LOT_UNMAPPED = (
    "Лот не привязан к аккаунту. Напишите !админ."
)
ORDER_ACCOUNT_BUSY = (
    "Лот уже занят другим покупателем. Напишите !админ."
)
ORDER_ACCOUNT_REPLACEMENT_PREFIX = (
    "Лот уже арендован другим покупателем. "
    "Мы выдали вам замену, потому что предыдущий лот был занят."
)
ACCOUNT_HEADER = "Ваш аккаунт:"
ACCOUNT_TIMER_NOTE = (
    "⏱️ Отсчет аренды начнется после первого получения кода (!код)."
)
RENTAL_STARTED_MESSAGE = (
    "⏱️ Аренда началась сейчас (с момента получения кода)."
)
COMMANDS_RU = (
    "Команды:\n"
    "!акк — данные аккаунта\n"
    "!код — код Steam Guard\n"
    "!сток — наличие аккаунтов\n"
    "!продлить <часы> <ID_аккаунта> — продлить аренду\n"
    "!пауза <ID> — пауза аренды на 1 час\n"
    "!продолжить <ID> — снять паузу раньше срока\n"
    "!админ — вызвать продавца\n"
    "!лпзамена <ID> — замена аккаунта (10 минут после !код)\n"
    "!отмена <ID> — отменить аренду"
)
RENTAL_FROZEN_MESSAGE = (
    "Администратор заморозил вашу аренду. Доступ временно приостановлен."
)
RENTAL_UNFROZEN_MESSAGE = (
    "Администратор разморозил вашу аренду. "
    "Доступ восстановлен. Что бы получить код еще раз пропишите команду !код."
)
RENTAL_PAUSED_MESSAGE = (
    "⏸️ Ваша аренда заморожена на 1 час.\n"
    "Чтобы продолжить раньше срока, напишите !продолжить"
)
RENTAL_PAUSE_ALREADY_USED_MESSAGE = (
    "⏸️ Пауза уже была использована для этой аренды."
)
RENTAL_ALREADY_PAUSED_MESSAGE = (
    "⏸️ Аренда уже на паузе."
)
RENTAL_PAUSE_IN_MATCH_MESSAGE = (
    "⚠️ Нельзя поставить аренду на паузу во время матча. "
    "Завершите матч и попробуйте снова."
)
RENTAL_CODE_BLOCKED_MESSAGE = (
    "⏸️ Аренда на паузе, коды на время паузы недоступны."
)
RENTAL_NOT_PAUSED_MESSAGE = (
    "▶️ Аренда не на паузе."
)
RENTAL_RESUMED_MESSAGE = (
    "▶️ Мы разморозили вашу аренду. "
    "Доступ восстановлен. Что бы получить код еще раз пропишите команду !код."
)
RENTAL_PAUSE_EXPIRED_MESSAGE = (
    "⏰ Пауза истекла (прошло 1 час). Аренда возобновлена."
)
RENTAL_EXPIRED_MESSAGE = "Аренда закончилась. Доступ закрыт."
RENTAL_EXPIRED_CONFIRM_MESSAGE = (
    "Заказ выполнен. Пожалуйста, зайдите в раздел «Покупки», выберите его в списке и нажмите кнопку «Подтвердить выполнение заказа»."
)
RENTAL_EXPIRE_DELAY_MESSAGE = (
    "Ваша аренда закончилась, но мы видим, что вы в матче.\n"
    "У вас есть время, чтобы закончить матч. Через 1 минуту я проверю снова.\n"
    "Доступ будет закрыт автоматически, если матч уже закончится.\n"
    "Если хотите продлить — используйте команду:\n"
    "!продлить <часы> <ID аккаунта>"
)
LP_REPLACE_WINDOW_MINUTES = 10
LP_REPLACE_MMR_RANGE = 1000
LP_REPLACE_NO_CODE_MESSAGE = (
    "Сначала получите код (!код), "
    "затем можно запросить замену."
)
LP_REPLACE_TOO_LATE_MESSAGE = (
    "Замена доступна только в течение "
    "10 минут после получения кода (!код)."
)
LP_REPLACE_NO_MMR_MESSAGE = (
    "Для замены нужен MMR аккаунта. "
    "Напишите администратору."
)
LP_REPLACE_NO_MATCH_MESSAGE = (
    "Нет свободного аккаунта для замены "
    "в пределах ±1000 MMR. Напишите администратору."
)
LP_REPLACE_FAILED_MESSAGE = (
    "Не удалось выполнить замену. "
    "Напишите администратору."
)
LP_REPLACE_SUCCESS_PREFIX = "✅ Замена выполнена. Новый аккаунт:"
ORDER_ID_RE = RegularExpressions().ORDER_ID
LOT_NUMBER_RE = re.compile(r"(?:№|#)\s*(\d+)")

_processed_orders: dict[str, set[str]] = {}
_processed_orders_lock = threading.Lock()
_redis_client = None
_chat_history_prefetch_seen: dict[tuple[int, int | None, int], float] = {}
_chat_history_prefetch_lock = threading.Lock()

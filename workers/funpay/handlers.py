"""
В данном модуле написаны хэндлеры для разных эвентов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal

from FunPayAPI import exceptions, utils as fp_utils
from FunPayAPI.updater.events import *

from Utils import cardinal_tools
from railway.db_utils import get_mysql_config
from railway.order_utils import apply_review_bonus_for_order
from locales.localizer import Localizer
from threading import Thread
import logging
import time

LAST_STACK_ID = ""
MSG_LOG_LAST_STACK_ID = ""

logger = logging.getLogger("FPC.handlers")
localizer = Localizer()
_ = localizer.translate



# INIT MESSAGE
def save_init_chats_handler(c: Cardinal, e: InitialChatEvent):
    """
    Кэширует существующие чаты (чтобы не отправлять приветственные сообщения).
    """
    if c.MAIN_CFG["Greetings"].getboolean("sendGreetings") and e.chat.id not in c.old_users:
        c.old_users[e.chat.id] = int(time.time())
        cardinal_tools.cache_old_users(c.old_users)


def update_threshold_on_initial_chat(c: Cardinal, e: InitialChatEvent):
    """
    Обновляет пороговое значение для определения новых чатов.
    """
    if e.chat.id > c.greeting_chat_id_threshold:
        c.greeting_chat_id_threshold = e.chat.id


# NEW MESSAGE / LAST CHAT MESSAGE CHANGED
def old_log_msg_handler(c: Cardinal, e: LastChatMessageChangedEvent):
    """
    Логирует полученное сообщение.
    """
    if not c.old_mode_enabled:
        return
    text, chat_name, chat_id = str(e.chat), e.chat.name, e.chat.id
    username = c.account.username if not e.chat.unread else e.chat.name

    logger.info(_("log_new_msg", chat_name, chat_id))
    for index, line in enumerate(text.split("\n")):
        if not index:
            logger.info(f"$MAGENTA└───> $YELLOW{username}: $CYAN{line}")
        else:
            logger.info(f"      $CYAN{line}")


def log_msg_handler(c: Cardinal, e: NewMessageEvent):
    global MSG_LOG_LAST_STACK_ID
    if e.stack.id() == MSG_LOG_LAST_STACK_ID:
        return

    chat_name, chat_id = e.message.chat_name, e.message.chat_id

    logger.info(_("log_new_msg", chat_name, chat_id))
    for index, event in enumerate(e.stack.get_stack()):
        username, text = event.message.author, event.message.text or event.message.image_link
        for line_index, line in enumerate(text.split("\n")):
            if not index and not line_index:
                logger.info(f"$MAGENTA└───> $YELLOW{username}: $CYAN{line}")
            elif not line_index:
                logger.info(f"      $YELLOW{username}: $CYAN{line}")
            else:
                logger.info(f"      $CYAN{line}")
    MSG_LOG_LAST_STACK_ID = e.stack.id()


def update_threshold_on_last_message_change(c: Cardinal, e: LastChatMessageChangedEvent | NewMessageEvent):
    """
    Обновляет пороговое значение для определения новых чатов.
    """
    # Должно выполняться после greetings_handler для корректной обработки
    # c.greeting_threshold_chat_ids (чтобы не спамило приветствиями)
    if not c.old_mode_enabled:
        if isinstance(e, LastChatMessageChangedEvent):
            return
        chat_id = e.message.chat_id
    else:
        chat_id = e.chat.id
    if e.runner_tag != c.last_greeting_chat_id_threshold_change_tag:
        c.greeting_chat_id_threshold = max([c.greeting_chat_id_threshold, *c.greeting_threshold_chat_ids])
        c.greeting_threshold_chat_ids = set()
        c.last_greeting_chat_id_threshold_change_tag = e.runner_tag
    c.greeting_threshold_chat_ids.add(chat_id)


def greetings_handler(c: Cardinal, e: NewMessageEvent | LastChatMessageChangedEvent):
    """
    Отправляет приветственное сообщение.
    """
    if not c.MAIN_CFG["Greetings"].getboolean("sendGreetings"):
        return
    if not c.old_mode_enabled:
        if isinstance(e, LastChatMessageChangedEvent):
            return
        obj = e.message
        chat_id, chat_name, mtype, its_me, badge = obj.chat_id, obj.chat_name, obj.type, obj.author_id == c.account.id, obj.badge
    else:
        obj = e.chat
        chat_id, chat_name, mtype, its_me, badge = obj.id, obj.name, obj.last_message_type, not obj.unread, None
    is_old_chat = (chat_id <= c.greeting_chat_id_threshold or chat_id in c.greeting_threshold_chat_ids)

    if any([c.MAIN_CFG["Greetings"].getboolean("onlyNewChats") and is_old_chat,
            time.time() - c.old_users.get(chat_id, 0) < float(
                c.MAIN_CFG["Greetings"]["greetingsCooldown"]) * 24 * 60 * 60,
            its_me, mtype in (MessageTypes.DEAR_VENDORS, MessageTypes.ORDER_CONFIRMED_BY_ADMIN), badge is not None,
            (mtype is not MessageTypes.NON_SYSTEM and c.MAIN_CFG["Greetings"].getboolean("ignoreSystemMessages"))]):
        return

    logger.info(_("log_sending_greetings", chat_name, chat_id))
    text = cardinal_tools.format_msg_text(c.MAIN_CFG["Greetings"]["greetingsText"], obj)
    Thread(target=c.send_message, args=(chat_id, text, chat_name), daemon=True).start()


def add_old_user_handler(c: Cardinal, e: NewMessageEvent | LastChatMessageChangedEvent):
    """
    Добавляет пользователя в список написавших.
    """
    if not c.MAIN_CFG["Greetings"].getboolean("sendGreetings") or c.MAIN_CFG["Greetings"].getboolean("onlyNewChats"):
        return

    if not c.old_mode_enabled:
        if isinstance(e, LastChatMessageChangedEvent):
            return
        chat_id, mtype = e.message.chat_id, e.message.type
    else:
        chat_id, mtype = e.chat.id, e.chat.last_message_type

    if mtype == MessageTypes.DEAR_VENDORS:
        return

    c.old_users[chat_id] = int(time.time())
    cardinal_tools.cache_old_users(c.old_users)


def send_response_handler(c: Cardinal, e: NewMessageEvent | LastChatMessageChangedEvent):
    """
    Проверяет, является ли сообщение командой, и если да, отправляет ответ на данную команду.
    """
    if not c.autoresponse_enabled:
        return
    if not c.old_mode_enabled:
        if isinstance(e, LastChatMessageChangedEvent):
            return
        obj, mtext = e.message, str(e.message)
        chat_id, chat_name, username = e.message.chat_id, e.message.chat_name, e.message.author
    else:
        obj, mtext = e.chat, str(e.chat)
        chat_id, chat_name, username = obj.id, obj.name, obj.name

    mtext = mtext.replace("\n", "")
    if any([c.bl_response_enabled and username in c.blacklist, (command := mtext.strip().lower()) not in c.AR_CFG]):
        return
    if not c.AR_CFG[command].getboolean("enabled"):
        return

    logger.info(_("log_new_cmd", command, chat_name, chat_id))
    response_text = cardinal_tools.format_msg_text(c.AR_CFG[command]["response"], obj)
    Thread(target=c.send_message, args=(chat_id, response_text, chat_name), daemon=True).start()


def process_review_handler(c: Cardinal, e: NewMessageEvent | LastChatMessageChangedEvent):
    if not c.old_mode_enabled:
        if isinstance(e, LastChatMessageChangedEvent):
            return
        obj = e.message
        message_type, its_me = obj.type, obj.i_am_buyer
        message_text, chat_id = str(obj), obj.chat_id

    else:
        obj = e.chat
        message_type, its_me = obj.last_message_type, f" {c.account.username} " in str(obj)
        message_text, chat_id = str(obj), obj.id

    if message_type not in [types.MessageTypes.NEW_FEEDBACK, types.MessageTypes.FEEDBACK_CHANGED] or its_me:
        return

    def send_reply():
        try:
            order = c.get_order_from_object(obj)
            if order is None:
                raise Exception("Не удалось получить объект заказа.")  # locale
        except:
            logger.error(f"Не удалось получить информацию о заказе для сообщения: \"{message_text}\".")  # locale
            logger.debug("TRACEBACK", exc_info=True)
            return

        if not order.review or not order.review.stars:
            return

        logger.info(f"Изменен отзыв на заказ #{order.id}.")  # locale

        if int(order.review.stars) == 5:
            try:
                mysql_cfg = get_mysql_config()
                apply_review_bonus_for_order(
                    mysql_cfg,
                    order_id=str(order.id),
                    owner=order.buyer_username,
                    bonus_minutes=60,
                )
            except Exception:
                logger.exception("Failed to apply 5-star rental bonus.")

        toggle = f"star{order.review.stars}Reply"
        text = f"star{order.review.stars}ReplyText"
        reply_text = None
        if c.MAIN_CFG["ReviewReply"].getboolean(toggle) and c.MAIN_CFG["ReviewReply"].get(text):
            try:
                # Укорачиваем текст до 999 символов (оставляем 1 на спецсимвол), до 10 строк
                def format_text4review(text_: str):
                    max_l = 999
                    text_ = text_[:max_l + 1]
                    if len(text_) > max_l:
                        ln = len(text_)
                        indexes = []
                        for char in (".", "!", "\n"):
                            index1 = text_.rfind(char)
                            indexes.extend([index1, text_[:index1].rfind(char)])
                        text_ = text_[:max(indexes, key=lambda x: (x < ln - 1, x))] + "🐦"
                    text_ = text_.strip()
                    while text_.count("\n") > 9 and text.count("\n\n") > 1:
                        # заменяем с конца все двойные переносы строк на одинарные, но оставляем как можно больше
                        # переносов строк и не менее одного двойного переноса
                        text_ = text_[::-1].replace("\n\n", "\n",
                                                    min([text_.count("\n\n") - 1, text_.count("\n") - 9]))[::-1]
                    if text_.count("\n") > 9:
                        text_ = text_[::-1].replace("\n", " ", text_.count("\n") - 9)[::-1]
                    return text_

                reply_text = cardinal_tools.format_order_text(c.MAIN_CFG["ReviewReply"].get(text), order)
                reply_text = format_text4review(reply_text)
                c.account.send_review(order.id, reply_text)
            except:
                logger.error(f"Произошла ошибка при ответе на отзыв {order.id}.")  # locale
                logger.debug("TRACEBACK", exc_info=True)

    Thread(target=send_reply, daemon=True).start()


def log_new_order_handler(c: Cardinal, e: NewOrderEvent, *args):
    """
    Логирует новый заказ.
    """
    logger.info(f"Новый заказ! ID: $YELLOW#{e.order.id}$RESET")


def update_current_lots(c: Cardinal, e: NewOrderEvent):
    logger.info("Получаю информацию о лотах...")  # locale
    attempts = 3
    while attempts:
        try:
            c.curr_profile = c.account.get_user(c.account.id)
            c.curr_profile_last_tag = e.runner_tag
            break
        except:
            logger.error("Произошла ошибка при получении информации о лотах.")  # locale
            logger.debug("TRACEBACK", exc_info=True)
            attempts -= 1
            time.sleep(2)
    else:
        logger.error("Не удалось получить информацию о лотах: превышено кол-во попыток.")  # locale
        return


def update_profile_lots(c: Cardinal, e: NewOrderEvent):
    """Обновляет лоты в c.profile"""
    if c.curr_profile_last_tag != e.runner_tag or c.profile_last_tag == e.runner_tag:
        return
    c.profile_last_tag = e.runner_tag
    lots = c.curr_profile.get_sorted_lots(1)

    for lot_id, lot in lots.items():
        c.profile.update_lot(lot)

def update_profiles_handler(cardinal: Cardinal, event: NewOrderEvent | OrdersListChangedEvent, *args):
    """Обновляет информацию о профилях и состояния лотов в отдельном потоке."""
    def f(c: Cardinal, e: NewOrderEvent):
        update_current_lots(c, e)
        update_profile_lots(c, e)

    if event.runner_tag != cardinal.last_profile_refresh_event_tag:
        cardinal.last_profile_refresh_event_tag = event.runner_tag
        Thread(target=f, args=(cardinal, event), daemon=True).start()

# BIND_TO_ORDER_STATUS_CHANGED
def send_thank_u_message_handler(cardinal: Cardinal, event: OrderStatusChangedEvent):
    """
    Отправляет ответное сообщение на подтверждение заказа.
    """
    if not cardinal.MAIN_CFG["OrderConfirm"].getboolean("sendReply") or event.order.status is not types.OrderStatuses.CLOSED:
        return

    text = cardinal_tools.format_order_text(cardinal.MAIN_CFG["OrderConfirm"]["replyText"], event.order)
    chat = cardinal.account.get_chat_by_name(event.order.buyer_username)
    if chat:
        chat_id = chat.id
    else:
        chat_id = event.order.chat_id
    logger.info(f"Пользователь $YELLOW{event.order.buyer_username}$RESET подтвердил выполнение заказа "  # locale
                f"$YELLOW{event.order.id}.$RESET")  # locale
    logger.info(f"Отправляю ответное сообщение ...")  # locale
    Thread(target=cardinal.send_message, args=(chat_id, text, event.order.buyer_username),
           kwargs={'watermark': cardinal.MAIN_CFG["OrderConfirm"].getboolean("watermark")}, daemon=True).start()


BIND_TO_INIT_MESSAGE = [save_init_chats_handler, update_threshold_on_initial_chat]

BIND_TO_LAST_CHAT_MESSAGE_CHANGED = [
    old_log_msg_handler,
    greetings_handler,
    update_threshold_on_last_message_change,
    add_old_user_handler,
    send_response_handler,
    process_review_handler,
]

BIND_TO_NEW_MESSAGE = [
    log_msg_handler,
    greetings_handler,
    update_threshold_on_last_message_change,
    add_old_user_handler,
    send_response_handler,
    process_review_handler,
]

BIND_TO_POST_LOTS_RAISE: list = []

# BIND_TO_ORDERS_LIST_CHANGED = [update_profiles_handler]

BIND_TO_NEW_ORDER = [
    log_new_order_handler,
    update_profiles_handler,
]

BIND_TO_ORDER_STATUS_CHANGED = [send_thank_u_message_handler]

BIND_TO_POST_START: list = []

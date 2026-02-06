"""
В данном модуле написаны хэндлеры для разных эвентов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal

from FunPayAPI.types import OrderShortcut, Order
from FunPayAPI import exceptions, utils as fp_utils
from FunPayAPI.updater.events import *

from Utils import cardinal_tools
from railway.db_utils import get_mysql_config
from railway.order_utils import apply_review_bonus_for_order
from locales.localizer import Localizer
from threading import Thread
import configparser
from datetime import datetime
import logging
import time
import re

LAST_STACK_ID = ""
MSG_LOG_LAST_STACK_ID = ""

logger = logging.getLogger("FPC.handlers")
localizer = Localizer()
_ = localizer.translate

ORDER_HTML_TEMPLATE = """<a href="https://funpay.com/orders/DELITEST/" class="tc-item">
   <div class="tc-date" bis_skin_checked="1">
      <div class="tc-date-time" bis_skin_checked="1">сегодня, $date</div>
      <div class="tc-date-left" bis_skin_checked="1">только что</div>
   </div>
   <div class="tc-order" bis_skin_checked="1">#DELITEST</div>
   <div class="order-desc" bis_skin_checked="1">
      <div bis_skin_checked="1">$lot_name</div>
      <div class="text-muted" bis_skin_checked="1">Автовыдача, Тест</div>
   </div>
   <div class="tc-user" bis_skin_checked="1">
      <div class="media media-user offline" bis_skin_checked="1">
         <div class="media-left" bis_skin_checked="1">
            <div class="avatar-photo pseudo-a" tabindex="0" data-href="https://funpay.com/users/000000/" style="background-image: url(/img/layout/avatar.png);" bis_skin_checked="1"></div>
         </div>
         <div class="media-body" bis_skin_checked="1">
            <div class="media-user-name" bis_skin_checked="1">
               <span class="pseudo-a" tabindex="0" data-href="https://funpay.com/users/000000/">$username</span>
            </div>
            <div class="media-user-status" bis_skin_checked="1">был 1.000.000 лет назад</div>
         </div>
      </div>
   </div>
   <div class="tc-status text-primary" bis_skin_checked="1">Оплачен</div>
   <div class="tc-price text-nowrap tc-seller-sum" bis_skin_checked="1">999999.0 <span class="unit">₽</span></div>
</a>"""


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


def test_auto_delivery_handler(c: Cardinal, e: NewMessageEvent | LastChatMessageChangedEvent):
    """
    Выполняет тест автовыдачи.
    """
    if not c.old_mode_enabled:
        if isinstance(e, LastChatMessageChangedEvent):
            return
        obj, message_text, chat_name, chat_id = e.message, str(e.message), e.message.chat_name, e.message.chat_id
    else:
        obj, message_text, chat_name, chat_id = e.chat, str(e.chat), e.chat.name, e.chat.id

    if not message_text.startswith("!автовыдача"):
        return

    split = message_text.split()
    if len(split) < 2:
        logger.warning("Одноразовый ключ автовыдачи не обнаружен.")  # locale
        return

    key = split[1].strip()
    if key not in c.delivery_tests:
        logger.warning("Невалидный одноразовый ключ автовыдачи.")  # locale
        return

    lot_name = c.delivery_tests[key]
    del c.delivery_tests[key]
    date = datetime.now()
    date_text = date.strftime("%H:%M")
    html = ORDER_HTML_TEMPLATE.replace("$username", chat_name).replace("$lot_name", lot_name).replace("$date",
                                                                                                      date_text)

    fake_order = OrderShortcut("ADTEST", lot_name, 0.0, Currency.UNKNOWN, chat_name, 000000, chat_id,
                               types.OrderStatuses.PAID,
                               date, "Авто-выдача, Тест", None, html)

    fake_event = NewOrderEvent(e.runner_tag, fake_order)
    c.run_handlers(c.new_order_handlers, (c, fake_event,))


def get_lot_config_by_name(c: Cardinal, name: str) -> configparser.SectionProxy | None:
    """
    Ищет секцию лота в конфиге автовыдачи.

    :param c: объект кардинала.
    :param name: название лота.

    :return: секцию конфига или None.
    """
    for i in c.AD_CFG.sections():
        if i in name:
            return c.AD_CFG[i]
    return None


def check_products_amount(config_obj: configparser.SectionProxy) -> int:
    file_name = config_obj.get("productsFileName")
    if not file_name:
        return 1
    return cardinal_tools.count_products(f"storage/products/{file_name}")


# Новый ордер (REGISTER_TO_NEW_ORDER)
def log_new_order_handler(c: Cardinal, e: NewOrderEvent, *args):
    """
    Логирует новый заказ.
    """
    logger.info(f"Новый заказ! ID: $YELLOW#{e.order.id}$RESET")


def setup_event_attributes_handler(c: Cardinal, e: NewOrderEvent, *args):
    config_section_name = None
    config_section_obj = None
    lot_shortcut = None
    lot_id = None
    lot_description = e.order.description
    # пробуем найти лот, чтобы не выдавать по строке, которую вписал покупатель при оформлении заказа
    for lot in sorted(list(c.profile.get_sorted_lots(2).get(e.order.subcategory, {}).values()),
                      key=lambda l: len(f"{l.server}, {l.side}, {l.description}"), reverse=True):

        temp_desc = ", ".join([i for i in [lot.server, lot.side, lot.description] if i])

        if temp_desc in e.order.description:
            lot_description = temp_desc
            lot_shortcut = lot
            lot_id = lot.id
            break

    for i in range(3):
        for lot_name in c.AD_CFG:
            if i == 0:
                rule = lot_description == lot_name
            elif i == 1:
                rule = lot_description.startswith(lot_name)
            else:
                rule = lot_name in lot_description

            if rule:
                config_section_obj = c.AD_CFG[lot_name]
                config_section_name = lot_name
                break
        if config_section_obj:
            break

    attributes = {"config_section_name": config_section_name, "config_section_obj": config_section_obj,
                  "delivered": False, "delivery_text": None, "goods_delivered": 0, "goods_left": None,
                  "error": 0, "error_text": None, "lot_id": lot_id, "lot_shortcut": lot_shortcut}
    for i in attributes:
        setattr(e, i, attributes[i])

    if config_section_obj is None:
        logger.info("Лот не найден в конфиге авто-выдачи!")  # todo
    else:
        logger.info("Лот найден в конфиге авто-выдачи!")  # todo


def deliver_goods(c: Cardinal, e: NewOrderEvent, *args):
    chat = c.account.get_chat_by_name(e.order.buyer_username)
    if chat:
        chat_id = chat.id
    else:
        chat_id = e.order.chat_id
    cfg_obj = getattr(e, "config_section_obj")
    delivery_text = cardinal_tools.format_order_text(cfg_obj["response"], e.order)

    amount, goods_left, products = 1, -1, []
    try:
        if file_name := cfg_obj.get("productsFileName"):
            if c.multidelivery_enabled and not cfg_obj.getboolean("disableMultiDelivery"):
                amount = e.order.amount if e.order.amount else 1
            products, goods_left = cardinal_tools.get_products(f"storage/products/{file_name}", amount)
            delivery_text = delivery_text.replace("$product", "\n".join(products).replace("\\n", "\n"))
    except Exception as exc:
        logger.error(
            f"Произошла ошибка при получении товаров для заказа $YELLOW{e.order.id}: {str(exc)}$RESET")  # locale
        logger.debug("TRACEBACK", exc)
        setattr(e, "error", 1)
        setattr(e, "error_text",
                f"Произошла ошибка при получении товаров для заказа {e.order.id}: {str(exc)}")  # locale
        return

    result = c.send_message(chat_id, delivery_text, e.order.buyer_username)
    if not result:
        logger.error(f"Не удалось отправить товар для ордера $YELLOW{e.order.id}$RESET.")  # locale
        setattr(e, "error", 1)
        setattr(e, "error_text", f"Не удалось отправить сообщение с товаром для заказа {e.order.id}.")  # locale
        if file_name and products:
            cardinal_tools.add_products(f"storage/products/{file_name}", products, at_zero_position=True)
    else:
        logger.info(f"Товар для заказа {e.order.id} выдан.")  # locale
        setattr(e, "delivered", True)
        setattr(e, "delivery_text", delivery_text)
        setattr(e, "goods_delivered", amount)
        setattr(e, "goods_left", goods_left)


def deliver_product_handler(c: Cardinal, e: NewOrderEvent, *args) -> None:
    """
    Обертка для deliver_product(), обрабатывающая ошибки.
    """
    if not c.MAIN_CFG["FunPay"].getboolean("autoDelivery"):
        return
    if e.order.buyer_username in c.blacklist and c.bl_delivery_enabled:
        logger.info(f"Пользователь {e.order.buyer_username} находится в ЧС и включена блокировка автовыдачи. "
                    f"$YELLOW(ID: {e.order.id})$RESET")  # locale
        return

    if (config_section_obj := getattr(e, "config_section_obj")) is None:
        return
    if config_section_obj.getboolean("disable"):
        logger.info(f"Для лота \"{e.order.description}\" отключена автовыдача.")  # locale
        return

    c.run_handlers(c.pre_delivery_handlers, (c, e))
    deliver_goods(c, e, *args)
    c.run_handlers(c.post_delivery_handlers, (c, e))


# REGISTER_TO_POST_DELIVERY
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

def update_lot_state(cardinal: Cardinal, lot: types.LotShortcut, task: int) -> bool:
    """
    Обновляет состояние лота

    :param cardinal: объект Кардинала.
    :param lot: объект лота.
    :param task: -1 - деактивировать лот. 1 - активировать лот.

    :return: результат выполнения.
    """
    attempts = 3
    while attempts:
        try:
            lot_fields = cardinal.account.get_lot_fields(lot.id)
            if lot_fields.auto_delivery:
                # если включена автовыдача FunPay - не трогаем
                return False
            elif lot_fields.amount and task == (1 if lot_fields.active else -1):
                #если у лота есть наличие (есть поле + не 0) и лот и так в нужном состоянии
                return True
            elif task == 1:
                lot_fields.active = True
                cardinal.account.save_lot(lot_fields)
                logger.info(f"Восстановил лот $YELLOW{lot.id} - {lot.description}$RESET.")  # locale
            elif task == -1:
                lot_fields.active = False
                cardinal.account.save_lot(lot_fields)
                logger.info(f"Деактивировал лот $YELLOW{lot.id} - {lot.description}$RESET.")  # locale
            return True
        except Exception as e:
            if isinstance(e, exceptions.LotParsingError):
                logger.error(f"Произошла ошибка при изменении состояния лота $YELLOW{lot.description}$RESET:"  # locale
                             "лот не найден.")
                return False
            logger.error(f"Произошла ошибка при изменении состояния лота $YELLOW{lot.description}$RESET.")  # locale
            logger.debug("TRACEBACK", exc_info=True)
            attempts -= 1
            time.sleep(2)
    logger.error(
        f"Не удалось изменить состояние лота $YELLOW{lot.description}$RESET: превышено кол-во попыток.")  # locale
    return False


def update_lots_states(cardinal: Cardinal, event: NewOrderEvent):
    if not cardinal.autorestore_enabled:
        return
    curr_profile_tag = cardinal.curr_profile_last_tag
    if cardinal.last_state_change_tag == curr_profile_tag:
        return
    cardinal.last_state_change_tag = curr_profile_tag
    lots = cardinal.curr_profile.get_sorted_lots(1)

    for lot in cardinal.profile.get_sorted_lots(3)[SubCategoryTypes.COMMON].values():
        if not lot.description:
            continue
        # -1 - деактивировать
        # 0 - ничего не делать
        # 1 - восстановить
        current_task = 0
        config_obj = get_lot_config_by_name(cardinal, lot.description)

        # Если лот уже деактивирован
        if lot.id not in lots:
            # и не найден в конфиге автовыдачи (глобальное автовосстановление включено)
            if config_obj is None:
                if cardinal.autorestore_enabled:
                    current_task = 1

            # и найден в конфиге автовыдачи
            else:
                # и глобальное автовосстановление вкл. + не выключено в самом лоте в конфиге автовыдачи
                if cardinal.autorestore_enabled and config_obj.get("disableAutoRestore") in ["0", None]:
                    current_task = 1
        if current_task:
            update_lot_state(cardinal, lot, current_task)
            time.sleep(0.5)

def update_profiles_handler(cardinal: Cardinal, event: NewOrderEvent | OrdersListChangedEvent, *args):
    """Обновляет информацию о профилях и состояния лотов в отдельном потоке."""
    def f(c: Cardinal, e: NewOrderEvent):
        update_current_lots(c, e)
        update_profile_lots(c, e)
        update_lots_states(c, e)

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
    test_auto_delivery_handler,
]

BIND_TO_NEW_MESSAGE = [
    log_msg_handler,
    greetings_handler,
    update_threshold_on_last_message_change,
    add_old_user_handler,
    send_response_handler,
    process_review_handler,
    test_auto_delivery_handler,
]

BIND_TO_POST_LOTS_RAISE: list = []

# BIND_TO_ORDERS_LIST_CHANGED = [update_profiles_handler]

BIND_TO_NEW_ORDER = [
    log_new_order_handler,
    setup_event_attributes_handler,
    deliver_product_handler,
    update_profiles_handler,
]

BIND_TO_ORDER_STATUS_CHANGED = [send_thank_u_message_handler]

BIND_TO_POST_DELIVERY: list = []

BIND_TO_POST_START: list = []

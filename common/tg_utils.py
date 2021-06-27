import re
import traceback

from bot import storage, bot, ApiException, Message, ReplyKeyboardMarkup, KeyboardButton
from common.models import User as DbUser
from config import Config
from texts import get_user_texts


def msg_to_remove(chat_id: int, msg_id: int):
    """
    Add message_id to storage list for removing
    :param chat_id:
    :param msg_id: message_id
    """
    data = storage.get_data(chat_id, default={})
    msgs_list = data.get('_msg_to_remove', [])
    msgs_list.append(msg_id)
    storage.update_data(chat_id, data={'_msg_to_remove': msgs_list})


def remove_msgs(chat_id: int, omit_last=False):
    """
    Remove all message in storage list for removing
    :param chat_id:
    :omit_last Omit delete last msg
    """
    data = storage.get_data(chat_id, default={})
    msgs_list = data.get('_msg_to_remove', [])

    if '_msg_to_remove' in data:
        data.pop('_msg_to_remove')

    l = msgs_list if not omit_last else msgs_list[:-1]
    for msg_id in l:
        # Failed to delete - just omit. Message still in chat. Not great failure
        try:
            bot.delete_message(chat_id, msg_id)
        except ApiException:
            pass

    l = [] if not omit_last else [msgs_list[-1]]
    bot.update_data({'_msg_to_remove': l}, chat_id)


def remove_msg(chat_id: int, msg_id: int):
    """
    Safe remove message from chat
    :param chat_id:
    :param msg_id: message_id
    """
    try:
        bot.delete_message(chat_id, msg_id)
    except ApiException:
        pass


def send_removing_message(chat_id, text, disable_web_page_preview=None, reply_to_message_id=None, reply_markup=None,
                          parse_mode=None, disable_notification=None) -> Message:
    """
    Send message and add it to removing list
    """

    message = bot.send_message(chat_id, text, disable_web_page_preview, reply_to_message_id, reply_markup,
                               parse_mode, disable_notification)
    msg_to_remove(chat_id, message.message_id)

    return message


def send_removing_photo(chat_id, photo, caption=None, reply_to_message_id=None, reply_markup=None,
                        parse_mode=None, disable_notification=None) -> Message:
    """
    Send photo and add it's message to removing list
    """

    message = bot.send_photo(chat_id, photo, caption, reply_to_message_id, reply_markup,
                             parse_mode, disable_notification)
    msg_to_remove(chat_id, message.message_id)

    return message


def true_func(arg):
    return True


GIRL_MENU_BUTTONS = ['menu_orders_button', 'menu_schedule_button',
                     'menu_wallet_button', 'menu_data_button',
                     'menu_settings_button', 'menu_support_button']

CLIENT_MENU_BUTTONS = ['menu_client_orders_button', 'menu_wallet_button',
                       'menu_girls_button', 'menu_settings_button',
                       'menu_news_button', 'menu_support_button']


def girl_menu_reply(user_id: int) -> ReplyKeyboardMarkup:
    texts = get_user_texts(user_id)

    reply = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for button in GIRL_MENU_BUTTONS:
        buttons.append(KeyboardButton(texts[button]))
    reply.add(*buttons)

    return reply


def client_menu_reply(user_id: int) -> ReplyKeyboardMarkup:
    texts = get_user_texts(user_id)

    reply = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for button in CLIENT_MENU_BUTTONS:
        buttons.append(KeyboardButton(texts[button]))
    reply.add(*buttons)

    return reply


def is_worker(msg: Message):
    query = DbUser.select().where(DbUser.user_id == msg.from_user.id, DbUser.role == 'worker')
    return query.exists()


def is_admin(msg: Message):
    query = DbUser.select().where(DbUser.user_id == msg.from_user.id, DbUser.role == 'admin')
    return query.exists()


def is_super_admin(msg: Message):
    return msg.from_user.id == Config.MAIN_ADMIN_ID and DbUser.select(DbUser.user_id == msg.from_user.id).exists()


def regexp_by_id(filter_value, msg: Message):
    if msg.content_type != 'text':
        return False

    texts = get_user_texts(msg.from_user.id)
    return bool(re.search(texts[filter_value], msg.text, re.IGNORECASE))

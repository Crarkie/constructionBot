import bot
from admin_handlers import super_admin_main_menu
from bot import *
from common.tg_utils import *
from texts import get_texts, DEFAULT_LANGUAGE
from common.models import *
from common.models import User as DbUser
from common.models_helpers import *

@bot.message_handler(commands=['start'])
def entry_start_handler(msg: Message):
    user = get_user_entity(msg.from_user.id)
    texts = get_user_texts(msg.from_user.id)

    if not user:
        send_removing_message(msg.from_user.id, texts['welcome_text'])
        remove_msg(msg.from_user.id, msg.message_id)
        bot.set_state('enter_name', msg.from_user.id)


@bot.message_handler(state='enter_name', func=true_func)
def enter_name_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    remove_msg(msg.from_user.id, msg.message_id)
    name = msg.text
    bot.update_data({'name': name}, msg.from_user.id)

    reply = InlineKeyboardMarkup(row_width=2)
    reply.add(InlineKeyboardButton(texts['yes_text'], callback_data='yes'),
              InlineKeyboardButton(texts['change_name'], callback_data='change_name'))

    if msg.from_user.id == Config.MAIN_ADMIN_ID:
        text = texts['confirm_name'].format(name=name)
    else:
        text = texts['send_add_request'].format(name=name)

    send_removing_message(msg.from_user.id, text, parse_mode='HTML', reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    bot.set_state('send_add_request', msg.from_user.id)


def send_add_request_to_admin(user, name):
    texts = get_user_texts(Config.MAIN_ADMIN_ID)

    reply = InlineKeyboardMarkup(row_width=1)
    reply.add(InlineKeyboardButton(texts['add_as_admin'], callback_data='add_request_admin:' + str(user.id)),
              InlineKeyboardButton(texts['add_as_worker'], callback_data='add_request_worker:' + str(user.id)),
              InlineKeyboardButton(texts['add_decline'], callback_data='add_request_decline:' + str(user.id)))
    bot.send_message(Config.MAIN_ADMIN_ID, texts['user_add_request'].format(name=name, username=user.username),
                     parse_mode='HTML', reply_markup=reply)


@bot.callback_query_handler(state='send_add_request', func=true_func)
def send_add_request_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    bot.answer_callback_query(callback.id)

    data = callback.data
    user_data = storage.get_data(callback.from_user.id)

    if data == 'yes':
        if callback.from_user.id == Config.MAIN_ADMIN_ID:
            DbUser.create(user_id=callback.from_user.id, role='admin',
                          language=DEFAULT_LANGUAGE, name=user_data['name'])
            super_admin_main_menu(callback.from_user.id)
            bot.set_state('main_menu', callback.from_user.id)
        else:
            send_removing_message(callback.from_user.id, texts['add_request_sent'])
            remove_msgs(callback.from_user.id, True)
            send_add_request_to_admin(callback.from_user, user_data['name'])
            bot.set_state('wait_approved', callback.from_user.id)
    elif data == 'change_name':
        send_removing_message(callback.from_user.id, texts['enter_your_name'])
        remove_msgs(callback.from_user.id, True)
        bot.set_state('enter_name', callback.from_user.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith('notify_'))
def notify_handler(callback: CallbackQuery):
    if callback.data == 'notify_close':
        bot.answer_callback_query(callback.id)
        remove_msg(callback.from_user.id, callback.message.message_id)



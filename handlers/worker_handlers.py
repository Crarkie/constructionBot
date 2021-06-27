import bot
from bot import *
from common.tg_utils import *
from entity_pager import EntityPager
from texts import get_texts, DEFAULT_LANGUAGE
from common.models import *
from common.models_helpers import *

WORKER_MAIN_MENU = ['create_request', 'my_tasks']


def worker_menu_reply(user_id):
    texts = get_user_texts(user_id)
    reply = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    reply.add(*map(lambda t: texts[t], WORKER_MAIN_MENU))
    return reply


def worker_main_menu(user_id):
    texts = get_user_texts(user_id)

    send_removing_message(user_id, texts['menu'], reply_markup=worker_menu_reply(user_id))
    remove_msgs(user_id, True)


@bot.message_handler(state='main_menu', func=is_worker)
def worker_main_menu_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    remove_msg(msg.from_user.id, msg.message_id)

    if msg.text == texts['create_request']:
        send_removing_message(msg.from_user.id, texts['enter_request_text'])
        remove_msgs(msg.from_user.id, True)
        bot.set_state('new_request_text', msg.from_user.id)
    elif msg.text == texts['my_tasks']:
        user = DbUser.get(msg.from_user.id)
        query = Task.select().join(TaskWorker).where(TaskWorker.worker == user,
                                                     Task.task_status.in_(['initiated', 'wait_approval'])).order_by(-Task.end_date)
        if query.count() == 0:
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

            send_removing_message(msg.from_user.id, texts['no_my_tasks'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(msg.from_user.id, True)
            bot.set_state('list_tasks', msg.from_user.id)
        else:
            pager = EntityPager(msg.from_user.id, query, lambda e: texts['actions'], lambda e: e.id, 'task_actions',
                                per_page=1)
            pager.first_page()
            entity = pager.get_current_entities()[0]

            date = entity.end_date.strftime('%H:%M %d.%m.%Y')
            text = texts['task_description'].format(task_number=entity.task_number,
                                                    task_text=entity.task_text,
                                                    task_end_date=date,
                                                    task_status=texts[entity.task_status])

            task_workers = TaskWorker.select().where(TaskWorker.task == entity)

            i = 1
            for worker in task_workers:
                user = worker.worker
                chat = bot.get_chat(user.user_id)
                text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
                i += 1

            if entity.task_photo is None:
                send_removing_message(msg.from_user.id, text,
                                      reply_markup=pager(), parse_mode='HTML')
            else:
                send_removing_photo(msg.from_user.id, entity.task_photo.file_id, text,
                                    reply_markup=pager(), parse_mode='HTML')
            remove_msgs(msg.from_user.id, True)
            bot.set_state('list_tasks', msg.from_user.id)
    else:
        worker_main_menu(msg.from_user.id)


@bot.message_handler(state='new_request_text', func=is_worker)
def admin_new_request_text(msg: Message):
    texts = get_user_texts(msg.from_user.id)
    text = msg.text
    bot.update_data({'request_text': text}, msg.from_user.id)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
    send_removing_message(msg.from_user.id, texts['request_attach_photo'],
                          reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    remove_msg(msg.from_user.id, msg.message_id)
    bot.set_state('new_request_attach_photo', msg.from_user.id)


@bot.message_handler(state='new_request_attach_photo', content_types=['photo'], func=is_worker)
def worker_request_attach_photo_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    photo, _ = Photo.get_or_create(file_id=msg.photo[-1].file_id)
    photo.download_file(bot)

    bot.update_data({'request_photo': photo.file_id}, msg.from_user.id)
    remove_msg(msg.from_user.id, msg.message_id)

    query = DbUser.select().where(DbUser.role == 'admin')
    pager = EntityPager(msg.from_user.id, query,
                        lambda e: e.name, lambda e: e.user_id, 'user')
    pager.first_page()
    send_removing_message(msg.from_user.id, texts['request_choose_admin'], reply_markup=pager())
    remove_msgs(msg.from_user.id, True)
    bot.set_state('request_choose_admin', msg.from_user.id)


@bot.callback_query_handler(state='new_request_attach_photo', func=is_worker)
def worker_request_attach_photo_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'omit':
        bot.update_data({'request_photo': None}, callback.from_user.id)

        query = DbUser.select().where(DbUser.role == 'admin')
        pager = EntityPager(callback.from_user.id, query,
                            lambda e: e.name, lambda e: e.user_id, 'user')
        pager.first_page()
        send_removing_message(callback.from_user.id, texts['request_choose_admin'], reply_markup=pager())
        remove_msgs(callback.from_user.id, True)
        bot.set_state('request_choose_admin', callback.from_user.id)


@bot.callback_query_handler(state='request_choose_admin', func=is_worker)
def worker_request_choose_admin(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    query = DbUser.select().where(DbUser.role == 'admin')
    pager = EntityPager(callback.from_user.id, query,
                        lambda e: e.name, lambda e: e.user_id, 'user')
    result = pager.handle_callback(callback)
    if result:
        if result == 'back':
            worker_main_menu(callback.from_user.id)
            bot.set_state('main_menu', callback.from_user.id)
        else:
            user_id = int(callback.data.split(':')[1])
            bot.update_data({'request_user_id': user_id}, callback.from_user.id)
            reply = InlineKeyboardMarkup(row_width=1)
            reply.add(InlineKeyboardButton(texts['yes_text'], callback_data='send_request'))
            reply.add(InlineKeyboardButton(texts['cancel'], callback_data='cancel_request'))


            send_removing_message(callback.from_user.id, texts['confirm_send_request'], reply_markup=reply, parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('confirm_request_send', callback.from_user.id)
    else:
        try:  # May be not modified
            bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=pager())
        except ApiException:
            pass


def send_request_notify(request: Request):
    texts = get_texts(DEFAULT_LANGUAGE)

    a_name = f'{request.added_by.name} (<i>@{bot.get_chat(request.added_by.user_id).username}</i>)'
    e_name = f'{request.executor.name} (<i>@{bot.get_chat(request.executor.user_id).username}</i>)'
    text = texts['new_request_notify'].format(request_number=request.task_number,
                                              added_by=a_name,
                                              request_text=request.request_text,
                                              executor_name=e_name) + '\n'

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

    if request.request_photo is not None:
        bot.send_photo(Config.GROUP_ID, request.request_photo.file_id, text, parse_mode='HTML')
        bot.send_photo(request.executor.user_id, request.request_photo.file_id, text, parse_mode='HTML',
                       reply_markup=reply)
    else:
        bot.send_message(Config.GROUP_ID, text, parse_mode='HTML')
        bot.send_message(request.executor.user_id, text, parse_mode='HTML',
                         reply_markup=reply)


@bot.callback_query_handler(state='confirm_request_send', func=is_worker)
def worker_request_send_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)
    data = callback.data

    if data == 'cancel_request':
        bot.answer_callback_query(callback.id, texts['request_canceled'])

        worker_main_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)
    elif data == 'send_request':
        data = storage.get_data(callback.from_user.id)

        request = Request.create(request_text=data['request_text'], request_photo=Photo.get_or_none(Photo.file_id==data['request_photo']),
                                 executor=DbUser.get(data['request_user_id']),
                                 added_by=DbUser.get(callback.from_user.id))
        send_request_notify(request)
        bot.answer_callback_query(callback.id, texts['request_sent'])

        worker_main_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)


@bot.callback_query_handler(state='list_tasks', func=is_worker)
def admin_list_tasks_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    user = DbUser.get(callback.from_user.id)
    query = Task.select().join(TaskWorker).where(TaskWorker.worker == user,
                                                 Task.task_status.in_(['initiated', 'wait_approval'])).order_by(-Task.end_date)
    pager = EntityPager(callback.from_user.id, query, lambda e: texts['actions'], lambda e: e.id, 'task_actions',
                        per_page=1)
    result = pager.handle_callback(callback)
    if result:
        if result == 'back':
            worker_main_menu(callback.from_user.id)
            bot.set_state('main_menu', callback.from_user.id)
        elif result.startswith('task_actions'):
            task_id = int(result.split(':')[1])
            task = Task.get(task_id)

            reply = InlineKeyboardMarkup(row_width=1)
            if task.task_status == 'initiated':
                reply.add(InlineKeyboardButton(texts['request_cancel'], callback_data='request_cancel:' + str(task_id)),
                          InlineKeyboardButton(texts['complete_task'], callback_data='complete_task:' + str(task_id)),
                          InlineKeyboardButton(texts['back'], callback_data='back'))
            else:
                reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

            send_removing_message(callback.from_user.id, texts['choose_action'], reply_markup=reply)
            remove_msgs(callback.from_user.id, True)
            bot.set_state('task_actions', callback.from_user.id)
    else:
        entity = pager.get_current_entities()[0]

        date = entity.end_date.strftime('%H:%M %d.%m.%Y')
        text = texts['task_description'].format(task_number=entity.task_number,
                                                task_text=entity.task_text,
                                                task_end_date=date,
                                                task_status=texts[entity.task_status])

        task_workers = TaskWorker.select().where(TaskWorker.task == entity)

        i = 1
        for worker in task_workers:
            user = worker.worker
            chat = bot.get_chat(user.user_id)
            text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
            i += 1
        if entity.task_photo is None:
            send_removing_message(callback.from_user.id, text,
                                  reply_markup=pager(), parse_mode='HTML')
        else:
            send_removing_photo(callback.from_user.id, entity.task_photo.file_id, text,
                                reply_markup=pager(), parse_mode='HTML')
        remove_msgs(callback.from_user.id, True)


@bot.callback_query_handler(state='task_actions', func=is_worker)
def worker_task_actions_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = callback.data
    if data == 'back':
        user = DbUser.get(callback.from_user.id)
        query = Task.select().join(TaskWorker).where(TaskWorker.worker == user,
                                                     Task.task_status.in_(['initiated', 'wait_approval']))\
            .order_by(-Task.end_date)
        if query.count() == 0:
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

            send_removing_message(callback.from_user.id, texts['no_my_tasks'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('list_tasks', callback.from_user.id)
        else:
            pager = EntityPager(callback.from_user.id, query, lambda e: texts['actions'], lambda e: e.id,
                                'task_actions',
                                per_page=1)
            entity = pager.get_current_entities()[0]

            date = entity.end_date.strftime('%H:%M %d.%m.%Y')
            text = texts['task_description'].format(task_number=entity.task_number,
                                                    task_text=entity.task_text,
                                                    task_end_date=date,
                                                    task_status=texts[entity.task_status])

            task_workers = TaskWorker.select().where(TaskWorker.task == entity)

            i = 1
            for worker in task_workers:
                user = worker.worker
                chat = bot.get_chat(user.user_id)
                text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
                i += 1

            if entity.task_photo is None:
                send_removing_message(callback.from_user.id, text,
                                      reply_markup=pager(), parse_mode='HTML')
            else:
                send_removing_photo(callback.from_user.id, entity.task_photo.file_id, text,
                                    reply_markup=pager(), parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('list_tasks', callback.from_user.id)
    elif data.startswith('request_cancel'):
        task_id = int(data.split(':')[1])
        task = Task.get(task_id)
        worker = DbUser.get(callback.from_user.id)
        chat = bot.get_chat(worker.user_id)
        worker_name = f'{worker.name} (<i>@{chat.username}</i>)'

        reply = InlineKeyboardMarkup(row_width=1)
        reply.add(InlineKeyboardButton(texts['cancel_button'], callback_data='admin_action:cancel_task:' +
                                                                             str(task_id) + ':' + str(
            callback.from_user.id)))
        reply.add(InlineKeyboardButton(texts['no_cancel_button'], callback_data='admin_action:no_cancel_task:' +
                                                                                str(task_id) + ':' + str(
            callback.from_user.id)))
        bot.send_message(task.added_by.user_id, texts['request_cancel_task'].format(worker_name=worker_name,
                                                                                    task_number=task.task_number,
                                                                                    task_text=task.task_text),
                         reply_markup=reply, parse_mode='HTML')
        bot.answer_callback_query(callback.id, texts['request_cancel_sent'])
        worker_main_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)
    elif data.startswith('complete_task'):
        task_id = int(data.split(':')[1])
        bot.update_data({'task_id': task_id}, callback.from_user.id)

        send_removing_message(callback.from_user.id, texts['task_result_enter_text'])
        remove_msgs(callback.from_user.id, True)
        bot.set_state('task_result_text', callback.from_user.id)


@bot.message_handler(state='task_result_text', func=is_worker)
def worker_result_text_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    text = msg.text
    remove_msg(msg.from_user.id, msg.message_id)

    bot.update_data({'task_text': text, 'task_photo': None}, msg.from_user.id)
    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
    send_removing_message(msg.from_user.id, texts['task_result_attach_photo'], reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    bot.set_state('task_result_photo', msg.from_user.id)


@bot.message_handler(state='task_result_photo', content_types=['photo'], func=is_worker)
def worker_result_photo_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    photo, _ = Photo.get_or_create(file_id=msg.photo[-1].file_id)
    photo.download_file(bot)

    bot.update_data({'task_photo': photo.file_id, 'task_invoice': None}, msg.from_user.id)
    remove_msg(msg.from_user.id, msg.message_id)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
    send_removing_message(msg.from_user.id, texts['task_result_attach_invoice_photo'], reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    bot.set_state('task_result_invoice', msg.from_user.id)


@bot.callback_query_handler(state='task_result_photo', func=is_worker)
def worker_result_photo_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'omit':
        bot.update_data({'task_invoice': None}, callback.from_user.id)

        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
        send_removing_message(callback.from_user.id, texts['task_result_attach_invoice_photo'], reply_markup=reply)
        remove_msgs(callback.from_user.id, True)
        bot.set_state('task_result_invoice', callback.from_user.id)


def send_complete_task(task_id, user_id, photo_id, invoice_id, result_text):
    task = Task.get(task_id)
    task.task_status = 'wait_approval'
    task.save()

    texts = get_user_texts(task.added_by.user_id)
    user = DbUser.get(user_id)

    reply = InlineKeyboardMarkup(row_width=2)
    bot.update_data({f't{task_id}': [user_id, photo_id, invoice_id, result_text]}, task.added_by.user_id)
    if photo_id is not None:
        reply.add(InlineKeyboardButton(texts['result_photo'], callback_data=f'admin_action:result_photo:{task_id}'))
    if invoice_id is not None:
        reply.add(InlineKeyboardButton(texts['result_invoice_photo'],
                                       callback_data=f'admin_action:result_invoice_photo:{task_id}'))

    reply.row(
        InlineKeyboardButton(texts['confirm_complete_task'], callback_data=f'admin_action:confirm_task:{task_id}'))
    reply.row(
        InlineKeyboardButton(texts['cancel_confirm_task'], callback_data=f'admin_action:cancel_confirm_task:{task_id}'))

    chat = bot.get_chat(user_id)
    name = f'{user.name} (<i>@{chat.username}</i>)'
    if task.task_photo is None:
        bot.send_message(task.added_by.user_id, texts['completed_task'].format(worker_name=name,
                                                                               task_number=task.task_number,
                                                                               task_text=task.task_text,
                                                                               result_text=result_text),
                         reply_markup=reply, parse_mode='HTML')
    else:
        bot.send_photo(task.added_by.user_id, task.task_photo.file_id,
                       texts['completed_task'].format(worker_name=name,
                                                      task_number=task.task_number,
                                                      task_text=task.task_text),
                       reply_markup=reply, parse_mode='HTML')


@bot.message_handler(state='task_result_invoice', content_types=['photo'], func=is_worker)
def worker_result_photo_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    photo, _ = Photo.get_or_create(file_id=msg.photo[-1].file_id)
    photo.download_file(bot)

    bot.update_data({'task_invoice': photo.file_id}, msg.from_user.id)
    remove_msg(msg.from_user.id, msg.message_id)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))
    bot.send_message(msg.from_user.id, texts['sent_to_confirm'], reply_markup=reply)

    data = storage.get_data(msg.from_user.id)
    send_complete_task(data['task_id'], msg.from_user.id, data['task_photo'], data['task_invoice'], data['task_text'])

    worker_main_menu(msg.from_user.id)
    bot.set_state('main_menu', msg.from_user.id)


@bot.callback_query_handler(state='task_result_invoice', func=is_worker)
def worker_result_photo_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'omit':
        bot.answer_callback_query(callback.id, texts['sent_to_confirm'])

        data = storage.get_data(callback.from_user.id)
        send_complete_task(data['task_id'], callback.from_user.id, data['task_photo'], data['task_invoice'], data['task_text'])

        worker_main_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)


@bot.message_handler(func=is_worker)
def worker_message_handler(msg: Message):
    remove_msg(msg.from_user.id, msg.message_id)
    worker_main_menu(msg.from_user.id)
    bot.set_state('main_menu', msg.from_user.id)

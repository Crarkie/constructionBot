from datetime import timedelta

import bot
from bot import *
from calendar_view import CalendarView
from common.tg_utils import *
from entity_pager import EntityPager
from texts import get_texts, DEFAULT_LANGUAGE
from common.models import *
from common.models import Invoice as DbInvoice
from common.models_helpers import *
from worker_handlers import worker_menu_reply

ADMIN_MAIN_MENU = ['requests', 'tasks', 'documents']
SUPER_ADMIN_MAIN_MENU = ADMIN_MAIN_MENU + ['users']

@bot.callback_query_handler(func=lambda c: c.data.startswith('notify_'))
def notify_handler(callback: CallbackQuery):
    if callback.data == 'notify_close':
        bot.answer_callback_query(callback.id)
        remove_msg(callback.from_user.id, callback.message.message_id)

def send_confirmed_task(task: Task):
    texts = get_texts(DEFAULT_LANGUAGE)

    date = task.end_date.strftime('%H:%M %d.%m.%Y')
    deadline = task.deadline_date.strftime('%H:%M %d.%m.%Y')
    executor = f'{task.end_by_worker.name} (<i>@{bot.get_chat(task.end_by_worker.user_id).username}</i>)'
    text = texts['confirmed_task_notify'].format(task_number=task.task_number,
                                                 executor_name=executor,
                                                 result_text=task.task_result_text,
                                                 deadline_date=deadline,
                                                 end_date=date)
    task_workers = TaskWorker.select().where(TaskWorker.task == task)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

    if task.task_result_photo is not None:
        bot.send_photo(Config.GROUP_ID, task.task_result_photo.file_id, text, parse_mode='HTML')
        for worker in task_workers:
            bot.send_photo(worker.worker.user_id, task.task_result_photo.file_id, text, parse_mode='HTML',
                           reply_markup=reply)
    else:
        bot.send_message(Config.GROUP_ID, text, parse_mode='HTML')
        for worker in task_workers:
            bot.send_message(worker.worker.user_id, text, parse_mode='HTML',
                             reply_markup=reply)


@bot.callback_query_handler(func=lambda c: is_admin(c) and c.data.startswith('admin_action'))
def admin_action_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)
    data = callback.data

    action = data.split(':')[1]
    if action == 'no_cancel_task':
        bot.answer_callback_query(callback.id, texts['no_cancel_sent'])
        remove_msg(callback.from_user.id, callback.message.message_id)
        user_id = int(data.split(':')[3])
        admin = bot.get_chat(callback.from_user.id)
        admin_user = DbUser.get(callback.from_user.id)
        admin = f'<b>{admin_user.name}</b> (<i>@{admin.username}</i>)'
        task = Task.get(int(data.split(':')[2]))

        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))
        bot.send_message(user_id, texts['no_cancel_notify'].format(admin=admin,
                                                                   task_number=task.task_number),
                         reply_markup=reply, parse_mode='HTML')
    elif action == 'cancel_task':
        task = Task.get(int(data.split(':')[2]))
        task.task_status = 'canceled'
        task.save()

        send_cancel_task_notify(task)
        bot.answer_callback_query(callback.id, texts['cancel_sent'])
        remove_msg(callback.from_user.id, callback.message.message_id)
    elif action == 'result_photo':
        task_id = int(data.split(':')[2])
        data = storage.get_data(callback.from_user.id)
        _, photo_id, _, _ = data[f't{task_id}']

        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['back'], callback_data=f'admin_action:task_result_back:{task_id}'))
        remove_msg(callback.from_user.id, callback.message.message_id)
        bot.send_photo(callback.from_user.id, photo_id, reply_markup=reply)
    elif action == 'result_invoice_photo':
        task_id = int(data.split(':')[2])
        data = storage.get_data(callback.from_user.id)
        _, _, invoice_id, _ = data[f't{task_id}']

        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['back'], callback_data=f'admin_action:task_result_back:{task_id}'))
        remove_msg(callback.from_user.id, callback.message.message_id)
        bot.send_photo(callback.from_user.id, invoice_id, reply_markup=reply)
    elif action == 'task_result_back':
        task_id = int(data.split(':')[2])
        data = storage.get_data(callback.from_user.id)
        user_id, photo_id, invoice_id, result_text = data[f't{task_id}']

        task = Task.get(task_id)
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
            InlineKeyboardButton(texts['cancel_confirm_task'],
                                 callback_data=f'admin_action:cancel_confirm_task:{task_id}'))

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
        remove_msg(callback.from_user.id, callback.message.message_id)
    elif action == 'cancel_confirm_task':
        task_id = int(data.split(':')[2])
        task = Task.get(task_id)
        task.task_status = 'initiated'
        task.save()
        data = storage.get_data(callback.from_user.id)
        user_id, photo_id, invoice_id, result_text = data[f't{task_id}']
        bot.answer_callback_query(callback.id, texts['sent_rework'])
        remove_msg(callback.from_user.id, callback.message.message_id)

        texts = get_user_texts(user_id)

        admin = DbUser.get(callback.from_user.id)
        chat = bot.get_chat(admin.user_id)
        admin = f'{admin.name} (<i>@{chat.username}</i>'

        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

        bot.send_message(user_id, texts['not_confirmed_task'].format(admin_name=admin,
                                                                     task_number=task.task_number),
                         parse_mode='HTML', reply_markup=reply)
    elif action == 'confirm_task':
        task_id = int(data.split(':')[2])
        task = Task.get(task_id)
        data = storage.get_data(callback.from_user.id)
        user_id, photo_id, invoice_id, result_text = data[f't{task_id}']

        task.task_status = 'completed'
        task.task_result_text = result_text
        if photo_id:
            result_photo = Photo.get(Photo.file_id == photo_id)
            task.task_result_photo = result_photo
        if invoice_id:
            invoice_photo = Photo.get(Photo.file_id == invoice_id)
            DbInvoice.create(photo=invoice_photo, responsible=DbUser.get(user_id), tie_task=task)
        task.end_by_worker = DbUser.get(user_id)
        task.deadline_date = datetime.now()
        task.save()

        send_confirmed_task(task)
        bot.answer_callback_query(callback.id, texts['confirmed_task'])
        remove_msg(callback.from_user.id, callback.message.message_id)


def admin_menu_reply(user_id):
    texts = get_user_texts(user_id)

    reply = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    reply.add(*map(lambda t: texts[t], ADMIN_MAIN_MENU))
    return reply


def super_admin_main_menu(user_id):
    texts = get_user_texts(user_id)

    reply = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    reply.add(*map(lambda t: texts[t], SUPER_ADMIN_MAIN_MENU))

    send_removing_message(user_id, texts['menu'], reply_markup=reply)
    remove_msgs(user_id, True)


def admin_main_menu(user_id):
    texts = get_user_texts(user_id)

    reply = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    reply.add(*map(lambda t: texts[t], ADMIN_MAIN_MENU))

    send_removing_message(user_id, texts['menu'], reply_markup=reply)
    remove_msgs(user_id, True)


def admin_menu(user_id):
    if user_id == Config.MAIN_ADMIN_ID:
        super_admin_main_menu(user_id)
    else:
        admin_main_menu(user_id)


@bot.message_handler(state='main_menu', func=is_admin)
def admin_main_menu_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    remove_msg(msg.from_user.id, msg.message_id)

    if msg.text == texts['users'] and is_super_admin(msg):
        query = DbUser.select().where(DbUser.user_id != msg.from_user.id)
        pager = EntityPager(msg.from_user.id, query, lambda e: str(e.name), lambda e: e.user_id, 'user')

        send_removing_message(msg.from_user.id, texts['users_menu'], reply_markup=pager())
        remove_msgs(msg.from_user.id, True)
        bot.set_state('users_menu', msg.from_user.id)
    elif msg.text == texts['tasks']:
        reply = InlineKeyboardMarkup(row_width=1)
        reply.add(InlineKeyboardButton(texts['make_new_task'], callback_data='make_new_task'))
        reply.add(InlineKeyboardButton(texts['list_tasks'], callback_data='list_tasks'))
        reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))
        send_removing_message(msg.from_user.id, texts['tasks_menu'], reply_markup=reply)
        remove_msgs(msg.from_user.id, True)
        bot.set_state('tasks_menu', msg.from_user.id)
    elif msg.text == texts['documents']:
        reply = InlineKeyboardMarkup(row_width=1)
        reply.add(InlineKeyboardButton(texts['tasks'], callback_data='doc_tasks'),
                  InlineKeyboardButton(texts['requests'], callback_data='doc_requests'),
                  InlineKeyboardButton(texts['invoices'], callback_data='doc_invoices'),
                  InlineKeyboardButton(texts['back'], callback_data='back'))
        send_removing_message(msg.from_user.id, texts['choose_doc_category'],
                              reply_markup=reply)
        remove_msgs(msg.from_user.id, True)
        bot.set_state('list_documents', msg.from_user.id)
    elif msg.text == texts['requests']:
        me = DbUser.get(msg.from_user.id)
        query = Request.select().where(Request.executor==me).order_by(-Request.date)
        pager = EntityPager(msg.from_user.id, query, lambda e: texts['actions'], lambda e: e.id, 'request_actions',
                            per_page=1)
        pager.first_page()
        try:
            entity = pager.get_current_entities()[0]
        except IndexError:
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

            send_removing_message(msg.from_user.id, texts['no_requests_db'], reply_markup=reply)
            remove_msgs(msg.from_user.id, True)
            bot.set_state('list_requests', msg.from_user.id)
            return

        date = entity.date.strftime('%H:%M %d.%m.%Y')
        by = f'{entity.added_by.name} (<i>@{bot.get_chat(entity.added_by.user_id).username}</i>)'

        text = texts['request_description'].format(request_number=entity.task_number,
                                                   request_text=entity.request_text,
                                                   request_by=by,
                                                   request_date=date)

        if entity.request_photo is None:
            send_removing_message(msg.from_user.id, text,
                                  reply_markup=pager(), parse_mode='HTML')
        else:
            send_removing_photo(msg.from_user.id, entity.request_photo.file_id, text,
                                reply_markup=pager(), parse_mode='HTML')
        remove_msgs(msg.from_user.id, True)
        bot.set_state('list_requests', msg.from_user.id)
    else:
        admin_menu(msg.from_user.id)


@bot.callback_query_handler(state='list_requests', func=is_admin)
def admin_list_requests_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    me = DbUser.get(callback.from_user.id)
    query = Request.select().where(Request.executor == me).order_by(-Request.date)
    pager = EntityPager(callback.from_user.id, query, lambda e: texts['actions'], lambda e: e.id, 'request_actions',
                        per_page=1)
    result = pager.handle_callback(callback)
    if result:
        if result == 'back':
            admin_menu(callback.from_user.id)
            bot.set_state('main_menu', callback.from_user.id)
        elif result.startswith('request_actions'):
            request_id = int(result.split(':')[1])
            request = Request.get(request_id)

            reply = InlineKeyboardMarkup(row_width=1)
            reply.add(InlineKeyboardButton(texts['cancel_request'], callback_data='request_cancel:' + str(request_id)),
                      InlineKeyboardButton(texts['complete_request'], callback_data='complete_request:' + str(request_id)),
                      InlineKeyboardButton(texts['back'], callback_data='back'))

            send_removing_message(callback.from_user.id, texts['choose_action'], reply_markup=reply)
            remove_msgs(callback.from_user.id, True)
            bot.set_state('request_actions', callback.from_user.id)
    else:
        entity = pager.get_current_entities()[0]

        date = entity.date.strftime('%H:%M %d.%m.%Y')
        by = f'{entity.added_by.name} (<i>@{bot.get_chat(entity.added_by.user_id).username}</i>)'

        text = texts['request_description'].format(request_number=entity.task_number,
                                                   request_text=entity.request_text,
                                                   request_by=by,
                                                   request_date=date)

        if entity.request_photo is None:
            send_removing_message(callback.from_user.id, text,
                                  reply_markup=pager(), parse_mode='HTML')
        else:
            send_removing_photo(callback.from_user.id, entity.request_photo.file_id, text,
                                reply_markup=pager(), parse_mode='HTML')
        remove_msgs(callback.from_user.id, True)


def send_request_canceled(request: Request):
    texts = get_texts(DEFAULT_LANGUAGE)

    date = request.date.strftime('%H:%M %d.%m.%Y')
    by = f'{request.added_by.name} (<i>@{bot.get_chat(request.added_by.user_id).username}</i>)'
    executor = f'{request.executor.name} (<i>@{bot.get_chat(request.executor.user_id).username}</i>)'

    text = texts['cancel_request_notify'].format(request_number=request.task_number,
                                                request_text=request.request_text,
                                                request_by=by,
                                                executor=executor,
                                                request_date=date)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

    if request.request_photo is not None:
        bot.send_photo(Config.GROUP_ID, request.request_photo.file_id, text, parse_mode='HTML')
        bot.send_photo(request.added_by.user_id, request.request_photo.file_id, text, parse_mode='HTML',
                       reply_markup=reply)
    else:
        bot.send_message(Config.GROUP_ID, text, parse_mode='HTML')
        bot.send_message(request.added_by.user_id, text, parse_mode='HTML',
                         reply_markup=reply)


@bot.callback_query_handler(state='request_actions', func=is_admin)
def admin_request_actions_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = callback.data
    if data == 'back':
        me = DbUser.get(callback.from_user.id)
        query = Request.select().where(Request.executor == me).order_by(-Request.date)
        if query.count() == 0:
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

            send_removing_message(callback.from_user.id, texts['no_requests_db'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('list_requests', callback.from_user.id)
        else:
            pager = EntityPager(callback.from_user.id, query, lambda e: texts['actions'], lambda e: e.id,
                                'request_actions',
                                per_page=1)
            entity = pager.get_current_entities()[0]

            date = entity.date.strftime('%H:%M %d.%m.%Y')
            by = f'{entity.added_by.name} (<i>@{bot.get_chat(entity.added_by.user_id).username}</i>)'

            text = texts['request_description'].format(request_number=entity.task_number,
                                                       request_text=entity.request_text,
                                                       request_by=by,
                                                       request_date=date)

            if entity.request_photo is None:
                send_removing_message(callback.from_user.id, text,
                                      reply_markup=pager(), parse_mode='HTML')
            else:
                send_removing_photo(callback.from_user.id, entity.request_photo.file_id, text,
                                    reply_markup=pager(), parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('list_requests', callback.from_user.id)
    elif data.startswith('request_cancel'):
        request_id = int(data.split(':')[1])
        request = Request.get(request_id)
        request.request_status = 'canceled'
        request.save()

        bot.answer_callback_query(callback.id, texts['request_canceled'])
        send_request_canceled(request)
        admin_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)
    elif data.startswith('complete_request'):
        request_id = int(data.split(':')[1])
        bot.update_data({'request_id': request_id}, callback.from_user.id)

        send_removing_message(callback.from_user.id, texts['request_result_enter_text'])
        remove_msgs(callback.from_user.id, True)
        bot.set_state('request_result_text', callback.from_user.id)


@bot.message_handler(state='request_result_text', func=is_admin)
def admin_result_text_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    text = msg.text
    remove_msg(msg.from_user.id, msg.message_id)

    bot.update_data({'request_text': text, 'request_photo': None}, msg.from_user.id)
    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
    send_removing_message(msg.from_user.id, texts['request_result_attach_photo'], reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    bot.set_state('request_result_photo', msg.from_user.id)


@bot.message_handler(state='request_result_photo', content_types=['photo'], func=is_admin)
def admin_result_photo_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    photo, _ = Photo.get_or_create(file_id=msg.photo[-1].file_id)
    photo.download_file(bot)

    bot.update_data({'request_photo': photo.file_id, 'request_invoice': None}, msg.from_user.id)
    remove_msg(msg.from_user.id, msg.message_id)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
    send_removing_message(msg.from_user.id, texts['request_result_attach_invoice_photo'], reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    bot.set_state('request_result_invoice', msg.from_user.id)


@bot.callback_query_handler(state='request_result_photo', func=is_admin)
def admin_result_photo_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'omit':
        bot.update_data({'request_invoice': None}, callback.from_user.id)

        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
        send_removing_message(callback.from_user.id, texts['request_result_attach_invoice_photo'], reply_markup=reply)
        remove_msgs(callback.from_user.id, True)
        bot.set_state('request_result_invoice', callback.from_user.id)


def send_complete_request(request: Request):
    texts = get_user_texts(request.executor.user_id)
    user = DbUser.get(request.executor.user_id)

    date = request.date.strftime('%H:%M %d.%m.%Y')
    by = f'{request.added_by.name} (<i>@{bot.get_chat(request.added_by.user_id).username}</i>)'
    executor = f'{request.executor.name} (<i>@{bot.get_chat(request.executor.user_id).username}</i>)'

    text = texts['confirmed_request_notify'].format(request_number=request.task_number,
                                                    result_text=request.request_result_text,
                                                    executor_name=executor,
                                                    request_date=date)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

    if request.request_result_photo is not None:
        bot.send_photo(Config.GROUP_ID, request.request_result_photo.file_id, text, parse_mode='HTML')
        bot.send_photo(request.added_by.user_id, request.request_result_photo.file_id, text, parse_mode='HTML',
                       reply_markup=reply)
    else:
        bot.send_message(Config.GROUP_ID, text, parse_mode='HTML')
        bot.send_message(request.added_by.user_id, text, parse_mode='HTML',
                         reply_markup=reply)

    query = Invoice.select().join(Request)
    if query.count() != 0:
        invoice = query.first()
        bot.send_photo(request.added_by.user_id, invoice.photo.file_id, texts['invoice_request_addition'],
                       parse_mode='HTML',
                       reply_markup=reply)


@bot.message_handler(state='request_result_invoice', content_types=['photo'], func=is_admin)
def admin_result_invoice_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    photo, _ = Photo.get_or_create(file_id=msg.photo[-1].file_id)
    photo.download_file(bot)

    bot.update_data({'request_invoice': photo.file_id}, msg.from_user.id)
    remove_msg(msg.from_user.id, msg.message_id)

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))
    bot.send_message(msg.from_user.id, texts['confirmed_request'], reply_markup=reply)

    data = storage.get_data(msg.from_user.id)
    request = Request.get(data['request_id'])
    request.request_result_text = data['request_text']
    request.date = datetime.now()
    if data['request_photo'] is not None:
        request.request_result_photo = Photo.get(Photo.file_id == data['request_photo'])
    request.save()

    if data['request_invoice'] is not None:
        Invoice.create(photo=Photo.get(Photo.file_id == data['request_invoice']),
                       responsible=DbUser.get(msg.from_user.id),
                       tie_request=request)

    send_complete_request(request)

    admin_menu(msg.from_user.id)
    bot.set_state('main_menu', msg.from_user.id)


@bot.callback_query_handler(state='request_result_invoice', func=is_admin)
def admin_result_invoice_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'omit':
        bot.answer_callback_query(callback.id, texts['confirmed_request'])

        data = storage.get_data(callback.from_user.id)
        request = Request.get(data['request_id'])
        request.request_result_text = data['request_text']
        request.date = datetime.now()
        if data['request_photo'] is not None:
            request.request_result_photo = Photo.get(Photo.file_id == data['request_photo'])
        request.save()

        if data['request_invoice'] is not None:
            Invoice.create(photo=Photo.get(Photo.file_id == data['request_invoice']),
                           responsible=DbUser.get(callback.from_user.id),
                           tie_request=request)

        send_complete_request(request)

        admin_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)


@bot.callback_query_handler(state='list_documents', func=is_admin)
def admin_documents_menu_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)
    data = callback.data

    if data == 'back':
        admin_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)
    elif data in ('doc_tasks', 'doc_requests', 'doc_invoices'):
        calendar = CalendarView(callback.from_user.id, need_back=True)

        send_removing_message(callback.from_user.id, texts['choose_doc_date'], reply_markup=calendar())
        remove_msgs(callback.from_user.id, True)

        bot.update_data(calendar.get_data(), callback.from_user.id)
        bot.update_data({'doc_type': data.split('_')[1]}, callback.from_user.id)
        bot.set_state('choose_doc_date', callback.from_user.id)


@bot.callback_query_handler(state='choose_doc_date', func=is_admin)
def admin_documents_calendar_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = storage.get_data(callback.from_user.id)
    calendar = CalendarView(callback.from_user.id, data['calendar_year'], data['calendar_month'], need_back=True)

    result = calendar.handle_callback(callback)
    bot.update_data(calendar.get_data(), callback.from_user.id)

    if result == 'answer_callback':
        bot.answer_callback_query(callback.id)
    elif result == 'redraw':
        bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=calendar())
        bot.answer_callback_query(callback.id)
    elif result == 'choose':
        c = calendar.get_data()
        date = datetime(c['calendar_year'], c['calendar_month'], c['calendar_day'], 0, 0)
        data = storage.get_data(callback.from_user.id)
        doctype = data['doc_type']

        if doctype == 'requests':
            query = Request.select().where(Request.request_result_photo.is_null(False),
                                           Request.date.between(date, date + timedelta(days=1)))
            bot.update_data({'date': [date.year, date.month, date.day]}, callback.from_user.id)
            if query.count() == 0:
                bot.answer_callback_query(callback.id, texts['no_doc_requests'])
            else:
                pager = EntityPager(callback.from_user.id, query, lambda e: e.task_number, lambda e: e.id,
                                    'request',
                                    per_page=1, no_element_button=True)
                pager.first_page()
                entity = pager.get_current_entities()[0]

                bot.send_photo(callback.from_user.id, entity.request_result_photo.file_id,
                               reply_markup=pager(), parse_mode='HTML')
                remove_msgs(callback.from_user.id, True)
                remove_msg(callback.from_user.id, callback.message.message_id)

                bot.set_state('list_requests_docs', callback.from_user.id)
        elif doctype == 'invoices':
            query = DbInvoice.select().where(DbInvoice.date.between(date, date + timedelta(days=1)))
            bot.update_data({'date': [date.year, date.month, date.day]}, callback.from_user.id)

            if query.count() == 0:
                bot.answer_callback_query(callback.id, texts['no_doc_invoices'])
            else:
                pager = EntityPager(callback.from_user.id, query, lambda e: e.id, lambda e: e.id,
                                    'invoice',
                                    per_page=1, no_element_button=True)
                pager.first_page()
                entity = pager.get_current_entities()[0]

                bot.send_photo(callback.from_user.id, entity.photo.file_id,
                               reply_markup=pager(), parse_mode='HTML')
                remove_msgs(callback.from_user.id, True)
                remove_msg(callback.from_user.id, callback.message.message_id)

                bot.set_state('list_invoices_docs', callback.from_user.id)
        elif doctype == 'tasks':
            query = TaskWorker.select().join(Task).where(Task.deadline_date.between(date, date + timedelta(days=1)),
                                                         Task.task_result_photo.is_null(False))
            bot.update_data({'date': [date.year, date.month, date.day]}, callback.from_user.id)

            pager = EntityPager(callback.from_user.id, query,
                                lambda e: e.worker.name, lambda e: e.worker.user_id, 'user')
            pager.first_page()
            bot.send_message(callback.from_user.id, texts['doc_tasks_choose_user'], reply_markup=pager(),
                             parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            remove_msg(callback.from_user.id, callback.message.message_id)
            bot.set_state('doc_tasks_choose_user', callback.from_user.id)
    elif result == 'back':
        reply = InlineKeyboardMarkup(row_width=1)
        reply.add(InlineKeyboardButton(texts['tasks'], callback_data='doc_tasks'),
                  InlineKeyboardButton(texts['requests'], callback_data='doc_requests'),
                  InlineKeyboardButton(texts['invoices'], callback_data='doc_invoices'),
                  InlineKeyboardButton(texts['back'], callback_data='back'))
        send_removing_message(callback.from_user.id, texts['choose_doc_category'],
                              reply_markup=reply)
        remove_msgs(callback.from_user.id, True)
        bot.set_state('list_documents', callback.from_user.id)


@bot.callback_query_handler(state='doc_tasks_choose_user', func=is_admin)
def admin_documents_tasks_user_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = storage.get_data(callback.from_user.id)
    date = datetime(*data['date'], 0, 0)

    query = TaskWorker.select().join(Task).where(Task.deadline_date.between(date, date + timedelta(days=1)),
                                                 Task.task_result_photo.is_null(False))
    pager = EntityPager(callback.from_user.id, query,
                        lambda e: e.name, lambda e: e.user_id, 'user')

    result = pager.handle_callback(callback)
    bot.answer_callback_query(callback.id)
    if result:
        if result == 'back':
            calendar = CalendarView(callback.from_user.id, date.year, date.month, need_back=True)

            send_removing_message(callback.from_user.id, texts['choose_doc_date'], reply_markup=calendar())
            remove_msgs(callback.from_user.id, True)
            remove_msg(callback.from_user.id, callback.message.message_id)

            bot.update_data(calendar.get_data(), callback.from_user.id)
            bot.set_state('choose_doc_date', callback.from_user.id)
        else:
            user_id = int(callback.data.split(':')[1])

            query = Task.select().join(TaskWorker).where(TaskWorker.worker_id == user_id,
                                                         Task.deadline_date.between(date, date + timedelta(days=1)),
                                                         Task.task_result_photo.is_null(False))

            pager = EntityPager(callback.from_user.id, query, lambda e: e.task_number, lambda e: e.id,
                                'task',
                                per_page=1, no_element_button=True)
            pager.first_page()
            entity = pager.get_current_entities()[0]

            bot.send_photo(callback.from_user.id, entity.task_result_photo.file_id,
                           reply_markup=pager(), parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            remove_msg(callback.from_user.id, callback.message.message_id)
            bot.update_data({'user_id': user_id}, callback.from_user.id)

            bot.set_state('list_tasks_docs', callback.from_user.id)
    else:
        try:  # May be not modified
            bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=pager())
        except ApiException:
            pass


@bot.callback_query_handler(state='list_requests_docs', func=is_admin)
def admin_list_requests_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = storage.get_data(callback.from_user.id)
    date = datetime(*data['date'], 0, 0)

    query = Request.select().where(Request.request_result_photo.is_null(False),
                                   Request.date.between(date, date + timedelta(days=1)))

    pager = EntityPager(callback.from_user.id, query, lambda e: e.task_number, lambda e: e.id,
                        'request',
                        per_page=1, no_element_button=True)

    result = pager.handle_callback(callback)
    bot.answer_callback_query(callback.id)
    if result:
        if result == 'back':
            calendar = CalendarView(callback.from_user.id, need_back=True)

            send_removing_message(callback.from_user.id, texts['choose_doc_date'], reply_markup=calendar())
            remove_msgs(callback.from_user.id, True)
            remove_msg(callback.from_user.id, callback.message.message_id)

            bot.update_data(calendar.get_data(), callback.from_user.id)
            bot.set_state('choose_doc_date', callback.from_user.id)
    else:
        try:  # May be not modified
            entity = pager.get_current_entities()[0]

            bot.send_photo(callback.from_user.id, entity.request_result_photo.file_id,
                           reply_markup=pager(), parse_mode='HTML')
            remove_msg(callback.from_user.id, callback.message.message_id)
            remove_msgs(callback.from_user.id, True)
        except ApiException:
            pass


@bot.callback_query_handler(state='list_invoices_docs', func=is_admin)
def admin_list_invoices_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = storage.get_data(callback.from_user.id)
    date = datetime(*data['date'], 0, 0)

    query = DbInvoice.select().where(DbInvoice.date.between(date, date + timedelta(days=1)))
    pager = EntityPager(callback.from_user.id, query, lambda e: e.id, lambda e: e.id,
                        'invoice',
                        per_page=1, no_element_button=True)

    result = pager.handle_callback(callback)
    bot.answer_callback_query(callback.id)
    if result:
        if result == 'back':
            calendar = CalendarView(callback.from_user.id, need_back=True)

            send_removing_message(callback.from_user.id, texts['choose_doc_date'], reply_markup=calendar())
            remove_msgs(callback.from_user.id, True)
            remove_msg(callback.from_user.id, callback.message.message_id)

            bot.update_data(calendar.get_data(), callback.from_user.id)
            bot.set_state('choose_doc_date', callback.from_user.id)
    else:
        try:  # May be not modified
            entity = pager.get_current_entities()[0]

            bot.send_photo(callback.from_user.id, entity.photo.file_id,
                           reply_markup=pager(), parse_mode='HTML')
            remove_msg(callback.from_user.id, callback.message.message_id)
            remove_msgs(callback.from_user.id, True)
        except ApiException:
            pass


@bot.callback_query_handler(state='list_tasks_docs', func=is_admin)
def admin_list_tasks_docs_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = storage.get_data(callback.from_user.id)
    user_id = int(data['user_id'])
    date = datetime(*data['date'], 0, 0)

    query = Task.select().join(TaskWorker).where(TaskWorker.worker_id == user_id,
                                                 Task.deadline_date.between(date, date + timedelta(days=1)),
                                                 Task.task_result_photo.is_null(False))
    pager = EntityPager(callback.from_user.id, query, lambda e: e.task_number, lambda e: e.id,
                        'task',
                        per_page=1, no_element_button=True)

    result = pager.handle_callback(callback)
    bot.answer_callback_query(callback.id)
    if result:
        if result == 'back':
            query = TaskWorker.select().join(Task).where(Task.deadline_date.between(date, date + timedelta(days=1)),
                                                         Task.task_result_photo.is_null(False))
            bot.update_data({'date': [date.year, date.month, date.day]}, callback.from_user.id)

            pager = EntityPager(callback.from_user.id, query,
                                lambda e: e.worker.name, lambda e: e.worker.user_id, 'user')
            bot.send_message(callback.from_user.id, texts['doc_tasks_choose_user'], reply_markup=pager(),
                             parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            remove_msg(callback.from_user.id, callback.message.message_id)

            bot.set_state('doc_tasks_choose_user', callback.from_user.id)
    else:
        try:  # May be not modified
            entity = pager.get_current_entities()[0]

            bot.send_photo(callback.from_user.id, entity.task_result_photo.file_id,
                           reply_markup=pager(), parse_mode='HTML')
            remove_msg(callback.from_user.id, callback.message.message_id)
            remove_msgs(callback.from_user.id, True)
        except ApiException:
            pass


@bot.callback_query_handler(state='tasks_menu', func=is_admin)
def admin_tasks_menu_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = callback.data
    if data == 'back':
        admin_menu(callback.from_user.id)
        bot.set_state('main_menu', callback.from_user.id)
    elif data == 'make_new_task':
        send_removing_message(callback.from_user.id, texts['new_task_enter_text'])
        remove_msgs(callback.from_user.id, True)
        bot.set_state('new_task_text', callback.from_user.id)
    elif data == 'list_tasks':
        query = Task.select().order_by(-Task.end_date)
        pager = EntityPager(callback.from_user.id, query, lambda e: texts['actions'], lambda e: e.id, 'task_actions',
                            per_page=1)
        pager.first_page()
        try:
            entity = pager.get_current_entities()[0]
        except IndexError:
            bot.answer_callback_query(callback.id, texts['no_tasks_db'])
            return

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


@bot.callback_query_handler(state='list_tasks', func=is_admin)
def admin_list_tasks_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    query = Task.select().order_by(-Task.end_date)
    pager = EntityPager(callback.from_user.id, query, lambda e: texts['actions'], lambda e: e.id, 'task_actions',
                        per_page=1)
    result = pager.handle_callback(callback)
    if result:
        if result == 'back':
            reply = InlineKeyboardMarkup(row_width=1)
            reply.add(InlineKeyboardButton(texts['make_new_task'], callback_data='make_new_task'))
            reply.add(InlineKeyboardButton(texts['list_tasks'], callback_data='list_tasks'))
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))
            send_removing_message(callback.from_user.id, texts['tasks_menu'], reply_markup=reply)
            remove_msgs(callback.from_user.id, True)
            bot.set_state('tasks_menu', callback.from_user.id)
        else:
            pass
    else:
        entity = pager.get_current_entities()[0]

        date = entity.end_date.strftime('%H:%M %d.%m.%Y')
        deadline_date = entity.deadline_date.strftime('%H:%M %d.%m.%Y')
        if entity.task_status == 'completed':
            text = texts['task_description_completed'].format(task_number=entity.task_number,
                                                              task_text=entity.task_text,
                                                              task_end_date=date,
                                                              task_status=texts[entity.task_status],
                                                              task_end_by=entity.end_by_worker.name,
                                                              task_deadline_date=deadline_date)
        else:
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


@bot.message_handler(state='new_task_text', func=is_admin)
def admin_new_task_text_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    task_text = msg.text
    remove_msg(msg.from_user.id, msg.message_id)
    bot.update_data({'task_text': task_text}, msg.from_user.id)
    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['omit'], callback_data='omit'))
    send_removing_message(msg.from_user.id, texts['new_task_attach_photo'], reply_markup=reply)
    remove_msgs(msg.from_user.id, True)
    bot.set_state('new_task_photo', msg.from_user.id)


@bot.message_handler(state='new_task_photo', content_types=['photo'], func=is_admin)
def admin_new_task_photo_handler(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    photo, _ = Photo.get_or_create(file_id=msg.photo[-1].file_id)
    photo.download_file(bot)

    bot.update_data({'task_photo': photo.file_id, 'task_workers': []}, msg.from_user.id)
    remove_msg(msg.from_user.id, msg.message_id)

    calendar = CalendarView(msg.from_user.id, need_back=False)

    send_removing_message(msg.from_user.id, texts['new_task_choose_end_date'], reply_markup=calendar())
    remove_msgs(msg.from_user.id, True)

    bot.update_data(calendar.get_data(), msg.from_user.id)
    bot.set_state('new_task_end_date', msg.from_user.id)


@bot.callback_query_handler(state='new_task_photo', func=is_admin)
def admin_new_task_photo_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'omit':
        bot.update_data({'task_photo': None, 'task_workers': []}, callback.from_user.id)

        calendar = CalendarView(callback.from_user.id, need_back=False)

        send_removing_message(callback.from_user.id, texts['new_task_choose_end_date'], reply_markup=calendar())
        remove_msgs(callback.from_user.id, True)

        bot.update_data(calendar.get_data(), callback.from_user.id)
        bot.set_state('new_task_end_date', callback.from_user.id)


@bot.callback_query_handler(state='new_task_end_date', func=is_admin)
def admin_new_task_end_data(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = storage.get_data(callback.from_user.id)
    calendar = CalendarView(callback.from_user.id, data['calendar_year'], data['calendar_month'], need_back=False)

    result = calendar.handle_callback(callback)
    bot.update_data(calendar.get_data(), callback.from_user.id)

    if result == 'answer_callback':
        bot.answer_callback_query(callback.id)
    elif result == 'redraw':
        bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=calendar())
        bot.answer_callback_query(callback.id)
    elif result == 'choose':
        date = calendar.get_datetime()
        if date < datetime.now() - timedelta(days=1):
            bot.answer_callback_query(callback.id, texts['incorrect_past_date'])
        else:
            send_removing_message(callback.from_user.id, texts['new_task_write_end_time'],
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('new_task_end_time', callback.from_user.id)


@bot.message_handler(state='new_task_end_time', func=is_admin)
def admin_new_task_end_time(msg: Message):
    texts = get_user_texts(msg.from_user.id)

    text = msg.text
    remove_msg(msg.from_user.id, msg.message_id)

    try:
        hour, minute = text.split(':')
        hour, minute = int(hour), int(minute)
    except:
        send_removing_message(msg.from_user.id, texts['incorrect_time_entered'])
        remove_msgs(msg.from_user.id, True)
    else:
        if (0 > hour or hour > 23) or (0 > minute or minute > 59):
            send_removing_message(msg.from_user.id, texts['incorrect_time_entered'])
            remove_msgs(msg.from_user.id, True)
        else:
            data = storage.get_data(msg.from_user.id)
            date = datetime(data['calendar_year'], data['calendar_month'], data['calendar_day'],
                            hour, minute, 0)
            if date <= datetime.now() + timedelta(minutes=15):
                send_removing_message(msg.from_user.id, texts['incorrect_time_entered'])
                remove_msgs(msg.from_user.id, True)
                return

            bot.update_data({'calendar_hour': hour, 'calendar_minute': minute}, msg.from_user.id)

            reply = InlineKeyboardMarkup(row_width=1)
            reply.add(InlineKeyboardButton(texts['new_task_add_worker'], callback_data='add_worker'))
            reply.add(InlineKeyboardButton(texts['new_task_add_task'], callback_data='add_task'))

            send_removing_message(msg.from_user.id, texts['new_task_add_workers'], reply_markup=reply)
            remove_msgs(msg.from_user.id, True)
            bot.set_state('new_task_add_worker', msg.from_user.id)


def send_cancel_task_notify(task: Task):
    texts = get_texts(DEFAULT_LANGUAGE)

    date = task.end_date.strftime('%H:%M %d.%m.%Y')
    text = texts['cancel_task_notify'].format(task_number=task.task_number,
                                              added_by=task.added_by.name, task_text=task.task_text,
                                              end_date=date) + '\n'
    task_workers = TaskWorker.select().where(TaskWorker.task == task)

    i = 1
    for worker in task_workers:
        user = worker.worker
        chat = bot.get_chat(user.user_id)
        text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
        i += 1

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

    if task.task_photo is not None:
        bot.send_photo(Config.GROUP_ID, task.task_photo.file_id, text, parse_mode='HTML')
        for worker in task_workers:
            bot.send_photo(worker.worker.user_id, task.task_photo.file_id, text, parse_mode='HTML',
                           reply_markup=reply)
    else:
        bot.send_message(Config.GROUP_ID, text, parse_mode='HTML')
        for worker in task_workers:
            bot.send_message(worker.worker.user_id, text, parse_mode='HTML',
                             reply_markup=reply)


def send_task_notify(task: Task):
    texts = get_texts(DEFAULT_LANGUAGE)

    date = task.end_date.strftime('%H:%M %d.%m.%Y')
    text = texts['new_task_notify_group'].format(task_number=task.task_number,
                                                 added_by=task.added_by.name, task_text=task.task_text,
                                                 end_date=date) + '\n'
    task_workers = TaskWorker.select().where(TaskWorker.task == task)

    i = 1
    for worker in task_workers:
        user = worker.worker
        chat = bot.get_chat(user.user_id)
        text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
        i += 1

    reply = InlineKeyboardMarkup()
    reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

    if task.task_photo is not None:
        bot.send_photo(Config.GROUP_ID, task.task_photo.file_id, text, parse_mode='HTML')
        for worker in task_workers:
            bot.send_photo(worker.worker.user_id, task.task_photo.file_id, text, parse_mode='HTML',
                           reply_markup=reply)
    else:
        bot.send_message(Config.GROUP_ID, text, parse_mode='HTML')
        for worker in task_workers:
            bot.send_message(worker.worker.user_id, text, parse_mode='HTML',
                             reply_markup=reply)


@bot.callback_query_handler(state='new_task_add_worker', func=is_admin)
def admin_new_task_add_worker(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'add_task':
        data = storage.get_data(callback.from_user.id)
        if len(data['task_workers']) <= 0:
            bot.answer_callback_query(callback.id, texts['new_task_no_workers'])
        else:
            date = datetime(data['calendar_year'], data['calendar_month'], data['calendar_day'],
                            data['calendar_hour'], data['calendar_minute'], 0)
            task = Task.create(added_by=DbUser.get(callback.from_user.id), task_text=data['task_text'],
                               end_date=date)
            if data['task_photo'] is not None:
                task.task_photo = Photo.get(file_id=data['task_photo'])
                task.save()

            for worker in data['task_workers']:
                TaskWorker.create(task=task, worker=DbUser.get(worker))

            bot.answer_callback_query(callback.id, texts['created_task'])
            send_task_notify(task)
            admin_menu(callback.from_user.id)
            bot.set_state('main_menu', callback.from_user.id)
    elif callback.data == 'add_worker':
        query = DbUser.select().where(DbUser.role == 'worker')
        pager = EntityPager(callback.from_user.id, query,
                            lambda e: e.name, lambda e: e.user_id, 'user')
        pager.first_page()
        send_removing_message(callback.from_user.id, texts['choose_worker'], reply_markup=pager())
        remove_msgs(callback.from_user.id, True)
        bot.set_state('new_task_choose_worker', callback.from_user.id)


@bot.callback_query_handler(state='new_task_choose_worker', func=is_admin)
def admin_new_task_choose_worker(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    query = DbUser.select().where(DbUser.role == 'worker')
    pager = EntityPager(callback.from_user.id, query,
                        lambda e: e.name, lambda e: e.user_id, 'user')
    result = pager.handle_callback(callback)
    if result:
        if result == 'back':
            reply = InlineKeyboardMarkup(row_width=1)
            reply.add(InlineKeyboardButton(texts['new_task_add_worker'], callback_data='add_worker'))
            reply.add(InlineKeyboardButton(texts['new_task_add_task'], callback_data='add_task'))

            text = texts['new_task_workers'] + '\n'
            workers = storage.get_data(callback.from_user.id)['task_workers']

            i = 1
            for worker in workers:
                user = DbUser.get(worker)
                chat = bot.get_chat(worker)
                text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
                i += 1

            send_removing_message(callback.from_user.id, text, reply_markup=reply, parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('new_task_add_worker', callback.from_user.id)
        else:
            user_id = int(callback.data.split(':')[1])
            data = storage.get_data(callback.from_user.id)['task_workers']
            data.append(user_id)
            bot.update_data({'task_workers': data}, callback.from_user.id)

            reply = InlineKeyboardMarkup(row_width=1)
            reply.add(InlineKeyboardButton(texts['new_task_add_worker'], callback_data='add_worker'))
            reply.add(InlineKeyboardButton(texts['new_task_add_task'], callback_data='add_task'))

            text = texts['new_task_workers'] + '\n'
            workers = storage.get_data(callback.from_user.id)['task_workers']

            i = 1
            for worker in workers:
                user = DbUser.get(worker)
                chat = bot.get_chat(worker)
                text += str(i) + ') <b>' + user.name + '</b> (<i>@' + chat.username + '</i>).\n'
                i += 1

            send_removing_message(callback.from_user.id, text, reply_markup=reply, parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('new_task_add_worker', callback.from_user.id)
    else:
        try:  # May be not modified
            bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=pager())
        except ApiException:
            pass


@bot.callback_query_handler(state='users_menu', func=is_super_admin)
def super_admin_users_menu_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = callback.data
    query = DbUser.select().where(DbUser.user_id != callback.from_user.id)
    pager = EntityPager(callback.from_user.id, query, lambda e: str(e.name), lambda e: e.user_id, 'user')
    result = pager.handle_callback(callback)
    if result:
        if result == 'back':
            super_admin_main_menu(callback.from_user.id)
            remove_msgs(callback.from_user.id, True)
            bot.set_state('main_menu', callback.from_user.id)
            pager.first_page()
        else:
            user = int(data.split(':')[1])
            user_entity = DbUser.get(user)

            bot.update_data({'selected': user}, callback.from_user.id)
            reply = InlineKeyboardMarkup(row_width=1)
            if user_entity.role == 'worker':
                reply.add(InlineKeyboardButton(texts['user_menu_make_admin'], callback_data='make_admin'))
            else:
                reply.add(InlineKeyboardButton(texts['user_menu_make_worker'], callback_data='make_worker'))
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

            username = bot.get_chat(user).username
            send_removing_message(callback.from_user.id,
                                  texts['user_menu_entity'].format(name=user_entity.name,
                                                                   username=username,
                                                                   role=texts[user_entity.role]),
                                  reply_markup=reply, parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('users_menu_entity', callback.from_user.id)
    else:
        try:  # May be not modified
            bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=pager())
        except ApiException:
            pass


@bot.callback_query_handler(state='users_menu_entity', func=is_super_admin)
def user_menu_entity_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = callback.data
    if data == 'make_admin':
        d = storage.get_data(callback.from_user.id)
        user = DbUser.get(d['selected'])
        if TaskWorker.select().where(TaskWorker.worker == user).exists():
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))
            send_removing_message(callback.from_user.id, texts['still_have_tasks'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('change_role_menu', callback.from_user.id)
        else:
            user.role = 'admin'
            user.save()
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))
            send_removing_message(callback.from_user.id, texts['successful_make_admin'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('change_role_menu', callback.from_user.id)
    elif data == 'make_worker':
        d = storage.get_data(callback.from_user.id)
        user = DbUser.get(d['selected'])
        if Request.select().where(Request.executor == user).exists():
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))
            send_removing_message(callback.from_user.id, texts['still_have_requests'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('change_role_menu', callback.from_user.id)
        else:
            user.role = 'worker'
            user.save()
            reply = InlineKeyboardMarkup()
            reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))
            send_removing_message(callback.from_user.id, texts['successful_make_worker'], reply_markup=reply,
                                  parse_mode='HTML')
            remove_msgs(callback.from_user.id, True)
            bot.set_state('change_role_menu', callback.from_user.id)
    elif data == 'back':
        query = DbUser.select().where(DbUser.user_id != callback.from_user.id)
        pager = EntityPager(callback.from_user.id, query, lambda e: str(e.name), lambda e: e.user_id, 'user')

        send_removing_message(callback.from_user.id, texts['users_menu'], reply_markup=pager())
        remove_msgs(callback.from_user.id, True)
        bot.set_state('users_menu', callback.from_user.id)


@bot.callback_query_handler(state='change_role_menu', func=is_super_admin)
def change_role_menu_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    if callback.data == 'back':
        data = storage.get_data(callback.from_user.id)
        user = data['selected']
        user_entity = DbUser.get(user)

        bot.update_data({'selected': user}, callback.from_user.id)
        reply = InlineKeyboardMarkup(row_width=1)
        if user_entity.role == 'worker':
            reply.add(InlineKeyboardButton(texts['user_menu_make_admin'], callback_data='make_admin'))
        else:
            reply.add(InlineKeyboardButton(texts['user_menu_make_worker'], callback_data='make_worker'))
        reply.add(InlineKeyboardButton(texts['back'], callback_data='back'))

        username = bot.get_chat(user).username
        send_removing_message(callback.from_user.id,
                              texts['user_menu_entity'].format(name=user_entity.name,
                                                               username=username,
                                                               role=texts[user_entity.role]),
                              reply_markup=reply, parse_mode='HTML')
        remove_msgs(callback.from_user.id, True)
        bot.set_state('users_menu_entity', callback.from_user.id)


@bot.callback_query_handler(func=is_super_admin)
def super_admin_callback_handler(callback: CallbackQuery):
    texts = get_user_texts(callback.from_user.id)

    data = callback.data
    add_data = None
    if ':' in data:
        add_data = data.split(':')[-1]
        data = data.split(':')[0]

    try:
        request_data = storage.get_data(int(add_data))
    except:
        return

    if data == 'add_request_decline':
        remove_msg(callback.from_user.id, callback.message.id)
        send_removing_message(int(add_data), texts['user_request_declined'])
        remove_msgs(int(add_data), True)
        bot.answer_callback_query(callback.id, texts['user_declined'])
    elif data == 'add_request_worker':
        remove_msg(callback.from_user.id, callback.message.id)
        send_removing_message(int(add_data), texts['user_request_worker'],
                              reply_markup=worker_menu_reply(int(add_data)))
        bot.set_state('main_menu', int(add_data))

        remove_msgs(int(add_data), True)
        bot.answer_callback_query(callback.id, texts['user_worker'])

        DbUser.create(user_id=int(add_data), role='worker', language=DEFAULT_LANGUAGE, name=request_data['name'])
    elif data == 'add_request_admin':
        remove_msg(callback.from_user.id, callback.message.id)
        send_removing_message(int(add_data), texts['user_request_admin'], reply_markup=admin_menu_reply(int(add_data)))
        bot.set_state('main_menu', int(add_data))

        remove_msgs(int(add_data), True)
        bot.answer_callback_query(callback.id, texts['user_admin'])

        DbUser.create(user_id=int(add_data), role='admin', language=DEFAULT_LANGUAGE, name=request_data['name'])


@bot.message_handler(func=is_admin)
def admin_message_handler(msg: Message):
    remove_msg(msg.from_user.id, msg.message_id)
    admin_menu(msg.from_user.id)
    bot.set_state('main_menu', msg.from_user.id)

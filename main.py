import traceback
from datetime import datetime, timedelta
from threading import Thread

import handlers.admin_handlers
import handlers.entry_handlers
import handlers.worker_handlers
from threading import Thread

from common.models import TaskNotify, TaskWorker
from texts import get_texts, DEFAULT_LANGUAGE

from bot import *


class Notifier(Thread):
    def __init__(self):
        self._run = True
        super().__init__()

    def run(self):
        while self._run:
            now = datetime.now()

            notifies = TaskNotify.select().where(TaskNotify.notify_date <= now)
            for notify in notifies:
                if notify.task.task_status in ('completed', 'canceled'):
                    notify.delete_instance()
                    continue
                self.send_notify(notify, bot)
                notify.delete_instance()

    def stop(self):
        self._run = False

    def send_notify(self, notify: TaskNotify, bot):
        if notify.task.task_photo is None:
            bot.send_message(Config.GROUP_ID, notify.notify_text, parse_mode='HTML')
        else:
            bot.send_photo(Config.GROUP_ID, notify.task.task_photo.file_id, notify.notify_text, parse_mode='HTML')

        task_workers = TaskWorker.select().where(TaskWorker.task == notify.task)

        texts = get_texts(DEFAULT_LANGUAGE)
        reply = InlineKeyboardMarkup()
        reply.add(InlineKeyboardButton(texts['close_notify'], callback_data='notify_close'))

        for task_worker in task_workers:
            if notify.task.task_photo is None:
                bot.send_message(task_worker.worker.user_id, notify.notify_text, parse_mode='HTML', reply_markup=reply)
            else:
                bot.send_photo(task_worker.worker.user_id, notify.task.task_photo.file_id, notify.notify_text, parse_mode='HTML',
                               reply_markup=reply)


def main():
    while True:
        try:
            notifier = Notifier()
            notifier.start()
            bot.polling(none_stop=True)
        except:
            print(traceback.format_exc())
        finally:
            notifier.stop()


if __name__ == '__main__':
    main()

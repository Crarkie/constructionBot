from threading import Thread

import handlers.admin_handlers
import handlers.entry_handlers
import handlers.worker_handlers
from bot import *

while True:
    try:
        bot.polling(none_stop=True)
    except:
        pass

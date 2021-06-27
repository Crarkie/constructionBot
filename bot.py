from fsm_telebot.storage.memory import MemoryStorage
from telebot.types import *
from telebot.apihelper import ApiException

from common.models import db
from common.postgres_storage import PostgresStorage
from config import Config
import fsm_telebot
import re
from telebot import apihelper


def _test_filter_fixed(self, filter, filter_value, message):
    test_cases = {
        'state': lambda msg: self.storage.get_state(msg.from_user.id, default='') == filter_value,
        'content_types': lambda msg: msg.content_type in filter_value,
        'regexp': lambda msg: msg.content_type == 'text' and re.search(filter_value, msg.text, re.IGNORECASE),
        'commands': lambda msg: msg.content_type == 'text' and util.extract_command(msg.text) in filter_value,
        'func': lambda msg: filter_value(msg)
    }

    return test_cases.get(filter, lambda msg: False)(message)


storage = PostgresStorage()
fsm_telebot.TeleBot._test_filter = _test_filter_fixed
bot = fsm_telebot.TeleBot(Config.TOKEN, storage=storage)
setattr(db, 'bot', bot)

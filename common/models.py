import os
import time

import requests
import telebot.apihelper
from playhouse.postgres_ext import PostgresqlExtDatabase
from telebot import TeleBot
from peewee import *
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from datetime import datetime
from typing import Tuple as TupleType

db = PostgresqlExtDatabase(Config.DB_DATABASE,
                           user=Config.DB_USER,
                           password=Config.DB_PASSWORD,
                           host='localhost',
                           port=5432)


class BaseModel(Model):
    class Meta:
        database = db
        legacy_table_names = False


class Photo(BaseModel):
    file_id = CharField(max_length=256, primary_key=True)
    date = DateTimeField(default=datetime.now)

    def _get_base_dir(self):
        return f'files/'

    def _get_relative_path(self):
        return os.path.join(self._get_base_dir(), str(self.date.year), str(self.date.month), str(self.date.day),
                            str(self.file_id) + '.jpg')

    def get_photo_file(self):
        return open(self._get_relative_path(), 'rb')

    def download_file(self, bot: TeleBot):
        if not os.path.exists(self._get_relative_path()):
            file = bot.get_file(self.file_id)
            content = bot.download_file(file.file_path)

            os.makedirs(os.path.split(self._get_relative_path())[0], exist_ok=True)  # make sure path exists
            with open(self._get_relative_path(), 'wb') as photo_file:
                photo_file.write(content)

    @classmethod
    def create(cls, **query):
        photo: Photo = super().create(**query)
        photo.download_file(db.bot)
        return photo


def default_name():
    return 'No name.'


def default_role():
    return 'worker'


class User(BaseModel):
    user_id = BigIntegerField(primary_key=True)
    role = CharField(max_length=32, default='worker')
    language = CharField(default='ru')
    name = CharField(max_length=128, default=default_name)


def default_task_text():
    return 'Нет описания.'


def task_states():
    return (
        'initiated',
        'canceled',
        'wait_approval'
        'completed'
    )


def request_states():
    return (
        'initiated'
        'canceled',
        'completed'
    )


def begin_task_state():
    return 'initiated'


def begin_request_state():
    return 'initiated'


def get_task_number():
    now = datetime.now().strftime('_%d_%m_%Y')
    return str(int(time.time()))[-4:] + now


class Task(BaseModel):
    task_number = CharField(unique=True, default=get_task_number)
    added_by = ForeignKeyField(User)
    end_date = DateTimeField(default=None, null=True)
    created_at = DateTimeField(default=datetime.now)
    deadline_date = DateTimeField(default=None, null=True)
    task_text = TextField(default=default_task_text)
    task_photo = ForeignKeyField(Photo, null=True, default=None)
    end_by_worker = ForeignKeyField(User, null=True, default=None)
    task_result_photo = ForeignKeyField(Photo, null=True, default=None)
    task_result_text = TextField(null=True, default=None)
    task_status = CharField(max_length=32, default=begin_task_state)


class TaskNotify(BaseModel):
    task = ForeignKeyField(Task, backref='notifies', on_delete='CASCADE')
    notify_date = DateTimeField()
    notify_text = TextField()


class TaskWorker(BaseModel):
    task = ForeignKeyField(Task, backref='workers', on_delete='CASCADE')
    worker = ForeignKeyField(User)


class Request(BaseModel):
    task_number = CharField(unique=True, default=get_task_number)
    added_by = ForeignKeyField(User)
    request_text = TextField(default=default_task_text)
    request_photo = ForeignKeyField(Photo, null=True, default=None)
    date = DateTimeField(default=datetime.now)
    request_result_photo = ForeignKeyField(Photo, null=True, default=None)
    request_result_text = TextField(null=True, default=None)
    request_status = CharField(max_length=32, default=begin_request_state)
    executor = ForeignKeyField(User)


class Invoice(BaseModel):
    photo = ForeignKeyField(Photo)
    date = DateTimeField(default=datetime.now)
    responsible = ForeignKeyField(User)
    tie_task = ForeignKeyField(Task, null=True, default=None)
    tie_request = ForeignKeyField(Request, null=True, default=None)

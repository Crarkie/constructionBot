import typing

from fsm_telebot import BaseStorage

from .models import *
from playhouse.postgres_ext import BinaryJSONField


class UserState(BaseModel):
    chat_user_id = CharField(max_length=64, primary_key=True)
    state = CharField(max_length=128, null=True, default=None)
    data = BinaryJSONField(default={})


class PostgresStorage(BaseStorage):
    """
    Storage based on PostgreSQL
    """

    def get_state(self, chat: typing.Union[int, str, None] = None, user: typing.Union[int, str, None] = None,
                  default: typing.Optional[str] = None) -> typing.Union[str]:
        chat, user = self.check_address(chat, user)
        state = UserState.get_or_none(chat_user_id=f'{chat}_{user}')
        return state.state if state else default

    def get_data(self, chat: typing.Union[int, str, None] = None, user: typing.Union[int, str, None] = None,
                 default: typing.Optional[str] = None) -> typing.Dict:
        chat, user = self.check_address(chat, user)
        state = UserState.get_or_none(chat_user_id=f'{chat}_{user}')
        return state.data if state else default

    def set_state(self, chat: typing.Union[int, str, None] = None, user: typing.Union[int, str, None] = None,
                  state: typing.Optional[typing.AnyStr] = None):
        chat, user = self.check_address(chat, user)
        user_state = UserState.get_or_none(chat_user_id=f'{chat}_{user}')
        if user_state:
            user_state.state = state
            user_state.save()
        else:
            UserState.create(chat_user_id=f'{chat}_{user}', state=state)

    def set_data(self, chat: typing.Union[int, str, None] = None, user: typing.Union[int, str, None] = None,
                 data: typing.Dict = None):
        chat, user = self.check_address(chat, user)
        user_state = UserState.get_or_none(chat_user_id=f'{chat}_{user}')
        if user_state:
            user_state.data = data
            user_state.save()
        else:
            UserState.create(chat_user_id=f'{chat}_{user}', data=data)

    def update_data(self, chat: typing.Union[int, str, None] = None, user: typing.Union[int, str, None] = None,
                    data: typing.Dict = None):
        chat, user = self.check_address(chat, user)
        user_state = UserState.get_or_none(chat_user_id=f'{chat}_{user}')
        if user_state:
            user_state.data.update(data)
            user_state.save()
        else:
            UserState.create(chat_user_id=f'{chat}_{user}', data=data)

    def close(self):
        pass

    def __init__(self):
        self._initialize()

    def _initialize(self):
        """
        Initialize DB and table
        :return:
        """
        db.create_tables([UserState])

from typing import Optional, List

from bot import *
from common.tg_utils import *
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass


@dataclass
class CallbackButtonInfo:
    text: str
    callback_data: str

    def to_inline_callback_button(self):
        """
        Construct InlineKeyboardButton from object info
        :return:
        """
        return InlineKeyboardButton(self.text, callback_data=self.callback_data)


class NoBottomButtonsMixin:

    def _bottom_buttons(self, reply_markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
        return reply_markup

    def _handle_bottom_buttons(self):
        return None


class BackBottomButtonsMixin:
    _prev_str = '◀'
    _next_str = '▶'
    _empty_str = ' '
    _back_str = '↩️'

    def _bottom_buttons(self, reply_markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
        """
        Add a row of bottom buttons if have
        """
        buttons = [InlineKeyboardButton(self._empty_str, callback_data='empty'),
                   InlineKeyboardButton(self._back_str, callback_data='back'),
                   InlineKeyboardButton(self._empty_str, callback_data='empty')]

        if self._have_prev_page():
            buttons[0] = InlineKeyboardButton(self._prev_str, callback_data='prev')
        if self._have_next_page():
            buttons[2] = InlineKeyboardButton(self._next_str, callback_data='next')

        reply_markup.row(*buttons)
        return reply_markup

    def _handle_bottom_buttons(self, callback: CallbackQuery) -> Optional[str]:
        """
        Handle row of bottom buttons
        :param callback: CallbackQuery
        :return: handled result or None
        """
        data = callback.data

        if data == 'prev':
            bot.answer_callback_query(callback.id)
            self._prev_page()
        elif data == 'next':
            bot.answer_callback_query(callback.id)
            self._next_page()

        if data == 'back':
            bot.answer_callback_query(callback.id)
            return 'back'

        return None


class InlineKeyboardPager(metaclass=ABCMeta):
    _prev_str = '◀'
    _next_str = '▶'
    _empty_str = ' '

    def __init__(self, user_id: int, row_width: int = 1, no_element_button=False):
        self._user_id = user_id
        self._row_width = row_width
        self._no_element_button = no_element_button

        self._page = 0
        self._load_page()

    def _save_page(self):
        """
        Save current page to storage
        """
        storage.update_data(self._user_id, data={'page': self._page})

    def _load_page(self):
        """
        Load current page from storage
        """
        self._page = storage.get_data(self._user_id, default={}).get('page', 0)

    @property
    @abstractmethod
    def _page_size(self) -> int:
        """
        Return page size
        :return: page size
        """
        pass

    def first_page(self):
        """
        Set first page
        """
        self._page = 0
        self._save_page()

    def last_page(self):
        """
        Set last page
        """
        self._page = self._list_len() // self._page_size - 1
        if self._list_len() % self._page_size != 0:
            self._page += 1
        self._save_page()

    @abstractmethod
    def _is_element_prefix(self, data: str) -> bool:
        """
        Is data string element's callback prefix?
        :param data: Callback data
        :return: True if data is element prefix else False
        """
        pass

    @abstractmethod
    def _list_len(self) -> int:
        """
        Return count of all elements
        """
        pass

    @abstractmethod
    def _get_callback_info(self, index: int) -> CallbackButtonInfo:
        """
        Return info for callback button for element at index
        :param index: index of element
        :return: dataclass[text, callback_data]
        """
        pass

    def _have_next_page(self) -> bool:
        """
        Have next page?
        :return: True if have next page else False
        """
        return self._list_len() > (self._page + 1) * self._page_size

    def _have_prev_page(self) -> bool:
        """
        Have previous page?
        :return:  True if have previous page else False
        """
        return self._page > 0

    def _next_page(self):
        """
        Switch to next page if have elements
        """
        if self._have_next_page():
            self._page += 1
            self._save_page()

    def _prev_page(self):
        """
        Switch to previous page if current page is not the start page
        """
        if self._have_prev_page():
            self._page -= 1
            self._save_page()

    def _bottom_buttons(self, reply_markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
        """
        Add a row of bottom buttons if have
        """
        buttons = [InlineKeyboardButton(self._empty_str, callback_data='empty'),
                   InlineKeyboardButton(self._empty_str, callback_data='empty')]
        if self._have_prev_page():
            buttons[0] = InlineKeyboardButton(self._prev_str, callback_data='prev')
        if self._have_next_page():
            buttons[1] = InlineKeyboardButton(self._next_str, callback_data='next')

        reply_markup.row(*buttons)
        return reply_markup

    def _handle_bottom_buttons(self, callback: CallbackQuery) -> Optional[str]:
        """
        Handle row of bottom buttons
        :param callback: CallbackQuery
        :return: handled result or None
        """
        data = callback.data

        if data == 'prev':
            bot.answer_callback_query(callback.id)
            self._prev_page()
        elif data == 'next':
            bot.answer_callback_query(callback.id)
            self._next_page()

        return None

    def handle_callback(self, callback: CallbackQuery, processed_answer_callback: bool = True) -> Optional[str]:
        """
        Handle callback for pager
        :param callback: CallbackQuery
        :param processed_answer_callback: call answer_callback_query on success handle element?
        :return: result or None
        """
        result = self._handle_bottom_buttons(callback)
        if not result:
            if self._is_element_prefix(callback.data):
                if processed_answer_callback:
                    bot.answer_callback_query(callback.id)
                return callback.data

        return result

    def __call__(self) -> InlineKeyboardMarkup:
        """
        Return current reply_markup
        """
        reply = InlineKeyboardMarkup(row_width=self._row_width)
        elements_buttons = []

        start_index = self._page * self._page_size
        end_index = start_index + self._page_size
        if end_index > self._list_len():
            end_index = self._list_len()

        for i in range(start_index, end_index):
            elements_buttons.append(self._get_callback_info(i).to_inline_callback_button())

        if not self._no_element_button:
            reply.add(*elements_buttons)
        reply = self._bottom_buttons(reply)

        return reply




import calendar
from datetime import datetime, timedelta
from typing import Optional

from bot import *
from common.tg_utils import *


class CalendarView:
    MONTH_NAMES = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль',
                   'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

    def __init__(self, user_id: int, year: int = None, month: int = None, need_back=True):
        self._user_id = user_id
        self._year = year
        self._month = month
        self._day = None
        self._need_back = need_back

    def handle_callback(self, callback: CallbackQuery) -> Optional[str]:
        """
        Handle callback for calendar
        :param callback: CallbackQuery
        :return: result
        """
        data = callback.data
        current = datetime(self._year, self._month, 1)
        if data == 'calendar_ignore':
            return 'answer_callback'
        elif data == 'calendar_prev':
            pre = current - timedelta(days=1)
            self._year, self._month = pre.year, pre.month
            return 'redraw'
        elif data == 'calendar_next':
            next = current + timedelta(days=31)
            self._year, self._month = next.year, next.month
            return 'redraw'
        elif data == 'calendar_back':
            return 'back'
        elif data.startswith('calendar_day'):
            self._day = int(data.split(':')[1])
            return 'choose'

    def get_data(self):
        return {'calendar_day': self._day, 'calendar_month': self._month, 'calendar_year': self._year}

    def get_datetime(self):
        if self._day is None:
            return None
        return datetime(self._year, self._month, self._day, 0, 0, 0)

    def __call__(self) -> InlineKeyboardMarkup:
        """
        Return current reply_markup
        """
        reply = InlineKeyboardMarkup()

        now = datetime.now()
        if self._year is None:
            self._year = now.year
        if self._month is None:
            self._month = now.month

        reply.add(InlineKeyboardButton(self.MONTH_NAMES[self._month - 1] + ' ' + str(self._year),
                                       callback_data='calendar_ignore'))

        row = []
        for day in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']:
            row.append(InlineKeyboardButton(day, callback_data='calendar_ignore'))
        reply.row(*row)

        cal = calendar.monthcalendar(self._year, self._month)
        for week in cal:
            row = []
            for day in week:
                if day == 0:
                    row.append(InlineKeyboardButton(' ', callback_data='calendar_ignore'))
                else:
                    row.append(InlineKeyboardButton(str(day),
                                                    callback_data='calendar_day:' + str(day)))
            reply.row(*row)

        if self._need_back:
            row = [InlineKeyboardButton('⬅', callback_data='calendar_prev'),
                   InlineKeyboardButton('↩️ Назад', callback_data='calendar_back'),
                   InlineKeyboardButton('➡', callback_data='calendar_next')]
        else:
            row = [InlineKeyboardButton('⬅', callback_data='calendar_prev'),
                   InlineKeyboardButton('➡', callback_data='calendar_next')]

        reply.row(*row)
        return reply



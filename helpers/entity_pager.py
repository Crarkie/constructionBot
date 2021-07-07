from texts import DEFAULT_LANGUAGE
from helpers.pager_list import *
from common.models import *

CITIES_PER_PAGE = 5


class EntityPager(BackBottomButtonsMixin, InlineKeyboardPager):
    def __init__(self, user_id: int, query, field_name_func, id_func, element_prefix: str, row_width: int = 1, per_page: int = 5,
                 no_element_button=False, save_prefix: str = None):
        super().__init__(user_id, row_width, no_element_button)
        try:
            self._lang = str(DbUser.get(user_id).language)
        except:
            self._lang = DEFAULT_LANGUAGE

        self._query = query
        self._field_name_func = field_name_func
        self._id_func = id_func
        self._element_prefix = element_prefix
        self._per_page = per_page
        if save_prefix:
            self._save_prefix = save_prefix
        self._prefetch = list(query.paginate(self._page + 1, self._per_page).execute())

    def _save_page(self):
        super()._save_page()
        self._prefetch = list(self._query.paginate(self._page + 1, self._per_page).execute())

    def get_current_entities(self) -> List:
        return self._prefetch

    @property
    def _page_size(self) -> int:
        return self._per_page

    def _is_element_prefix(self, data: str) -> bool:
        return data.startswith(self._element_prefix)

    def _list_len(self) -> int:
        return self._query.count()

    def _get_callback_info(self, index: int) -> CallbackButtonInfo:
        entity = self._prefetch[index - self._page_size * self._page]
        text = self._field_name_func(entity)
        return CallbackButtonInfo(text, f'{self._element_prefix}:{self._id_func(entity)}')
import yaml
from typing import Dict

from bot import storage
from common.models import User

__all__ = ['get_texts', 'get_user_texts']

SUPPORTED_LANGUAGES = ['ru', 'en']
DEFAULT_LANGUAGE = 'ru'
_ru = yaml.safe_load(open('texts/ru.yml', encoding='utf-8'))
#_en = yaml.safe_load(open('texts/en.yml', encoding='utf-8'))


texts = {'ru': _ru }


def get_texts(language: str = None) -> Dict[str, str]:
    """
    Return dict with texts corresponding the language,
    else return texts for default language
    :param language: ru/en
    :return: dict with texts
    """
    if language in SUPPORTED_LANGUAGES:
        return texts[language]
    else:
        return texts[DEFAULT_LANGUAGE]


def get_user_texts(user_id: int) -> Dict[str, str]:
    """
    Return dict with corresponding user's language
    else return texts for default language
    :param user_id:
    :return: dict with texts
    """

    # search first user in DB
    user = User.get_or_none(user_id)
    if user:
        return get_texts(user.language)

    # if not found then search in storage
    lang = storage.get_data(user_id, default={'lang': DEFAULT_LANGUAGE}).get('lang', DEFAULT_LANGUAGE)
    return get_texts(lang)


ZERO_EMOJI = '0⃣'.encode('utf-8')
DIGIT_EMOJI_TABLE = [ch for ch in map(lambda i: (bytes([ZERO_EMOJI[0] + i]) + ZERO_EMOJI[1:]).decode('utf-8'),
                                      range(0, 10))]


def number_to_emoji(num: int) -> str:
    s, num = '', str(num)
    for digit in num:
        s += DIGIT_EMOJI_TABLE[int(digit)]
    return s

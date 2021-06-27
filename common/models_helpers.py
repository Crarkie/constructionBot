from typing import Union, Optional
from .models import *


def get_user_entity(user_id: int) -> Union[User, None]:
    """
    Get user entity (Girl or Client) by user_id
    """
    user = User.get_or_none(user_id)
    if not user:
        return
    
    return user


def str_to_bool(s: str) -> Optional[bool]:
    if s == 'False':
        return False
    elif s == 'True':
        return True

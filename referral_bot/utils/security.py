import re

from referral_bot.config import ADMIN_IDS

SQLITE_INTEGER_MIN = -9223372036854775808
SQLITE_INTEGER_MAX = 9223372036854775807

_ASCII_POSITIVE_INT = re.compile(r"[0-9]+")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _parse_bounded_int(value, *, min_value, max_value):
    """Shared bounded integer parser used by all public parse helpers.

    Rules:
        - accepts str or int
        - strips surrounding whitespace from strings
        - rejects empty / non-ASCII-numeric / negative / too-large values
        - rejects values above max_value and below min_value
        - never raises for malformed input; returns None instead
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        num = value
    elif isinstance(value, str):
        s = value.strip()
        if not s or len(s) > 40:
            return None
        if not _ASCII_POSITIVE_INT.fullmatch(s):
            return None
        try:
            num = int(s)
        except (ValueError, OverflowError):
            return None
    else:
        return None
    if num < min_value:
        return None
    if num > max_value:
        return None
    return num


def parse_positive_int(value, *, max_value=SQLITE_INTEGER_MAX):
    """Parse user-controlled input into a positive integer within [1, max_value].

    Never raises for malformed input; returns None instead.
    """
    return _parse_bounded_int(value, min_value=1, max_value=max_value)


def parse_non_negative_int(value, *, max_value=SQLITE_INTEGER_MAX):
    """Parse user-controlled input into a non-negative integer within [0, max_value].

    Allows 0 (unlike parse_positive_int). Never raises for malformed input;
    returns None instead.
    """
    return _parse_bounded_int(value, min_value=0, max_value=max_value)


def parse_telegram_id(value):
    """Parse a Telegram user identifier from user-controlled input.

    Telegram IDs are positive integers that must fit into the SQLite
    INTEGER storage class to avoid OverflowError on insert/query.
    Returns None when invalid. Never raises.
    """
    return parse_positive_int(value, max_value=SQLITE_INTEGER_MAX)
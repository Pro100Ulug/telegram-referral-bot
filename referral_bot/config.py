import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
PROXY_URL = os.getenv("PROXY_URL", "") or None


def get_db_path():
    raw = os.getenv("DB_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return BASE_DIR / "referral_bot.db"


DB_PATH = get_db_path()

REFERRAL_BONUS = 5
DAILY_REWARD_BASE = 2
COINS_PER_LEVEL = 50
MIN_WITHDRAW_AMOUNT = 50
MAX_ADMIN_ADD_COINS = 10000
MAX_SETTING_VALUE = 1000000
COLLECT_ATTEMPT_LIMIT = 3
COLLECT_ATTEMPT_WINDOW_SECONDS = 60


def calculate_level(coins: int) -> int:
    return coins // COINS_PER_LEVEL + 1

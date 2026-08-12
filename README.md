# Referral Bot

Telegram-бот партнёрской программы на aiogram 3.x.

## Структура

```
referral_bot/
├── main.py              # Точка входа
├── config.py            # Конфигурация
├── database/
│   ├── database.py      # SQL-запросы и CRUD
│   └── migrations.py    # Миграции schema
├── handlers/
│   ├── start.py         # /start
│   ├── profile.py       # /profile
│   ├── referral.py      # /referral, /partners
│   ├── wallet.py        # /balance, /collect, /top, /history
│   ├── withdrawal.py    # /withdraw, /my_withdrawals
│   └── admin.py         # /confirm, /pending, /stats, /withdrawals, /approve, /reject
├── services/
│   ├── referral_service.py    # Бизнес-логика рефералов
│   ├── wallet_service.py      # Бизнес-логика кошелька
│   └── withdrawal_service.py  # Бизнес-логика вывода
├── keyboards/
│   └── menus.py         # Клавиатуры
└── tests/
    └── test_database.py # Тесты БД
```

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Создайте файл `.env` в корне проекта:

```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
```

## Запуск

```bash
python -m referral_bot.main
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация |
| `/profile` | Профиль |
| `/balance` | Баланс |
| `/collect` | Собрать награду (раз в 24ч) |
| `/referral` | Партнёрская ссылка |
| `/partners` | Мои приглашённые |
| `/top` | Топ-10 |
| `/history` | История транзакций |
| `/withdraw СУММА РЕКВИЗИТЫ` | Вывод средств |
| `/my_withdrawals` | Мои заявки |

### Админ-команды

| Команда | Описание |
|---------|----------|
| `/confirm USER_ID` | Подтвердить реферальный бонус |
| `/pending` | Ожидающие подтверждения |
| `/withdrawals` | Заявки на вывод |
| `/approve ID` | Одобрить вывод |
| `/reject ID КОММЕНТАРИЙ` | Отклонить вывод |
| `/stats` | Статистика |

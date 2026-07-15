# 🍇 Grappa - Telegram Client CLI

Современный CLI-клиент Telegram, построенный с использованием функциональной архитектуры и лучших практик разработки.

## 💡 О проекте

**Grappa** - это proof-of-concept альтернативного CLI-клиента Telegram. Основная идея проекта - создать инструмент для умной работы с Telegram чатами, который поможет:

- **Отслеживать упоминания** - находить где и в каком контексте вас упомянули
- **Анализировать диалоги** - получать сводки важных сообщений
- **Быстро ориентироваться** - мгновенно находить нужные чаты и сообщения
- **Автоматизировать рутину** - освободить время от ручного просмотра всех чатов

Проект построен по принципам Clean Architecture с упором на тестируемость, расширяемость и производительность.

## 🎯 Текущее состояние (v0.1.0)

На данный момент реализован **базовый Telegram клиент** с возможностями:

- ✅ Авторизация через Telegram API с сохранением сессии
- ✅ Получение списка чатов пользователя
- ✅ Красивый CLI интерфейс с Rich
- ✅ Полное покрытие тестами
- ✅ Настройка через переменные окружения

**Готовые команды:**
- `poetry run grappa test-connection` - проверка подключения
- `poetry run grappa chats sync --limit 0` - синхронизировать кеш чатов
- `poetry run grappa chats list --limit N` - список чатов из кеша
- `poetry run grappa chats search "query"` - поиск чатов по кешу
- `poetry run grappa messages download <chat> --limit N --media` - скачать сообщения и медиа
- `poetry run grappa messages sync <chat>` - докачать только новые сообщения (дельта) с медиа
- `poetry run grappa messages list <chat> [--text]` - показать локальную копию чата
- `poetry run grappa messages search "query" [--chat <chat>] [--api]` - поиск сообщений
- `poetry run grappa folders sync` - синхронизировать Telegram folders
- `poetry run grappa folders list` - список folders
- `poetry run grappa folders chats <folder>` - чаты из выбранной папки
- `poetry run grappa list-chats --limit N` - старый alias для списка чатов

## 🚀 Планируемые возможности

- 🎯 **Детекция упоминаний** - поиск сообщений где упомянули пользователя
- 📊 **Анализ контекста** - умное извлечение контекста вокруг упоминаний
- 🔗 **Генерация ссылок** - прямые ссылки на найденные сообщения
- 📨 **Обработка медиа** - работа с фото, видео, документами
- 🤖 **ИИ-инструменты поверх grappa** - суммаризация, категоризация, приоритизация (отдельным слоем, не в самом клиенте)
- 📈 **Аналитика** - статистика активности в чатах

## 🏗️ Архитектура проекта

```
├── 📁 grappa/                 # Python-пакет приложения
│   ├── main.py               # CLI приложение (entry point `grappa`)
│   ├── 📁 client/            # Telegram клиент
│   │   ├── __init__.py       # Экспорты модуля
│   │   └── telegram_client.py # Основной клиент с Pyrogram
│   ├── 📁 config/            # Конфигурация
│   │   └── settings.py       # Настройки через Pydantic Settings
│   ├── 📁 data/              # Модели данных
│   │   └── models.py         # UserInfo, ChatInfo, MessageInfo, MentionInfo
│   ├── 📁 chat_manager/      # Управление чатами
│   ├── 📁 message_parser/    # Парсинг сообщений
│   ├── 📁 storage/           # Локальный кеш
│   └── 📁 utils/             # 🚧 Утилиты (планируется)
├── 📁 tests/                 # Тесты
│   ├── conftest.py           # Общие фикстуры
│   ├── test_client/          # Тесты клиента
│   └── test_*/               # Тесты других модулей
├── 📄 install.sh             # curl-инсталлер для систем без Homebrew
├── 📄 pyproject.toml         # Poetry конфигурация
├── 📄 env.example            # Пример настроек
└── 📄 .env                   # Ваши настройки (не в git)
```

## 📋 Требования

- Python 3.10+
- Poetry для управления зависимостями
- Telegram API credentials (api_id, api_hash)

## 📦 Установка

### Homebrew (macOS / Linux)

```bash
brew tap hmepas/formulae
brew install grappa
```

Или последнюю dev-версию из `main`:

```bash
brew install --HEAD hmepas/formulae/grappa
```

### Через curl (системы без Homebrew)

Требуется Python 3.10–3.13:

```bash
curl -fsSL https://raw.githubusercontent.com/hmepas/grappa/main/install.sh | bash
```

Скрипт ставит grappa в изолированный virtualenv (`~/.local/share/grappa`) и
создаёт симлинк `~/.local/bin/grappa`.

При первом запуске grappa сам запросит Telegram API-ключи и сохранит их в
`~/.config/grappa/config.env` (уважается `XDG_CONFIG_HOME`). Приоритет
настроек: переменные окружения > `./.env` в текущей директории > глобальный
конфиг. Рабочие файлы хранятся в `~/.grappa/data/` (кеш чатов и сообщений,
`downloads/` для медиа, `sessions/` для сессии Telegram) независимо от того,
откуда запущена grappa; пути переопределяются через `GRAPPA_DATA_DIR`,
`GRAPPA_DOWNLOADS_DIR` и `GRAPPA_SESSION_DIR`.

## 🛠️ Установка для разработки

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd grappa
```

2. Установите зависимости через Poetry:
```bash
poetry install
```

3. Установите pre-commit хуки:
```bash
poetry run pre-commit install
```

4. **Настройте конфигурацию:**
   - Скопируйте файл примера: `cp env.example .env`
   - Отредактируйте `.env` файл и добавьте ваши Telegram API данные:
     - `TELEGRAM_API_ID` - получите на https://my.telegram.org/apps
     - `TELEGRAM_API_HASH` - получите на https://my.telegram.org/apps
     - `TELEGRAM_PHONE_NUMBER` - ваш номер телефона в международном формате

## 🎯 Использование

### Проверка подключения
```bash
poetry run grappa test-connection
```

### Синхронизация и список чатов
```bash
poetry run grappa chats sync --limit 0
poetry run grappa chats list --limit 10
poetry run grappa chats list --archived --limit 10
poetry run grappa chats list --exclude-archived --limit 10
poetry run grappa chats refresh-archive
poetry run grappa chats archive --dry-run <chat_id>
poetry run grappa chats archive --yes <chat_id>
poetry run grappa chats unarchive --yes <chat_id>
poetry run grappa chats search "telegram"
```

Приватные чаты получают имя из first/last name собеседника, а ваш собственный
чат называется «Saved Messages» (ищется через `chats search saved`; в командах
сообщений также работает ссылка `me`). Чтобы имена появились в старом кеше,
перезапустите `chats sync`.

### Telegram folders
```bash
poetry run grappa folders sync
poetry run grappa folders list
poetry run grappa folders chats WB --limit 20
poetry run grappa folders chats 8 --ids-only
```

После `folders sync` список чатов также показывает папки, в которых находится чат.

### Скачать сообщения чата
```bash
# последние 100 сообщений
poetry run grappa messages download @chat_username --limit 100

# сообщения за дату/период, с медиа
poetry run grappa messages download @chat_username --from 2026-06-01 --to 2026-06-05 --limit 1000 --media

# весь чат: осторожно, может быть очень долго
poetry run grappa messages download @chat_username --limit 0 --media
```

### Поддержание локальной копии чата (дельта-синк)

```bash
# первый запуск скачивает всю историю (с медиа), повторные - только новые сообщения
poetry run grappa messages sync @chat_username

# Saved Messages: "me" уходит напрямую в Telegram (InputPeerSelf)
poetry run grappa messages sync me

# без медиа / в свою директорию для медиа
poetry run grappa messages sync @chat_username --no-media
poetry run grappa messages sync @chat_username --media-dir ~/tg-archive/mychat

# посмотреть локальную копию текстом со путями к медиа-файлам
poetry run grappa messages list @chat_username --text --limit 0
```

Сообщения хранятся в `~/.grappa/data/messages/<chat_id>.json`, медиа - в
`~/.grappa/data/downloads/<chat_id>/<message_id>_<имя_файла>` (гифки, фото, видео, голосовые,
кружки, стикеры, аудио и документы). Синк движется только вперёд: правки и
удаления сообщений старше последнего закешированного не отслеживаются.

### Поиск сообщений
```bash
# по локальному кешу во всех скачанных чатах
poetry run grappa messages search "важный текст"

# по локальному кешу внутри одного чата
poetry run grappa messages search "важный текст" --chat @chat_username

# через Telegram API
poetry run grappa messages search "важный текст" --chat @chat_username --api
```

### Отладочный режим
```bash
poetry run grappa --debug <команда>
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
poetry run pytest

# Запуск с покрытием
poetry run pytest --cov

# Запуск конкретного модуля
poetry run pytest tests/test_client/ -v
```

## 🔧 Разработка

### Линтинг и форматирование
```bash
# Форматирование кода
poetry run black . --exclude=".venv"

# Сортировка импортов
poetry run isort . --skip=.venv

# Проверка типов
poetry run mypy .

# Проверка стиля кода
poetry run flake8 . --exclude=.venv
```

### Pre-commit
Все проверки запускаются автоматически перед коммитом:
```bash
poetry run pre-commit run --all-files
```

## 📊 Style Guide

- **Форматирование**: Black (line-length=88)
- **Импорты**: isort (profile="black")
- **Типизация**: mypy (strict mode)
- **Документация**: Google style docstrings
- **Тестирование**: pytest + pytest-asyncio
- **Архитектура**: Clean Architecture, DRY, функциональный подход

## 🤝 Контрибьюция

1. Создайте feature branch от main
2. Внесите изменения с тестами
3. Убедитесь что все pre-commit проверки проходят
4. Создайте Pull Request

## 📝 Лицензия

MIT License

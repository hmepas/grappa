# 🍇 Grappa - AI-Augmented Telegram Client

Современный ИИ аугментированный Telegram клиент, построенный с использованием функциональной архитектуры и лучших практик разработки.

## 🚀 Возможности

- 📱 Подключение к Telegram от имени пользователя
- 🔍 Быстрый поиск и фильтрация чатов
- 📨 Обработка всех типов медиа сообщений
- 🎯 Детекция упоминаний пользователя в чатах
- 🔗 Генерация ссылок на сообщения
- 🧪 Полное покрытие тестами
- 📊 Структурированное логирование

## 🏗️ Архитектура

Проект построен по модульной архитектуре с четким разделением ответственности:

```
grappa/
├── client/          # Telegram клиент и авторизация
├── message_parser/  # Парсинг и обработка сообщений
├── chat_manager/    # Управление чатами
├── data/           # Модели данных
├── config/         # Конфигурация
└── utils/          # Утилиты
```

## 📋 Требования

- Python 3.10+
- Poetry для управления зависимостями
- Telegram API credentials (api_id, api_hash)

## 🛠️ Установка

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

4. Создайте файл конфигурации `.env`:
```bash
cp .env.example .env
# Отредактируйте .env файл, добавив ваши Telegram API данные
```

## 🎯 Использование

### Базовый запуск
```bash
poetry run grappa
```

### Запуск с отладкой
```bash
poetry run grappa --debug
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
poetry run pytest

# Запуск с покрытием
poetry run pytest --cov=grappa

# Запуск конкретного модуля
poetry run pytest tests/test_client/
```

## 🔧 Разработка

### Линтинг и форматирование
```bash
# Форматирование кода
poetry run black grappa/ tests/

# Сортировка импортов
poetry run isort grappa/ tests/

# Проверка типов
poetry run mypy grappa/

# Проверка стиля кода
poetry run flake8 grappa/ tests/
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

## 🤝 Контрибьюция

1. Создайте feature branch от main
2. Внесите изменения с тестами
3. Убедитесь что все pre-commit проверки проходят
4. Создайте Pull Request

## 📝 Лицензия

MIT License 
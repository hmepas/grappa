# 📋 CONTEXT.md - Chat Context & Current State

## 🎯 **Принцип работы с документацией:**

- **📋 CONTEXT.md** - контекст текущего чата, состояние проекта, ключевые решения
- **📝 TODO.md** - детальный план задач, по которому двигаемся в реализации
- **📖 README.md** - общее описание проекта, архитектура, инструкции для пользователей

**Правило:** Всегда обновляй все три файла при значимых изменениях проекта!

---

## 🚀 **Текущее состояние проекта (v0.1.0):**

### ✅ **Что работает:**
- **Telegram клиент** - TelegramClient с авторизацией через Pyrogram
- **Сессия** - сохранение и восстановление сессии пользователя
- **CLI интерфейс** - commands: `test-connection`, `list-chats --limit N`
- **Модели данных** - UserInfo, ChatInfo, MessageInfo, MentionInfo (Pydantic)
- **Конфигурация** - через .env файл с валидацией
- **Тесты** - 6/6 passing, полное покрытие core функциональности
- **Линтеры** - black, isort, flake8 (120 chars), pre-commit hooks
- **Реальное подключение** - протестировано с API, работает как @hmepas

### 🏗️ **Архитектура:**
```
grappa/
├── client/           # TelegramClient (Pyrogram wrapper)
├── config/           # Settings с Pydantic Settings
├── data/            # Модели: UserInfo, ChatInfo, etc.
├── tests/           # Полное покрытие тестами
├── main.py          # CLI с Click + Rich
└── sessions/        # Telegram сессии
```

---

## ⚠️ **Главная проблема для решения:**

**МЕДЛЕННЫЙ ПОИСК ЧАТОВ** 🐌
- Каждый `list_chats` = новый API запрос
- Нет локального кеширования
- Линейный поиск без индексации
- API rate limits (300 req/min)
- Плохой UX для больших списков чатов

**Цель:** Мгновенный поиск с кешированием и индексацией

---

## 🎯 **Ключевые архитектурные решения:**

### **Storage Strategy: JSON files** ✅
**Почему JSON, а не SQLite/Redis:**
- ✅ Простота - нет внешних зависимостей
- ✅ Портабельность - работает везде
- ✅ Git-friendly - можно коммитить кеш для отладки
- ✅ Быстрая итерация - легко менять структуру
- ❌ Минусы: нет транзакций, ручное индексирование

### **Search Strategy: Hybrid approach** ✅
- **Exact match**: @username, chat_id → O(1) lookup
- **Fuzzy search**: названия чатов → Levenshtein distance
- **Filters**: type:group, members:>100, recent, etc.
- **Ranking**: recency + frequency + relevance scores

### **Cache Strategy: Smart incremental** ✅
- **Full sync**: первый запуск или `--force`
- **Incremental sync**: только изменившиеся чаты
- **Smart refresh**: только если кеш устарел (> 1 час)
- **Background sync**: подтягивание в фоне с rate limiting

### **Performance Targets** 🎯
- **Search speed**: < 50ms для cached queries
- **Cache hit rate**: > 90% для repeated searches
- **Memory usage**: < 50MB для 10K чатов
- **API efficiency**: < 10 API calls за обычную сессию

---

## 🏗️ **Phase 1 - Следующие шаги (приоритет):**

### 1. **CacheStorage класс**
```python
class CacheStorage:
    async def save_chats(chats: List[ChatInfo]) -> None
    async def load_chats() -> List[ChatInfo]
    async def save_metadata(meta: CacheMetadata) -> None
    async def is_cache_stale() -> bool
```

### 2. **Расширить ChatInfo модель**
```python
class ChatInfo(BaseModel):
    # существующие поля...
    last_seen: Optional[datetime] = None
    message_count: Optional[int] = None
    activity_score: float = 0.0
    access_count: int = 0
```

### 3. **Базовый ChatManager**
```python
class ChatManager:
    async def get_chats(force_refresh: bool = False) -> List[ChatInfo]
    async def search_chats(query: str) -> List[ChatInfo]
    async def sync_from_api() -> int  # returns updated count
```

### 4. **CLI команды**
- `grappa search "query"` - поиск по кешу
- `grappa sync` - принудительная синхронизация
- `grappa list --recent` - недавние чаты

---

## 🔧 **Технические детали:**

### **Новые зависимости:**
```toml
python-Levenshtein = "^0.20.9"  # fuzzy search
filelock = "^3.13.1"            # concurrent access
tqdm = "^4.66.1"                # progress bars
```

### **Файловая структура кеша:**
```
data/
├── chats_cache.json      # List[ChatInfo] - основные данные
├── search_index.json     # Индексы для быстрого поиска
├── chat_stats.json       # Статистика использования
└── cache_metadata.json   # Версия, last_update, etc.
```

### **Graceful Degradation:**
- Если кеш сломан → fallback на прямые API вызовы
- Если API недоступен → работаем только с кешем
- Если индекс сломан → linear search по кешу
- Всегда показываем прогресс пользователю

---

## 📋 **Статус документации:**

- ✅ **TODO.md** - создан детальный план на 4 фазы реализации
- ✅ **README.md** - актуальный, описывает текущие возможности v0.1.0
- ✅ **CONTEXT.md** - этот файл, контекст чата
- ⚠️ **Нужно обновить README.md** после реализации поиска

---

## 🚨 **Важные принципы:**

1. **Не ломать существующий код** - все текущие команды должны работать
2. **Тесты покрывают новую функциональность** - TDD approach
3. **API efficiency** - batch requests, rate limiting
4. **User experience** - показывать прогресс, graceful errors
5. **Функциональный подход** - чистые функции, минимум side effects

---

## 🎯 **Success Criteria для Phase 1:**

- [ ] Кеш сохраняется и загружается корректно
- [ ] `grappa search` работает быстрее чем API запрос
- [ ] Все существующие тесты проходят
- [ ] Новые тесты покрывают кеширование
- [ ] CLI показывает понятные сообщения об ошибках
- [ ] Документация обновлена

**Готов к реализации!** 🚀

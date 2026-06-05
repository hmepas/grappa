# 🚀 TODO: Fast Chat Search & Management

## 🎯 Goal: Реализовать быстрый поиск и управление чатами с кешированием

### 📊 Current Problems:
- [ ] Каждый `list_chats` делает новый API запрос (медленно)
- [ ] Нет локального кеширования данных
- [ ] Линейный поиск без индексации
- [ ] Нет фильтрации по типам/активности
- [ ] API rate limits (300 req/min)

---

## 🏗️ Architecture Plan

### 1. 📦 Data Storage Layer

#### 1.1 Local Cache Structure
```
data/
├── chats_cache.json           # Основной кеш чатов
├── search_index.json          # Поисковые индексы
├── chat_stats.json            # Статистика использования
└── cache_metadata.json        # Метаданные кеша
```

**Tasks:**
- [ ] Create `CacheStorage` class для работы с JSON файлами
- [ ] Implement cache versioning и migration
- [ ] Add cache invalidation strategies
- [ ] Handle concurrent access (file locking)

#### 1.2 Data Models Extension
- [ ] Extend `ChatInfo` with `last_seen`, `message_count`, `activity_score`
- [ ] Add `CacheMetadata` model (version, last_update, total_chats)
- [ ] Create `ChatStats` model (access_count, last_accessed, message_frequency)
- [ ] Add `SearchIndex` models для разных типов индексов

### 2. 🔍 Search Index Layer

#### 2.1 Search Indexes
- [ ] **Title Index**: word → [chat_ids] (для fuzzy search)
- [ ] **Username Index**: username → chat_id (O(1) lookup)
- [ ] **Type Index**: chat_type → [chat_ids] (группы, каналы, etc.)
- [ ] **Activity Index**: activity_level → [chat_ids] (по убыванию активности)

**Tasks:**
- [ ] Create `ChatSearchIndex` class
- [ ] Implement text tokenization (split, lowercase, remove punctuation)
- [ ] Add fuzzy search with Levenshtein distance (threshold = 2)
- [ ] Create prefix search for fast typing suggestions

#### 2.2 Search Query Parser
```
Examples:
- "telegram" → fuzzy search by title
- "@durov" → exact username search
- "type:group" → filter by type
- "members:>100" → filter by member count
- "#crypto recent" → keyword + recent filter
```

**Tasks:**
- [ ] Create `SearchQueryParser` class
- [ ] Support query syntax: `field:value`, `@username`, `#tag`
- [ ] Add boolean operators: AND, OR, NOT
- [ ] Implement query validation и error handling

### 3. ⚡ ChatManager Layer

#### 3.1 Core ChatManager Class
```python
class ChatManager:
    async def search_chats(query: str, limit: int = 20) -> List[ChatInfo]
    async def get_chat_by_id(chat_id: int) -> Optional[ChatInfo]
    async def get_chat_by_username(username: str) -> Optional[ChatInfo]
    async def get_recent_chats(limit: int = 10) -> List[ChatInfo]
    async def refresh_cache(force: bool = False) -> None
    async def sync_incremental() -> int  # returns number of updated chats
```

**Tasks:**
- [ ] Implement `ChatManager` with dependency injection
- [ ] Add smart cache refresh (only if stale > 1 hour)
- [ ] Create incremental sync (fetch only updated chats)
- [ ] Add background sync с rate limiting
- [ ] Implement cache warming strategies

#### 3.2 Performance Optimization
- [ ] **Fast path**: username/chat_id lookup (< 10ms)
- [ ] **Medium path**: fuzzy search with index (< 100ms)
- [ ] **Slow path**: full API sync when cache miss
- [ ] Add request batching (combine multiple searches)
- [ ] Implement result caching for repeated queries

### 4. 🔧 Integration Layer

#### 4.1 CLI Commands Enhancement
```bash
# Fast search commands
grappa search "telegram"               # search by title
grappa search "@durov"                 # search by username
grappa search "type:group members:>100" # filtered search
grappa list --recent                   # recent chats only
grappa list --type=channel             # channels only
grappa sync                           # force cache refresh
```

**Tasks:**
- [ ] Add `search` command to main CLI
- [ ] Enhance `list-chats` with filters (`--type`, `--recent`, `--active`)
- [ ] Add `sync` command для manual cache refresh
- [ ] Create interactive search mode (live search)
- [ ] Add search result ranking и pagination

#### 4.2 TelegramClient Integration
- [ ] Add batch loading methods to `TelegramClient`
- [ ] Implement incremental sync detection
- [ ] Add progress reporting for large syncs
- [ ] Handle API rate limiting gracefully
- [ ] Create retry logic with exponential backoff

### 5. 📈 Advanced Features

#### 5.1 Smart Ranking
- [ ] **Recency score**: recently accessed chats rank higher
- [ ] **Frequency score**: frequently used chats rank higher
- [ ] **Activity score**: chats with recent messages rank higher
- [ ] **Relevance score**: fuzzy match quality
- [ ] Combined scoring algorithm

#### 5.2 Analytics & Insights
- [ ] Track search patterns и popular queries
- [ ] Chat usage analytics (most/least used)
- [ ] Performance metrics (cache hit rate, search latency)
- [ ] Export analytics to JSON for analysis

### 6. 🧪 Testing Strategy

#### 6.1 Unit Tests
- [ ] Test `ChatSearchIndex` with different query types
- [ ] Test `CacheStorage` with concurrent access
- [ ] Test `SearchQueryParser` with edge cases
- [ ] Mock Telegram API для integration tests

#### 6.2 Performance Tests
- [ ] Benchmark search with 1K, 10K, 100K chats
- [ ] Test cache loading/saving performance
- [ ] Memory usage profiling
- [ ] Search latency measurements

#### 6.3 Integration Tests
- [ ] Test full sync flow with real Telegram API
- [ ] Test incremental sync with simulated updates
- [ ] Test error recovery (corrupted cache, API errors)
- [ ] Test CLI commands end-to-end

---

## 🎯 Implementation Priority

### Phase 1: Core Infrastructure (Week 1)
1. [ ] `CacheStorage` class with JSON persistence
2. [ ] Extended data models (`ChatInfo`, `CacheMetadata`)
3. [ ] Basic `ChatManager` with cache loading/saving
4. [ ] Simple search by title (exact match)

### Phase 2: Search & Index (Week 2)
1. [ ] `ChatSearchIndex` with title/username indexes
2. [ ] `SearchQueryParser` with basic syntax
3. [ ] Fuzzy search implementation
4. [ ] CLI `search` command

### Phase 3: Performance & Sync (Week 3)
1. [ ] Incremental sync detection
2. [ ] Background sync with rate limiting
3. [ ] Search result ranking
4. [ ] Performance optimization

### Phase 4: Advanced Features (Week 4)
1. [ ] Interactive search mode
2. [ ] Analytics и insights
3. [ ] Advanced filtering
4. [ ] Complete test coverage

---

## 📋 Technical Decisions

### Storage Format: JSON vs SQLite vs Redis
**Decision: JSON files** ✅
- Pros: Simple, portable, git-friendly, no dependencies
- Cons: No transactions, manual indexing, memory usage
- Alternative: SQLite for complex queries later

### Search Algorithm: Exact vs Fuzzy vs Full-text
**Decision: Hybrid approach** ✅
- Exact match for usernames/IDs (O(1))
- Fuzzy search for titles (Levenshtein + prefix)
- Full-text search for descriptions (future)

### Cache Strategy: Full vs Incremental vs Smart
**Decision: Smart incremental** ✅
- Full sync on first run or force refresh
- Incremental sync based on `last_update` timestamp
- Smart refresh only when cache is stale

### Rate Limiting: Simple vs Adaptive vs Token Bucket
**Decision: Simple with backoff** ✅
- Start with fixed delays between requests
- Add exponential backoff on API errors
- Monitor rate limits and adapt

---

## 🔗 Dependencies to Add

```toml
# For fuzzy search
python-Levenshtein = "^0.20.9"

# For file locking (concurrent access)
filelock = "^3.13.1"

# For progress bars during sync
tqdm = "^4.66.1"

# For advanced text processing (future)
# nltk = "^3.8.1"
```

---

## 📝 Success Metrics

- [ ] **Search Speed**: < 50ms for cached queries
- [ ] **Cache Hit Rate**: > 90% for repeated searches
- [ ] **Memory Usage**: < 50MB for 10K chats
- [ ] **API Efficiency**: < 10 API calls for typical session
- [ ] **User Experience**: Instant search feedback

---

## 🚀 Future Enhancements

- [ ] **AI-powered search**: semantic similarity, intent detection
- [ ] **Cross-platform sync**: sync cache across devices
- [ ] **Real-time updates**: WebSocket notifications
- [ ] **Export/Import**: backup/restore functionality
- [ ] **Plugin system**: custom search filters

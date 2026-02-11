# MySQL Cost Analysis (Repo-Specific)

## Executive summary

Your current architecture is likely expensive **not because MySQL is wrong**, but because the app pattern creates many short-lived DB connections and high polling traffic.

Most of the savings can come from:

1. **Connection pooling / persistent connections** (reduce connect/disconnect overhead).
2. **Lower DB polling frequency by moving “pending work” to a queue pattern**.
3. **Avoiding repeated schema checks (`information_schema`) on hot paths**.
4. **Keeping only hot operational data in MySQL; archiving historical chat/memory data**.

This keeps the same product behavior while reducing DB CPU and connection pressure.

---

## What I found in this repo

### 1) Very high number of per-function `mysql.connector.connect(...)`

In `workers/funpay/railway` alone there are many direct connection opens in utility functions, each opened and closed inside function scope (`conn = mysql.connector.connect(...); ...; conn.close()`).

Representative files include:
- `chat_utils.py`
- `lot_utils.py`
- `raise_utils.py`
- `order_utils.py`
- `memory_utils.py`
- `blacklist_utils.py`

This pattern is also present in other services/workers.

**Impact:** lots of connection churn and authentication/handshake overhead, which pushes you toward higher DB tiers.

### 2) Tight polling loops in workers

The FunPay worker defaults to poll every **6s** (`FUNPAY_POLL_SECONDS`, default 6) and does repeated DB reads in that loop (`get_user_id_by_username`, outbox processing, chat sync, raise sync checks).  
The PlayerOk worker also loops every **15s** by default.

**Impact:** steady baseline query load even when business activity is low.

### 3) Repeated `information_schema` checks on active paths

`table_exists` / `column_exists` query `information_schema` and are called in frequently used utilities before normal queries.

**Impact:** extra metadata queries that add CPU and latency and do not provide business value once schema is stable.

### 4) MySQL stores growing conversational/history data

`chat_ai_memory` stores freeform TEXT content and performs `%LIKE%` scans across `content` and `key_text` tokens.

**Impact:** as rows grow, fetch/update costs rise and force larger DB plans.

---

## Cheaper architecture options (same efficiency)

## Option A (fastest ROI, minimal rewrite): Keep MySQL, optimize access

1. Introduce a small DB access layer with:
   - process-level connection pool,
   - reusable context manager,
   - consistent timeouts/retries.
2. Replace per-function fresh connects with pooled checkout.
3. Cache schema capability once at startup (or once per process), not every request.
4. Add/verify indexes for hottest filters:
   - outbox: `(status, user_id, workspace_id, id)`
   - messages: `(user_id, workspace_id, chat_id, sent_time)`
   - chats: `(user_id, workspace_id, chat_id)` and `(user_id, workspace_id, name)`
5. Reduce polling aggressiveness with adaptive backoff:
   - active chats: keep near-real-time,
   - idle workspaces: increase poll interval progressively.

**Expected effect:** often 30–60% reduction in DB CPU/connect overhead without feature changes.

## Option B (best cost/perf medium-term): MySQL + Redis queue/cache

Keep MySQL as source of truth, but move high-frequency “is there work?” checks to Redis:

- Push outbound messages to Redis stream/list at write time.
- Worker blocks on Redis (BLPOP/XREAD) instead of polling MySQL each cycle.
- Periodically persist status to MySQL.

Also cache read-heavy lookups in Redis (workspace config, user_id by username, recent chat mapping).

**Expected effect:** big drop in repetitive read queries and smoother latency at peak.

## Option C (largest savings for history-heavy workloads): Hot/Cold data split

- Keep only recent operational window in MySQL (e.g., last 14–30 days chats).
- Archive old messages/AI memory to cheaper object storage (S3-compatible) or ClickHouse/Postgres cold store.
- Query archive only in admin/history screens.

**Expected effect:** smaller MySQL dataset, better buffer cache hit ratio, lower tier requirement.

---

## Concrete low-risk changes you can do first

1. **Connection pooling first** (highest immediate gain).
2. **Memoize `table_exists`/`column_exists` results** per process.
3. **Cache `get_user_id_by_username`** (TTL 5–15 minutes) to remove repeated identical lookups in loops.
4. **Batch outbox status updates** (single `UPDATE ... WHERE id IN (...)`) instead of many small transactions.
5. **Tune poll intervals by activity** rather than fixed global low intervals.
6. **Add retention job** for `chat_messages` / `chat_ai_memory`.

---

## Suggested target design (balanced)

- MySQL: smaller plan, primary transactional tables only.
- Redis: queue + short TTL cache.
- Background archival task: move cold chat/history rows daily.
- Observability:
  - slow query log,
  - query per second by table,
  - connection count,
  - p95/p99 query latency.

If those four metrics improve, you can safely downsize MySQL tier while keeping the same user-facing behavior.

---

## How to validate savings before/after

Track for 3–7 days per phase:

1. DB CPU %
2. Active connections / max connections
3. Queries per second
4. p95 query latency
5. Worker message processing latency

Then downsize instance one tier and compare error/latency budget.


---

## Chat system: cheapest path with same efficiency

If chat is your biggest cost center, prioritize these in order:

### Phase 1 (1-2 days): Reduce query volume without changing product behavior

1. **Outbox query to event-driven read path**
   - Today workers poll `chat_outbox` every loop.
   - Add Redis list/stream per workspace (`chat:outbox:<workspace_id>`) and push outbox IDs at enqueue time.
   - Worker blocks with `BLPOP`/`XREADGROUP` and fetches only those IDs from MySQL.
   - Keep MySQL as source of truth for final status (`pending/sent/failed`) to preserve reliability.

2. **Batch status updates for sends**
   - Instead of updating each message row one-by-one, flush in batches (e.g. every 100 messages or every 1s).
   - Use one statement for success and one for failures with grouped IDs.

3. **Cache chat-id resolution**
   - `owner -> chat_id` can be cached for short TTL (e.g. 5-10 minutes).
   - This removes repeated `SELECT ... FROM chats` in active sessions.

4. **Avoid repeated schema checks in chat hot path**
   - Resolve table/column capability once at startup and store in memory.
   - Remove repeated `information_schema` calls from per-message operations.

### Phase 2 (3-5 days): Keep MySQL lean for chat history

1. **Hot/cold split for `chat_messages`**
   - Keep only recent N days (e.g. 30 days) in main MySQL.
   - Archive older rows daily to cheaper storage.

2. **Retention for AI memory**
   - Lower `AI_MEMORY_MAX_PER_CHAT` and keep only high-value items.
   - Optional: move semantic memory to a compact KV/doc store, keeping only references in MySQL.

3. **Right indexes for chat tables**
   - `chat_outbox(status, user_id, workspace_id, id)`
   - `chat_messages(user_id, workspace_id, chat_id, sent_time)`
   - `chats(user_id, workspace_id, name)`

### Expected savings for chat-heavy workloads

- **DB read QPS:** down 40-80% once outbox polling becomes event-driven.
- **Connections churn:** down significantly with pooling + less polling.
- **CPU:** down 30-60% depending on current active chats.

### Safety checklist (to keep same reliability)

- Keep message idempotency key (avoid duplicate sends on retry).
- Keep MySQL transaction on final state write.
- Add dead-letter handling for permanently failed sends.
- Add replay script: rebuild Redis outbox queue from MySQL rows where `status='pending'`.

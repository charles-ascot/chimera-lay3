# CHIMERA v2 — Complete Build Prompt

Use this prompt to recreate the Chimera Lay Betting App from scratch.

---

## PROMPT

Build me a full-stack **Betfair Exchange lay betting application** called **Chimera v2** for automated lay betting on **GB & IE horse racing WIN markets** only.

### Tech Stack

- **Backend**: Python 3.12, FastAPI, aiosqlite (async SQLite), httpx (async HTTP), websockets
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand (state management), Axios, React Router v6
- **Database**: SQLite (auto-created on startup, no migrations needed)
- **Deployment**: Google Cloud Run `europe-west2` (backend) + Cloudflare Pages (frontend)
- **Production server**: Gunicorn with Uvicorn workers (single worker for SQLite safety)

### Betfair API Integration

The app connects to the **Betfair Exchange** via two APIs:

1. **REST JSON-RPC API** (`https://api.betfair.com/exchange/betting/json-rpc/v1`):
   - Authentication via `https://identitysso.betfair.com/api/login` (username/password, returns session token)
   - Keep-alive via `https://identitysso.betfair.com/api/keepAlive`
   - `listMarketCatalogue` — get today's markets with runner names, start times, venues
   - `listMarketBook` — get live prices (back/lay odds and sizes)
   - `placeOrders` — place lay bets
   - `cancelOrders` — cancel unmatched bets
   - `listCurrentOrders` — check order status
   - Account API (`https://api.betfair.com/exchange/account/json-rpc/v1`): `getAccountFunds`, `getAccountStatement`
   - All requests need headers: `X-Application: {app_key}`, `X-Authentication: {session_token}`, `Content-Type: application/json`

2. **Stream API** (`stream-api.betfair.com:443` over SSL):
   - CRLF-delimited JSON messages over async SSL socket
   - Protocol: Connect → Authenticate → Subscribe → Receive delta updates
   - Market subscription with filter: `eventTypeIds: ["7"]` (horse racing), `countryCodes: ["GB", "IE"]`, `marketTypes: ["WIN"]`
   - Data fields: `EX_BEST_OFFERS_DISP`, `EX_LTP`, `EX_MARKET_DEF`, `EX_TRADED_VOL` with `ladderLevels: 3`
   - Processes MCM (Market Change Messages) with delta-merge on price levels
   - Processes OCM (Order Change Messages) for real-time bet status
   - **IMPORTANT**: The stream API does NOT include runner names in `marketDefinition.runners` — only `id`, `status`, `sortPriority`. Runner names must be fetched separately from the REST `listMarketCatalogue` API and cached.
   - Includes heartbeat mechanism, auto-reconnect with exponential backoff

### Price Cache

Build an in-memory `PriceCache` class that processes stream delta updates:

```
markets[market_id] = {
    "marketDefinition": {...},
    "runners": {
        selection_id (int): {
            "atb": [[price, size], ...],   # Available to Back
            "atl": [[price, size], ...],   # Available to Lay
            "ltp": float,                   # Last Traded Price
            "tv": float,                    # Total Volume
        }
    },
    "status": "OPEN" | "SUSPENDED" | "CLOSED",
    "inPlay": bool,
    "marketTime": str (ISO),
    "lastUpdate": float (timestamp),
}
```

Delta merge: updates are `[price, size]` pairs — size 0 means remove that price level. Support both full image (`img: true`) and delta updates.

### Database Schema (SQLite)

Auto-create these tables on startup:

1. **sessions** — Current Betfair session token storage
2. **bets** — All placed bets with fields: `bet_id, market_id, market_name, venue, country_code, race_time, selection_id, runner_name, side, stake, odds, liability, zone, confidence, rule_id, persistence_type, status, result, profit_loss, size_matched, size_remaining, avg_price_matched, placed_at, matched_at, settled_at, source (AUTO/MANUAL/STAGED), raw_response`
3. **daily_stats** — Aggregated daily P/L
4. **auto_session** — Engine state that survives restarts: `is_running, active_plugins (JSON), processed_markets (JSON), daily_exposure, daily_pnl, bets_placed_today, last_reset_date, settings (JSON)`
5. **plugins** — Strategy plugin metadata and config
6. **stream_archive** — Raw stream API messages for research/replay
7. **decision_log** — Every engine evaluation decision with full context

### Backend API Endpoints

**Auth** (`/api/auth`):
- `POST /login` — Authenticate with Betfair
- `POST /logout` — Logout and clear session
- `POST /keepalive` — Extend session lifetime
- `GET /session` — Check session status

**Markets** (`/api/markets`):
- `GET /catalogue` — List today's GB/IE WIN horse racing markets
- `POST /book` — Get market book with prices
- `GET /{market_id}/book` — Get single market book

**Orders** (`/api/orders`):
- `POST /place` — Place a manual lay bet
- `POST /cancel` — Cancel unmatched order
- `GET /current` — List current orders

**Account** (`/api/account`):
- `GET /balance` — Available funds + daily stats
- `GET /statement` — Account statement

**Auto-Betting** (`/api/auto`):
- `POST /start` — Start engine (mode: STAGING or LIVE)
- `POST /stop` — Stop engine
- `POST /go-live` — Switch from STAGING to LIVE without restart
- `POST /go-staging` — Switch from LIVE to STAGING without restart
- `POST /pause` — Pause engine (loop stays alive, skips scanning)
- `POST /resume` — Resume from PAUSED to previous mode
- `GET /status` — Engine status + daily stats
- `GET /bets` — List auto/staged bets
- `PUT /settings` — Update engine settings
- `GET /plugins` — List plugins
- `PUT /plugins/{id}` — Update plugin settings
- `PUT /plugins/order` — Set plugin evaluation priority

**History** (`/api/history`):
- `GET /bets` — Filterable bet history (period, source, status)
- `GET /stats` — Stats for period (ROI, win rate, total staked)
- `GET /export` — CSV export
- `GET /decision-log` — Engine decision log

**WebSocket** (`/ws/prices`):
- Real-time bridge: stream price updates, market status, order updates, engine activity broadcasts

**Stream Management**:
- `POST /api/stream/start` — Start stream
- `POST /api/stream/stop` — Stop stream
- `GET /api/stream/status` — Connection status
- `GET /api/stream/cache` — Price cache summary

**Health**: `GET /health`

### Auto-Betting Engine

Background asyncio task that runs continuously (survives frontend tab close):

**Modes**:
- `STOPPED` — Not running
- `STAGING` — Full pipeline runs, bets recorded as `source=STAGED` (no real money)
- `LIVE` — Real bets placed via REST API (`source=AUTO`)
- `PAUSED` — Loop stays alive but skips scanning. Remembers previous mode for resume.

**Engine Flow** (every 2 seconds):
1. Read markets from stream price cache (primary) or REST API fallback
2. **Fetch catalogue metadata** on first scan and every 5 minutes — the Stream API does NOT provide runner names, venues, or market start times reliably. Cache runner names (`market_id → {selection_id → name}`), venues, and start times from REST `listMarketCatalogue`.
3. For each market: skip if already processed, closed, or in-play
4. Check duplicate — already bet on this market? (In LIVE mode, exclude STAGED bets from this check)
5. Build market info using cached catalogue metadata (venue, runner names, start time)
6. Run active plugins in priority order
7. If plugin returns ACCEPT with candidates:
   - STAGING mode → record simulated bet (`source=STAGED`)
   - LIVE mode → place real bet via REST API (`source=AUTO`)
8. Log every decision to decision_log table
9. Broadcast activity to frontend via WebSocket

**Staging → Live Transition**:
When switching from STAGING to LIVE:
- Clear `_processed_markets` set so markets are re-evaluated for real bets
- In LIVE mode, filter out STAGED bets from `today_bets` so they don't count towards per-race limits
- `has_bet_on_market()` accepts `exclude_staged` parameter to ignore STAGED bets

**REST API Fallback**:
When stream cache is empty, fetch markets via REST (`listMarketCatalogue` + `listMarketBook`). Convert REST response format to match stream cache format so the scanning loop works unchanged.

### Plugin System

**Base Plugin** (Abstract Base Class):
```python
class BasePlugin(ABC):
    def get_id(self) -> str
    def get_name(self) -> str
    def get_version(self) -> str
    def get_author(self) -> str
    def get_description(self) -> str
    def get_config(self) -> dict

    def evaluate(
        self,
        runners: list[dict],       # Live prices per runner
        market: dict,               # Market metadata
        daily_pnl: float,          # Today's P/L
        daily_exposure: float,     # Today's total liability
        bets_today: list[dict],    # Today's bets
        settings: dict,            # Engine settings
    ) -> PluginResult
```

**PluginResult**: `action` (ACCEPT/REJECT/SKIP), `candidates` (list of BetCandidate), `analysis`, `reason`

**BetCandidate**: `runner_name, selection_id, market_id, odds, stake, liability, zone, confidence, reason`

**Plugin Loader**: Discovers plugins in `plugins/` directory, manages enable/disable and priority ordering.

### Mark's Rule Set 1 Plugin

Lay betting strategy targeting odds range 3.00–4.49. Config stored in `marks_rule_1.json`.

**Rule 1 — Odds Filter**: Only accept 3.00 ≤ lay odds ≤ 4.49. Best lay = lowest price in the `atl` ladder.

**Rule 2 — Tiered Staking**:
- **PRIME** zone (3.50–3.99): £3 stake, HIGH confidence
- **STRONG** zone (3.00–3.49): £2 stake, MEDIUM-HIGH confidence
- **SECONDARY** zone (4.00–4.49): £2 stake, MEDIUM confidence

**Rule 3 — Time Filter**: If race is >420 minutes away, halve the stake (0.5x modifier). Betfair accepts £1 minimum lay bets, so PRIME £3 → £1.50, STRONG/SECONDARY £2 → £1.

**Rule 4 — Drift Filter** (monitoring mode): Track odds movement between placement and match. Warning at -5%, alert at -10%, critical at -20%. Currently logs only, does not auto-cancel.

**Rule 5 — Favourite Filter**: Skip the top 2 favourites in each race (runners with lowest lay odds). Laying favourites is higher risk because they win more often. Configurable via `skip_top_n` in config.

**Risk Management**:
- Max £9 liability per bet (`stake × (odds - 1)`)
- Max £75 daily exposure
- Daily stop-loss: halt at -£25
- Max 1 bet per race
- No limit on concurrent bets — bet on every qualifying race

**Candidate Selection**: If multiple runners qualify in a race, sort by zone priority (PRIME > STRONG > SECONDARY), take the best one (1 bet per race).

### Frontend Pages

**5 pages** with React Router:

1. **Login Page** — Betfair username/password form
2. **Account Page** — Balance, daily stats, account statement
3. **Manual Betting Page** — Market catalogue browser, runner prices, manual lay bet placement with bet slip
4. **Auto Betting Page** — Engine controls (mode selector: Live/Staged, Start/Pause/Stop buttons), plugin manager (enable/disable, configure, reorder priority), settings editor (max liability, daily exposure, stop-loss, concurrent bets), real-time activity log, staged/auto bets table with inline stats
5. **History Page** — Bet history table (filterable by period/source/status), stats dashboard (ROI, win rate), CSV export

**Layout**: Dark theme with `AppShell` wrapper (navbar + main content). Navbar shows logo, navigation links, engine running indicator, user menu.

**State Management** (Zustand stores):
- `auth` — Login state, session token, keepAlive timer
- `markets` — Market catalogue, live prices from WebSocket
- `auto` — Engine status, plugins, auto bets, activity log
- `betslip` — Manual bet slip state
- `toast` — Notification messages

**WebSocket Client**: Auto-reconnect with exponential backoff (max 30s), ping/pong heartbeat, handlers for price updates, market status, order updates, engine status, and engine activity.

**API Client**: Axios with base URL from `VITE_API_URL` env var, 401 interceptor triggers logout.

**Theme**: Dark navy background (`#0f0f1a`), golden accent (`#C8956C`), Tailwind CSS.

### Configuration

**Backend** (`config.py`):
```
BETFAIR_APP_KEY = "HTPjf4PpMGLksswf"  (App ID 137035, NO delay)
EVENT_TYPE_IDS = ["7"]                  (Horse Racing)
COUNTRY_CODES = ["GB", "IE"]
MARKET_TYPES = ["WIN"]
SESSION_TIMEOUT_HOURS = 12
CORS_ORIGINS = ["http://localhost:5173", "https://*.pages.dev", "https://lay3.thync.online"]
```

**Default Engine Settings**:
```
max_liability_per_bet: 9.00
max_daily_exposure: 75.00
daily_stop_loss: -25.00
max_concurrent_bets: 999  (effectively unlimited)
max_bets_per_race: 1
```

### Deployment

**Backend — Google Cloud Run**:
- Region: `europe-west2` (UK — required because Betfair geo-blocks non-UK/IE IPs)
- Dockerfile: Python 3.12-slim, gunicorn with 1 uvicorn worker
- Port 8080, 512Mi memory, 1 CPU
- Single instance (SQLite isn't multi-writer safe)

**Frontend — Cloudflare Pages**:
- Build: `npm run build`, output: `dist`
- Environment: `VITE_API_URL` and `VITE_WS_URL` pointing to Cloud Run URL

### Key Architecture Decisions

1. **Single-file SQLite** — Simple, no DB server needed. Single Cloud Run instance avoids write conflicts.
2. **Stream API as primary price source** — Real-time deltas, no polling. REST as fallback only.
3. **Runner name caching** — Stream API doesn't provide runner names. Fetch from REST catalogue on engine start, refresh every 5 minutes.
4. **Plugin architecture** — Strategies are pluggable. Engine evaluates all active plugins in priority order. Easy to add new strategies.
5. **STAGING mode** — Full pipeline without real money. Test strategies safely. Switch to LIVE without restart.
6. **State persistence** — Engine state (processed markets, settings, mode) persists in SQLite. Survives app restarts.
7. **Favourite filter** — Never lay the top 2 favourites in a race. They win too often.
8. **Staging/Live isolation** — STAGED bets don't block LIVE bets. Processed markets clear on mode switch.

### Important Betfair Notes

- Betfair accepts **£1 minimum** lay stakes (not £2)
- A single lay bet can be **split-matched** against multiple backers — this is normal exchange behaviour, not duplicate bets
- The `selectionId` from Betfair is always an **integer** — ensure type consistency when using as dict keys
- `listMarketCatalogue` with `RUNNER_DESCRIPTION` projection returns `runnerName` per runner
- Stream `marketDefinition.runners` only has `id` and `status` — NO names
- `persistence_type: "LAPSE"` means cancel unmatched portion at in-play transition
- Always use `from` time as now (UTC) for market catalogue to get today's upcoming markets

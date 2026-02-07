# CHIMERA v2 — Setup, Installation & Deployment Instructions

## Project Overview
This is a Betfair Exchange lay betting application for GB & IE horse racing WIN markets.
- **Backend**: Python FastAPI at `v2/backend/`
- **Frontend**: React 18 + TypeScript + Vite + Tailwind at `v2/frontend/`
- **Database**: SQLite (auto-created on first run)
- **Deployment**: Cloudflare Pages (frontend) + Google Cloud Run europe-west2 (backend)

---

## STEP 1: Backend Setup

```bash
cd /Users/charles/Projects/chimera-lay-app/v2/backend

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Test that it starts (database will auto-create)
uvicorn main:app --reload --port 8080
```

Verify by opening http://localhost:8080/docs — you should see the Swagger API docs.

---

## STEP 2: Frontend Setup

```bash
cd /Users/charles/Projects/chimera-lay-app/v2/frontend

# Install Node.js if not already installed
# (check with: node --version)
# If missing, install via Homebrew:
brew install node

# Install dependencies
npm install

# Create .env file for local development
cp .env.example .env

# Start dev server
npm run dev
```

The frontend dev server runs at http://localhost:5173 and proxies API calls to the backend at :8080 automatically (configured in vite.config.ts).

---

## STEP 3: Verify Local Development

1. Start backend: `cd v2/backend && source venv/bin/activate && uvicorn main:app --reload --port 8080`
2. Start frontend: `cd v2/frontend && npm run dev`
3. Open http://localhost:5173
4. Login with Betfair credentials
5. Check that markets load on the Manual Betting page
6. Check that the Auto Betting page shows Mark's Rule Set 1 plugin

---

## STEP 4: Critical Bug Fix — Pre-Race Timing

The old app placed bets at 5-7am for afternoon races, causing heavy losses by laying genuine contenders at unreliable early-morning odds.

In `v2/backend/services/auto_engine.py`, the `_scan_markets` method needs to enforce a pre-race window. Add a time-to-race check that **skips markets more than 30 minutes before race start**:

In the `_scan_markets` method, after the `inPlay` check and before the duplicate bet check, add:

```python
# Skip if too far from race start (only bet within pre-race window)
market_def = market_data.get("marketDefinition", {})
market_time_str = market_def.get("marketTime")
if market_time_str:
    try:
        mt = market_time_str.replace("Z", "+00:00")
        start = datetime.fromisoformat(mt)
        mins_to_race = (start - datetime.now(timezone.utc)).total_seconds() / 60
        pre_race_window = self._settings.get("pre_race_window_minutes", 30)
        if mins_to_race > pre_race_window or mins_to_race < 0:
            continue
    except (ValueError, TypeError):
        pass
```

Also add `pre_race_window_minutes: 30` to the default settings dict in `__init__`.

This ensures bets are only placed when the market is liquid and odds are meaningful — typically 5-30 minutes before off.

---

## STEP 5: Google Cloud Run Deployment (Backend)

The backend MUST be deployed in the UK (europe-west2) due to Betfair geo-blocking from South Africa.

### Prerequisites
- Google Cloud CLI installed (`brew install google-cloud-sdk`)
- A GCP project with billing enabled
- Docker installed

### Create the service

```bash
cd /Users/charles/Projects/chimera-lay-app/v2/backend

# Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Create Artifact Registry repository (one-time)
gcloud artifacts repositories create chimera \
  --repository-format=docker \
  --location=europe-west2 \
  --description="Chimera container images"

# Build and push Docker image
gcloud builds submit --tag europe-west2-docker.pkg.dev/YOUR_PROJECT_ID/chimera/backend:latest

# Deploy to Cloud Run
gcloud run deploy chimera-v2 \
  --image europe-west2-docker.pkg.dev/YOUR_PROJECT_ID/chimera/backend:latest \
  --region europe-west2 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 1 \
  --timeout 300 \
  --set-env-vars "DATABASE_PATH=/data/chimera.db"
```

### Persistent Storage
Cloud Run is stateless — the SQLite database will be lost on redeployment. For persistent storage, add a Cloud Storage FUSE mount or switch to a Cloud SQL instance. For now, the simplest approach:

1. Create a Google Cloud Storage bucket: `gsutil mb -l europe-west2 gs://chimera-v2-data/`
2. Mount it via Cloud Run volume mounts, OR
3. Add periodic database backup to GCS in the application

Note the deployed URL (e.g. `https://chimera-v2-XXXXX-nw.a.run.app`) — you'll need it for the frontend.

---

## STEP 6: Cloudflare Pages Deployment (Frontend)

### Prerequisites
- Cloudflare account
- Wrangler CLI: `npm install -g wrangler`

### Build and deploy

```bash
cd /Users/charles/Projects/chimera-lay-app/v2/frontend

# Set the production API URL (your Cloud Run URL from Step 5)
# Create .env.production file:
echo "VITE_API_URL=https://YOUR-CLOUD-RUN-URL" > .env.production
echo "VITE_WS_URL=wss://YOUR-CLOUD-RUN-URL/ws/prices" >> .env.production

# Build for production
npm run build

# Deploy to Cloudflare Pages
wrangler pages deploy dist --project-name chimera-lay-v2
```

Or connect via GitHub:
1. Push to GitHub
2. In Cloudflare Dashboard → Pages → Create Project → Connect to GitHub
3. Build settings: Framework = Vite, Build command = `npm run build`, Output directory = `dist`
4. Add environment variables: `VITE_API_URL` and `VITE_WS_URL`

### Custom Domain
If using `lay2.thync.online`:
1. In Cloudflare Pages project → Custom Domains → Add `lay2.thync.online`
2. It will auto-configure DNS if the domain is on Cloudflare

---

## STEP 7: CORS Configuration

After deployment, update `v2/backend/config.py` to include your production frontend URL in `CORS_ORIGINS`:

```python
CORS_ORIGINS: list = field(default_factory=lambda: [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://chimera-lay-v2.pages.dev",
    "https://lay2.thync.online",
])
```

Then redeploy the backend.

---

## STEP 8: Optional — Claude API for AI Analysis

If you want AI analysis on the History page:

1. Get an Anthropic API key from https://console.anthropic.com
2. Set it as an environment variable on Cloud Run:

```bash
gcloud run services update chimera-v2 \
  --region europe-west2 \
  --set-env-vars "ANTHROPIC_API_KEY=sk-ant-xxxxx"
```

---

## Environment Variables Summary

### Backend (Cloud Run)
| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_PATH` | Path to SQLite file | Yes (default: `chimera.db`) |
| `BETFAIR_APP_KEY` | Betfair API key | Yes (hardcoded default) |
| `ANTHROPIC_API_KEY` | Claude API key for AI analysis | No |

### Frontend (Cloudflare Pages)
| Variable | Description | Required |
|----------|-------------|----------|
| `VITE_API_URL` | Backend URL (Cloud Run) | Yes |
| `VITE_WS_URL` | WebSocket URL | Yes |

---

## File Structure Reference

```
v2/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Configuration
│   ├── database.py           # SQLite schema & operations
│   ├── models.py             # Pydantic models
│   ├── Dockerfile            # Cloud Run container
│   ├── requirements.txt      # Python dependencies
│   ├── routers/              # API endpoint handlers
│   │   ├── auth.py           # Login/logout/keepAlive
│   │   ├── markets.py        # Market catalogue & book
│   │   ├── orders.py         # Place/cancel bets
│   │   ├── account.py        # Balance & statement
│   │   ├── auto_betting.py   # Engine control & plugins
│   │   ├── history.py        # History, stats, export, AI
│   │   └── websocket.py      # WS price bridge
│   ├── services/             # Business logic
│   │   ├── betfair_client.py # Betfair REST API
│   │   ├── stream_client.py  # Betfair Stream API (SSL)
│   │   ├── stream_manager.py # Price cache & WS bridge
│   │   ├── auto_engine.py    # Background betting engine
│   │   └── plugin_loader.py  # Plugin discovery
│   └── plugins/              # Strategy plugins
│       ├── base.py           # BasePlugin ABC
│       ├── marks_rule_1.py   # Mark's Rule Set 1
│       └── marks_rule_1.json # Strategy config
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Router, auth guard, WS
│   │   ├── main.tsx          # React entry
│   │   ├── index.css         # Tailwind + custom theme
│   │   ├── pages/            # 5 page components
│   │   ├── components/       # Shared UI components
│   │   ├── store/            # 5 Zustand stores
│   │   ├── lib/              # API client, WS client, utils
│   │   └── types/            # TypeScript types
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
```

# Yt Creator Helper (Creator Growth Lab)

An end-to-end YouTube channel analysis tool with a web UI and a Python “intelligence” backend.

- **UI:** ASP.NET Core MVC app with Identity (login/register) + SQLite.
- **API:** FastAPI service that pulls data from the YouTube Data API, runs an ML pipeline (embeddings + clustering), generates insights, and saves results to JSON.

This README focuses on the **pipeline**: what happens when you click **Analyze**, what “model/LLM” components are used, and where outputs are stored.

---

## Architecture (high level)

**Projects**

- `CreatorGrowthLab.UI/` — ASP.NET Core MVC web app (net9.0)
- `Python/cgl_api/` — FastAPI backend

**Default URLs/ports**

- UI: `http://localhost:5080` (or `https://localhost:7268`)
- API: `http://127.0.0.1:8000`

---

## The pipeline (what the backend does)

When you submit an analysis from the Dashboard, the UI calls the FastAPI backend, which runs this pipeline:

### 0) Input

The request includes:

- `channel_id` (must start with `UC...`)
- `n_videos`
- `baseline_window`

### 1) Resolve channel id (optional)

If you only have a handle/URL (like `@someCreator`), the UI uses:

- `GET /resolve/channel-id?url_or_handle=...`

### 2) Fetch + cache raw channel/video data

The backend uses the YouTube Data API (requires `YOUTUBE_API_KEY`) to fetch:

- Channel identity (title + thumbnail)
- Uploads playlist id
- Latest `n_videos` video ids
- Video details: title, publish time, views/likes/comments, duration

Raw responses are cached under `Python/cgl_api/data/raw/` to reduce repeated API calls.

### 3) KPIs + baseline normalization

- Compute `views_per_day` per video (with a capped window)
- Compute a baseline (median `views_per_day` over the most recent `baseline_window` videos)
- Compute `relative_performance = views_per_day / baseline`

### 4) Feature engineering (non-LLM)

The backend derives features from titles and timestamps (no LLM):

- Title length, word count, caps ratio, emoji count, punctuation flags
- Publish hour/day-of-week/weekend
- Engagement/like/comment rates

### 5) Topic discovery (ML: embeddings + clustering)

This is the core “model” stage.

1. **Embeddings:** encode titles using `sentence-transformers`.
  - Model: `all-MiniLM-L6-v2`
2. **Clustering:** group embeddings into topics using `HDBSCAN` over cosine distances.
3. **Topic scoring:** compute topic summaries (avg/median performance, volatility, momentum, fatigue) and derive a human-readable verdict (e.g., Rising Bet / Fading Idea / Reliable Performer).

### 6) Topic labeling (optional LLM)

After topics are discovered, the backend tries to generate a short label for each cluster.

- If `GEMINI_API_KEY` is set, it uses Gemini to produce a 2–5 word label from example titles.
- Labels are cached in `Python/topic_label_cache.json` to avoid repeated calls.
- If an LLM key isn’t configured or the call fails, labeling falls back to a simple/default label.

### 7) Perception signals (heuristics)

The backend also emits simple, rule-based “perception signals” from titles (not an LLM), e.g. spam-like capitalization, money-bait symbols, overly long titles.

### 8) Persist + return

The backend returns the full `AnalyticsResponse` and also writes it to:

- `Python/cgl_api/data/results/<channelId>_<timestamp>.json`

The UI History page reads those saved JSON files.

---

## API endpoints

- `GET /health` — health check
- `GET /resolve/channel-id?url_or_handle=...` — resolve handle/url → channel id
- `POST /analyze/channel` — run the full pipeline and return an `AnalyticsResponse`

---

## Prerequisites

- **.NET SDK 9** (because the UI targets `net9.0`)
- **Python 3.10+** (3.11 recommended)
- A **YouTube Data API key** in `YOUTUBE_API_KEY`

Optional:

- `GEMINI_API_KEY` to enable Gemini topic labeling (otherwise labels fall back)

---

## Quickstart (local dev)

### 1) Start the FastAPI backend

From the repo root:

```powershell
cd .\Python\cgl_api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `Python/.env` (this location is important: the backend loads `.env` from the `Python/` folder):

```env
YOUTUBE_API_KEY=YOUR_KEY_HERE
GEMINI_API_KEY=OPTIONAL_KEY_HERE
```

Run the API:

```powershell
python -m uvicorn cgl_api.main:app --reload --host 127.0.0.1 --port 8000
```

It should start on `http://127.0.0.1:8000`.

### 2) Start the ASP.NET Core UI

In a new terminal:

```powershell
cd .\CreatorGrowthLab.UI
dotnet restore
```

Create/update the local SQLite DB (Identity tables) using EF Core migrations:

```powershell
# If you don't have dotnet-ef installed
dotnet tool install --global dotnet-ef

# Apply migrations
dotnet ef database update
```

Run the UI:

```powershell
dotnet run
```

Then open:

- `http://localhost:5080` (HTTP)
- `https://localhost:7268` (HTTPS)

---

## Configuration

### UI config (`CreatorGrowthLab.UI/appsettings.json`)

- `AnalyticsApi:BaseUrl`
  - Default: `http://127.0.0.1:8000`
  - Points the UI’s `AnalyticsApiClientService` to the FastAPI backend.

- `AnalyticsStorage:ResultsDir`
  - Default: `../Python/cgl_api/data/results`
  - Where the UI looks for saved JSON runs (used by History).

- `ConnectionStrings:Default`
  - Default: `Data Source=app.db`
  - SQLite file for Identity + app data.

### Backend config (`Python/cgl_api/core/config.py`)

- `YOUTUBE_API_KEY`
  - Must be set (env var or `Python/.env`). Backend throws if missing.

- `GEMINI_API_KEY` (optional)
  - Enables Gemini-powered topic labeling.

---

## Troubleshooting

### `WinError 10013` when starting uvicorn on port 8000

This usually means **port 8000 is already in use** by another process (often an earlier uvicorn run).

Check what owns the port:

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Then stop the old process (replace PID):

```powershell
Stop-Process -Id <PID> -Force
```

---

## Project layout (pipeline map)

- `CreatorGrowthLab.UI/Controllers/`
  - `DashboardController` — analysis UI and API calls
  - `ResolveController` — resolve handle/url → channel id
  - `HistoryController` — list and view saved runs

- `CreatorGrowthLab.UI/services/`
  - `AnalyticsApiClientService` — HTTP client for the FastAPI backend
  - `AnalyticsRunStore` — reads saved JSON results for History

- `Python/cgl_api/routers/`
  - `health.py`, `request.py`, `resolve.py`

- `Python/cgl_api/services/`
  - `youtube_service.py` — YouTube Data API calls + caching
  - `feature_service.py` — engineered features (no ML)
  - `topic_service.py` — embeddings + clustering + topic performance + verdict rules
  - `topic_labeler.py` — optional LLM topic naming + caching
  - `perception_service.py` — heuristic “perception signals” from titles
  - `analytics_service.py` — orchestrates the pipeline, writes results JSON

---

## Common issues

- **Backend fails on startup with `YOUTUBE_API_KEY is not set...`**
  - Add `YOUTUBE_API_KEY` to `Python/.env` or set it in your environment.

- **UI shows API unhealthy**
  - Confirm the backend is running on `http://127.0.0.1:8000`.
  - If you changed the API port, update `AnalyticsApi:BaseUrl`.

- **History is empty**
  - Run at least one analysis first.
  - Confirm `AnalyticsStorage:ResultsDir` points to the backend’s results directory.

---

## Improvements (pipeline-focused)

### Correctness / consistency

- Align request defaults: UI defaults `n_videos=30` while backend defaults to `50`.
- Generate shared contracts (OpenAPI → C#) to avoid response/schema drift.
- Add versioning to saved result files so History can survive schema changes.

### Reliability / quotas

- Add rate limiting + backoff for YouTube API calls to reduce quota failures.
- Add a run-cache keyed by `(channel_id, n_videos, baseline_window)` to skip recomputation.
- Persist run metadata in SQLite instead of scanning a folder if History grows.

### Model/LLM quality

- Improve topic embeddings by including descriptions/tags (not only titles).
- Add evaluation signals (topic coherence/stability) and log them per run.
- Add an optional LLM summarization step (3 bullets of “what to do next”) behind a feature flag.

### DevEx

- Add `Python/.env.example` documenting `YOUTUBE_API_KEY` / `GEMINI_API_KEY`.
- Add a PowerShell script to start UI + API together.
- Add CI: `dotnet build` + a minimal API import/test run.

---

## License

Internal/unspecified. Add a license file if you plan to publish this.

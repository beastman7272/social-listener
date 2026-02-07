
# Social Listener (Reddit-first, Flask + SQLite, HITL)

A small, self-hosted social listening app that monitors public Reddit discussions in a configurable set of subreddits, performs a low-cost keyword/rule pass, and (optionally) uses OpenAI to generate a **binary relevance decision** plus a **suggested draft response** for human review.

This project is **Human-in-the-Loop (HITL)**: it **does not post** to Reddit or any other platform.

---

## For Reddit reviewers (what this app does / does not do)

### What it does
- Reads **public content** from specified subreddits (posts + comments).
- Stores the content in a local SQLite database for review.
- Performs a **cheap rule stage** (keywords/phrases + simple location heuristics).
- When configured and permitted, runs a **delta-based GenAI stage**:
  - Only when policy triggers are met (cooldowns, max evals, new comments).
  - Produces: `relevant` (0/1), short reason, optional detections, and a draft reply.
- Presents flagged items in a web UI for human review (copy/edit/save draft).

### What it does NOT do
- **No posting, replying, voting, messaging, or moderation actions**
- **No automation of user interactions**
- **No scraping of private communities**
- **No bypassing Reddit controls**
- **No collection of non-public user data**

### Rate / cost controls
- Uses an explicit `REDDIT_USER_AGENT`
- Designed for limited scope (small list of subreddits)
- GenAI calls are limited by policy:
  - max evaluations per thread
  - cooldown minutes
  - delta-only evaluation (new comments)
  - truncation of delta comments sent

### Credentials status
Reddit ingestion is scaffolded to use environment variables. If Reddit API credentials are missing, the ingest script exits cleanly without writing partial data.

---

## Features (V1)
- Flask server-rendered UI (Jinja)
- SQLite persistence (local file in `instance/`)
- Thread model = post + all comments
- Rules stage:
  - `(any service keyword) AND (any intent phrase)`
  - optional negative keywords (block)
  - simple in-area/unknown inference
- Watching window:
  - threads enter “watching” after first rule hit
  - active window defaults to 5 days (configurable)
- GenAI stage (optional):
  - delta-based triggers + dedupe
  - suggested draft response + detections
- HITL dashboard:
  - flagged queue
  - editable drafts (Save + Copy)

---

## Repo layout

app/
routes/ # Flask routes (UI + minimal POST for draft save)
services/ # Rules + GenAI evaluator
collectors/ # Reddit client/collector (PRAW)
repo/ # SQLite persistence (schema, reads, writes)
templates/ # Jinja templates
static/ # Minimal assets
scripts/ # init_db, seed_config, run_ingest_reddit
instance/ # local SQLite DB (ignored by git)
docs/ # PRD, architecture, data model, specs, wireframes

---

## Quickstart (dev)

1) Create and activate venv (WSL/Linux/macOS)

python3 -m venv .venv
source .venv/bin/activate

2) Install dependencies

pip install -r requirements.txt

3) Environment variables
Copy the example env file and edit it locally:

cp .env.example .env

Set at least:
REDDIT_USER_AGENT (required)
REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET (required to ingest)
OPENAI_API_KEY (required only to run GenAI stage)

Notes:
.env is ignored by git.
If Reddit creds are missing, ingestion exits cleanly.
If OpenAI key is missing, ingestion continues and skips GenAI.

4) Initialize the database

python -m scripts.init_db

5) Seed default config (recommended)

python -m scripts.seed_config

6) Run the web app

python app.py

Then open:
http://127.0.0.1:5000/queue
http://127.0.0.1:5000/threads
http://127.0.0.1:5000/runs

7) Run ingestion

python -m scripts.run_ingest_reddit

Configuration

Config is stored in the SQLite config table (JSON strings / scalars). Common keys:
subreddits (JSON list)
keywords_include (JSON list)
keywords_intent (JSON list)
keywords_negative (JSON list)
include_unknown_location (true/false)
active_window_days (int)

GenAI policy keys (seed script sets defaults):
max_genai_evals_per_thread
genai_cooldown_minutes
delta_min_new_comments
max_delta_comments_sent

Security & privacy

Designed for local/self-hosted operation
No secrets are committed to the repo
No auto-posting or automated user interaction
OpenAI calls are optional and policy-gated
Store only what you ingest locally (SQLite)

Responsible Builder Compliance: Includes a dedicated cleanup script (scripts/compliance_cleanup.py) that uses PRAW to verify content status. It hard-deletes any local SQLite records (posts/comments) within 48 hours if they are removed from Reddit, satisfying the platform’s data retention policy.

License

Add your preferred license (MIT/Apache-2.0/etc.). If unsure, MIT is common for small tooling repos.



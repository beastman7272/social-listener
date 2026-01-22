# Dev

## Initialize the database

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
```

## Environment variables

Create a local `.env` file (not committed) and fill in Reddit credentials:

```bash
cp .env.example .env
```

Required for ingestion:

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`

Optional for now:

- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`

## Run the app

```bash
source .venv/bin/activate
python app.py
```

## Run Reddit ingest (manual)

```bash
source .venv/bin/activate
python scripts/run_ingest_reddit.py
```

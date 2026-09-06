# Job Scraper (JSearch + Jooble)

Fetches job listings from JSearch (RapidAPI) and Jooble, then saves them to:
- `data/jobs_results.json`
- `data/jobs.db` (SQLite)

## 1. Setup

1. Copy `.env.example` to `.env` and fill in your real keys:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env`:
   ```
   RAPIDAPI_KEY=xxxx
   RAPIDAPI_HOST=jsearch.p.rapidapi.com
   JOOBLE_KEY=xxxx
   ```

## 2. Run locally (without Docker)

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 3. Run with Docker

Build the image:
```bash
docker build -t job-scraper .
```

Run it, mounting a local `data/` folder so the output survives after the container exits, and passing your `.env` file in:
```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  job-scraper
```

After it finishes, check `./data/jobs_results.json` and `./data/jobs.db` on your machine.

## 4. Inspect the SQLite database

```bash
sqlite3 data/jobs.db "SELECT job_title, company, city FROM jobs LIMIT 5;"
```

## Project structure

```
job_scraper/
├── main.py            # extraction script
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .env.example        # template — copy to .env, never commit .env
└── data/                # created at runtime, holds jobs.db + jobs_results.json
```

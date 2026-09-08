import os
import re
import json
import sqlite3
import time
from pathlib import Path
from dotenv import load_dotenv
import requests

# ==========================================
# 1. Setup: paths + environment variables
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(dotenv_path=BASE_DIR / ".env")
RAPID_KEY = os.getenv("RAPIDAPI_KEY")
RAPID_HOST = os.getenv("RAPIDAPI_HOST", "jsearch.p.rapidapi.com")
JOOBLE_KEY = os.getenv("JOOBLE_KEY")

DB_PATH = DATA_DIR / "jobs.db"
JSON_PATH = DATA_DIR / "jobs_results.json"

all_jobs = []

# Add near the top with your other constants
COMMON_SKILLS = [
    # Testing & QA
    "Manual Testing", "Automation Testing", "Selenium", "TestNG", "JUnit",
    "Postman", "API Testing", "Regression Testing", "Test Cases", "QA",
    "Quality Assurance", "Cypress", "Appium", "Load Testing", "Performance Testing",
    "Bug Tracking", "Test Automation Framework",

    # Data
    "SQL", "Python", "Excel", "Power BI", "Tableau", "Data Analysis",
    "Data Visualization", "ETL", "Machine Learning", "Data Cleaning",
    "Pandas", "NumPy", "R", "Statistics",

    # Dev/General tech
    "Java", "JavaScript", "C++", "C#", "Node.js", "React", "REST API",
    "Git", "GitHub", "Docker", "Kubernetes", "AWS", "Azure", "Linux",
    "Agile", "Scrum", "Jira", "CI/CD",
]


def extract_skills_from_text(text):
    """
    Extract known skills from free text (job description) using
    word-boundary regex matching so short tokens like 'R' or 'QA'
    don't match inside unrelated words.
    """
    if not text:
        return "N/A"
    text_lower = text.lower()
    found = [
        skill for skill in COMMON_SKILLS
        if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text_lower)
    ]
    return ", ".join(found) if found else "N/A"


# ==========================================
# 2. Fetch jobs from JSearch API
# ==========================================
def fetch_jsearch():
    if not RAPID_KEY:
        print("⚠️  RAPIDAPI_KEY not set, skipping JSearch.")
        return

    print("⏳ Fetching jobs from JSearch...")
    url = "https://jsearch.p.rapidapi.com/search-v2"
    headers = {
        "x-rapidapi-key": RAPID_KEY.strip(),
        "x-rapidapi-host": RAPID_HOST.strip(),
    }
    params = {
        "query": "Software Quality Assurance OR Data in Saudi Arabia",
        "page": "1",
        "num_pages": "1",
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=30)
        if res.status_code != 200:
            print(f"⚠️  JSearch failed (status {res.status_code}): {res.text}")
            return

        data = res.json().get("data", {}).get("jobs", [])
        for job in data:
            min_salary = job.get("job_min_salary")
            max_salary = job.get("job_max_salary")
            currency = job.get("job_salary_currency", "")
            period = job.get("job_salary_period", "")
            if min_salary or max_salary:
                parts = []
                if min_salary:
                    parts.append(str(min_salary))
                if max_salary:
                    parts.append(str(max_salary))
                salary = f"{' - '.join(parts)} {currency} / {period}".strip()
            else:
                salary = "N/A"

            # Prefer the structured skills field from the API when present;
            # only fall back to keyword-matching the full description text
            # if that field is empty.
            description = job.get("job_description", "")
            skills_list = job.get("job_required_skills")
            if isinstance(skills_list, list) and skills_list:
                skills = ", ".join(skills_list)
            elif skills_list:
                skills = str(skills_list)
            else:
                skills = extract_skills_from_text(description)

            exp = job.get("job_required_experience")
            if not isinstance(exp, dict):
                exp = {}

            if exp.get("no_experience_required"):
                experience_level = "No experience required"
            elif exp.get("required_experience_in_months"):
                experience_level = f"{exp.get('required_experience_in_months')} months experience"
            elif exp.get("experience_mentioned"):
                experience_level = "Experience mentioned (unspecified)"
            else:
                experience_level = "N/A"

            all_jobs.append({
                "source": "JSearch",
                "job_title": job.get("job_title"),
                "company": job.get("employer_name"),
                "city": job.get("job_city", "N/A"),
                "location": f"{job.get('job_city', '')}, {job.get('job_country', '')}".strip(", "),
                "employment_type": job.get("job_employment_type"),
                "salary": salary,
                "skills": skills,
                "experience_level": experience_level,
                "apply_link": job.get("job_apply_link"),
                "posted_at": job.get("job_posted_at_datetime_utc"),
                "description": description if description else "N/A",
            })
        print(f"✔️  Fetched {len(data)} jobs from JSearch.")

    except Exception as e:
        print(f"❌ Error connecting to JSearch: {e}")


# ==========================================
# 3. Fetch jobs from Jooble API
# ==========================================
def fetch_jooble():
    if not JOOBLE_KEY:
        print("⚠️  JOOBLE_KEY not set, skipping Jooble.")
        return

    print("⏳ Fetching jobs from Jooble...")
    url = f"https://sa.jooble.org/api/{JOOBLE_KEY.strip()}"
    payload = {"keywords": "Software Quality Assurance", "location": "Saudi Arabia"}
    try:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code != 200:
            print(f"⚠️  Jooble failed (status {res.status_code}): {res.text}")
            return
        data = res.json().get("jobs", [])
        for job in data:
            # Jooble's "snippet" is the closest thing to a description here.
            description = job.get("snippet", "")
            all_jobs.append({
                "source": "Jooble",
                "job_title": job.get("title"),
                "company": job.get("company"),
                "city": job.get("location", "N/A"),
                "location": job.get("location"),
                "employment_type": job.get("type", "N/A"),
                "salary": job.get("salary", "N/A"),
                "skills": extract_skills_from_text(description),
                "experience_level": "N/A",
                "apply_link": job.get("link"),
                "posted_at": job.get("updated"),
                "description": description if description else "N/A",
            })
        print(f"✔️  Fetched {len(data)} jobs from Jooble.")
    except Exception as e:
        print(f"❌ Error connecting to Jooble: {e}")


# ==========================================
# 4. Save results to SQLite
# ==========================================
def save_to_sqlite(jobs):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            job_title TEXT,
            company TEXT,
            city TEXT,
            location TEXT,
            employment_type TEXT,
            salary TEXT,
            skills TEXT,
            experience_level TEXT,
            apply_link TEXT UNIQUE,
            posted_at TEXT,
            fetched_at TEXT,
            description TEXT
        )
    """)
    fetched_at = time.strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for job in jobs:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO jobs
                (source, job_title, company, city, location, employment_type,
                 salary, skills, experience_level, apply_link, posted_at, fetched_at,
                 description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("source"), job.get("job_title"), job.get("company"),
                job.get("city"), job.get("location"), job.get("employment_type"),
                job.get("salary"), job.get("skills"), job.get("experience_level"),
                job.get("apply_link"), job.get("posted_at"), fetched_at,
                job.get("description", "N/A"),
            ))
            if cur.rowcount:
                inserted += 1
        except sqlite3.Error as e:
            print(f"⚠️  DB insert error: {e}")
    conn.commit()
    conn.close()
    return inserted


# ==========================================
# 5. Save results to JSON
# ==========================================
def save_to_json(jobs):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


# ==========================================
# 6. Inspection helpers (run only if you ask for them)
# ==========================================
def show_db_summary():
    """Prints row counts and a sample of stored jobs. Safe to call
    any time AFTER the jobs table has been created (i.e. after main())."""
    if not DB_PATH.exists():
        print("ℹ️  No database found yet. Run main() first.")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM jobs")
        print("Total rows in DB:", cur.fetchone())

        cur.execute("SELECT COUNT(*), COUNT(DISTINCT apply_link) FROM jobs")
        print("Total vs distinct apply_link:", cur.fetchone())

        cur.execute("SELECT source, apply_link FROM jobs LIMIT 10")
        for row in cur.fetchall():
            print(row)
    except sqlite3.OperationalError as e:
        print(f"ℹ️  Could not read jobs table: {e}")
    finally:
        conn.close()


def show_json_skills():
    """Prints job titles + extracted skills from the saved JSON file.
    Safe to call any time AFTER save_to_json() has run."""
    if not JSON_PATH.exists():
        print("ℹ️  No JSON results found yet. Run main() first.")
        return
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    for job in jobs:
        print(f"[{job['source']}] {job['job_title']}")
        print(f"   skills: {job['skills']}")
        print()


# ==========================================
# 7. Main
# ==========================================
def main():
    fetch_jsearch()
    fetch_jooble()

    if not all_jobs:
        print("\n❌ No results found. Check your API keys in the .env file.")
        return

    save_to_json(all_jobs)
    inserted = save_to_sqlite(all_jobs)

    print("\n" + "=" * 50)
    print(f"🎉 Saved {len(all_jobs)} jobs total.")
    print(f"   JSON  -> {JSON_PATH}")
    print(f"   SQLite -> {DB_PATH} ({inserted} new rows inserted)")
    print("=" * 50)
    print("\nSample:")
    for job in all_jobs[:5]:
        print(f" - [{job['source']}] {job['job_title']} @ {job['company']} ({job['city']})")


if __name__ == "__main__":
    main()

    # Optional: uncomment these to inspect results after a run.
    print(show_db_summary())
    print(show_json_skills())
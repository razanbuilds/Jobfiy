import os
import re
import json
import sqlite3
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# 1. Setup
# ============================================================

try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd()

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "jobs.db"
JSON_PATH = DATA_DIR / "jobs_results.json"

load_dotenv(dotenv_path=BASE_DIR / ".env")

RAPID_HOST = os.getenv(
    "RAPIDAPI_HOST",
    "jsearch.p.rapidapi.com"
)

RAPID_KEY = os.getenv("RAPIDAPI_KEY")


# Databricks Secret fallback
if not RAPID_KEY:
    try:
        RAPID_KEY = dbutils.secrets.get(
            scope="job-pipeline-secrets",
            key="RAPIDAPI_KEY"
        )
    except Exception as e:
        print(
            "Could not load RAPIDAPI_KEY "
            f"from Databricks Secrets: {e}"
        )


all_jobs = []


# ============================================================
# 2. Constants
# ============================================================

SAUDI_CITIES = [
    "Riyadh",
    "Jeddah",
    "Mecca",
    "Makkah",
    "Medina",
    "Madinah",
    "Dammam",
    "Khobar",
    "Al Khobar",
    "Dhahran",
    "Hofuf",
    "Al Hofuf",
    "Hafar Al-Batin",
    "Jubail",
    "Tabuk",
    "Abha",
    "Khamis Mushait",
    "Taif",
    "Yanbu",
    "Najran",
    "Jizan",
    "Buraidah",
    "Qassim",
    "Al Ahsa",
]


COMMON_SKILLS = [
    # Testing / QA
    "Manual Testing",
    "Automation Testing",
    "Selenium",
    "TestNG",
    "JUnit",
    "Postman",
    "API Testing",
    "Regression Testing",
    "Test Cases",
    "QA",
    "Quality Assurance",
    "Cypress",
    "Appium",
    "Load Testing",
    "Performance Testing",
    "Bug Tracking",
    "Test Automation Framework",

    # Data
    "SQL",
    "Python",
    "Excel",
    "Power BI",
    "Tableau",
    "Data Analysis",
    "Data Analytics",
    "Data Visualization",
    "ETL",
    "Machine Learning",
    "Data Cleaning",
    "Pandas",
    "NumPy",
    "R",
    "Statistics",
    "Spark",
    "PySpark",
    "Databricks",
    "Snowflake",

    # Development
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "C#",
    "Node.js",
    "React",
    "REST API",
    "Git",
    "GitHub",

    # Cloud / DevOps
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "Linux",
    "DevOps",
    "CI/CD",

    # Project / Agile
    "Agile",
    "Scrum",
    "Jira",

    # Cybersecurity
    "Cybersecurity",
    "Information Security",
    "Network Security",
]


# ============================================================
# 3. Helper functions
# ============================================================

def join_non_empty(parts, separator=", "):
    cleaned_parts = [
        str(part).strip()
        for part in parts
        if str(part).strip()
    ]
    return separator.join(cleaned_parts)


def extract_skills_from_text(text):
    """
    Extract known technical skills from title + description.
    """

    if not text:
        return "N/A"

    text_lower = str(text).lower()
    found = []

    for skill in COMMON_SKILLS:
        pattern = (
            r"\b"
            + re.escape(skill.lower())
            + r"\b"
        )

        if re.search(pattern, text_lower):
            found.append(skill)

    # Remove duplicates while keeping order
    found = list(dict.fromkeys(found))

    return join_non_empty(found) if found else "N/A"


# ============================================================
# 4. JSearch
# ============================================================

def fetch_jsearch():

    if not RAPID_KEY:
        print(
            "⚠️ RAPIDAPI_KEY not set. "
            "Skipping JSearch."
        )
        return

    print("\n⏳ Fetching jobs from JSearch...")

    url = (
        "https://jsearch.p.rapidapi.com/"
        "search-v2"
    )

    headers = {
        "x-rapidapi-key": RAPID_KEY,
        "x-rapidapi-host": RAPID_HOST,
        "Content-Type": "application/json",
    }

    params = {
        "query": "technology jobs",
        "num_pages": "1",
        "country": "sa",
        "date_posted": "all",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60,
        )

        if response.status_code != 200:
            print(
                "⚠️ JSearch failed "
                f"(status {response.status_code})"
            )
            print(response.text[:500])
            return

        response_data = response.json()

        jobs = (
            response_data
            .get("data", {})
            .get("jobs", [])
        )

        # One timestamp for this API run
        fetched_at = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        added = 0

        for job in jobs:

            # ------------------------------------------------
            # Title / description
            # ------------------------------------------------

            job_title = (
                job.get("job_title")
                or "N/A"
            )

            description = (
                job.get("job_description")
                or "N/A"
            )

            text_for_skills = (
                f"{job_title} {description}"
            )

            # ------------------------------------------------
            # Salary
            # ------------------------------------------------

            min_salary = job.get(
                "job_min_salary"
            )

            max_salary = job.get(
                "job_max_salary"
            )

            currency = (
                job.get("job_salary_currency")
                or ""
            )

            period = (
                job.get("job_salary_period")
                or ""
            )

            if (
                min_salary is not None
                or max_salary is not None
            ):
                salary_parts = []

                if min_salary is not None:
                    salary_parts.append(
                        str(min_salary)
                    )

                if max_salary is not None:
                    salary_parts.append(
                        str(max_salary)
                    )
                salary = join_non_empty(
                    salary_parts,
                    separator=" - "
                )

                if currency:
                    salary += f" {currency}"

                if period:
                    salary += f" / {period}"

            else:
                salary = "N/A"

            # ------------------------------------------------
            # Skills
            # ------------------------------------------------

            skills_list = job.get(
                "job_required_skills"
            )

            if (
                isinstance(skills_list, list)
                and skills_list
            ):
                skills = join_non_empty(
                    skills_list
                )

            elif skills_list:
                skills = str(skills_list)

            else:
                skills = extract_skills_from_text(
                    text_for_skills
                )

            # ------------------------------------------------
            # Experience
            # ------------------------------------------------

            experience = job.get(
                "job_required_experience"
            )

            if not isinstance(
                experience,
                dict
            ):
                experience = {}

            if experience.get(
                "no_experience_required"
            ):
                experience_level = (
                    "No experience required"
                )

            elif experience.get(
                "required_experience_in_months"
            ):
                months = experience.get(
                    "required_experience_in_months"
                )

                experience_level = (
                    f"{months} months experience"
                )

            elif experience.get(
                "experience_mentioned"
            ):
                experience_level = (
                    "Experience mentioned "
                    "(unspecified)"
                )

            else:
                experience_level = "N/A"

            # ------------------------------------------------
            # Location
            # ------------------------------------------------

            city = job.get("job_city")
            country = job.get("job_country")

            if country == "SA":
                country = "Saudi Arabia"

            location_parts = []

            if city:
                location_parts.append(
                    str(city).strip()
                )

            if country:
                location_parts.append(
                    str(country).strip()
                )

            location = (
                join_non_empty(location_parts)
                if location_parts
                else "N/A"
            )

            # ------------------------------------------------
            # Posted date
            # ------------------------------------------------

            # JSearch search-v2 may return relative Arabic
            # values such as "قبل يومين".
            # We preserve the source value here.
            posted_at = (
                job.get("job_posted_at")
                or "N/A"
            )

            # ------------------------------------------------
            # Apply link
            # ------------------------------------------------

            apply_link = (
                job.get("job_apply_link")
                or job.get("job_google_link")
                or ""
            )

            # ------------------------------------------------
            # Normalized record
            # ------------------------------------------------

            normalized_job = {
                "source": "JSearch",
                "job_title": job_title,

                "company": (
                    job.get("employer_name")
                    or "N/A"
                ),

                "city": city or "N/A",
                "location": location,

                "employment_type": (
                    job.get(
                        "job_employment_type"
                    )
                    or "N/A"
                ),

                "salary": salary,
                "skills": skills,
                "experience_level": experience_level,
                "apply_link": apply_link,

                "posted_at": posted_at,

                # Important for converting
                # "قبل يومين" during cleaning
                "fetched_at": fetched_at,

                "description": description,
            }

            all_jobs.append(
                normalized_job
            )

            added += 1

        print(
            f"✔️ Fetched {len(jobs)} jobs "
            "from JSearch."
        )

        print(
            f"   Added {added} JSearch jobs."
        )

    except requests.RequestException as e:
        print(
            "❌ JSearch connection error: "
            f"{e}"
        )

    except Exception as e:
        print(
            "❌ JSearch processing error: "
            f"{e}"
        )


# ============================================================
# 5. Remove duplicates from current run
# ============================================================

def remove_current_run_duplicates(jobs):

    unique_jobs = []
    seen = set()

    for job in jobs:

        apply_link = (
            job.get("apply_link")
            or ""
        ).strip()

        if apply_link:
            unique_key = (
                "link",
                apply_link.lower(),
            )

        else:
            unique_key = (
                "job",

                str(
                    job.get(
                        "job_title",
                        ""
                    )
                ).lower().strip(),

                str(
                    job.get(
                        "company",
                        ""
                    )
                ).lower().strip(),

                str(
                    job.get(
                        "location",
                        ""
                    )
                ).lower().strip(),
            )

        if unique_key in seen:
            continue

        seen.add(unique_key)
        unique_jobs.append(job)

    return unique_jobs


# ============================================================
# 6. Save to JSON
# ============================================================

def save_to_json(jobs):

    with open(
        JSON_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            jobs,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# 7. Save to SQLite
# ============================================================

def save_to_sqlite(jobs):

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
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
        """
    )

    inserted = 0

    for job in jobs:

        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO jobs
                (
                    source,
                    job_title,
                    company,
                    city,
                    location,
                    employment_type,
                    salary,
                    skills,
                    experience_level,
                    apply_link,
                    posted_at,
                    fetched_at,
                    description
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    job.get("source"),
                    job.get("job_title"),
                    job.get("company"),
                    job.get("city"),
                    job.get("location"),
                    job.get(
                        "employment_type"
                    ),
                    job.get("salary"),
                    job.get("skills"),
                    job.get(
                        "experience_level"
                    ),
                    job.get("apply_link"),
                    job.get("posted_at"),
                    job.get("fetched_at"),
                    job.get(
                        "description",
                        "N/A"
                    ),
                )
            )

            if cur.rowcount:
                inserted += 1

        except sqlite3.Error as e:
            print(
                f"⚠️ DB insert error: {e}"
            )

    conn.commit()
    conn.close()

    return inserted


# ============================================================
# 8. Inspection
# ============================================================

def show_db_summary():

    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT COUNT(*) FROM jobs"
        )

        total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(DISTINCT apply_link)
            FROM jobs
            """
        )

        distinct_links = (
            cur.fetchone()[0]
        )

        print(
            "\nTotal rows in DB:",
            total
        )

        print(
            "Distinct apply links:",
            distinct_links
        )

    except sqlite3.Error as e:
        print(
            f"⚠️ Could not inspect DB: {e}"
        )

    finally:
        conn.close()


def show_json_sample():

    if not JSON_PATH.exists():
        return

    with open(
        JSON_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        jobs = json.load(file)

    if not jobs:
        return

    first_job = jobs[0]

    print("\n===== SAMPLE JOB =====")
    print(
        "Title      :",
        first_job.get("job_title")
    )
    print(
        "Posted at  :",
        first_job.get("posted_at")
    )
    print(
        "Fetched at :",
        first_job.get("fetched_at")
    )
    print(
        "Skills     :",
        first_job.get("skills")
    )


# ============================================================
# 9. Main
# ============================================================

def main():

    all_jobs.clear()

    print("\n" + "=" * 60)
    print("JOB SCRAPING")
    print("=" * 60)

    # Active API
    fetch_jsearch()

    # Daily Jobs API intentionally disabled
    # because of current RapidAPI plan limits.

    if not all_jobs:
        print(
            "\n❌ No jobs were returned "
            "from the API."
        )
        return

    unique_jobs = (
        remove_current_run_duplicates(
            all_jobs
        )
    )

    duplicates_removed = (
        len(all_jobs)
        - len(unique_jobs)
    )

    save_to_json(unique_jobs)

    inserted = save_to_sqlite(
        unique_jobs
    )

    print("\n" + "=" * 60)

    print(
        f"🎉 Collected "
        f"{len(all_jobs)} jobs."
    )

    print(
        f"🧹 Removed "
        f"{duplicates_removed} duplicates."
    )

    print(
        f"💾 Saved "
        f"{len(unique_jobs)} unique jobs."
    )

    print(
        f"   JSON   -> {JSON_PATH}"
    )

    print(
        f"   SQLite -> {DB_PATH}"
    )

    print(
        f"   New SQLite rows -> "
        f"{inserted}"
    )

    print("=" * 60)


# ============================================================
# 10. Run
# ============================================================

if __name__ == "__main__":

    main()

    show_db_summary()
    show_json_sample()
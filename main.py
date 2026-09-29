
import os
import re
import json
import time
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv


# ============================================================
# 1. Setup
# ============================================================

try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd()


DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# Existing repository JSON storage

JSON_PATH = (
    DATA_DIR / "jobs_results.json"
)


# ============================================================
# Databricks Bronze Volume
# ============================================================

BRONZE_DIR = Path(
    "/Volumes/job_data_pipeline/bronze/"
    "job_data"
)

BRONZE_JSON_PATH = (
    BRONZE_DIR / "jobs_results.json"
)


# Unity Catalog Bronze table
BRONZE_TABLE = (
    "job_data_pipeline.bronze.jobs"
)


# ============================================================
# Environment Variables
# ============================================================

load_dotenv(
    dotenv_path=BASE_DIR / ".env"
)


RAPID_HOST = os.getenv(
    "RAPIDAPI_HOST",
    "jsearch.p.rapidapi.com"
)


RAPID_KEY = os.getenv(
    "RAPIDAPI_KEY"
)


# ============================================================
# Databricks Secret fallback
# ============================================================

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
# 3. Helper Functions
# ============================================================

def join_non_empty(
    parts,
    separator=", "
):

    cleaned_parts = [
        str(part).strip()
        for part in parts
        if str(part).strip()
    ]

    return separator.join(
        cleaned_parts
    )


def extract_skills_from_text(text):
    """
    Extract known technical skills
    from title + description.
    """

    if not text:
        return "N/A"

    text_lower = str(
        text
    ).lower()

    found = []


    for skill in COMMON_SKILLS:

        pattern = (
            r"\b"
            + re.escape(
                skill.lower()
            )
            + r"\b"
        )

        if re.search(
            pattern,
            text_lower
        ):

            found.append(
                skill
            )


    # Remove duplicates while preserving order
    found = list(
        dict.fromkeys(found)
    )


    return (
        join_non_empty(found)
        if found
        else "N/A"
    )


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


    print(
        "\n⏳ Fetching jobs from JSearch..."
    )


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

            print(
                response.text[:500]
            )

            return


        response_data = (
            response.json()
        )


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

            # ==================================================
            # Title / Description
            # ==================================================

            job_title = (
                job.get("job_title")
                or "N/A"
            )


            description = (
                job.get(
                    "job_description"
                )
                or "N/A"
            )


            text_for_skills = (
                f"{job_title} "
                f"{description}"
            )


            # ==================================================
            # Salary
            # ==================================================

            min_salary = job.get(
                "job_min_salary"
            )


            max_salary = job.get(
                "job_max_salary"
            )


            currency = (
                job.get(
                    "job_salary_currency"
                )
                or ""
            )


            period = (
                job.get(
                    "job_salary_period"
                )
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

                    salary += (
                        f" {currency}"
                    )


                if period:

                    salary += (
                        f" / {period}"
                    )

            else:

                salary = "N/A"


            # ==================================================
            # Skills
            # ==================================================

            skills_list = job.get(
                "job_required_skills"
            )


            if (
                isinstance(
                    skills_list,
                    list
                )
                and skills_list
            ):

                skills = (
                    join_non_empty(
                        skills_list
                    )
                )


            elif skills_list:

                skills = str(
                    skills_list
                )


            else:

                skills = (
                    extract_skills_from_text(
                        text_for_skills
                    )
                )


            # ==================================================
            # Experience
            # ==================================================

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


            # ==================================================
            # Location
            # ==================================================

            city = job.get(
                "job_city"
            )


            country = job.get(
                "job_country"
            )


            if country == "SA":

                country = (
                    "Saudi Arabia"
                )


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
                join_non_empty(
                    location_parts
                )
                if location_parts
                else "N/A"
            )


            # ==================================================
            # Posted Date
            # ==================================================

            # JSearch may return relative values such as:
            # "قبل يومين"
            # Preserve source value here.
            posted_at = (
                job.get(
                    "job_posted_at"
                )
                or "N/A"
            )


            # ==================================================
            # Apply Link
            # ==================================================

            apply_link = (
                job.get(
                    "job_apply_link"
                )
                or job.get(
                    "job_google_link"
                )
                or ""
            )


            # ==================================================
            # Normalized Record
            # ==================================================

            normalized_job = {

                "source": "JSearch",

                "job_title":
                    job_title,

                "company": (
                    job.get(
                        "employer_name"
                    )
                    or "N/A"
                ),

                "city":
                    city or "N/A",

                "location":
                    location,

                "employment_type": (
                    job.get(
                        "job_employment_type"
                    )
                    or "N/A"
                ),

                "salary":
                    salary,

                "skills":
                    skills,

                "experience_level":
                    experience_level,

                "apply_link":
                    apply_link,

                "posted_at":
                    posted_at,

                # Used by cleaning.py to convert
                # relative posting dates.
                "fetched_at":
                    fetched_at,

                "description":
                    description,
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
# 5. Remove Duplicates From Current Run
# ============================================================

def remove_current_run_duplicates(
    jobs
):

    unique_jobs = []
    seen = set()


    for job in jobs:

        apply_link = (
            job.get(
                "apply_link"
            )
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
                )
                .lower()
                .strip(),

                str(
                    job.get(
                        "company",
                        ""
                    )
                )
                .lower()
                .strip(),

                str(
                    job.get(
                        "location",
                        ""
                    )
                )
                .lower()
                .strip(),
            )


        if unique_key in seen:
            continue


        seen.add(
            unique_key
        )

        unique_jobs.append(
            job
        )


    return unique_jobs


# ============================================================
# 6. Save JSON + Bronze Volume
# ============================================================

def save_to_json(jobs):
    """
    Merge the current API batch with existing Bronze history,
    deduplicate by apply_link, then save the complete Bronze dataset.
    """

    BRONZE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    current_df = pd.DataFrame(jobs)

    frames = []

    # --------------------------------------------------------
    # Existing Bronze history
    # --------------------------------------------------------

    if BRONZE_JSON_PATH.exists():

        with open(
            BRONZE_JSON_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            existing_data = json.load(f)

        existing_df = pd.json_normalize(
            existing_data
        )

        frames.append(existing_df)

        print(
            "Existing Bronze rows:",
            len(existing_df)
        )

    # --------------------------------------------------------
    # Current API batch
    # --------------------------------------------------------

    frames.append(current_df)

    combined_df = pd.concat(
        frames,
        ignore_index=True
    )

    rows_before = len(combined_df)

    # Prefer apply_link as the persistent job identity.
    valid_link_mask = (
        combined_df["apply_link"].notna()
        & (
            combined_df["apply_link"]
            .astype(str)
            .str.strip()
            != ""
        )
    )

    with_link = combined_df[
        valid_link_mask
    ].copy()

    without_link = combined_df[
        ~valid_link_mask
    ].copy()

    with_link = with_link.drop_duplicates(
        subset=["apply_link"],
        keep="last"
    )

    # Fallback for jobs with no apply_link.
    without_link = without_link.drop_duplicates(
        subset=[
            "job_title",
            "company",
            "location"
        ],
        keep="last"
    )

    bronze_df = pd.concat(
        [
            with_link,
            without_link
        ],
        ignore_index=True
    )

    duplicates_removed = (
        rows_before - len(bronze_df)
    )

    records = (
        bronze_df
        .where(
            pd.notna(bronze_df),
            None
        )
        .to_dict(
            orient="records"
        )
    )

    # --------------------------------------------------------
    # Repository JSON
    # --------------------------------------------------------

    with open(
        JSON_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            records,
            f,
            ensure_ascii=False,
            indent=2,
            default=str
        )

    # --------------------------------------------------------
    # Databricks Bronze Volume JSON
    # --------------------------------------------------------

    with open(
        BRONZE_JSON_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            records,
            f,
            ensure_ascii=False,
            indent=2,
            default=str
        )

    print(
        "Current API rows:",
        len(current_df)
    )

    print(
        "Bronze duplicates removed:",
        duplicates_removed
    )

    print(
        "Total Bronze history:",
        len(bronze_df)
    )

    print(
        "🥉 Bronze JSON ->",
        BRONZE_JSON_PATH
    )

    return records

def update_bronze_unity_catalog():
    """
    Read Bronze JSON from the Databricks Volume,
    create a Spark DataFrame, and update the Bronze
    Delta table registered in Unity Catalog.
    """

    # ========================================================
    # Get Spark Session
    # ========================================================

    try:

        spark_session = spark

    except NameError:

        print(
            "ℹ️ Spark is not available. "
            "Unity Catalog Bronze update skipped."
        )

        return


    # ========================================================
    # Validate Bronze File
    # ========================================================

    if not BRONZE_JSON_PATH.exists():

        raise FileNotFoundError(
            "Bronze JSON not found: "
            f"{BRONZE_JSON_PATH}"
        )


    print(
        "\n" + "=" * 60
    )

    print(
        "UPDATING BRONZE UNITY CATALOG TABLE"
    )

    print(
        "=" * 60
    )


    # ========================================================
    # Bronze JSON -> Spark DataFrame
    # ========================================================

    # jobs_results.json is stored as one JSON array.
    # Therefore multiline=true is required.
    bronze_df = (
        spark_session.read
        .option(
            "multiline",
            "true"
        )
        .json(
            str(
                BRONZE_JSON_PATH
            )
        )
    )


    bronze_rows = (
        bronze_df.count()
    )


    if bronze_rows == 0:

        raise ValueError(
            "Bronze DataFrame is empty. "
            "Unity Catalog table was not updated."
        )


    print(
        "Bronze DataFrame rows:",
        bronze_rows
    )


    print(
        "Bronze DataFrame columns:",
        bronze_df.columns
    )


    # ========================================================
    # Spark DataFrame -> Unity Catalog Delta Table
    # ========================================================

    (
        bronze_df.write
        .format("delta")
        .mode("overwrite")
        .option(
            "overwriteSchema",
            "true"
        )
        .saveAsTable(
            BRONZE_TABLE
        )
    )


    # ========================================================
    # Validate Unity Catalog Table
    # ========================================================

    bronze_table_df = (
        spark_session.table(
            BRONZE_TABLE
        )
    )


    bronze_table_rows = (
        bronze_table_df.count()
    )


    print(
        "✓ Unity Catalog table updated:"
    )


    print(
        f"  {BRONZE_TABLE}"
    )


    print(
        "Bronze Unity Catalog rows:",
        bronze_table_rows
    )


    print(
        "=" * 60
    )


# ============================================================
# 8. Inspection
# ============================================================

def show_json_sample():

    if not JSON_PATH.exists():
        return


    with open(
        JSON_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        jobs = json.load(
            file
        )


    if not jobs:
        return


    first_job = jobs[0]


    print(
        "\n===== SAMPLE JOB ====="
    )


    print(
        "Title      :",
        first_job.get(
            "job_title"
        )
    )


    print(
        "Posted at  :",
        first_job.get(
            "posted_at"
        )
    )


    print(
        "Fetched at :",
        first_job.get(
            "fetched_at"
        )
    )


    print(
        "Skills     :",
        first_job.get(
            "skills"
        )
    )


# ============================================================
# 9. Main
# ============================================================

def main():

    all_jobs.clear()


    print(
        "\n" + "=" * 60
    )

    print(
        "JOB SCRAPING"
    )

    print(
        "=" * 60
    )


    # ========================================================
    # Active API
    # ========================================================

    fetch_jsearch()


    # Daily Jobs API intentionally disabled
    # because of current RapidAPI plan limits.


    if not all_jobs:

        print(
            "\n❌ No jobs were returned "
            "from the API."
        )

        return


    # ========================================================
    # Remove Current-Run Duplicates
    # ========================================================

    unique_jobs = (
        remove_current_run_duplicates(
            all_jobs
        )
    )


    duplicates_removed = (
        len(all_jobs)
        - len(unique_jobs)
    )


    # ========================================================
    # Save Bronze JSON
    # ========================================================

    bronze_jobs = save_to_json(
        unique_jobs
    )


    # ========================================================
    # Update Bronze Unity Catalog Table
    # ========================================================

    update_bronze_unity_catalog()


    # ========================================================
    # Summary
    # ========================================================

    print(
        "\n" + "=" * 60
    )


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
        f"   JSON   -> "
        f"{JSON_PATH}"
    )


    print(
        f"   Bronze -> "
        f"{BRONZE_JSON_PATH}"
    )


    print(
        f"   UC     -> "
        f"{BRONZE_TABLE}"
    )


    print(
        "=" * 60
    )


# ============================================================
# 10. Run
# ============================================================

if __name__ == "__main__":

    main()

    show_json_sample()
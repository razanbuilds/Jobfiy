import json
import hashlib
import ast
from pathlib import Path
import os
from dotenv import load_dotenv
import snowflake.connector

import pandas as pd

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CLEANED_DATA_PATH = BASE_DIR / "data" / "jobs_cleaned.json"
ENV_PATH = BASE_DIR / ".env"


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------
load_dotenv(ENV_PATH)
# ---------------------------------------------------------
# Connect to Snowflake
# ---------------------------------------------------------
conn = snowflake.connector.connect(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database="JOBS_ANALYTICS",
    schema="JOBS"
)

cursor = conn.cursor()

print("\nConnected to Snowflake successfully.")


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CLEANED_DATA_PATH = BASE_DIR / "data" / "jobs_cleaned.json"


# ---------------------------------------------------------
# Load cleaned data
# ---------------------------------------------------------
with open(CLEANED_DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.json_normalize(data)

# Standardize column names
df.columns = [col.upper() for col in df.columns]

# ---------------------------------------------------------
# Generate stable JOB_ID
# ---------------------------------------------------------
def generate_job_id(row):
    unique_string = (
        str(row.get("JOB_TITLE", "")).strip().lower()
        + "|"
        + str(row.get("COMPANY", "")).strip().lower()
        + "|"
        + str(row.get("LOCATION", "")).strip().lower()
        + "|"
        + str(row.get("APPLY_LINK", "")).strip().lower()
    )

    return hashlib.sha256(
        unique_string.encode("utf-8")
    ).hexdigest()[:16]


df["JOB_ID"] = df.apply(generate_job_id, axis=1)

print("JOB_ID generated.")
print(df[["JOB_ID", "JOB_TITLE", "COMPANY"]].head())

print("Cleaned data loaded successfully.")
print("Rows:", len(df))
print("Columns:", df.columns.tolist())
cursor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()")

result = cursor.fetchone()

print("Database:", result[0])
print("Schema:", result[1])
# ---------------------------------------------------------
# Load DIM_COMPANY
# ---------------------------------------------------------

companies = (
    df["COMPANY"]
    .dropna()
    .astype(str)
    .str.strip()
    .replace("", pd.NA)
    .dropna()
    .drop_duplicates()
)

print(f"\nUnique companies found: {len(companies)}")

for company in companies:
    cursor.execute(
        """
        SELECT COMPANY_KEY
        FROM DIM_COMPANY
        WHERE COMPANY_NAME = %s
        """,
        (company,)
    )

    existing_company = cursor.fetchone()

    if existing_company is None:
        cursor.execute(
            """
            INSERT INTO DIM_COMPANY (COMPANY_NAME)
            VALUES (%s)
            """,
            (company,)
        )

conn.commit()

print("DIM_COMPANY loaded successfully.")
# ---------------------------------------------------------
# Load DIM_LOCATION
# ---------------------------------------------------------

locations = (
    df[["CITY", "LOCATION"]]
    .copy()
)

# Convert NaN to None for Snowflake
locations = locations.where(pd.notna(locations), None)

# Remove duplicate city/location combinations
locations = locations.drop_duplicates()

print(f"\nUnique locations found: {len(locations)}")

for _, row in locations.iterrows():

    city = row["CITY"]
    location = row["LOCATION"]

    # Check if this city/location combination already exists
    cursor.execute(
        """
        SELECT LOCATION_KEY
        FROM DIM_LOCATION
        WHERE EQUAL_NULL(CITY, %s)
          AND EQUAL_NULL(LOCATION, %s)
        """,
        (city, location)
    )

    existing_location = cursor.fetchone()

    if existing_location is None:
        cursor.execute(
            """
            INSERT INTO DIM_LOCATION (
                CITY,
                LOCATION
            )
            VALUES (%s, %s)
            """,
            (city, location)
        )

conn.commit()

print("DIM_LOCATION loaded successfully.")
# ---------------------------------------------------------
# Load DIM_DATE
# ---------------------------------------------------------

dates = df[
    ["POSTED_DATE", "POSTED_YEAR", "POSTED_MONTH", "POSTED_DAY"]
].copy()

# Convert POSTED_DATE to datetime
dates["POSTED_DATE"] = pd.to_datetime(
    dates["POSTED_DATE"],
    errors="coerce"
)

# Remove rows with invalid/missing dates
dates = dates.dropna(subset=["POSTED_DATE"])

# Create DATE_KEY: YYYYMMDD
dates["DATE_KEY"] = (
    dates["POSTED_DATE"]
    .dt.strftime("%Y%m%d")
    .astype(int)
)

# Remove duplicate dates
dates = dates.drop_duplicates(subset=["DATE_KEY"])

print(f"\nUnique dates found: {len(dates)}")

for _, row in dates.iterrows():

    date_key = int(row["DATE_KEY"])
    posted_date = row["POSTED_DATE"].date()
    posted_year = int(row["POSTED_YEAR"])
    posted_month = int(row["POSTED_MONTH"])
    posted_day = int(row["POSTED_DAY"])

    # Check if date already exists
    cursor.execute(
        """
        SELECT DATE_KEY
        FROM DIM_DATE
        WHERE DATE_KEY = %s
        """,
        (date_key,)
    )

    existing_date = cursor.fetchone()

    if existing_date is None:
        cursor.execute(
            """
            INSERT INTO DIM_DATE (
                DATE_KEY,
                POSTED_DATE,
                POSTED_YEAR,
                POSTED_MONTH,
                POSTED_DAY
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                date_key,
                posted_date,
                posted_year,
                posted_month,
                posted_day
            )
        )

conn.commit()

print("DIM_DATE loaded successfully.")
# ---------------------------------------------------------
# Load DIM_JOB
# ---------------------------------------------------------

jobs = df[
    [
        "JOB_ID",
        "JOB_TITLE",
        "SOURCE",
        "EMPLOYMENT_TYPE",
        "EXPERIENCE_LEVEL",
        "APPLY_LINK",
        "DESCRIPTION",
        "POSTED_AT"
    ]
].copy()

# Convert NaN values to None
jobs = jobs.where(pd.notna(jobs), None)

# One row per JOB_ID
jobs = jobs.drop_duplicates(subset=["JOB_ID"])

print(f"\nUnique jobs found: {len(jobs)}")

for _, row in jobs.iterrows():

    job_id = row["JOB_ID"]

    # Check if job already exists
    cursor.execute(
        """
        SELECT JOB_KEY
        FROM DIM_JOB
        WHERE JOB_ID = %s
        """,
        (job_id,)
    )

    existing_job = cursor.fetchone()

    if existing_job is None:

        cursor.execute(
            """
            INSERT INTO DIM_JOB (
                JOB_ID,
                JOB_TITLE,
                SOURCE,
                EMPLOYMENT_TYPE,
                EXPERIENCE_LEVEL,
                APPLY_LINK,
                DESCRIPTION,
                POSTED_AT
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["JOB_ID"],
                row["JOB_TITLE"],
                row["SOURCE"],
                row["EMPLOYMENT_TYPE"],
                row["EXPERIENCE_LEVEL"],
                row["APPLY_LINK"],
                row["DESCRIPTION"],
                row["POSTED_AT"]
            )
        )

conn.commit()

print("DIM_JOB loaded successfully.")
# ---------------------------------------------------------
# Helper: Parse FINAL_SKILLS
# ---------------------------------------------------------

def parse_skills(value):

    if value is None or pd.isna(value):
        return []

    # Already a Python list
    if isinstance(value, list):
        return value

    value = str(value).strip()

    if not value:
        return []

    # Example: "['Python', 'SQL', 'Snowflake']"
    try:
        parsed = ast.literal_eval(value)

        if isinstance(parsed, list):
            return parsed

    except (ValueError, SyntaxError):
        pass

    # Fallback: "Python, SQL, Snowflake"
    return value.split(",")


# ---------------------------------------------------------
# Extract unique skills
# ---------------------------------------------------------

unique_skills = set()

for value in df["FINAL_SKILLS"]:

    skills = parse_skills(value)

    for skill in skills:

        skill = str(skill).strip()

        if skill:
            unique_skills.add(skill)


print(f"\nUnique skills found: {len(unique_skills)}")


# ---------------------------------------------------------
# Load DIM_SKILL
# ---------------------------------------------------------

for skill in sorted(unique_skills):

    cursor.execute(
        """
        SELECT SKILL_KEY
        FROM DIM_SKILL
        WHERE SKILL_NAME = %s
        """,
        (skill,)
    )

    existing_skill = cursor.fetchone()

    if existing_skill is None:

        cursor.execute(
            """
            INSERT INTO DIM_SKILL (SKILL_NAME)
            VALUES (%s)
            """,
            (skill,)
        )


conn.commit()

print("DIM_SKILL loaded successfully.")
# ---------------------------------------------------------
# Load FACT_JOBS
# ---------------------------------------------------------

print("\nLoading FACT_JOBS...")

facts_inserted = 0
facts_skipped = 0

for _, row in df.iterrows():

    # -----------------------------------------------------
    # 1. Get JOB_KEY
    # -----------------------------------------------------
    cursor.execute(
        """
        SELECT JOB_KEY
        FROM DIM_JOB
        WHERE JOB_ID = %s
        """,
        (row["JOB_ID"],)
    )

    job_result = cursor.fetchone()

    if job_result is None:
        print(f"Warning: JOB_KEY not found for {row['JOB_ID']}")
        continue

    job_key = job_result[0]


    # -----------------------------------------------------
    # 2. Get COMPANY_KEY
    # -----------------------------------------------------
    company_key = None

    if pd.notna(row["COMPANY"]):

        company = str(row["COMPANY"]).strip()

        cursor.execute(
            """
            SELECT COMPANY_KEY
            FROM DIM_COMPANY
            WHERE COMPANY_NAME = %s
            """,
            (company,)
        )

        company_result = cursor.fetchone()

        if company_result:
            company_key = company_result[0]


    # -----------------------------------------------------
    # 3. Get LOCATION_KEY
    # -----------------------------------------------------
    city = row["CITY"] if pd.notna(row["CITY"]) else None
    location = row["LOCATION"] if pd.notna(row["LOCATION"]) else None

    cursor.execute(
        """
        SELECT LOCATION_KEY
        FROM DIM_LOCATION
        WHERE EQUAL_NULL(CITY, %s)
          AND EQUAL_NULL(LOCATION, %s)
        """,
        (city, location)
    )

    location_result = cursor.fetchone()

    location_key = (
        location_result[0]
        if location_result
        else None
    )


    # -----------------------------------------------------
    # 4. Get DATE_KEY
    # -----------------------------------------------------
    date_key = None

    if pd.notna(row["POSTED_DATE"]):

        posted_date = pd.to_datetime(
            row["POSTED_DATE"],
            errors="coerce"
        )

        if pd.notna(posted_date):

            date_key = int(
                posted_date.strftime("%Y%m%d")
            )


    # -----------------------------------------------------
    # 5. Convert boolean values
    # -----------------------------------------------------
    is_remote = bool(row["IS_REMOTE"]) if pd.notna(row["IS_REMOTE"]) else False
    has_salary = bool(row["HAS_SALARY"]) if pd.notna(row["HAS_SALARY"]) else False


    # -----------------------------------------------------
    # 6. Check if job already exists in FACT_JOBS
    # -----------------------------------------------------
    cursor.execute(
        """
        SELECT JOB_KEY
        FROM FACT_JOBS
        WHERE JOB_KEY = %s
        """,
        (job_key,)
    )

    existing_fact = cursor.fetchone()


    # -----------------------------------------------------
    # 7. Insert only new jobs
    # -----------------------------------------------------
    if existing_fact is None:

        cursor.execute(
            """
            INSERT INTO FACT_JOBS (
                JOB_KEY,
                COMPANY_KEY,
                LOCATION_KEY,
                DATE_KEY,
                IS_REMOTE,
                HAS_SALARY
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                job_key,
                company_key,
                location_key,
                date_key,
                is_remote,
                has_salary
            )
        )

        facts_inserted += 1

    else:
        facts_skipped += 1


conn.commit()

print("FACT_JOBS loaded successfully.")
print("Inserted:", facts_inserted)
print("Already existed:", facts_skipped)
# ---------------------------------------------------------
# Load BRIDGE_JOB_SKILL
# ---------------------------------------------------------

print("\nLoading BRIDGE_JOB_SKILL...")

bridge_inserted = 0
bridge_skipped = 0

for _, row in df.iterrows():

    # -----------------------------------------------------
    # 1. Get JOB_KEY
    # -----------------------------------------------------
    cursor.execute(
        """
        SELECT JOB_KEY
        FROM DIM_JOB
        WHERE JOB_ID = %s
        """,
        (row["JOB_ID"],)
    )

    job_result = cursor.fetchone()

    if job_result is None:
        continue

    job_key = job_result[0]


    # -----------------------------------------------------
    # 2. Get skills for this job
    # -----------------------------------------------------
    skills = parse_skills(row["FINAL_SKILLS"])

    for skill in skills:

        skill = str(skill).strip()

        if not skill:
            continue


        # -------------------------------------------------
        # 3. Get SKILL_KEY
        # -------------------------------------------------
        cursor.execute(
            """
            SELECT SKILL_KEY
            FROM DIM_SKILL
            WHERE SKILL_NAME = %s
            """,
            (skill,)
        )

        skill_result = cursor.fetchone()

        if skill_result is None:
            continue

        skill_key = skill_result[0]


        # -------------------------------------------------
        # 4. Check if relationship already exists
        # -------------------------------------------------
        cursor.execute(
            """
            SELECT 1
            FROM BRIDGE_JOB_SKILL
            WHERE JOB_KEY = %s
              AND SKILL_KEY = %s
            """,
            (job_key, skill_key)
        )

        existing_bridge = cursor.fetchone()


        # -------------------------------------------------
        # 5. Insert new relationship
        # -------------------------------------------------
        if existing_bridge is None:

            cursor.execute(
                """
                INSERT INTO BRIDGE_JOB_SKILL (
                    JOB_KEY,
                    SKILL_KEY
                )
                VALUES (%s, %s)
                """,
                (job_key, skill_key)
            )

            bridge_inserted += 1

        else:
            bridge_skipped += 1


conn.commit()

print("BRIDGE_JOB_SKILL loaded successfully.")
print("Inserted:", bridge_inserted)
print("Already existed:", bridge_skipped)
cursor.close()
conn.close()
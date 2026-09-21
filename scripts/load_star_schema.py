"""
Load cleaned job data into Snowflake Star Schema.

Source:
    data/jobs_cleaned.json

Target:
    JOBS_ANALYTICS.JOBS

Tables:
    DIM_COMPANY
    DIM_LOCATION
    DIM_DATE
    DIM_JOB
    DIM_SKILL
    FACT_JOBS
    BRIDGE_JOB_SKILL
"""
# /// script
# [tool.databricks.environment]
# dependencies = [
#   "snowflake-connector-python",
#   "databricks-sdk",
# ]
# ///
import json
import hashlib
from pathlib import Path

import pandas as pd
import snowflake.connector


# ============================================================
# 1. Project paths
# ============================================================

try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = Path.cwd()

if SCRIPT_DIR.name == "scripts":
    BASE_DIR = SCRIPT_DIR.parent
else:
    BASE_DIR = SCRIPT_DIR

CLEANED_DATA_PATH = (
    BASE_DIR
    / "data"
    / "jobs_cleaned.json"
)

print("BASE_DIR :", BASE_DIR)
print("Input    :", CLEANED_DATA_PATH)

if not CLEANED_DATA_PATH.exists():
    raise FileNotFoundError(
        f"Cleaned data not found: {CLEANED_DATA_PATH}\n"
        "Run cleaning.py first."
    )


# ============================================================
# 2. Databricks Secrets
# ============================================================

try:
    from databricks.sdk.runtime import dbutils
except ImportError:
    dbutils = None


SECRET_SCOPE = "job-pipeline-secrets"


def get_secret(key):

    if dbutils is None:
        raise RuntimeError(
            "Databricks dbutils is not available. "
            "Run this script inside Databricks."
        )

    return dbutils.secrets.get(
        scope=SECRET_SCOPE,
        key=key
    )


# ============================================================
# 3. Connect to Snowflake
# ============================================================

print("\nConnecting to Snowflake...")

conn = snowflake.connector.connect(
    user=get_secret(
        "SNOWFLAKE_USER"
    ),
    password=get_secret(
        "SNOWFLAKE_PASSWORD"
    ),
    account=get_secret(
        "SNOWFLAKE_ACCOUNT"
    ),
    warehouse=get_secret(
        "SNOWFLAKE_WAREHOUSE"
    ),
    database="JOBS_ANALYTICS",
    schema="JOBS"
)

cursor = conn.cursor()

print(
    "Connected to Snowflake successfully."
)

cursor.execute(
    """
    SELECT
        CURRENT_DATABASE(),
        CURRENT_SCHEMA(),
        CURRENT_WAREHOUSE()
    """
)

database, schema, warehouse = (
    cursor.fetchone()
)

print("Database :", database)
print("Schema   :", schema)
print("Warehouse:", warehouse)


# ============================================================
# 4. Load cleaned JSON
# ============================================================

with open(
    CLEANED_DATA_PATH,
    "r",
    encoding="utf-8"
) as f:
    data = json.load(f)

df = pd.json_normalize(data)

df.columns = [
    col.upper()
    for col in df.columns
]

print(
    f"\nCleaned data loaded: "
    f"{len(df)} rows"
)

print(
    "Columns:",
    df.columns.tolist()
)


# ============================================================
# 5. Validate required columns
# ============================================================

REQUIRED_COLUMNS = [
    "SOURCE",
    "JOB_TITLE",
    "COMPANY",
    "CITY",
    "LOCATION",
    "EMPLOYMENT_TYPE",
    "SKILLS",
    "EXPERIENCE_LEVEL",
    "APPLY_LINK",
    "POSTED_AT",
    "DESCRIPTION",
    "IS_REMOTE",
    "HAS_SALARY",
    "POSTED_DATE",
    "POSTED_YEAR",
    "POSTED_MONTH",
    "POSTED_DAY",
]

missing_columns = [
    col
    for col in REQUIRED_COLUMNS
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        "Missing columns in cleaned data: "
        + ", ".join(missing_columns)
    )


# ============================================================
# 6. Convert pandas missing values to Python None
# ============================================================

def to_none(value):

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


# ============================================================
# 7. Generate stable JOB_ID
# ============================================================

def normalize_id_value(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return (
        str(value)
        .strip()
        .lower()
    )


def generate_job_id(row):

    unique_string = "|".join([
        normalize_id_value(
            row.get("JOB_TITLE")
        ),
        normalize_id_value(
            row.get("COMPANY")
        ),
        normalize_id_value(
            row.get("LOCATION")
        ),
        normalize_id_value(
            row.get("APPLY_LINK")
        ),
    ])

    return hashlib.sha256(
        unique_string.encode("utf-8")
    ).hexdigest()[:16]


df["JOB_ID"] = df.apply(
    generate_job_id,
    axis=1
)

print("\nJOB_ID generated.")

print(
    df[
        [
            "JOB_ID",
            "JOB_TITLE",
            "COMPANY"
        ]
    ].head()
)


# ============================================================
# 8. Normalize date columns
# ============================================================

df["POSTED_AT"] = pd.to_datetime(
    df["POSTED_AT"],
    errors="coerce",
    utc=True
)

df["POSTED_DATE"] = pd.to_datetime(
    df["POSTED_DATE"],
    errors="coerce"
)


# ============================================================
# 9. Load DIM_COMPANY
# ============================================================

print(
    "\n===== DIM_COMPANY ====="
)

companies = (
    df["COMPANY"]
    .dropna()
    .astype(str)
    .str.strip()
)

companies = (
    companies[
        companies != ""
    ]
    .drop_duplicates()
)

company_inserted = 0
company_skipped = 0

for company in companies:

    cursor.execute(
        """
        SELECT COMPANY_KEY
        FROM DIM_COMPANY
        WHERE COMPANY_NAME = %s
        """,
        (company,)
    )

    if cursor.fetchone() is None:

        cursor.execute(
            """
            INSERT INTO DIM_COMPANY (
                COMPANY_NAME
            )
            VALUES (%s)
            """,
            (company,)
        )

        company_inserted += 1

    else:
        company_skipped += 1

conn.commit()

print(
    "Inserted:",
    company_inserted
)

print(
    "Already existed:",
    company_skipped
)


# ============================================================
# 10. Load DIM_LOCATION
# ============================================================

print(
    "\n===== DIM_LOCATION ====="
)

locations = (
    df[
        [
            "CITY",
            "LOCATION"
        ]
    ]
    .drop_duplicates()
)

location_inserted = 0
location_skipped = 0

for _, row in locations.iterrows():

    city = to_none(
        row["CITY"]
    )

    location = to_none(
        row["LOCATION"]
    )

    # Skip completely empty location
    if (
        city is None
        and location is None
    ):
        continue

    cursor.execute(
        """
        SELECT LOCATION_KEY
        FROM DIM_LOCATION
        WHERE EQUAL_NULL(CITY, %s)
          AND EQUAL_NULL(LOCATION, %s)
        """,
        (
            city,
            location
        )
    )

    if cursor.fetchone() is None:

        cursor.execute(
            """
            INSERT INTO DIM_LOCATION (
                CITY,
                LOCATION
            )
            VALUES (%s, %s)
            """,
            (
                city,
                location
            )
        )

        location_inserted += 1

    else:
        location_skipped += 1

conn.commit()

print(
    "Inserted:",
    location_inserted
)

print(
    "Already existed:",
    location_skipped
)


# ============================================================
# 11. Load DIM_DATE
# ============================================================

print(
    "\n===== DIM_DATE ====="
)

dates = (
    df[
        [
            "POSTED_DATE",
            "POSTED_YEAR",
            "POSTED_MONTH",
            "POSTED_DAY"
        ]
    ]
    .dropna(
        subset=["POSTED_DATE"]
    )
    .copy()
)

dates["DATE_KEY"] = (
    dates["POSTED_DATE"]
    .dt.strftime("%Y%m%d")
    .astype(int)
)

dates = (
    dates
    .drop_duplicates(
        subset=["DATE_KEY"]
    )
)

date_inserted = 0
date_skipped = 0

for _, row in dates.iterrows():

    date_key = int(
        row["DATE_KEY"]
    )

    posted_date = (
        row["POSTED_DATE"]
        .date()
    )

    posted_year = int(
        row["POSTED_YEAR"]
    )

    posted_month = int(
        row["POSTED_MONTH"]
    )

    posted_day = int(
        row["POSTED_DAY"]
    )

    cursor.execute(
        """
        SELECT DATE_KEY
        FROM DIM_DATE
        WHERE DATE_KEY = %s
        """,
        (date_key,)
    )

    if cursor.fetchone() is None:

        cursor.execute(
            """
            INSERT INTO DIM_DATE (
                DATE_KEY,
                POSTED_DATE,
                POSTED_YEAR,
                POSTED_MONTH,
                POSTED_DAY
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                date_key,
                posted_date,
                posted_year,
                posted_month,
                posted_day
            )
        )

        date_inserted += 1

    else:
        date_skipped += 1

conn.commit()

print(
    "Inserted:",
    date_inserted
)

print(
    "Already existed:",
    date_skipped
)


# ============================================================
# 12. Load DIM_JOB
# ============================================================

print(
    "\n===== DIM_JOB ====="
)

jobs = (
    df[
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
    ]
    .drop_duplicates(
        subset=["JOB_ID"]
    )
)

job_inserted = 0
job_skipped = 0

for _, row in jobs.iterrows():

    job_id = row["JOB_ID"]

    cursor.execute(
        """
        SELECT JOB_KEY
        FROM DIM_JOB
        WHERE JOB_ID = %s
        """,
        (job_id,)
    )

    if cursor.fetchone() is not None:

        job_skipped += 1
        continue

    posted_at = to_none(
        row["POSTED_AT"]
    )

    # Snowflake connector handles
    # Python datetime better than pandas Timestamp
    if posted_at is not None:
        posted_at = (
            posted_at
            .to_pydatetime()
        )

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
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            job_id,
            to_none(
                row["JOB_TITLE"]
            ),
            to_none(
                row["SOURCE"]
            ),
            to_none(
                row["EMPLOYMENT_TYPE"]
            ),
            to_none(
                row["EXPERIENCE_LEVEL"]
            ),
            to_none(
                row["APPLY_LINK"]
            ),
            to_none(
                row["DESCRIPTION"]
            ),
            posted_at
        )
    )

    job_inserted += 1

conn.commit()

print(
    "Inserted:",
    job_inserted
)

print(
    "Already existed:",
    job_skipped
)


# ============================================================
# 13. Parse SKILLS
# ============================================================

def parse_skills(value):

    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass

    if isinstance(value, list):

        return [
            str(skill).strip()
            for skill in value
            if str(skill).strip()
        ]

    value = str(value).strip()

    if not value:
        return []

    return [
        skill.strip()
        for skill in value.split(",")
        if skill.strip()
    ]


# ============================================================
# 14. Extract unique skills
# ============================================================

unique_skills = set()

for value in df["SKILLS"]:

    for skill in parse_skills(value):

        if skill:
            unique_skills.add(
                skill
            )

print(
    "\n===== DIM_SKILL ====="
)

print(
    "Unique skills:",
    len(unique_skills)
)


# ============================================================
# 15. Load DIM_SKILL
# ============================================================

skill_inserted = 0
skill_skipped = 0

for skill in sorted(
    unique_skills,
    key=str.lower
):

    cursor.execute(
        """
        SELECT SKILL_KEY
        FROM DIM_SKILL
        WHERE SKILL_NAME = %s
        """,
        (skill,)
    )

    if cursor.fetchone() is None:

        cursor.execute(
            """
            INSERT INTO DIM_SKILL (
                SKILL_NAME
            )
            VALUES (%s)
            """,
            (skill,)
        )

        skill_inserted += 1

    else:
        skill_skipped += 1

conn.commit()

print(
    "Inserted:",
    skill_inserted
)

print(
    "Already existed:",
    skill_skipped
)


# ============================================================
# 16. Load FACT_JOBS
# ============================================================

print(
    "\n===== FACT_JOBS ====="
)

facts_inserted = 0
facts_skipped = 0

for _, row in df.iterrows():

    # --------------------------------------------------------
    # JOB_KEY
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT JOB_KEY
        FROM DIM_JOB
        WHERE JOB_ID = %s
        """,
        (
            row["JOB_ID"],
        )
    )

    result = cursor.fetchone()

    if result is None:

        print(
            "Warning: JOB_KEY not found:",
            row["JOB_ID"]
        )

        continue

    job_key = result[0]


    # --------------------------------------------------------
    # COMPANY_KEY
    # --------------------------------------------------------

    company_key = None

    company = to_none(
        row["COMPANY"]
    )

    if company is not None:

        cursor.execute(
            """
            SELECT COMPANY_KEY
            FROM DIM_COMPANY
            WHERE COMPANY_NAME = %s
            """,
            (
                str(company).strip(),
            )
        )

        result = cursor.fetchone()

        if result:
            company_key = result[0]


    # --------------------------------------------------------
    # LOCATION_KEY
    # --------------------------------------------------------

    location_key = None

    city = to_none(
        row["CITY"]
    )

    location = to_none(
        row["LOCATION"]
    )

    if not (
        city is None
        and location is None
    ):

        cursor.execute(
            """
            SELECT LOCATION_KEY
            FROM DIM_LOCATION
            WHERE EQUAL_NULL(CITY, %s)
              AND EQUAL_NULL(LOCATION, %s)
            """,
            (
                city,
                location
            )
        )

        result = cursor.fetchone()

        if result:
            location_key = result[0]


    # --------------------------------------------------------
    # DATE_KEY
    # --------------------------------------------------------

    date_key = None

    posted_date = to_none(
        row["POSTED_DATE"]
    )

    if posted_date is not None:

        posted_date = pd.to_datetime(
            posted_date,
            errors="coerce"
        )

        if pd.notna(
            posted_date
        ):
            date_key = int(
                posted_date.strftime(
                    "%Y%m%d"
                )
            )


    # --------------------------------------------------------
    # Flags
    # --------------------------------------------------------

    is_remote = (
        bool(row["IS_REMOTE"])
        if pd.notna(
            row["IS_REMOTE"]
        )
        else False
    )

    has_salary = (
        bool(row["HAS_SALARY"])
        if pd.notna(
            row["HAS_SALARY"]
        )
        else False
    )


    # --------------------------------------------------------
    # Existing fact?
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT JOB_KEY
        FROM FACT_JOBS
        WHERE JOB_KEY = %s
        """,
        (
            job_key,
        )
    )

    if cursor.fetchone() is not None:

        facts_skipped += 1
        continue


    # --------------------------------------------------------
    # Insert
    # --------------------------------------------------------

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
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
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

conn.commit()

print(
    "Inserted:",
    facts_inserted
)

print(
    "Already existed:",
    facts_skipped
)


# ============================================================
# 17. Load BRIDGE_JOB_SKILL
# ============================================================

print(
    "\n===== BRIDGE_JOB_SKILL ====="
)

bridge_inserted = 0
bridge_skipped = 0

for _, row in df.iterrows():

    # JOB_KEY
    cursor.execute(
        """
        SELECT JOB_KEY
        FROM DIM_JOB
        WHERE JOB_ID = %s
        """,
        (
            row["JOB_ID"],
        )
    )

    result = cursor.fetchone()

    if result is None:
        continue

    job_key = result[0]

    # Skills for this job
    skills = parse_skills(
        row["SKILLS"]
    )

    for skill in skills:

        cursor.execute(
            """
            SELECT SKILL_KEY
            FROM DIM_SKILL
            WHERE SKILL_NAME = %s
            """,
            (
                skill,
            )
        )

        result = cursor.fetchone()

        if result is None:
            continue

        skill_key = result[0]

        cursor.execute(
            """
            SELECT 1
            FROM BRIDGE_JOB_SKILL
            WHERE JOB_KEY = %s
              AND SKILL_KEY = %s
            """,
            (
                job_key,
                skill_key
            )
        )

        if cursor.fetchone() is not None:

            bridge_skipped += 1
            continue

        cursor.execute(
            """
            INSERT INTO BRIDGE_JOB_SKILL (
                JOB_KEY,
                SKILL_KEY
            )
            VALUES (
                %s,
                %s
            )
            """,
            (
                job_key,
                skill_key
            )
        )

        bridge_inserted += 1

conn.commit()

print(
    "Inserted:",
    bridge_inserted
)

print(
    "Already existed:",
    bridge_skipped
)


# ============================================================
# 18. Final Snowflake counts
# ============================================================

print(
    "\n===== SNOWFLAKE STAR SCHEMA ====="
)

tables = [
    "DIM_COMPANY",
    "DIM_LOCATION",
    "DIM_DATE",
    "DIM_JOB",
    "DIM_SKILL",
    "FACT_JOBS",
    "BRIDGE_JOB_SKILL",
]

for table in tables:

    cursor.execute(
        f"SELECT COUNT(*) FROM {table}"
    )

    count = (
        cursor.fetchone()[0]
    )

    print(
        f"{table:<20} {count}"
    )


# ============================================================
# 19. Close connection
# ============================================================

cursor.close()
conn.close()

print(
    "\nSnowflake connection closed."
)

print(
    "\nSTAR SCHEMA LOAD COMPLETED SUCCESSFULLY"
)
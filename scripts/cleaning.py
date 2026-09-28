
# ============================================================
# Job Data Cleaning & Transformation Pipeline
#
# Medallion Architecture:
# Bronze -> Cleaning/Transformation -> Silver
#
# Reads:
# /Volumes/job_data_pipeline/default/job_data/bronze/jobs_results.json
#
# Writes:
# /Volumes/job_data_pipeline/default/job_data/silver/jobs_cleaned.json
#
# Unity Catalog:
# job_data_pipeline.default.silver_jobs
# ============================================================

import json
import re
import html
from pathlib import Path

import pandas as pd


# ============================================================
# 1. Paths
# ============================================================

try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = Path.cwd()


if SCRIPT_DIR.name == "scripts":
    BASE_DIR = SCRIPT_DIR.parent
else:
    BASE_DIR = SCRIPT_DIR


# ------------------------------------------------------------
# Databricks Medallion Volume
# ------------------------------------------------------------

VOLUME_ROOT = Path(
    "/Volumes/job_data_pipeline/default/job_data"
)

BRONZE_DIR = VOLUME_ROOT / "bronze"
SILVER_DIR = VOLUME_ROOT / "silver"

RAW_PATH = (
    BRONZE_DIR / "jobs_results.json"
)

OUTPUT_PATH = (
    SILVER_DIR / "jobs_cleaned.json"
)


# ------------------------------------------------------------
# Unity Catalog
# ------------------------------------------------------------

SILVER_TABLE = (
    "job_data_pipeline.default.silver_jobs"
)


print("BASE_DIR :", BASE_DIR)
print("🥉 Bronze:", RAW_PATH)
print("🥈 Silver:", OUTPUT_PATH)
print("UC Silver:", SILVER_TABLE)


# ------------------------------------------------------------
# Validate Bronze input
# ------------------------------------------------------------

if not RAW_PATH.exists():

    raise FileNotFoundError(
        f"Bronze input file not found: {RAW_PATH}\n"
        "Run main.py first so Bronze data is created."
    )


# ============================================================
# 2. Load Bronze JSON
# ============================================================

with open(
    RAW_PATH,
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)


df = pd.json_normalize(data)


print(
    f"\nLoaded Bronze rows: {len(df)}"
)


# ============================================================
# 3. Validate Required Source Columns
# ============================================================

REQUIRED_SOURCE_COLUMNS = [
    "source",
    "job_title",
    "company",
    "city",
    "location",
    "employment_type",
    "salary",
    "skills",
    "experience_level",
    "apply_link",
    "posted_at",
    "fetched_at",
    "description",
]


missing_columns = [
    col
    for col in REQUIRED_SOURCE_COLUMNS
    if col not in df.columns
]


if missing_columns:

    raise ValueError(
        "Missing required columns in Bronze data: "
        + ", ".join(missing_columns)
    )


# ============================================================
# 4. Remove Duplicate Jobs
# ============================================================

rows_before = len(df)


df = df.drop_duplicates(
    subset=[
        "job_title",
        "company",
        "location"
    ],
    keep="first"
).copy()


duplicates_removed = (
    rows_before - len(df)
)


print(
    f"Duplicates removed: "
    f"{duplicates_removed}"
)


# ============================================================
# 5. Normalize Missing Values
# ============================================================

MISSING_TOKENS = [
    "N/A",
    "NA",
    "None",
    "NULL",
    "",
]


df = df.replace(
    MISSING_TOKENS,
    pd.NA
)


# ============================================================
# 6. Clean Text Fields
# ============================================================

TEXT_COLUMNS = [
    "source",
    "job_title",
    "company",
    "city",
    "location",
    "employment_type",
    "skills",
    "experience_level",
    "apply_link",
]


text_column_set = set(
    df.columns
)


for col in TEXT_COLUMNS:

    if col in text_column_set:

        df[col] = (
            df[col]
            .astype("string")
            .str.strip()
            .str.replace(
                r"\s+",
                " ",
                regex=True
            )
        )


# ============================================================
# 7. Standardize Employment Type
# ============================================================

EMPLOYMENT_TYPE_MAP = {

    "full-time": "Full-time",
    "full time": "Full-time",
    "fulltime": "Full-time",

    "part-time": "Part-time",
    "part time": "Part-time",
    "parttime": "Part-time",

    "contract": "Contract",
    "internship": "Internship",
    "temporary": "Temporary",
}


df["employment_type"] = (
    df["employment_type"]
    .str.lower()
    .replace(
        EMPLOYMENT_TYPE_MAP
    )
)


# ============================================================
# 8. Clean Company
# ============================================================

def clean_company(company):

    if pd.isna(company):
        return pd.NA


    company = re.sub(
        r"\s+",
        " ",
        str(company)
    ).strip()


    if company.islower():

        company = (
            company.title()
        )


    return company


df["company"] = (
    df["company"]
    .apply(
        clean_company
    )
)


# ============================================================
# 9. Clean Description
# ============================================================

def clean_description(value):

    if pd.isna(value):
        return pd.NA


    text = html.unescape(
        str(value)
    )


    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )


    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()


    return (
        text
        if text
        else pd.NA
    )


df["description"] = (
    df["description"]
    .apply(
        clean_description
    )
)


# ============================================================
# 10. Clean Skills
# ============================================================

def clean_skills(value):

    if pd.isna(value):
        return pd.NA


    skills = [

        skill.strip()

        for skill
        in str(value).split(",")

        if skill.strip()
    ]


    # Remove duplicate skills while preserving order
    skills = list(
        dict.fromkeys(
            skills
        )
    )


    if not skills:
        return pd.NA


    return ", ".join(
        skills
    )


df["skills"] = (
    df["skills"]
    .apply(
        clean_skills
    )
)


# ============================================================
# 11. Missing-Value Report
# ============================================================

print(
    "\n===== MISSING VALUE HANDLING ====="
)


for col in [
    "salary",
    "city",
    "employment_type",
    "skills",
    "experience_level",
    "posted_at",
    "fetched_at",
    "description",
]:

    missing_count = (
        df[col]
        .isna()
        .sum()
    )


    print(
        f"{col}: "
        f"{missing_count} missing values "
        "retained as NULL"
    )


# ============================================================
# 12. Parse fetched_at
# ============================================================

df["fetched_at"] = (
    pd.to_datetime(
        df["fetched_at"],
        errors="coerce",
        utc=True
    )
)


# ============================================================
# 13. Parse posted_at
# ============================================================

ARABIC_DIGITS = (
    str.maketrans(
        "٠١٢٣٤٥٦٧٨٩",
        "0123456789"
    )
)


def parse_posted_at(
    value,
    fetched_at
):

    if (
        pd.isna(value)
        or pd.isna(fetched_at)
    ):

        return pd.NaT


    text = (
        str(value)
        .strip()
        .translate(
            ARABIC_DIGITS
        )
    )


    # --------------------------------------------------------
    # Current day
    # --------------------------------------------------------

    if text in [
        "الآن",
        "اليوم",
        "قبل قليل",
    ]:

        return fetched_at


    # --------------------------------------------------------
    # Yesterday
    # --------------------------------------------------------

    if text in [
        "أمس",
        "امس",
        "قبل يوم",
        "قبل يوم واحد",
    ]:

        return (
            fetched_at
            - pd.Timedelta(
                days=1
            )
        )


    # --------------------------------------------------------
    # Two days
    # --------------------------------------------------------

    if text == "قبل يومين":

        return (
            fetched_at
            - pd.Timedelta(
                days=2
            )
        )


    # --------------------------------------------------------
    # Minutes
    # --------------------------------------------------------

    match = re.search(
        r"قبل\s+(\d+)\s+"
        r"(?:دقيقة|دقائق)",
        text
    )


    if match:

        minutes = int(
            match.group(1)
        )


        return (
            fetched_at
            - pd.Timedelta(
                minutes=minutes
            )
        )


    # --------------------------------------------------------
    # Hours
    # --------------------------------------------------------

    match = re.search(
        r"قبل\s+(\d+)\s+"
        r"(?:ساعة|ساعات)",
        text
    )


    if match:

        hours = int(
            match.group(1)
        )


        return (
            fetched_at
            - pd.Timedelta(
                hours=hours
            )
        )


    # --------------------------------------------------------
    # Days
    # --------------------------------------------------------

    match = re.search(
        r"قبل\s+(\d+)\s+"
        r"(?:يوم|أيام|ايام)",
        text
    )


    if match:

        days = int(
            match.group(1)
        )


        return (
            fetched_at
            - pd.Timedelta(
                days=days
            )
        )


    # --------------------------------------------------------
    # Weeks
    # --------------------------------------------------------

    if text in [
        "قبل أسبوع",
        "قبل اسبوع",
    ]:

        return (
            fetched_at
            - pd.Timedelta(
                days=7
            )
        )


    if text in [
        "قبل أسبوعين",
        "قبل اسبوعين",
    ]:

        return (
            fetched_at
            - pd.Timedelta(
                days=14
            )
        )


    match = re.search(
        r"قبل\s+(\d+)\s+"
        r"(?:أسبوع|اسبوع|أسابيع|اسابيع)",
        text
    )


    if match:

        weeks = int(
            match.group(1)
        )


        return (
            fetched_at
            - pd.Timedelta(
                weeks=weeks
            )
        )


    # --------------------------------------------------------
    # ISO / English datetime
    # --------------------------------------------------------

    try:

        return pd.to_datetime(
            text,
            errors="raise",
            utc=True
        )


    except Exception:

        return pd.NaT


df["posted_at"] = (
    df.apply(
        lambda row: parse_posted_at(
            row["posted_at"],
            row["fetched_at"]
        ),
        axis=1
    )
)


df["posted_at"] = (
    pd.to_datetime(
        df["posted_at"],
        errors="coerce",
        utc=True
    )
)


# ============================================================
# 14. Experience Level
# ============================================================

VALID_LEVELS = [
    "Intern",
    "Junior",
    "Mid Level",
    "Senior",
    "Senior Lead",
    "Lead",
    "Manager",
    "Director",
    "Principal",
]


df["experience_level"] = (
    df["experience_level"]
    .where(
        df["experience_level"]
        .isin(
            VALID_LEVELS
        ),
        pd.NA
    )
)


def extract_experience_level(
    title,
    description
):

    title = (
        ""
        if pd.isna(title)
        else str(title).lower()
    )


    description = (
        ""
        if pd.isna(description)
        else str(description).lower()
    )


    # --------------------------------------------------------
    # Title first
    # --------------------------------------------------------

    if re.search(
        r"\bintern(ship)?\b",
        title
    ):

        return "Intern"


    if re.search(
        r"\bsenior\s+lead\b",
        title
    ):

        return "Senior Lead"


    if re.search(
        r"\bprincipal\b",
        title
    ):

        return "Principal"


    if re.search(
        r"\b(?:senior|sr\.?)\b",
        title
    ):

        return "Senior"


    if re.search(
        r"\b(?:lead|team lead|leader)\b",
        title
    ):

        return "Lead"


    if re.search(
        r"\b(?:manager|manger)\b",
        title
    ):

        return "Manager"


    if re.search(
        r"\bdirector\b",
        title
    ):

        return "Director"


    if re.search(
        r"\b(?:junior|jr\.?|entry[- ]level)\b",
        title
    ):

        return "Junior"


    # --------------------------------------------------------
    # Description fallback
    # --------------------------------------------------------

    patterns = [
        r"\b(\d+)\s*(?:-|to)\s*\d+\s*years?",
        r"\b(\d+)\s*\+\s*years?",
        r"\b(?:minimum|at least)\s+(\d+)\s*years?",
        r"\b(\d+)\s*years?\s+(?:of\s+)?experience\b",
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            description
        )


        if match:

            years = int(
                match.group(1)
            )


            if years <= 2:
                return "Junior"


            if years <= 5:
                return "Mid Level"


            return "Senior"


    return pd.NA


missing_before = (
    df["experience_level"]
    .isna()
    .sum()
)


mask = (
    df["experience_level"]
    .isna()
)


df.loc[
    mask,
    "experience_level"
] = (
    df.loc[mask]
    .apply(
        lambda row: (
            extract_experience_level(
                row["job_title"],
                row["description"]
            )
        ),
        axis=1
    )
)


recovered = (
    missing_before
    - df["experience_level"]
    .isna()
    .sum()
)


print(
    f"Experience levels recovered: "
    f"{recovered}"
)


# ============================================================
# 15. Recover City
# ============================================================

SAUDI_CITIES = [
    "Riyadh",
    "Jeddah",
    "Makkah",
    "Mecca",
    "Madinah",
    "Medina",
    "Dammam",
    "Khobar",
    "Al Khobar",
    "Dhahran",
    "Taif",
    "Tabuk",
    "Abha",
    "Jubail",
    "Yanbu",
    "Najran",
    "Jizan",
    "Buraidah",
    "Hafar Al-Batin",
]


def recover_city(row):

    if pd.notna(
        row["city"]
    ):

        return row["city"]


    values = [
        row.get(
            "location",
            ""
        ),
        row.get(
            "job_title",
            ""
        ),
        row.get(
            "description",
            ""
        ),
    ]


    text = " ".join(
        ""
        if pd.isna(value)
        else str(value)

        for value in values
    )


    for city in SAUDI_CITIES:

        pattern = (
            r"(?<!\w)"
            + re.escape(city)
            + r"(?!\w)"
        )


        if re.search(
            pattern,
            text,
            re.IGNORECASE
        ):

            return city


    return pd.NA


missing_before = (
    df["city"]
    .isna()
    .sum()
)


df["city"] = (
    df.apply(
        recover_city,
        axis=1
    )
)


cities_recovered = (
    missing_before
    - df["city"]
    .isna()
    .sum()
)


print(
    f"Cities recovered: "
    f"{cities_recovered}"
)


# ============================================================
# 16. Derived Flags
# ============================================================

remote_text = (
    df["job_title"]
    .fillna("")
    .astype(str)
    + " "
    + df["description"]
    .fillna("")
    .astype(str)
).str.lower()


df["is_remote"] = (
    remote_text
    .str.contains(
        r"\bremote\b",
        regex=True
    )
    .astype(
        "boolean"
    )
)


# Salary itself is not required in Gold.
# Retain whether salary information was available.

df["has_salary"] = (
    df["salary"]
    .notna()
    .astype(
        "boolean"
    )
)


# ============================================================
# 17. Date Dimension Fields
# ============================================================

df["posted_date"] = (
    df["posted_at"]
    .dt.date
)


df["posted_year"] = (
    df["posted_at"]
    .dt.year
    .astype(
        "Int64"
    )
)


df["posted_month"] = (
    df["posted_at"]
    .dt.month
    .astype(
        "Int64"
    )
)


df["posted_day"] = (
    df["posted_at"]
    .dt.day
    .astype(
        "Int64"
    )
)


# ============================================================
# 18. Data Quality Checks
# ============================================================

print(
    "\n===== DATA QUALITY CHECKS ====="
)


for col in [
    "job_title",
    "company",
    "location",
]:

    missing_count = (
        df[col]
        .isna()
        .sum()
    )


    if missing_count == 0:

        print(
            f"{col}: PASS"
        )


    else:

        print(
            f"{col}: WARNING - "
            f"{missing_count} missing values"
        )


duplicate_count = (
    df.duplicated(
        subset=[
            "job_title",
            "company",
            "location"
        ]
    )
    .sum()
)


if duplicate_count == 0:

    print(
        "Duplicate jobs: PASS"
    )


else:

    print(
        "Duplicate jobs: WARNING - "
        f"{duplicate_count}"
    )


invalid_levels = df.loc[
    df["experience_level"].notna()
    & ~df["experience_level"].isin(
        VALID_LEVELS
    ),
    "experience_level"
].unique()


if len(invalid_levels) == 0:

    print(
        "Experience levels: PASS"
    )


else:

    print(
        "Experience levels: WARNING - "
        f"{invalid_levels}"
    )


for col in [
    "is_remote",
    "has_salary",
]:

    valid = (
        df[col]
        .dropna()
        .isin([
            True,
            False
        ])
        .all()
    )


    if valid:

        print(
            f"{col}: PASS"
        )


    else:

        print(
            f"{col}: WARNING"
        )


# ============================================================
# 19. Whitespace Checks
# ============================================================

print(
    "\n===== WHITESPACE CHECK ====="
)


for col in TEXT_COLUMNS:

    if col not in text_column_set:
        continue


    values = (
        df[col]
        .dropna()
        .astype(str)
    )


    leading_trailing = (
        values
        .str.match(
            r"^\s|\s$"
        )
        .sum()
    )


    multiple_spaces = (
        values
        .str.contains(
            r"\s{2,}",
            regex=True
        )
        .sum()
    )


    if (
        leading_trailing == 0
        and multiple_spaces == 0
    ):

        print(
            f"{col}: PASS"
        )


    else:

        print(
            f"{col}: WARNING - "
            f"{leading_trailing} "
            "leading/trailing, "
            f"{multiple_spaces} "
            "multiple-space values"
        )


# ============================================================
# 20. Remove Raw Salary Field
# ============================================================

# Gold schema uses HAS_SALARY instead.

df = df.drop(
    columns=[
        "salary"
    ]
)


# ============================================================
# 21. Final Data Quality Report
# ============================================================

print(
    "\n===== FINAL DATA QUALITY REPORT ====="
)


print(
    "Rows:",
    len(df)
)


print(
    "Columns:",
    len(df.columns)
)


print(
    "\nMissing values:\n",
    df.isna()
    .sum()
    .sort_values(
        ascending=False
    )
)


print(
    "\nExperience level distribution:\n",
    df["experience_level"]
    .value_counts(
        dropna=False
    )
)


print(
    "\nRemote jobs:\n",
    df["is_remote"]
    .value_counts(
        dropna=False
    )
)


print(
    "\nJobs with salary:\n",
    df["has_salary"]
    .value_counts(
        dropna=False
    )
)


print(
    "\nDuplicate jobs remaining:",
    df.duplicated(
        subset=[
            "job_title",
            "company",
            "location"
        ]
    ).sum()
)


# ============================================================
# 22. Save Cleaned Data to Silver Volume
# ============================================================

SILVER_DIR.mkdir(
    parents=True,
    exist_ok=True
)


df.to_json(
    OUTPUT_PATH,
    orient="records",
    force_ascii=False,
    indent=2,
    date_format="iso"
)


print(
    f"\n🥈 Silver JSON -> "
    f"{OUTPUT_PATH}"
)


print(
    f"Saved {len(df)} cleaned rows "
    "to Silver."
)


# ============================================================
# 23. Update Silver Unity Catalog Table
# ============================================================

def update_silver_unity_catalog():
    """
    Read the cleaned Silver JSON from the Databricks Volume,
    create a Spark DataFrame, and update the Silver Delta
    table registered in Unity Catalog.
    """

    # --------------------------------------------------------
    # Get Spark Session
    # --------------------------------------------------------

    try:

        spark_session = spark


    except NameError:

        print(
            "ℹ️ Spark is not available. "
            "Unity Catalog Silver update skipped."
        )

        return


    # --------------------------------------------------------
    # Validate Silver JSON
    # --------------------------------------------------------

    if not OUTPUT_PATH.exists():

        raise FileNotFoundError(
            "Silver JSON not found: "
            f"{OUTPUT_PATH}"
        )


    print(
        "\n" + "=" * 60
    )


    print(
        "UPDATING SILVER UNITY CATALOG TABLE"
    )


    print(
        "=" * 60
    )


    # --------------------------------------------------------
    # Silver JSON -> Spark DataFrame
    # --------------------------------------------------------

    # jobs_cleaned.json is stored as one JSON array.
    # Therefore multiline=true is required.

    silver_df = (
        spark_session.read
        .option(
            "multiline",
            "true"
        )
        .json(
            str(
                OUTPUT_PATH
            )
        )
    )


    silver_rows = (
        silver_df.count()
    )


    if silver_rows == 0:

        raise ValueError(
            "Silver DataFrame is empty. "
            "Unity Catalog table was not updated."
        )


    print(
        "Silver DataFrame rows:",
        silver_rows
    )


    print(
        "Silver DataFrame columns:",
        silver_df.columns
    )


    # --------------------------------------------------------
    # Spark DataFrame -> Unity Catalog Delta Table
    # --------------------------------------------------------

    (
        silver_df.write
        .format("delta")
        .mode("overwrite")
        .option(
            "overwriteSchema",
            "true"
        )
        .saveAsTable(
            SILVER_TABLE
        )
    )


    # --------------------------------------------------------
    # Validate Unity Catalog Table
    # --------------------------------------------------------

    silver_table_df = (
        spark_session.table(
            SILVER_TABLE
        )
    )


    silver_table_rows = (
        silver_table_df.count()
    )


    print(
        "✓ Unity Catalog table updated:"
    )


    print(
        f"  {SILVER_TABLE}"
    )


    print(
        "Silver Unity Catalog rows:",
        silver_table_rows
    )


    print(
        "=" * 60
    )


# Run Silver Unity Catalog update
update_silver_unity_catalog()


# ============================================================
# 24. Final Validation
# ============================================================

print(
    "\n===== NULL PERCENTAGES ====="
)


print(
    df.isnull()
    .mean()
    .mul(100)
)


print(
    "\n===== FINAL COLUMNS ====="
)


print(
    df.columns.tolist()
)


print(
    "\n===== DATA TYPES ====="
)


print(
    df.dtypes
)


print(
    "\n===== DATE SAMPLE ====="
)


print(
    df[
        [
            "job_title",
            "posted_at",
            "fetched_at",
            "posted_date",
            "posted_year",
            "posted_month",
            "posted_day",
        ]
    ].head()
)


print(
    "\n===== SKILLS SAMPLE ====="
)


print(
    df[
        [
            "job_title",
            "skills"
        ]
    ].head()
)


# ============================================================
# 25. Pipeline Summary
# ============================================================

print(
    "\n" + "=" * 60
)


print(
    "🥉 BRONZE -> CLEANING -> 🥈 SILVER COMPLETE"
)


print(
    f"Bronze input : {RAW_PATH}"
)


print(
    f"Silver output: {OUTPUT_PATH}"
)


print(
    f"Silver UC    : {SILVER_TABLE}"
)


print(
    "=" * 60
)




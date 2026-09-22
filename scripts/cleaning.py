"""
Job data cleaning & transformation pipeline.

Reads:
    data/jobs_results.json

Writes:
    data/jobs_cleaned.json
"""

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

DATA_DIR = BASE_DIR / "data"

RAW_PATH = DATA_DIR / "jobs_results.json"
OUTPUT_PATH = DATA_DIR / "jobs_cleaned.json"

print("BASE_DIR:", BASE_DIR)
print("Input   :", RAW_PATH)
print("Output  :", OUTPUT_PATH)

if not RAW_PATH.exists():
    raise FileNotFoundError(
        f"Input file not found: {RAW_PATH}\n"
        "Run main.py first."
    )


# ============================================================
# 2. Load raw JSON
# ============================================================

with open(
    RAW_PATH,
    "r",
    encoding="utf-8"
) as f:
    data = json.load(f)

df = pd.json_normalize(data)

print(f"Loaded rows: {len(df)}")


# ============================================================
# 3. Validate required source columns
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
        "Missing required columns in jobs_results.json: "
        + ", ".join(missing_columns)
    )


# ============================================================
# 4. Remove duplicate jobs
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
# 5. Normalize missing values
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
# 6. Clean text fields
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

text_column_set = set(df.columns)

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
# 7. Standardize employment type
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
    .replace(EMPLOYMENT_TYPE_MAP)
)


# ============================================================
# 8. Clean company
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
        company = company.title()

    return company


df["company"] = (
    df["company"]
    .apply(clean_company)
)


# ============================================================
# 9. Clean description
# ============================================================

def clean_description(value):

    if pd.isna(value):
        return pd.NA

    text = html.unescape(
        str(value)
    )

    # Remove HTML
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    # Remove extra whitespace
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
    .apply(clean_description)
)


# ============================================================
# 10. Clean skills
# ============================================================

def clean_skills(value):

    if pd.isna(value):
        return pd.NA

    skills = [
        skill.strip()
        for skill in str(value).split(",")
        if skill.strip()
    ]

    # Remove duplicates while preserving order
    skills = list(
        dict.fromkeys(skills)
    )

    if not skills:
        return pd.NA

    return ", ".join(skills)


df["skills"] = (
    df["skills"]
    .apply(clean_skills)
)


# ============================================================
# 11. Missing-value report
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

df["fetched_at"] = pd.to_datetime(
    df["fetched_at"],
    errors="coerce",
    utc=True
)


# ============================================================
# 13. Parse posted_at
# ============================================================

ARABIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789"
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
        .translate(ARABIC_DIGITS)
    )

    # --------------------------------------------------------
    # Relative Arabic values
    # --------------------------------------------------------

    if text in [
        "الآن",
        "اليوم",
        "قبل قليل",
    ]:
        return fetched_at

    if text in [
        "أمس",
        "امس",
        "قبل يوم",
        "قبل يوم واحد",
    ]:
        return (
            fetched_at
            - pd.Timedelta(days=1)
        )

    if text == "قبل يومين":
        return (
            fetched_at
            - pd.Timedelta(days=2)
        )

    # --------------------------------------------------------
    # Minutes
    # Example:
    # قبل 30 دقيقة
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
    # Examples:
    # قبل 23 ساعة
    # قبل 3 ساعات
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
    # Example:
    # قبل 3 أيام
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
            - pd.Timedelta(days=7)
        )

    if text in [
        "قبل أسبوعين",
        "قبل اسبوعين",
    ]:
        return (
            fetched_at
            - pd.Timedelta(days=14)
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
    # Normal ISO / English datetime
    # --------------------------------------------------------

    try:
        return pd.to_datetime(
            text,
            errors="raise",
            utc=True
        )

    except Exception:
        return pd.NaT


# THIS WAS MISSING IN THE OLD CODE
df["posted_at"] = df.apply(
    lambda row: parse_posted_at(
        row["posted_at"],
        row["fetched_at"]
    ),
    axis=1
)

# Guarantee datetime dtype
df["posted_at"] = pd.to_datetime(
    df["posted_at"],
    errors="coerce",
    utc=True
)


# ============================================================
# 14. Experience level
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


# Existing API values may not match our final categories
df["experience_level"] = (
    df["experience_level"]
    .where(
        df["experience_level"]
        .isin(VALID_LEVELS),
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
] = df.loc[mask].apply(
    lambda row: extract_experience_level(
        row["job_title"],
        row["description"]
    ),
    axis=1
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
# 15. Recover city
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
        row.get("location", ""),
        row.get("job_title", ""),
        row.get("description", ""),
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

df["city"] = df.apply(
    recover_city,
    axis=1
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
# 16. Derived flags
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
    .astype("boolean")
)


# Salary has NOT been converted to numeric.
# We only need whether salary information exists.
df["has_salary"] = (
    df["salary"]
    .notna()
    .astype("boolean")
)


# ============================================================
# 17. Date dimension fields
# ============================================================

# posted_at is ALREADY a datetime.
# Do not parse the Arabic source string again.

df["posted_date"] = (
    df["posted_at"]
    .dt.date
)

df["posted_year"] = (
    df["posted_at"]
    .dt.year
    .astype("Int64")
)

df["posted_month"] = (
    df["posted_at"]
    .dt.month
    .astype("Int64")
)

df["posted_day"] = (
    df["posted_at"]
    .dt.day
    .astype("Int64")
)


# ============================================================
# 18. Data quality checks
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
# 19. Whitespace checks
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
# 20. Remove raw salary field
# ============================================================

# Star schema only needs HAS_SALARY.
df = df.drop(
    columns=["salary"]
)


# ============================================================
# 21. Final report
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
# 22. Save cleaned JSON
# ============================================================

OUTPUT_PATH.parent.mkdir(
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
    f"\nSaved {len(df)} rows to "
    f"{OUTPUT_PATH.resolve()}"
)


# ============================================================
# 23. Final validation
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
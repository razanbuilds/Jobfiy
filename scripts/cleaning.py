"""
Job data cleaning & transformation pipeline (job_scraper project).
Reads raw jobs_master.json, cleans/enriches it, and writes jobs_cleaned.json.
"""

import json
import re
import html
from pathlib import Path

import pandas as pd

# -------------------------------------------------------------------------
# 1. Load raw data
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "data" / "jobs_master.json"
OUTPUT_PATH = BASE_DIR / "data" / "jobs_cleaned.json"

with open(RAW_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.json_normalize(data)

print("\n===== EMPLOYMENT TYPE =====")
print(df["employment_type"].value_counts(dropna=False))

print("\n===== COMPANY =====")
print(df["company"].value_counts(dropna=False).head(50))

print("\n===== LOCATION =====")
print(df["location"].value_counts(dropna=False).head(50))

print("\n===== CITY =====")
print(df["city"].value_counts(dropna=False).head(50))

print("Loaded shape:", df.shape)
print("Columns:", df.columns.tolist())

# -------------------------------------------------------------------------
# 2. Remove duplicate job postings
# -------------------------------------------------------------------------
rows_before = len(df)
df = df.drop_duplicates(subset=["job_title", "company", "location"], keep="first").copy()
print(f"Duplicates removed: {rows_before - len(df)}")

# -------------------------------------------------------------------------
# 3. Normalize missing-value placeholders
# -------------------------------------------------------------------------
MISSING_TOKENS = ["N/A", "NA", "None", "NULL", ""]
df = df.replace(MISSING_TOKENS, pd.NA)

# -------------------------------------------------------------------------
# 4. Standardize categorical values
# -------------------------------------------------------------------------

CATEGORICAL_COLUMNS = [
    "source",
    "company",
    "city",
    "location",
    "employment_type",
    "experience_level",
]

for col in CATEGORICAL_COLUMNS:
    if col in df.columns:
        df[col] = (
            df[col]
            .astype("string")
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )

EMPLOYMENT_TYPE_MAP = {
    "full-time": "Full-time",
    "full time": "Full-time",
    "fulltime": "Full-time",
}

df["employment_type"] = df["employment_type"].replace(EMPLOYMENT_TYPE_MAP)


def standardize_company(company):
    if pd.isna(company):
        return pd.NA

    company = str(company).strip()

    if company.islower():
        company = company.title()

    return company


df["company"] = df["company"].apply(standardize_company)


def clean_description(value):
    if pd.isna(value):
        return pd.NA
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)          # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()       # collapse whitespace
    return text if text else pd.NA


df["description"] = df["description"].apply(clean_description)


def clean_company(company):
    if pd.isna(company):
        return pd.NA
    company = re.sub(r"\s+", " ", str(company)).strip()
    if company.islower():
        company = company.title()
    return company


df["company"] = df["company"].apply(clean_company)


# -------------------------------------------------------------------------
# 5. Handle missing values
# -------------------------------------------------------------------------
# Keep missing values as NULL when no reliable source is available.
# Do not replace missing values with arbitrary defaults.

MISSING_VALUE_COLUMNS = [
    "salary",
    "city",
    "employment_type",
    "skills",
    "final_skills",
    "combined_text",
    "listed_skills",
    "extracted_skills",
    "experience_level",
    "posted_at",
    "description",
]

print("\n===== MISSING VALUE HANDLING =====")

for col in MISSING_VALUE_COLUMNS:
    if col in df.columns:
        missing_count = df[col].isna().sum()
        print(f"{col}: {missing_count} missing values retained as NULL")

# -------------------------------------------------------------------------
# 6. Type conversions
# -------------------------------------------------------------------------
df["posted_at"] = pd.to_datetime(df["posted_at"], format="mixed", errors="coerce", utc=True)
df["salary"] = pd.to_numeric(df["salary"], errors="coerce").astype("Float64")

# -------------------------------------------------------------------------
# 6. Experience level: keep only valid categories, then recover the rest
# -------------------------------------------------------------------------
VALID_LEVELS = ["Intern", "Junior", "Mid Level", "Senior", "Senior Lead",
                 "Lead", "Manager", "Director", "Principal"]

df["experience_level"] = df["experience_level"].where(df["experience_level"].isin(VALID_LEVELS), pd.NA)


def extract_experience_level(title, description):
    title = "" if pd.isna(title) else str(title).lower()
    description = "" if pd.isna(description) else str(description).lower()

    # Title-based rules (checked from most to least specific)
    if re.search(r"\bintern(ship)?\b", title):
        return "Intern"
    if re.search(r"\bsenior\s+lead\b", title):
        return "Senior Lead"
    if re.search(r"\bprincipal\b", title):
        return "Principal"
    if re.search(r"\b(?:senior|sr\.?)\b", title):
        return "Senior"
    if re.search(r"\b(?:lead|team lead|leader)\b", title):
        return "Lead"
    if re.search(r"\b(?:manager|manger)\b", title):
        return "Manager"
    if re.search(r"\bdirector\b", title):
        return "Director"
    if re.search(r"\b(?:junior|jr\.?|entry[- ]level)\b", title):
        return "Junior"

    # Description-based fallback: look for years of experience
    patterns = [
        r"\b(\d+)\s*(?:-|to)\s*\d+\s*years?",
        r"\b(\d+)\s*\+\s*years?",
        r"\b(?:minimum|at least)\s+(\d+)\s*years?",
        r"\b(\d+)\s*years?\s+(?:of\s+)?experience\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            years = int(match.group(1))
            if years <= 2:
                return "Junior"
            elif years <= 5:
                return "Mid Level"
            else:
                return "Senior"

    return pd.NA


missing_before = df["experience_level"].isna().sum()
mask = df["experience_level"].isna()
df.loc[mask, "experience_level"] = df.loc[mask].apply(
    lambda row: extract_experience_level(row["job_title"], row["description"]), axis=1
)
print(f"Experience levels recovered: {missing_before - df['experience_level'].isna().sum()}")

# -------------------------------------------------------------------------
# 7. City recovery from location / title / description text
# -------------------------------------------------------------------------
SAUDI_CITIES = [
    "Riyadh", "Jeddah", "Makkah", "Mecca", "Madinah", "Medina", "Dammam",
    "Khobar", "Al Khobar", "Dhahran", "Taif", "Tabuk", "Abha", "Jubail",
    "Yanbu", "Najran", "Jizan", "Buraidah", "Hafar Al-Batin",
]


def recover_city(row):
    if pd.notna(row["city"]):
        return row["city"]

    text = " ".join([str(row.get("location", "")), str(row.get("job_title", "")),
                      str(row.get("description", ""))])

    for city in SAUDI_CITIES:
        if re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", text, re.IGNORECASE):
            return city
    return pd.NA


missing_before = df["city"].isna().sum()
df["city"] = df.apply(recover_city, axis=1)
print(f"Cities recovered: {missing_before - df['city'].isna().sum()}")

# -------------------------------------------------------------------------
# 8. Derived flags & date parts
# -------------------------------------------------------------------------
remote_text = (df["job_title"].fillna("") + " " + df["description"].fillna("")).str.lower()
df["is_remote"] = remote_text.str.contains(r"\bremote\b", regex=True).astype("boolean")

df["has_salary"] = df["salary"].notna().astype("boolean")

df["posted_date"] = df["posted_at"].dt.date
df["posted_year"] = df["posted_at"].dt.year.astype("Int64")
df["posted_month"] = df["posted_at"].dt.month.astype("Int64")
df["posted_day"] = df["posted_at"].dt.day.astype("Int64")

# -------------------------------------------------------------------------
# 9. Skills cleanup
# -------------------------------------------------------------------------

# Clean extra whitespace in combined_text
if "combined_text" in df.columns:
    df["combined_text"] = (
        df["combined_text"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def clean_skills(value):
    if pd.isna(value):
        return pd.NA
    skills = [s.strip() for s in str(value).split(",") if s.strip()]
    skills = list(dict.fromkeys(skills))  # de-duplicate, keep order
    return ", ".join(skills) if skills else pd.NA


if "final_skills" in df.columns:
    df["final_skills"] = df["final_skills"].apply(clean_skills)

# -------------------------------------------------------------------------
# 11. Data quality checks
# -------------------------------------------------------------------------

print("\n===== DATA QUALITY CHECKS =====")

# Check required fields
REQUIRED_COLUMNS = ["job_title", "company", "location"]

for col in REQUIRED_COLUMNS:
    missing_count = df[col].isna().sum()
    if missing_count == 0:
        print(f"{col}: PASS")
    else:
        print(f"{col}: WARNING - {missing_count} missing values")

# Check duplicate jobs
duplicate_count = df.duplicated(
    subset=["job_title", "company", "location"]
).sum()

if duplicate_count == 0:
    print("Duplicate jobs: PASS")
else:
    print(f"Duplicate jobs: WARNING - {duplicate_count} duplicates")

# Check experience levels
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

invalid_levels = df.loc[
    df["experience_level"].notna()
    & ~df["experience_level"].isin(VALID_LEVELS),
    "experience_level"
].unique()

if len(invalid_levels) == 0:
    print("Experience levels: PASS")
else:
    print(f"Experience levels: WARNING - {invalid_levels}")

# Check boolean columns
for col in ["is_remote", "has_salary"]:
    invalid_boolean = df[col].dropna().isin([True, False]).all()

    if invalid_boolean:
        print(f"{col}: PASS")
    else:
        print(f"{col}: WARNING - invalid values found")

# Drop col salary
df = df.drop(columns=["salary"])
print(df["has_salary"])

# -------------------------------------------------------------------------
# 12. Whitespace checks
# -------------------------------------------------------------------------

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
    "description",
    "combined_text",
    "extracted_skills",
    "listed_skills",
    "final_skills",
]

print("\n===== WHITESPACE CHECK =====")

for col in TEXT_COLUMNS:
    if col in df.columns:
        values = df[col].dropna().astype(str)

        leading_trailing = values.str.match(r"^\s|\s$").sum()
        multiple_spaces = values.str.contains(r"\s{2,}", regex=True).sum()

        if leading_trailing == 0 and multiple_spaces == 0:
            print(f"{col}: PASS")
        else:
            print(
                f"{col}: WARNING - "
                f"{leading_trailing} leading/trailing, "
                f"{multiple_spaces} multiple-space values"
            )

# -------------------------------------------------------------------------
# 13. Final quality report
# -------------------------------------------------------------------------
print("\n===== FINAL DATA QUALITY REPORT =====")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("\nMissing values:\n", df.isna().sum().sort_values(ascending=False))
print("\nExperience level distribution:\n", df["experience_level"].value_counts(dropna=False))
print("\nRemote jobs:\n", df["is_remote"].value_counts(dropna=False))
print("\nJobs with salary:\n", df["has_salary"].value_counts(dropna=False))
print("\nDuplicate jobs remaining:", df.duplicated(subset=["job_title", "company", "location"]).sum())

# -------------------------------------------------------------------------
# 14. Save
# -------------------------------------------------------------------------
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.to_json(OUTPUT_PATH, orient="records", force_ascii=False, indent=2, date_format="iso")

print(f"\nSaved {len(df)} rows to {OUTPUT_PATH.resolve()}")

null_percentages = df.isnull().mean() * 100
print(null_percentages)
print(df["has_salary"].value_counts())
df.columns = df.columns.str.upper()
print(df[
    ["SKILLS", "EXTRACTED_SKILLS", "LISTED_SKILLS", "FINAL_SKILLS"]
].head())
print(df.dtypes)

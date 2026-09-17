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
RAW_PATH = SCRIPT_DIR / "jobs_master.json"
OUTPUT_PATH = SCRIPT_DIR / "jobs_cleaned.json"

with open(RAW_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.json_normalize(data)

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
# 4. Clean text columns
# -------------------------------------------------------------------------
TEXT_COLUMNS = ["source", "job_title", "company", "city", "location",
                 "employment_type", "experience_level"]

for col in TEXT_COLUMNS:
    if col in df.columns:
        df[col] = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


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
# 5. Type conversions
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
def clean_skills(value):
    if pd.isna(value):
        return pd.NA
    skills = [s.strip() for s in str(value).split(",") if s.strip()]
    skills = list(dict.fromkeys(skills))  # de-duplicate, keep order
    return ", ".join(skills) if skills else pd.NA


if "final_skills" in df.columns:
    df["final_skills"] = df["final_skills"].apply(clean_skills)

# -------------------------------------------------------------------------
# 10. Final quality report
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
# 11. Save
# -------------------------------------------------------------------------
OUTPUT_PATH.parent.mkdir(exist_ok=True)
df.to_json(OUTPUT_PATH, orient="records", force_ascii=False, indent=2, date_format="iso")

print(f"\nSaved {len(df)} rows to {OUTPUT_PATH.resolve()}")
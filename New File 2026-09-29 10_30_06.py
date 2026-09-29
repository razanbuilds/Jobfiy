"""
One-time migration: SQLite historical jobs -> Databricks Bronze.

Run this ONCE in Databricks after uploading jobs.db to the project.
It merges SQLite history with any existing Bronze JSON/Table data,
deduplicates by apply_link, then writes the consolidated Bronze dataset
to both the Volume JSON and Unity Catalog Delta table.
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(
    "/Workspace/Users/reyofalthobaiti@gmail.com/JopDataPipeline123"
)

SQLITE_PATH = PROJECT_ROOT / "data" / "jobs.db"

BRONZE_DIR = Path(
    "/Volumes/job_data_pipeline/bronze/job_data"
)

BRONZE_JSON_PATH = BRONZE_DIR / "jobs_results.json"

BRONZE_TABLE = "job_data_pipeline.bronze.jobs"

JOB_COLUMNS = [
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


# ============================================================
# 1. Validate SQLite source
# ============================================================

if not SQLITE_PATH.exists():
    raise FileNotFoundError(
        f"SQLite database not found: {SQLITE_PATH}"
    )

print("SQLite source:", SQLITE_PATH)


# ============================================================
# 2. Read historical SQLite jobs
# ============================================================

with sqlite3.connect(SQLITE_PATH) as conn:
    sqlite_df = pd.read_sql_query(
        "SELECT * FROM jobs",
        conn,
    )

print("SQLite rows:", len(sqlite_df))

# SQLite's internal surrogate ID is not part of Bronze.
sqlite_df = sqlite_df.drop(
    columns=["id"],
    errors="ignore",
)

missing = [
    col for col in JOB_COLUMNS
    if col not in sqlite_df.columns
]

if missing:
    raise ValueError(
        "SQLite is missing required columns: "
        + ", ".join(missing)
    )

sqlite_df = sqlite_df[JOB_COLUMNS].copy()


# ============================================================
# 3. Read existing Bronze JSON, if present
# ============================================================

bronze_frames = [sqlite_df]

if BRONZE_JSON_PATH.exists():
    with open(
        BRONZE_JSON_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        existing_data = json.load(f)

    existing_df = pd.json_normalize(existing_data)

    # Align columns safely.
    for col in JOB_COLUMNS:
        if col not in existing_df.columns:
            existing_df[col] = None

    existing_df = existing_df[JOB_COLUMNS]

    bronze_frames.append(existing_df)

    print(
        "Existing Bronze JSON rows:",
        len(existing_df),
    )
else:
    print(
        "No existing Bronze JSON found. "
        "Migrating SQLite history only."
    )


# ============================================================
# 4. Merge + deduplicate
# ============================================================

bronze_df = pd.concat(
    bronze_frames,
    ignore_index=True,
)

rows_before = len(bronze_df)

# apply_link is the historical incremental key used by SQLite.
with_link = bronze_df[
    bronze_df["apply_link"].notna()
    & (
        bronze_df["apply_link"]
        .astype(str)
        .str.strip()
        != ""
    )
].copy()

without_link = bronze_df[
    ~bronze_df.index.isin(with_link.index)
].copy()

with_link = with_link.drop_duplicates(
    subset=["apply_link"],
    keep="last",
)

# Fallback for records without apply_link.
without_link = without_link.drop_duplicates(
    subset=[
        "job_title",
        "company",
        "location",
    ],
    keep="last",
)

bronze_df = pd.concat(
    [with_link, without_link],
    ignore_index=True,
)

duplicates_removed = rows_before - len(bronze_df)

print("Combined rows before dedup:", rows_before)
print("Duplicates removed:", duplicates_removed)
print("Final Bronze rows:", len(bronze_df))


# ============================================================
# 5. Save consolidated history to Bronze Volume
# ============================================================

BRONZE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

records = (
    bronze_df
    .where(pd.notna(bronze_df), None)
    .to_dict(orient="records")
)

with open(
    BRONZE_JSON_PATH,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        records,
        f,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

print("Bronze JSON:", BRONZE_JSON_PATH)


# ============================================================
# 6. Update Bronze Unity Catalog Delta table
# ============================================================

try:
    spark_session = spark
except NameError:
    try:
        from databricks.sdk.runtime import spark as spark_session
    except ImportError as exc:
        raise RuntimeError(
            "Spark is unavailable. Run this migration in Databricks."
        ) from exc

spark_bronze_df = (
    spark_session.read
    .option("multiline", "true")
    .json(str(BRONZE_JSON_PATH))
)

(
    spark_bronze_df.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(BRONZE_TABLE)
)

table_count = spark_session.table(
    BRONZE_TABLE
).count()

print("Bronze UC table:", BRONZE_TABLE)
print("Bronze UC rows:", table_count)


# ============================================================
# 7. Validation
# ============================================================

if table_count != len(bronze_df):
    raise ValueError(
        "Migration validation failed: "
        f"JSON rows={len(bronze_df)}, "
        f"table rows={table_count}"
    )

print("=" * 60)
print("SQLITE -> BRONZE MIGRATION COMPLETE")
print("Historical SQLite rows:", len(sqlite_df))
print("Final Bronze rows:", len(bronze_df))
print("Validation: PASS")
print("=" * 60)

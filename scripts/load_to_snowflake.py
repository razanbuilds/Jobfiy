import hashlib
from pathlib import Path
import os

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas


# ============================================================
# 1. Project paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
CLEANED_PATH = BASE_DIR / "data" / "jobs_cleaned.json"

load_dotenv(BASE_DIR / ".env")


# ============================================================
# 2. Check that cleaned data exists
# ============================================================

if not CLEANED_PATH.exists():
    raise FileNotFoundError(
        f"Cleaned data file not found: {CLEANED_PATH}"
    )


# ============================================================
# 3. Load the latest cleaned JSON
# ============================================================

df_snowflake = pd.read_json(CLEANED_PATH)
df_snowflake = df_snowflake.reset_index(drop=True)

print(f"Loaded latest cleaned data: {df_snowflake.shape}")


# ============================================================
# 4. Prepare column names for Snowflake
# ============================================================

df_snowflake.columns = df_snowflake.columns.str.upper()

print("Columns:")
print(", ".join(df_snowflake.columns))


# ============================================================
# 5. Convert list columns to strings
# ============================================================
# The source JSON contains:
#
#   extracted_skills: [...]
#   listed_skills: [...]
#
# Snowflake columns become:
#
#   EXTRACTED_SKILLS
#   LISTED_SKILLS
#
# Convert lists into comma-separated strings before uploading.


list_columns = [
    "EXTRACTED_SKILLS",
    "LISTED_SKILLS"
]

for col in list_columns:
    if col in df_snowflake.columns:
        df_snowflake[col] = df_snowflake[col].apply(
            lambda x: ", ".join(map(str, x))
            if isinstance(x, list)
            else x
        )

print("Skill columns prepared.")


# ============================================================
# 6. Prepare date/time columns
# ============================================================

# POSTED_AT
#
# Example:
# 2026-09-11T17:07:27.250Z
#
# Convert to UTC-aware datetime.

if "POSTED_AT" in df_snowflake.columns:
    df_snowflake["POSTED_AT"] = pd.to_datetime(
        df_snowflake["POSTED_AT"],
        errors="coerce",
        utc=True
    )


# POSTED_DATE
#
# Example:
# 2026-09-11T00:00:00.000
#
# Convert to a date value.

if "POSTED_DATE" in df_snowflake.columns:
    df_snowflake["POSTED_DATE"] = pd.to_datetime(
        df_snowflake["POSTED_DATE"],
        errors="coerce"
    ).dt.date


# ============================================================
# 7. Normalize values used to generate JOB_ID
# ============================================================

def normalize_key_value(value) -> str:
    """
    Normalize a value before using it to build JOB_ID.

    Examples:

        " Software Engineer "
        "software engineer"
        "SOFTWARE   ENGINEER"

    all become:

        "software engineer"
    """

    if value is None:
        return ""

    # Handle pandas NaN / NaT safely.
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return " ".join(
        str(value).strip().lower().split()
    )


# ============================================================
# 8. Generate JOB_ID
# ============================================================
#
# Preferred identity:
#
#     APPLY_LINK
#
# Fallback:
#
#     JOB_TITLE + COMPANY + LOCATION
#
# APPLY_LINK is preferred because it is much closer to a
# stable identifier for the actual job posting.
#
# Example:
#
#     https://sa.jooble.org/jdp/6257477343626522564
#
# becomes the basis for the SHA-256 JOB_ID.
#
# If APPLY_LINK is missing, we fall back to the other fields.


def make_job_id(row) -> str:

    # --------------------------------------------------------
    # Preferred key: APPLY_LINK
    # --------------------------------------------------------

    apply_link = normalize_key_value(
        row.get("APPLY_LINK")
    )

    if apply_link:
        raw_key = f"URL|{apply_link}"

    # --------------------------------------------------------
    # Fallback key
    # --------------------------------------------------------

    else:
        job_title = normalize_key_value(
            row.get("JOB_TITLE")
        )

        company = normalize_key_value(
            row.get("COMPANY")
        )

        location = normalize_key_value(
            row.get("LOCATION")
        )

        raw_key = (
            f"FALLBACK|"
            f"{job_title}|"
            f"{company}|"
            f"{location}"
        )

    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


# Generate JOB_ID for every row.
#
# If JOB_ID already exists in the cleaned JSON, preserve it.
# Otherwise generate it using the logic above.

if "JOB_ID" not in df_snowflake.columns:

    df_snowflake["JOB_ID"] = df_snowflake.apply(
        make_job_id,
        axis=1
    )

    print(
        "JOB_ID generated using APPLY_LINK "
        "with TITLE + COMPANY + LOCATION fallback."
    )

else:
    # Make sure existing JOB_ID values are strings.
    df_snowflake["JOB_ID"] = (
        df_snowflake["JOB_ID"]
        .astype(str)
        .str.strip()
    )

    print("Existing JOB_ID column detected; preserving it.")


# ============================================================
# 9. Validate JOB_ID values
# ============================================================

missing_job_ids = (
    df_snowflake["JOB_ID"].isna()
    | (df_snowflake["JOB_ID"].astype(str).str.strip() == "")
)

if missing_job_ids.any():
    raise ValueError(
        f"Found {missing_job_ids.sum()} rows without a valid JOB_ID."
    )


# ============================================================
# 10. Deduplicate the current batch
# ============================================================
#
# MERGE requires the source table to contain at most one row
# for each JOB_ID.
#
# If the same job appears multiple times in the current scrape,
# keep the latest version when SCRAPED_AT exists.
#
# Otherwise, keep the last occurrence.


before = len(df_snowflake)


if "SCRAPED_AT" in df_snowflake.columns:

    df_snowflake["SCRAPED_AT"] = pd.to_datetime(
        df_snowflake["SCRAPED_AT"],
        errors="coerce",
        utc=True
    )

    df_snowflake = (
        df_snowflake
        .sort_values(
            by="SCRAPED_AT",
            na_position="first"
        )
        .drop_duplicates(
            subset=["JOB_ID"],
            keep="last"
        )
    )

else:

    df_snowflake = (
        df_snowflake
        .drop_duplicates(
            subset=["JOB_ID"],
            keep="last"
        )
    )


dropped = before - len(df_snowflake)

if dropped:
    print(
        f"Dropped {dropped} duplicate rows "
        f"within the current batch."
    )


print(
    f"Final batch size after deduplication: "
    f"{len(df_snowflake)} rows."
)


# ============================================================
# 11. Connect to Snowflake
# ============================================================

conn = snowflake.connector.connect(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA")
)

print("Connected to Snowflake successfully!")


# ============================================================
# 12. Start incremental load
# ============================================================

cursor = conn.cursor()

try:

    # ========================================================
    # 12.1 Check target table columns
    # ========================================================
    #
    # This lets us safely use optional metadata columns:
    #
    #   CREATED_AT
    #   UPDATED_AT
    #   LAST_SEEN_AT
    #
    # These are not part of the scraped JSON.


    column_result = cursor.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = CURRENT_SCHEMA()
          AND TABLE_NAME = 'CLEANED_JOBS'
    """).fetchall()

    target_columns = {
        row[0].upper()
        for row in column_result
    }

    if "JOB_ID" not in target_columns:
        raise RuntimeError(
            "CLEANED_JOBS does not contain a JOB_ID column."
        )


    # ========================================================
    # 12.2 Add LAST_SEEN_AT to the source batch if available
    # ========================================================
    #
    # LAST_SEEN_AT tells us when the job was last observed
    # by the scraper.
    #
    # It is updated every time the job appears in a scrape.
    #
    # It is NOT updated for jobs that don't appear in the
    # current scrape.


    if "LAST_SEEN_AT" in target_columns:

        df_snowflake["LAST_SEEN_AT"] = pd.Timestamp.now(
            tz="UTC"
        )


    # ========================================================
    # 12.3 Create temporary staging table
    # ========================================================
    #
    # The staging table has the exact same structure as
    # CLEANED_JOBS but is temporary and session-scoped.


    cursor.execute("""
        CREATE OR REPLACE TEMPORARY TABLE CLEANED_JOBS_STAGE
        LIKE CLEANED_JOBS
    """)

    print("Temporary staging table created.")


    # ========================================================
    # 12.4 Upload current batch to staging
    # ========================================================


    success, nchunks, nrows, output = write_pandas(
        conn=conn,
        df=df_snowflake,
        table_name="CLEANED_JOBS_STAGE",
        use_logical_type=True
    )

    if not success:
        raise RuntimeError(
            "Upload to CLEANED_JOBS_STAGE failed."
        )

    print(
        f"Staged {nrows} rows "
        f"in {nchunks} chunk(s)."
    )


    # ========================================================
    # 12.5 Build MERGE column lists
    # ========================================================
    #
    # JOB_ID is the matching key.
    #
    # CREATED_AT should only be set when inserting.
    #
    # UPDATED_AT should change when a matched job is updated.
    #
    # All other source columns are updated normally.


    system_managed_columns = {
        "JOB_ID",
        "CREATED_AT",
        "UPDATED_AT"
    }

    update_columns = [
        column
        for column in df_snowflake.columns
        if column not in system_managed_columns
    ]


    # ========================================================
    # 12.6 Build UPDATE clause
    # ========================================================


    update_assignments = [
        f"target.{column} = source.{column}"
        for column in update_columns
    ]


    if "UPDATED_AT" in target_columns:
        update_assignments.append(
            "target.UPDATED_AT = CURRENT_TIMESTAMP()"
        )


    update_clause = ",\n                ".join(
        update_assignments
    )


    # ========================================================
    # 12.7 Build INSERT clause
    # ========================================================
    #
    # CREATED_AT and UPDATED_AT are generated by Snowflake
    # rather than coming from the scraper.


    insert_columns = [
        column
        for column in df_snowflake.columns
        if column != "CREATED_AT"
    ]

    insert_values = [
        f"source.{column}"
        for column in insert_columns
    ]


    if "CREATED_AT" in target_columns:

        insert_columns.append("CREATED_AT")

        insert_values.append(
            "CURRENT_TIMESTAMP()"
        )


    if "UPDATED_AT" in target_columns:

        insert_columns.append("UPDATED_AT")

        insert_values.append(
            "CURRENT_TIMESTAMP()"
        )


    insert_columns_clause = ", ".join(
        insert_columns
    )

    insert_values_clause = ", ".join(
        insert_values
    )


    # ========================================================
    # 12.8 Build MERGE statement
    # ========================================================


    merge_sql = f"""
        MERGE INTO CLEANED_JOBS AS target

        USING CLEANED_JOBS_STAGE AS source

        ON target.JOB_ID = source.JOB_ID

        WHEN MATCHED THEN
            UPDATE SET
                {update_clause}

        WHEN NOT MATCHED THEN
            INSERT (
                {insert_columns_clause}
            )
            VALUES (
                {insert_values_clause}
            )
    """


    # ========================================================
    # 12.9 Execute MERGE
    # ========================================================


    cursor.execute(merge_sql)

    print(
        "Merge complete: "
        f"{cursor.rowcount} rows affected "
        "(inserted + updated)."
    )


    # ========================================================
    # 12.10 Commit
    # ========================================================


    conn.commit()

    print("Transaction committed successfully.")


# ============================================================
# 13. Roll back on failure
# ============================================================


except Exception:

    conn.rollback()

    print(
        "ERROR: Transaction rolled back."
    )

    raise


# ============================================================
# 14. Close Snowflake connection
# ============================================================


finally:

    cursor.close()
    conn.close()

    print("Snowflake connection closed.")


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

print(f"Loaded latest cleaned data: {df_snowflake.shape}")


# ============================================================
# 4. Prepare column names for Snowflake
# ============================================================

df_snowflake.columns = df_snowflake.columns.str.upper()


# ============================================================
# 5. Convert list columns to strings
# ============================================================

list_columns = [
    "EXTRACTED_SKILLS",
    "LISTED_SKILLS"
]

for col in list_columns:
    if col in df_snowflake.columns:
        df_snowflake[col] = df_snowflake[col].apply(
            lambda x: ", ".join(x)
            if isinstance(x, list)
            else x
        )

print("Skill columns prepared.")


# ============================================================
# 6. Prepare date columns
# ============================================================

if "POSTED_DATE" in df_snowflake.columns:
    df_snowflake["POSTED_DATE"] = pd.to_datetime(
        df_snowflake["POSTED_DATE"],
        errors="coerce"
    ).dt.date


if "POSTED_AT" in df_snowflake.columns:
    df_snowflake["POSTED_AT"] = pd.to_datetime(
        df_snowflake["POSTED_AT"],
        errors="coerce",
        utc=True
    )


# ============================================================
# 7. Connect to Snowflake
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
# 8. Replace old data with the latest cleaned data
# ============================================================

cursor = conn.cursor()

try:

    # Remove previous rows
    cursor.execute("TRUNCATE TABLE CLEANED_JOBS")

    print("Old CLEANED_JOBS data removed.")


    # Upload latest DataFrame
    success, nchunks, nrows, output = write_pandas(
        conn=conn,
        df=df_snowflake,
        table_name="CLEANED_JOBS",
        use_logical_type=True
    )


    if success:
        print("Upload successful!")
        print(f"Rows loaded: {nrows}")
        print(f"Chunks: {nchunks}")

    else:
        print("Upload failed.")


finally:

    cursor.close()
    conn.close()

    print("Snowflake connection closed.")
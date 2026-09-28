
"""
Job Data Pipeline

Medallion Architecture:

Job Sources
    ↓
main.py
    ↓
Bronze - Databricks Volume
    ↓
Bronze - Unity Catalog Delta Table
    ↓
cleaning.py
    ↓
Silver - Databricks Volume
    ↓
Silver - Unity Catalog Delta Table
    ↓
load_star_schema.py
    ↓
Gold - Snowflake Star Schema

Pipeline Flow:
1. Scrape job data
2. Save raw data to Bronze Volume
3. Update Bronze Unity Catalog table
4. Clean and transform Bronze data
5. Save cleaned data to Silver Volume
6. Update Silver Unity Catalog table
7. Read Silver Unity Catalog table
8. Load data into Snowflake Gold Star Schema
"""

from pathlib import Path


# ============================================================
# 1. Project Paths
# ============================================================

DATABRICKS_PROJECT = Path(
    "/Workspace/Users/"
    "reyofalthobaiti@gmail.com/"
    "JopDataPipeline123"
)


if DATABRICKS_PROJECT.exists():

    BASE_DIR = DATABRICKS_PROJECT

else:

    try:

        BASE_DIR = (
            Path(__file__)
            .resolve()
            .parent
        )

    except NameError:

        BASE_DIR = Path.cwd()


# ------------------------------------------------------------
# Pipeline Scripts
# ------------------------------------------------------------

SCRAPER_SCRIPT = (
    BASE_DIR / "main.py"
)

CLEANING_SCRIPT = (
    BASE_DIR
    / "scripts"
    / "cleaning.py"
)

STAR_SCHEMA_SCRIPT = (
    BASE_DIR
    / "scripts"
    / "load_star_schema.py"
)


# ============================================================
# 2. Medallion Storage Paths
# ============================================================

VOLUME_ROOT = Path(
    "/Volumes/"
    "job_data_pipeline/"
    "default/"
    "job_data"
)


BRONZE_PATH = (
    VOLUME_ROOT
    / "bronze"
    / "jobs_results.json"
)


SILVER_PATH = (
    VOLUME_ROOT
    / "silver"
    / "jobs_cleaned.json"
)


# ------------------------------------------------------------
# Unity Catalog Tables
# ------------------------------------------------------------

BRONZE_TABLE = (
    "job_data_pipeline."
    "default."
    "bronze_jobs"
)


SILVER_TABLE = (
    "job_data_pipeline."
    "default."
    "silver_jobs"
)


print(
    "BASE_DIR:",
    BASE_DIR
)


print(
    "Bronze Volume:",
    BRONZE_PATH
)


print(
    "Bronze UC:",
    BRONZE_TABLE
)


print(
    "Silver Volume:",
    SILVER_PATH
)


print(
    "Silver UC:",
    SILVER_TABLE
)


# ============================================================
# 3. Validate Pipeline Scripts
# ============================================================

PIPELINE_SCRIPTS = [
    SCRAPER_SCRIPT,
    CLEANING_SCRIPT,
    STAR_SCHEMA_SCRIPT,
]


for script in PIPELINE_SCRIPTS:

    if not script.exists():

        raise FileNotFoundError(
            "Pipeline script not found: "
            f"{script}"
        )


print(
    "\nPipeline scripts: PASS"
)


# ============================================================
# 4. Run Pipeline Step
# ============================================================

def run_step(
    step_name,
    script_path
):
    """
    Execute a Python pipeline script inside the current
    Python process.

    Databricks runtime objects such as dbutils and spark
    are passed to each script.
    """

    print(
        "\n" + "=" * 60
    )

    print(
        f"STARTING: {step_name}"
    )

    print(
        "=" * 60
    )


    # --------------------------------------------------------
    # Validate Script
    # --------------------------------------------------------

    if not script_path.exists():

        raise FileNotFoundError(
            "Script not found: "
            f"{script_path}"
        )


    # --------------------------------------------------------
    # Read Script
    # --------------------------------------------------------

    code = (
        script_path
        .read_text(
            encoding="utf-8"
        )
    )


    # --------------------------------------------------------
    # Prepare Script Environment
    # --------------------------------------------------------

    script_globals = {

        "__name__":
            "__main__",

        "__file__":
            str(script_path),

        "__builtins__":
            __builtins__,
    }


    # --------------------------------------------------------
    # Pass Databricks dbutils
    # --------------------------------------------------------

    if "dbutils" in globals():

        script_globals[
            "dbutils"
        ] = globals()[
            "dbutils"
        ]


    # --------------------------------------------------------
    # Pass Databricks Spark Session
    # --------------------------------------------------------

    if "spark" in globals():

        script_globals[
            "spark"
        ] = globals()[
            "spark"
        ]


    # --------------------------------------------------------
    # Execute Script
    # --------------------------------------------------------

    try:

        exec(
            compile(
                code,
                str(script_path),
                "exec"
            ),
            script_globals
        )


    except Exception as error:

        print(
            "\n" + "=" * 60
        )

        print(
            f"FAILED: {step_name}"
        )

        print(
            "=" * 60
        )

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise


    print(
        "\n" + "-" * 60
    )

    print(
        f"COMPLETED: {step_name}"
    )

    print(
        "-" * 60
    )


# ============================================================
# 5. Validate Bronze Volume
# ============================================================

def validate_bronze_volume():

    print(
        "\n===== BRONZE VOLUME VALIDATION ====="
    )


    if not BRONZE_PATH.exists():

        raise FileNotFoundError(
            "Bronze file was not created:\n"
            f"{BRONZE_PATH}"
        )


    size = (
        BRONZE_PATH
        .stat()
        .st_size
    )


    if size == 0:

        raise ValueError(
            "Bronze file exists "
            "but is empty."
        )


    print(
        "Bronze Volume: PASS"
    )


    print(
        "Path:",
        BRONZE_PATH
    )


    print(
        "Size:",
        size,
        "bytes"
    )


# ============================================================
# 6. Validate Bronze Unity Catalog
# ============================================================

def validate_bronze_unity_catalog():

    print(
        "\n===== BRONZE UNITY CATALOG VALIDATION ====="
    )


    if "spark" not in globals():

        raise RuntimeError(
            "Spark is not available. "
            "Cannot validate Bronze Unity Catalog table."
        )


    try:

        bronze_df = (
            spark.table(
                BRONZE_TABLE
            )
        )


        row_count = (
            bronze_df.count()
        )


    except Exception as error:

        raise RuntimeError(
            "Could not read Bronze Unity Catalog table: "
            f"{BRONZE_TABLE}"
        ) from error


    if row_count == 0:

        raise ValueError(
            "Bronze Unity Catalog "
            "table is empty."
        )


    print(
        "Bronze Unity Catalog: PASS"
    )


    print(
        "Table:",
        BRONZE_TABLE
    )


    print(
        "Rows:",
        row_count
    )


# ============================================================
# 7. Validate Silver Volume
# ============================================================

def validate_silver_volume():

    print(
        "\n===== SILVER VOLUME VALIDATION ====="
    )


    if not SILVER_PATH.exists():

        raise FileNotFoundError(
            "Silver file was not created:\n"
            f"{SILVER_PATH}"
        )


    size = (
        SILVER_PATH
        .stat()
        .st_size
    )


    if size == 0:

        raise ValueError(
            "Silver file exists "
            "but is empty."
        )


    print(
        "Silver Volume: PASS"
    )


    print(
        "Path:",
        SILVER_PATH
    )


    print(
        "Size:",
        size,
        "bytes"
    )


# ============================================================
# 8. Validate Silver Unity Catalog
# ============================================================

def validate_silver_unity_catalog():

    print(
        "\n===== SILVER UNITY CATALOG VALIDATION ====="
    )


    if "spark" not in globals():

        raise RuntimeError(
            "Spark is not available. "
            "Cannot validate Silver Unity Catalog table."
        )


    try:

        silver_df = (
            spark.table(
                SILVER_TABLE
            )
        )


        row_count = (
            silver_df.count()
        )


    except Exception as error:

        raise RuntimeError(
            "Could not read Silver Unity Catalog table: "
            f"{SILVER_TABLE}"
        ) from error


    if row_count == 0:

        raise ValueError(
            "Silver Unity Catalog "
            "table is empty."
        )


    print(
        "Silver Unity Catalog: PASS"
    )


    print(
        "Table:",
        SILVER_TABLE
    )


    print(
        "Rows:",
        row_count
    )


# ============================================================
# 9. Main Pipeline
# ============================================================

def main():

    print(
        "\n" + "=" * 60
    )

    print(
        "JOB DATA PIPELINE"
    )

    print(
        "=" * 60
    )


    print(
        "\nMedallion Pipeline Flow:"
    )


    print(
        "Job Sources"
        " -> Bronze Volume"
        " -> Bronze UC"
        " -> Silver Volume"
        " -> Silver UC"
        " -> Snowflake Gold"
    )


    # ========================================================
    # STEP 1
    # Job Sources -> Bronze
    # ========================================================

    run_step(
        "Job Scraping -> Bronze",
        SCRAPER_SCRIPT
    )


    # --------------------------------------------------------
    # Validate Bronze Volume
    # --------------------------------------------------------

    validate_bronze_volume()


    # --------------------------------------------------------
    # Validate Bronze Unity Catalog
    # --------------------------------------------------------

    validate_bronze_unity_catalog()


    # ========================================================
    # STEP 2
    # Bronze -> Silver
    # ========================================================

    run_step(
        "Bronze -> Silver Cleaning & Transformation",
        CLEANING_SCRIPT
    )


    # --------------------------------------------------------
    # Validate Silver Volume
    # --------------------------------------------------------

    validate_silver_volume()


    # --------------------------------------------------------
    # Validate Silver Unity Catalog
    # --------------------------------------------------------

    validate_silver_unity_catalog()


    # ========================================================
    # STEP 3
    # Silver UC -> Snowflake Gold
    # ========================================================

    run_step(
        "Silver Unity Catalog -> Snowflake Gold Star Schema",
        STAR_SCHEMA_SCRIPT
    )


    # ========================================================
    # Pipeline Complete
    # ========================================================

    print(
        "\n" + "=" * 60
    )


    print(
        "PIPELINE COMPLETED SUCCESSFULLY"
    )


    print(
        "=" * 60
    )


    print(
        "\nFinal Pipeline:"
    )


    print(
        "1. Job data scraped from JSearch"
    )


    print(
        "2. Raw data stored in Bronze Volume"
    )


    print(
        "3. Bronze Spark DataFrame stored "
        "as Unity Catalog Delta table"
    )


    print(
        "4. Bronze data cleaned and transformed"
    )


    print(
        "5. Cleaned data stored in Silver Volume"
    )


    print(
        "6. Silver Spark DataFrame stored "
        "as Unity Catalog Delta table"
    )


    print(
        "7. Silver Unity Catalog table "
        "loaded into Snowflake Gold"
    )


    # --------------------------------------------------------
    # Databricks Storage
    # --------------------------------------------------------

    print(
        "\nDatabricks Storage:"
    )


    print(
        "Bronze Volume:",
        BRONZE_PATH
    )


    print(
        "Bronze UC:",
        BRONZE_TABLE
    )


    print(
        "Silver Volume:",
        SILVER_PATH
    )


    print(
        "Silver UC:",
        SILVER_TABLE
    )


    # --------------------------------------------------------
    # Snowflake
    # --------------------------------------------------------

    print(
        "\nSnowflake Gold:"
    )


    print(
        "Database: JOBS_ANALYTICS"
    )


    print(
        "Schema:   JOBS"
    )


    # --------------------------------------------------------
    # Final Architecture
    # --------------------------------------------------------

    print(
        "\nArchitecture:"
    )


    print(
        "JSearch"
        " -> Bronze Volume"
        " -> bronze_jobs UC"
        " -> Cleaning"
        " -> Silver Volume"
        " -> silver_jobs UC"
        " -> Snowflake Gold"
    )


# ============================================================
# 10. Entry Point
# ============================================================

if __name__ == "__main__":

    main()



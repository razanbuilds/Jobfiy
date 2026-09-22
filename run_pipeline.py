"""
Job Data Pipeline

Pipeline flow:
1. Scrape job data
2. Clean and transform data
3. Load data into Snowflake Star Schema
"""

import sys
from pathlib import Path


# =========================================================
# Project Paths
# =========================================================

DATABRICKS_PROJECT = Path(
    "/Workspace/Users/reyofalthobaiti@gmail.com/JopDataPipeline123"
)

if DATABRICKS_PROJECT.exists():
    BASE_DIR = DATABRICKS_PROJECT
else:
    try:
        BASE_DIR = Path(__file__).resolve().parent
    except NameError:
        BASE_DIR = Path.cwd()


SCRAPER_SCRIPT = BASE_DIR / "main.py"
CLEANING_SCRIPT = BASE_DIR / "scripts" / "cleaning.py"
STAR_SCHEMA_SCRIPT = BASE_DIR / "scripts" / "load_star_schema.py"

print("BASE_DIR:", BASE_DIR)


# =========================================================
# Run Pipeline Step
# =========================================================

def run_step(step_name, script_path):
    """
    Run a Python script inside the current Python process.

    This is important in Databricks so scripts can access
    notebook-installed packages and Databricks utilities.
    """

    print("\n" + "=" * 60)
    print(f"STARTING: {step_name}")
    print("=" * 60)

    if not script_path.exists():
        raise FileNotFoundError(
            f"Script not found: {script_path}"
        )

    # Read script
    code = script_path.read_text(encoding="utf-8")

    # Give the executed script a correct __file__
    script_globals = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__builtins__": __builtins__,
    }
   

# Pass Databricks utilities to executed scripts
    if "dbutils" in globals():
     script_globals["dbutils"] = globals()["dbutils"]

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
        print("\n" + "=" * 60)
        print(f"FAILED: {step_name}")
        print("=" * 60)
        print(error)
        raise

    print(f"\nCOMPLETED: {step_name}")


# =========================================================
# Main Pipeline
# =========================================================

def main():

    print("\n" + "=" * 60)
    print("JOB DATA PIPELINE")
    print("=" * 60)

    print("\nPipeline Flow:")
    print("Scraping -> Cleaning -> Snowflake Star Schema")

    # 1. Scrape jobs
    run_step(
        "Job Scraping",
        SCRAPER_SCRIPT
    )

    # 2. Clean data
    run_step(
        "Data Cleaning & Transformation",
        CLEANING_SCRIPT
    )

    # 3. Load into Snowflake
    run_step(
        "Snowflake Star Schema Load",
        STAR_SCHEMA_SCRIPT
    )

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)

    print("\nPipeline finished:")
    print("1. Jobs scraped")
    print("2. Data cleaned and transformed")
    print("3. Star Schema loaded into Snowflake")

    print("\nSnowflake:")
    print("Database: JOBS_ANALYTICS")
    print("Schema:   JOBS")


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":
    main()
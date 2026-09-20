"""
Job Data Pipeline

Pipeline flow:
1. Scrape job data
2. Clean and transform data
3. Load data into Snowflake Star Schema
"""

import subprocess
import sys
from pathlib import Path


# =========================================================
# Project Paths
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SCRAPER_SCRIPT = BASE_DIR / "main.py"
CLEANING_SCRIPT = BASE_DIR / "scripts" / "cleaning.py"
STAR_SCHEMA_SCRIPT = BASE_DIR / "scripts" / "load_star_schema.py"


# =========================================================
# Run Pipeline Step
# =========================================================

def run_step(step_name, script_path):
    """
    Run one Python script as part of the pipeline.

    If the script fails, stop the entire pipeline.
    """

    print("\n" + "=" * 60)
    print(f"STARTING: {step_name}")
    print("=" * 60)

    # Make sure the script exists
    if not script_path.exists():
        print(f"\nERROR: Script not found:")
        print(script_path)
        print("\nPipeline stopped.")
        sys.exit(1)

    # Run using the same Python interpreter / venv
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BASE_DIR
    )

    # Stop pipeline if this step fails
    if result.returncode != 0:
        print("\n" + "=" * 60)
        print(f"FAILED: {step_name}")
        print(f"Exit code: {result.returncode}")
        print("Pipeline stopped.")
        print("=" * 60)

        sys.exit(result.returncode)

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

    # -----------------------------------------------------
    # Step 1: Scrape Jobs
    # -----------------------------------------------------

    run_step(
        "Job Scraping",
        SCRAPER_SCRIPT
    )

    # -----------------------------------------------------
    # Step 2: Clean & Transform Data
    # -----------------------------------------------------

    run_step(
        "Data Cleaning & Transformation",
        CLEANING_SCRIPT
    )

    # -----------------------------------------------------
    # Step 3: Load Snowflake Star Schema
    # -----------------------------------------------------

    run_step(
        "Snowflake Star Schema Load",
        STAR_SCHEMA_SCRIPT
    )

    # -----------------------------------------------------
    # Pipeline Finished
    # -----------------------------------------------------

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
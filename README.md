# Job Data Engineering Pipeline

## 1. Project Summary

This project delivers an **automated, end-to-end cloud data engineering pipeline** that transforms raw job postings into structured, analytics-ready data for job market analysis.

Job data is ingested from the **JSearch API** and processed through a **Medallion Architecture**. Raw records are stored in the **Bronze layer** in Azure Databricks, then cleaned, standardized, deduplicated, and enriched in the **Silver layer** using Python and Pandas. The processed data is incrementally loaded into the **Gold layer in Snowflake**, where it is modeled as a **Star Schema** optimized for analytical queries.

The workflow is executed as an **Azure Databricks Job** and orchestrated by **Azure Data Factory (ADF)**, enabling scheduled and repeatable pipeline runs. The resulting Snowflake data supports an interactive **Streamlit dashboard** for exploring job-market trends, companies, locations, skills, and other employment insights.

### Architecture

```text
JSearch API
     ↓
🥉 Bronze — Azure Databricks
Raw Job Data
     ↓
🥈 Silver — Azure Databricks
Cleaned & Transformed Data
     ↓
🥇 Gold — Snowflake
Analytics-Ready Star Schema
     ↓
Streamlit Dashboard

Azure Data Factory
        ↓
Orchestrates & Schedules
        ↓
Databricks Job
```

### Key Capabilities

- Automated API-based data ingestion
- Medallion Architecture: **Bronze → Silver → Gold**
- Data cleaning, transformation, enrichment, and validation
- Incremental loading to reduce duplicate records
- Snowflake dimensional modeling using a **Star Schema**
- Automated execution through **Databricks Jobs**
- Scheduling and orchestration through **Azure Data Factory**
- Interactive analytics through **Streamlit**

The project demonstrates the complete data engineering lifecycle from **data ingestion and transformation to cloud warehousing, orchestration, and analytics**.

---

## 2. Requirements

### Tools and Accounts

- Python 3
- Git
- JSearch API account
- Azure Databricks workspace
- Azure Data Factory
- Snowflake account

### Python Packages

Install the dependencies listed in `requirements.txt`.

Main packages include:

```text
pandas
requests
snowflake-connector-python
python-dotenv
databricks-sdk
```

### Databricks Storage

The Bronze and Silver layers use Databricks Unity Catalog Volumes:

```text
/Volumes/job_data_pipeline/bronze/job_data/
/Volumes/job_data_pipeline/silver/job_data/
```

---

## 3. Installation

Clone the repository:

```bash
git clone <repository-url>
cd JopDataPipeline123
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

The production pipeline is designed to run in **Azure Databricks**.

---

## 4. Run the Project

Run the complete pipeline from the project directory:

```bash
python run_pipeline.py
```

`run_pipeline.py` executes all stages sequentially:

```text
main.py
   ↓
Bronze
   ↓
scripts/cleaning.py
   ↓
Silver
   ↓
scripts/load_star_schema.py
   ↓
Snowflake Gold
```

### Expected Outputs

**Bronze — Raw Data**

```text
/Volumes/job_data_pipeline/bronze/job_data/jobs_results.json
```

**Silver — Cleaned Data**

```text
/Volumes/job_data_pipeline/silver/job_data/jobs_cleaned.json
```

**Gold — Snowflake Star Schema**

```text
DIM_COMPANY
DIM_LOCATION
DIM_DATE
DIM_JOB
DIM_SKILL
FACT_JOBS
BRIDGE_JOB_SKILL
```

For automated execution, `run_pipeline.py` is configured as an **Azure Databricks Job**, which can be triggered and scheduled through **Azure Data Factory**.

---

## 5. API Keys & Environment Variables

The project requires credentials for the JSearch API and Snowflake.

### JSearch

```text
JSEARCH_API_KEY
```

### Snowflake

```text
SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PASSWORD
SNOWFLAKE_WAREHOUSE
SNOWFLAKE_DATABASE
SNOWFLAKE_SCHEMA
```

Sensitive credentials are managed using **Databricks Secrets** and should not be committed to GitHub.

The configured Snowflake user must have the required permissions to access the target warehouse, database, schema, and tables.

---

## 6. Known Issues

- Pipeline execution depends on **JSearch API availability**, response times, and API limits.
- Source job postings may contain missing fields such as salary, city, skills, or experience level.
- Some attributes are derived from unstructured job descriptions and therefore depend on the quality of the source data.
- Additional job data sources could be integrated in the future to improve dataset coverage.
- The Streamlit analytics layer can be expanded with additional metrics, filters, and visualizations.
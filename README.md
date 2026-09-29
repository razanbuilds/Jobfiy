# Job Data Engineering Pipeline

## Overview

This project is an end-to-end **Data Engineering Pipeline** that collects technology job postings from the **JSearch API**, processes them in **Azure Databricks**, and loads analytics-ready data into **Snowflake**.

The project follows the **Medallion Architecture**:

**Bronze → Silver → Gold**

**Azure Data Factory (ADF)** orchestrates and schedules the pipeline, while **Streamlit** is used for data visualization.

---

## Architecture

```text
JSearch API
     │
     ▼
main.py
     │
     ▼
🥉 Bronze — Databricks
Raw Job Data
     │
     ▼
cleaning.py
     │
     ▼
🥈 Silver — Databricks
Cleaned Data
     │
     ▼
load_star_schema.py
     │
     ▼
🥇 Gold — Snowflake
Star Schema
     │
     ▼
Streamlit Dashboard
```

**ADF → Databricks Job → Bronze → Silver → Gold**

---

## Medallion Architecture

### 🥉 Bronze

Raw job data is collected from the **JSearch API** using `main.py`.

Stored in a Databricks Volume:

```text
/Volumes/job_data_pipeline/bronze/job_data/jobs_results.json
```

### 🥈 Silver

`scripts/cleaning.py` cleans and transforms the Bronze data.

Main transformations:

- Remove duplicates
- Handle missing values
- Clean locations and cities
- Process skills
- Extract experience levels
- Detect remote jobs and salary availability
- Process posting dates

Stored in:

```text
/Volumes/job_data_pipeline/silver/job_data/jobs_cleaned.json
```

### 🥇 Gold

`scripts/load_star_schema.py` loads the Silver data into **Snowflake**.

The Gold layer uses a **Star Schema** for analytics.

---

## Snowflake Star Schema

```text
DIM_COMPANY
     │
     ▼
FACT_JOBS ─── DIM_LOCATION
     │
     ├─────── DIM_DATE
     │
     ▼
DIM_JOB
     │
     ▼
BRIDGE_JOB_SKILL
     │
     ▼
DIM_SKILL
```

### Tables

- `FACT_JOBS`
- `DIM_JOB`
- `DIM_COMPANY`
- `DIM_LOCATION`
- `DIM_DATE`
- `DIM_SKILL`
- `BRIDGE_JOB_SKILL`

`BRIDGE_JOB_SKILL` handles the many-to-many relationship between jobs and skills.

---

# How to Run the Pipeline

## Step 1 — Open the Databricks Workspace

Open **Azure Databricks** and navigate to the project repository:

```text
JopDataPipeline123
```

---

## Step 2 — Install Dependencies

Make sure the required packages are installed:

```bash
pip install -r requirements.txt
```

Main dependencies include:

```text
pandas
requests
snowflake-connector-python
python-dotenv
databricks-sdk
```

---

## Step 3 — Configure Secrets

The pipeline requires credentials for:

```text
JSearch API
Snowflake Account
Snowflake Username
Snowflake Password
Snowflake Warehouse
```

These credentials are stored securely using **Databricks Secrets** and are not hard-coded in the repository.

---

## Step 4 — Run the Complete Pipeline

The main entry point is:

```bash
python run_pipeline.py
```

This automatically runs:

```text
1. main.py
      ↓
   Bronze

2. cleaning.py
      ↓
   Silver

3. load_star_schema.py
      ↓
   Gold
```

You do **not** need to run each script separately.

---

## Step 5 — Verify Bronze

Check the Bronze Databricks Volume:

```text
/Volumes/job_data_pipeline/bronze/job_data/
```

Expected file:

```text
jobs_results.json
```

This contains the raw collected job data.

---

## Step 6 — Verify Silver

Check:

```text
/Volumes/job_data_pipeline/silver/job_data/
```

Expected file:

```text
jobs_cleaned.json
```

This contains the cleaned and transformed job data.

---

## Step 7 — Verify Gold in Snowflake

Open Snowflake:

```text
JOBS_ANALYTICS
   └── JOBS
```

Verify the Star Schema tables:

```text
FACT_JOBS
DIM_JOB
DIM_COMPANY
DIM_LOCATION
DIM_DATE
DIM_SKILL
BRIDGE_JOB_SKILL
```

Example validation:

```sql
SELECT COUNT(*) FROM FACT_JOBS;
```

---

## Step 8 — Run Through Databricks Job

The production pipeline is configured as a **Databricks Job**.

The job executes:

```text
run_pipeline.py
```

Run the job and verify that the execution status is:

```text
Succeeded
```

---

## Step 9 — Run Through ADF

**Azure Data Factory** is the orchestrator.

```text
ADF Trigger
    ↓
Databricks Job
    ↓
run_pipeline.py
    ↓
Bronze → Silver → Gold
```

ADF can run the pipeline automatically using a scheduled trigger.

Check the ADF Monitor page to verify that the pipeline run **Succeeded**.

---

## Project Structure

```text
JopDataPipeline123/
│
├── main.py
├── run_pipeline.py
├── requirements.txt
│
└── scripts/
    ├── cleaning.py
    └── load_star_schema.py
```

| File | Purpose |
|---|---|
| `main.py` | Ingestion → Bronze |
| `cleaning.py` | Transformation → Silver |
| `load_star_schema.py` | Loading → Gold |
| `run_pipeline.py` | Runs the complete pipeline |

---

## Technologies

- Python
- Pandas
- JSearch API
- Azure Databricks
- Databricks Unity Catalog & Volumes
- Azure Data Factory
- Snowflake
- SQL
- Streamlit
- GitHub

---

## Key Features

- Medallion Architecture
- Automated API ingestion
- Bronze and Silver Databricks storage
- Data cleaning and validation
- Incremental Snowflake loading
- Star Schema
- Databricks Job automation
- ADF orchestration and scheduling
- Secure Databricks Secrets
- Streamlit analytics dashboard

---

## Final Pipeline

```text
JSearch API
    ↓
🥉 Bronze
    ↓
🥈 Silver
    ↓
🥇 Gold — Snowflake
    ↓
Streamlit
```

**Azure Data Factory orchestrates the Databricks Job that executes the complete pipeline.**

### Final Workflow

**JSearch API → Python ETL → Databricks Job → Snowflake Star Schema**

with **Azure Data Factory** handling orchestration and scheduling.

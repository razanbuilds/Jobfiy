# Job Data Engineering Pipeline

## Overview

This project is an end-to-end **Data Engineering Pipeline** designed to collect technology job postings from the **JSearch API**, clean and transform the data using Python, and load the processed data into a **Snowflake Data Warehouse**.

The pipeline runs on **Azure Databricks**, while **Azure Data Factory (ADF)** is used for orchestration and scheduling.

The goal is to create an automated workflow that continuously collects new job data and stores it in an analytics-ready **Star Schema**.

---

## Architecture

```text
                  Azure Data Factory
              Orchestration & Scheduling
                         │
                         ▼
                  Databricks Job
                         │
                         ▼
                  run_pipeline.py
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
 Data Ingestion      Cleaning &       Data Loading
    main.py         Transformation    load_star_schema.py
        │            cleaning.py           │
        ▼                │                 ▼
   JSearch API           ▼              Snowflake
                    Cleaned Data        Star Schema
```

### Pipeline Flow

**ADF → Databricks Job → Data Ingestion → Cleaning & Transformation → Incremental Loading → Snowflake**

---

## Pipeline Stages

### 1. Data Ingestion

`main.py` is responsible for collecting technology job postings from the **JSearch API**.

The ingestion process includes:

- Fetching technology job postings
- Normalizing API responses
- Removing duplicate jobs
- Adding a `fetched_at` ingestion timestamp
- Storing the collected data for further processing

---

### 2. Data Cleaning & Transformation

`scripts/cleaning.py` cleans and prepares the collected data before loading it into the data warehouse.

The transformation process includes:

- Handling missing values
- Removing duplicate records
- Cleaning text fields
- Processing job locations and Saudi cities
- Processing skills
- Identifying experience levels
- Identifying remote jobs
- Detecting salary availability
- Converting relative posting times into timestamps
- Creating date attributes such as year, month, and day

The cleaned data is then prepared for loading into Snowflake.

---

### 3. Data Loading

`scripts/load_star_schema.py` loads the transformed data into **Snowflake**.

The pipeline uses an **incremental loading** approach to prevent existing jobs from being repeatedly inserted.

A stable `JOB_ID` is generated for each job to help identify previously loaded records.

---

## Snowflake Data Model

The data warehouse follows a **Star Schema** optimized for job market analysis.

```text
                     DIM_COMPANY
                          │
                          │
DIM_LOCATION ──────── FACT_JOBS ──────── DIM_DATE
                          │
                          │
                       DIM_JOB
                          │
                          │
                  BRIDGE_JOB_SKILL
                          │
                          │
                      DIM_SKILL
```

### Tables

| Table | Description |
|---|---|
| `FACT_JOBS` | Central fact table for job postings |
| `DIM_JOB` | Job details |
| `DIM_COMPANY` | Company information |
| `DIM_LOCATION` | Job location information |
| `DIM_DATE` | Job posting date attributes |
| `DIM_SKILL` | Skills associated with jobs |
| `BRIDGE_JOB_SKILL` | Connects jobs and skills through a many-to-many relationship |

---

## Databricks

**Azure Databricks** is used as the execution environment for the pipeline.

The main pipeline entry point is:

```bash
python run_pipeline.py
```

`run_pipeline.py` executes the three pipeline stages sequentially:

```text
main.py
   ↓
cleaning.py
   ↓
load_star_schema.py
```

The complete workflow is configured as a **Databricks Job**, allowing the pipeline to run as a managed workload.

---

## Azure Data Factory

**Azure Data Factory (ADF)** is used as the pipeline orchestrator.

ADF connects to Databricks and triggers the configured **Databricks Job**.

A scheduled trigger can be configured in ADF to run the pipeline automatically at a specified time.

```text
ADF Schedule Trigger
        ↓
Databricks Job
        ↓
run_pipeline.py
        ↓
Data Ingestion
        ↓
Cleaning & Transformation
        ↓
Snowflake Load
```

---

## Security

Sensitive credentials are not hard-coded in the source code.

**Databricks Secrets** are used to securely manage credentials such as:

- JSearch API key
- Snowflake username
- Snowflake password
- Snowflake account
- Snowflake warehouse

---

## Project Structure

```text
JopDataPipeline123/
│
├── main.py
├── run_pipeline.py
├── requirements.txt
├── README.md
│
├── scripts/
│   ├── cleaning.py
│   └── load_star_schema.py
│
└── data/
    ├── jobs_results.json
    └── jobs_cleaned.json
```

---

## Requirements

The project dependencies are listed in `requirements.txt`:

```txt
pandas
requests
snowflake-connector-python
python-dotenv
databricks-sdk
```

Install them using:

```bash
pip install -r requirements.txt
```

---

## Technologies Used

- **Python** — Pipeline development
- **Pandas** — Data cleaning and transformation
- **JSearch API** — Job data source
- **Azure Databricks** — Pipeline execution
- **Azure Data Factory (ADF)** — Orchestration and scheduling
- **Snowflake** — Cloud data warehouse
- **SQL** — Data modeling and warehouse operations
- **Git & GitHub** — Version control

---

## Key Features

- End-to-end data engineering pipeline
- API-based data ingestion
- Automated data cleaning and transformation
- Incremental data loading
- Snowflake cloud data warehouse
- Star Schema dimensional modeling
- Job-to-skill many-to-many modeling
- Databricks Job execution
- Azure Data Factory orchestration
- Scheduled pipeline execution
- Secure credential management with Databricks Secrets
- GitHub version control

---

## Summary

This project demonstrates a complete **cloud data engineering workflow**, starting from job data ingestion and ending with analytics-ready data stored in Snowflake.

The final pipeline combines **JSearch API, Python, Azure Databricks, Azure Data Factory, and Snowflake** to create an automated and maintainable data processing workflow.

### Final Workflow

**JSearch API → Python ETL → Databricks Job → Snowflake Star Schema**

with **Azure Data Factory** handling orchestration and scheduling.

# Job Data Pipeline

## Overview

This project is an end-to-end **Data Engineering Pipeline** that collects technology job postings, cleans and transforms the data, and loads it into a **Snowflake Data Warehouse**.

The pipeline runs on **Azure Databricks** and is orchestrated using **Azure Data Factory (ADF)**.

## Architecture

```text
JSearch API
     ↓
Data Ingestion
     ↓
Data Cleaning & Transformation
     ↓
Snowflake Star Schema
     ↑
Azure Databricks
     ↑
Azure Data Factory (ADF)
```

## How the Pipeline Works

The pipeline runs through three main steps:

**1. Data Ingestion — `main.py`**  
Collects technology job postings from the JSearch API and stores the raw data.

**2. Data Cleaning — `cleaning.py`**  
Cleans and transforms the collected data by handling missing values, removing duplicates, processing dates, locations, skills, and other job attributes.

**3. Data Loading — `load_star_schema.py`**  
Loads the cleaned data incrementally into a Snowflake Star Schema.

The entire process is executed through:

`run_pipeline.py`

## Snowflake Data Model

The data warehouse contains:

- `FACT_JOBS`
- `DIM_JOB`
- `DIM_COMPANY`
- `DIM_LOCATION`
- `DIM_DATE`
- `DIM_SKILL`
- `BRIDGE_JOB_SKILL`

The bridge table is used to handle the many-to-many relationship between jobs and skills.

## Automation

The complete automated workflow is:

```text
Azure Data Factory
        ↓
Databricks Job
        ↓
run_pipeline.py
        ↓
JSearch API
        ↓
Data Cleaning
        ↓
Incremental Load
        ↓
Snowflake
```

**Azure Data Factory** acts as the orchestrator and triggers the **Databricks Job** based on a schedule.

**Azure Databricks** executes the Python pipeline.

**Snowflake** stores the final transformed data in a Star Schema.

## Security

API keys and Snowflake credentials are securely stored using **Databricks Secrets** instead of being hard-coded in the source code.

## Technologies

- Python
- Pandas
- JSearch API
- Azure Databricks
- Azure Data Factory
- Snowflake
- SQL
- GitHub

## Project Structure

```text
JopDataPipeline123/
│
├── main.py
├── run_pipeline.py
│
├── scripts/
│   ├── cleaning.py
│   └── load_star_schema.py
│
└── data/
```

## Final Pipeline

**JSearch API → Databricks → Data Cleaning & Transformation → Snowflake → ADF Orchestration**

The result is an automated and reusable data pipeline for collecting and processing technology job market data.

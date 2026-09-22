"""
Job Market Data Pipeline — Streamlit Dashboard

Connects DIRECTLY to Snowflake (JOBS_ANALYTICS.JOBS) and queries the
live star schema. No local files, no CSVs — every number on this page
comes straight from a SELECT against the tables your pipeline loaded.

Requires a .env file (NOT .env.example) in the project root with:

    SNOWFLAKE_ACCOUNT=xxxxx
    SNOWFLAKE_USER=xxxxx
    SNOWFLAKE_PASSWORD=xxxxx
    SNOWFLAKE_WAREHOUSE=xxxxx

(Database/schema are hardcoded below since they're fixed: JOBS_ANALYTICS.JOBS)

Run with:
    pip install streamlit snowflake-connector-python python-dotenv pandas
    streamlit run dashboard.py
"""

import os

import pandas as pd
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Job Market Dashboard", layout="wide")


# ============================================================
# Connection (cached so we don't reconnect on every rerun)
# ============================================================

@st.cache_resource
def get_connection():
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_WAREHOUSE"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        st.error(
            "Missing Snowflake credentials in your .env file: "
            + ", ".join(missing)
            + "\n\nCopy .env.example to .env and fill in real values "
              "(ask a teammate for the actual account/user/password)."
        )
        st.stop()

    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database="JOBS_ANALYTICS",
        schema="JOBS",
    )


@st.cache_data(ttl=600)
def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ============================================================
# Header
# ============================================================

st.title("📊 Job Market Data Pipeline — Live Dashboard")
st.caption("Data source: Snowflake · JOBS_ANALYTICS.JOBS (live query, not a snapshot)")

# ============================================================
# Top-line metrics
# ============================================================

counts = run_query(
    """
    SELECT
        (SELECT COUNT(*) FROM FACT_JOBS)     AS total_jobs,
        (SELECT COUNT(*) FROM DIM_COMPANY)   AS total_companies,
        (SELECT COUNT(*) FROM DIM_SKILL)     AS total_skills,
        (SELECT COUNT(*) FROM DIM_LOCATION)  AS total_locations
    """
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Job Postings", int(counts["TOTAL_JOBS"][0]))
c2.metric("Unique Companies", int(counts["TOTAL_COMPANIES"][0]))
c3.metric("Unique Skills", int(counts["TOTAL_SKILLS"][0]))
c4.metric("Unique Locations", int(counts["TOTAL_LOCATIONS"][0]))

st.divider()

# ============================================================
# Top skills in demand (via bridge table)
# ============================================================

st.subheader("🔧 Top 10 Most In-Demand Skills")

top_skills = run_query(
    """
    SELECT s.SKILL_NAME, COUNT(*) AS JOB_COUNT
    FROM BRIDGE_JOB_SKILL b
    JOIN DIM_SKILL s ON b.SKILL_KEY = s.SKILL_KEY
    GROUP BY s.SKILL_NAME
    ORDER BY JOB_COUNT DESC
    LIMIT 10
    """
)

if not top_skills.empty:
    st.bar_chart(top_skills.set_index("SKILL_NAME")["JOB_COUNT"])
else:
    st.info("No skill data yet — check that BRIDGE_JOB_SKILL has rows.")

# ============================================================
# Jobs by city
# ============================================================

st.subheader("📍 Job Postings by City")

by_city = run_query(
    """
    SELECT l.CITY, COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    WHERE l.CITY IS NOT NULL
    GROUP BY l.CITY
    ORDER BY JOB_COUNT DESC
    LIMIT 15
    """
)

if not by_city.empty:
    st.bar_chart(by_city.set_index("CITY")["JOB_COUNT"])
else:
    st.info("No location data yet.")

# ============================================================
# Top hiring companies
# ============================================================

st.subheader("🏢 Top 10 Hiring Companies")

top_companies = run_query(
    """
    SELECT c.COMPANY_NAME, COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_COMPANY c ON f.COMPANY_KEY = c.COMPANY_KEY
    GROUP BY c.COMPANY_NAME
    ORDER BY JOB_COUNT DESC
    LIMIT 10
    """
)

if not top_companies.empty:
    st.bar_chart(top_companies.set_index("COMPANY_NAME")["JOB_COUNT"])
else:
    st.info("No company data yet.")

# ============================================================
# Postings over time
# ============================================================

st.subheader("📅 Postings Over Time")

by_date = run_query(
    """
    SELECT d.POSTED_DATE, COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    GROUP BY d.POSTED_DATE
    ORDER BY d.POSTED_DATE
    """
)

if not by_date.empty:
    by_date["POSTED_DATE"] = pd.to_datetime(by_date["POSTED_DATE"])
    st.line_chart(by_date.set_index("POSTED_DATE")["JOB_COUNT"])
else:
    st.info("No date data yet.")

# ============================================================
# Remote vs on-site split
# ============================================================

st.subheader("🏠 Remote vs On-site")

remote_split = run_query(
    """
    SELECT
        CASE WHEN IS_REMOTE THEN 'Remote' ELSE 'On-site' END AS WORK_TYPE,
        COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS
    GROUP BY WORK_TYPE
    """
)

if not remote_split.empty:
    st.bar_chart(remote_split.set_index("WORK_TYPE")["JOB_COUNT"])

st.divider()

# ============================================================
# Raw data preview (proves the pipeline actually loaded real rows)
# ============================================================

st.subheader("🔍 Sample of Loaded Job Records")

sample = run_query(
    """
    SELECT
        j.JOB_TITLE,
        c.COMPANY_NAME,
        l.CITY,
        j.EMPLOYMENT_TYPE,
        j.EXPERIENCE_LEVEL,
        f.IS_REMOTE,
        d.POSTED_DATE
    FROM FACT_JOBS f
    JOIN DIM_JOB j       ON f.JOB_KEY = j.JOB_KEY
    LEFT JOIN DIM_COMPANY c  ON f.COMPANY_KEY = c.COMPANY_KEY
    LEFT JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    LEFT JOIN DIM_DATE d     ON f.DATE_KEY = d.DATE_KEY
    ORDER BY d.POSTED_DATE DESC NULLS LAST
    LIMIT 50
    """
)

st.dataframe(sample, use_container_width=True)

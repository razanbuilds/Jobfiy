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
    pip install streamlit snowflake-connector-python python-dotenv pandas matplotlib
    streamlit run dashboard.py
"""

import os

import pandas as pd
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Jobify Dashboard", page_icon="logo.png", layout="wide")

# ============================================================
# Look & feel — navy palette matching the Jobify logo
# ============================================================

PRIMARY = "#1B2A4A"      # deep navy — bars, accents, headers
PRIMARY_LIGHT = "#5C7DAA"  # muted steel blue — metric values, secondary bars
ACCENT = "#C99A3B"       # warm gold — used sparingly (remote split, highlights)
INK = "#0E1626"
CARD_BG = "rgba(27, 42, 74, 0.08)"
CARD_BORDER = "rgba(27, 42, 74, 0.25)"

st.markdown(
    f"""
    <style>
        .stMetric {{
            background: {CARD_BG};
            border: 1px solid {CARD_BORDER};
            border-radius: 10px;
            padding: 12px 16px;
        }}
        [data-testid="stMetricValue"] {{
            color: {PRIMARY_LIGHT};
        }}
        [data-testid="stMetricLabel"] {{
            color: {INK};
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid {CARD_BORDER};
            border-radius: 8px;
        }}
        h1, h2, h3 {{
            color: {PRIMARY};
        }}
        section[data-testid="stSidebar"] {{
            border-right: 1px solid {CARD_BORDER};
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Logo only next to the title — not pinned at the top of the sidebar/app
title_col1, title_col2 = st.columns([1, 8], vertical_alignment="center")
with title_col1:
    st.image("logo.png", width=64)
with title_col2:
    st.title("Jobify — Live Job Market Dashboard")

st.caption("Data source: Snowflake · JOBS_ANALYTICS.JOBS (live query, not a snapshot)")

# ============================================================
# City name normalization (Arabic → English)
#
# NOTE: this list covers the variants seen so far. Run
#   SELECT DISTINCT CITY FROM DIM_LOCATION;
# in Snowflake and send me the output if you want this made
# fully exhaustive — anything not in this map passes through
# unchanged, so an unmapped Arabic name would still show up
# as its own bar.
# ============================================================

CITY_MAP = {
    "الرياض": "Riyadh",
    "الدمام": "Dammam",
    "مكة": "Makkah",
    "جدة": "Jeddah",
    "المدينة": "Madinah",
    "الخبر": "Al Khobar",
    "أبها": "Abha",
}
CITY_DROP = {"دول"}  # not a real city — placeholder/bad data

# Same bilingual-data problem showed up in EMPLOYMENT_TYPE ("دوام كامل" =
# Full-time, etc). Same caveat as CITY_MAP: extend this if
# SELECT DISTINCT EMPLOYMENT_TYPE FROM DIM_JOB turns up more variants.
EMPLOYMENT_MAP = {
    "دوام كامل": "Full-time",
    "دوام جزئي": "Part-time",
    "عقد": "Contract",
    "تدريب": "Internship",
    "مؤقت": "Temporary",
    "عن بُعد": "Remote",
}


def normalize_employment(series: pd.Series) -> pd.Series:
    return series.replace(EMPLOYMENT_MAP)


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
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params or {})
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def normalize_city(series: pd.Series) -> pd.Series:
    out = series.replace(CITY_MAP)
    out = out.where(~series.isin(CITY_DROP), None)
    return out


# ============================================================
# Sidebar filters
# ============================================================

st.sidebar.header("Filters")

city_options_raw = run_query(
    "SELECT DISTINCT CITY FROM DIM_LOCATION WHERE CITY IS NOT NULL ORDER BY CITY"
)
city_options_raw["CITY_EN"] = normalize_city(city_options_raw["CITY"])
city_lookup = dict(zip(city_options_raw["CITY_EN"], city_options_raw["CITY"]))
city_choices = sorted([c for c in city_lookup if c])
selected_cities_en = st.sidebar.multiselect("City", city_choices)
selected_cities_raw = [city_lookup[c] for c in selected_cities_en]

emp_options_raw = run_query(
    "SELECT DISTINCT EMPLOYMENT_TYPE FROM DIM_JOB WHERE EMPLOYMENT_TYPE IS NOT NULL ORDER BY 1"
)
emp_options_raw["EMP_EN"] = normalize_employment(emp_options_raw["EMPLOYMENT_TYPE"])
emp_lookup = dict(zip(emp_options_raw["EMP_EN"], emp_options_raw["EMPLOYMENT_TYPE"]))
emp_choices = sorted(emp_lookup.keys())
selected_emp_en = st.sidebar.multiselect("Employment type", emp_choices)
selected_emp = [emp_lookup[e] for e in selected_emp_en]

work_type = st.sidebar.radio("Work type", ["All", "Remote", "On-site"], horizontal=True)

date_bounds = run_query(
    "SELECT MIN(POSTED_DATE) AS MIN_D, MAX(POSTED_DATE) AS MAX_D FROM DIM_DATE d JOIN FACT_JOBS f ON f.DATE_KEY = d.DATE_KEY"
)
min_d, max_d = date_bounds["MIN_D"][0], date_bounds["MAX_D"][0]
date_range = st.sidebar.date_input("Posted date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

if st.sidebar.button("Reset filters"):
    st.rerun()

# Build a shared WHERE clause + params from the filters above
where_clauses = ["1=1"]
params: dict = {}

if selected_cities_raw:
    where_clauses.append("l.CITY IN (%(cities)s)".replace("%(cities)s", ",".join(f"'{c}'" for c in selected_cities_raw)))
if selected_emp:
    where_clauses.append("j.EMPLOYMENT_TYPE IN (%(emp)s)".replace("%(emp)s", ",".join(f"'{e}'" for e in selected_emp)))
if work_type == "Remote":
    where_clauses.append("f.IS_REMOTE = TRUE")
elif work_type == "On-site":
    where_clauses.append("f.IS_REMOTE = FALSE")
if isinstance(date_range, tuple) and len(date_range) == 2:
    where_clauses.append(f"d.POSTED_DATE BETWEEN '{date_range[0]}' AND '{date_range[1]}'")

WHERE_SQL = " AND ".join(where_clauses)

# ============================================================
# Top-line metrics, with week-over-week trend
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

trend = run_query(
    """
    SELECT
        SUM(CASE WHEN d.POSTED_DATE >= DATEADD('day', -7, CURRENT_DATE) THEN 1 ELSE 0 END) AS last_7,
        SUM(CASE WHEN d.POSTED_DATE >= DATEADD('day', -14, CURRENT_DATE)
                 AND d.POSTED_DATE < DATEADD('day', -7, CURRENT_DATE) THEN 1 ELSE 0 END) AS prior_7
    FROM FACT_JOBS f
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    """
)
last_7 = int(trend["LAST_7"][0] or 0)
prior_7 = int(trend["PRIOR_7"][0] or 0)
delta = last_7 - prior_7

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Job Postings", int(counts["TOTAL_JOBS"][0]), delta=f"{delta:+d} vs prior week")
c2.metric("Unique Companies", int(counts["TOTAL_COMPANIES"][0]))
c3.metric("Unique Skills", int(counts["TOTAL_SKILLS"][0]))
c4.metric("Unique Locations", int(counts["TOTAL_LOCATIONS"][0]))

st.divider()

# ============================================================
# Top skills in demand (via bridge table)
# ============================================================

st.subheader("🔧 Top 10 Most In-Demand Skills")

top_skills = run_query(
    f"""
    SELECT s.SKILL_NAME, COUNT(*) AS JOB_COUNT
    FROM BRIDGE_JOB_SKILL b
    JOIN DIM_SKILL s ON b.SKILL_KEY = s.SKILL_KEY
    JOIN FACT_JOBS f ON b.JOB_KEY = f.JOB_KEY
    JOIN DIM_JOB j ON f.JOB_KEY = j.JOB_KEY
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}
    GROUP BY s.SKILL_NAME
    ORDER BY JOB_COUNT DESC
    LIMIT 10
    """
)

if not top_skills.empty:
    st.bar_chart(top_skills.set_index("SKILL_NAME")["JOB_COUNT"], color=PRIMARY)
else:
    st.info("No skill data matches the current filters.")

# ============================================================
# Jobs by city
# ============================================================

st.subheader("📍 Job Postings by City")

by_city = run_query(
    f"""
    SELECT l.CITY AS CITY_RAW, COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN DIM_JOB j ON f.JOB_KEY = j.JOB_KEY
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL} AND l.CITY IS NOT NULL
    GROUP BY l.CITY
    ORDER BY JOB_COUNT DESC
    """
)

if not by_city.empty:
    by_city["CITY"] = normalize_city(by_city["CITY_RAW"])
    by_city = by_city.dropna(subset=["CITY"]).groupby("CITY", as_index=False)["JOB_COUNT"].sum()
    by_city = by_city.sort_values("JOB_COUNT", ascending=False).head(15)
    st.bar_chart(by_city.set_index("CITY")["JOB_COUNT"], color=PRIMARY)
else:
    st.info("No location data matches the current filters.")

# ============================================================
# Top hiring companies
# ============================================================

st.subheader("🏢 Top 10 Hiring Companies")

top_companies = run_query(
    f"""
    SELECT c.COMPANY_NAME, COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_COMPANY c ON f.COMPANY_KEY = c.COMPANY_KEY
    JOIN DIM_JOB j ON f.JOB_KEY = j.JOB_KEY
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}
    GROUP BY c.COMPANY_NAME
    ORDER BY JOB_COUNT DESC
    LIMIT 10
    """
)

if not top_companies.empty:
    st.bar_chart(top_companies.set_index("COMPANY_NAME")["JOB_COUNT"], horizontal=True, color=PRIMARY)
else:
    st.info("No company data matches the current filters.")

# ============================================================
# Skills by city — cross-tab so you can see what's in demand where
# ============================================================

st.subheader("🧭 Top Skills by City")

skills_by_city = run_query(
    f"""
    SELECT l.CITY AS CITY_RAW, s.SKILL_NAME, COUNT(*) AS JOB_COUNT
    FROM BRIDGE_JOB_SKILL b
    JOIN DIM_SKILL s ON b.SKILL_KEY = s.SKILL_KEY
    JOIN FACT_JOBS f ON b.JOB_KEY = f.JOB_KEY
    JOIN DIM_JOB j ON f.JOB_KEY = j.JOB_KEY
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL} AND l.CITY IS NOT NULL
    GROUP BY l.CITY, s.SKILL_NAME
    """
)

if not skills_by_city.empty:
    skills_by_city["CITY"] = normalize_city(skills_by_city["CITY_RAW"])
    skills_by_city = skills_by_city.dropna(subset=["CITY"])
    top_cities_for_pivot = (
        skills_by_city.groupby("CITY")["JOB_COUNT"].sum().sort_values(ascending=False).head(6).index
    )
    pivot = (
        skills_by_city[skills_by_city["CITY"].isin(top_cities_for_pivot)]
        .pivot_table(index="SKILL_NAME", columns="CITY", values="JOB_COUNT", aggfunc="sum", fill_value=0)
    )
    top_skill_rows = pivot.sum(axis=1).sort_values(ascending=False).head(10).index
    pivot = pivot.loc[top_skill_rows]
    st.dataframe(
        pivot.style.background_gradient(cmap="Blues", axis=None),
        use_container_width=True,
    )
else:
    st.info("No skill/city data matches the current filters.")

# ============================================================
# Postings over time
# ============================================================

st.subheader("📅 Postings Over Time")

by_date = run_query(
    f"""
    SELECT d.POSTED_DATE, COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    JOIN DIM_JOB j ON f.JOB_KEY = j.JOB_KEY
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    WHERE {WHERE_SQL}
    GROUP BY d.POSTED_DATE
    ORDER BY d.POSTED_DATE
    """
)

if not by_date.empty:
    by_date["POSTED_DATE"] = pd.to_datetime(by_date["POSTED_DATE"])
    st.line_chart(by_date.set_index("POSTED_DATE")["JOB_COUNT"], color=PRIMARY)
    st.caption(
        "If this line spikes or drops to 0 sharply, check DIM_DATE / POSTED_DATE for "
        "missing or bad values rather than assuming it's real hiring activity."
    )
else:
    st.info("No date data matches the current filters.")

# ============================================================
# Remote vs on-site split
# ============================================================

st.subheader("🏠 Remote vs On-site")

remote_split = run_query(
    f"""
    SELECT
        CASE WHEN f.IS_REMOTE THEN 'Remote' ELSE 'On-site' END AS WORK_TYPE,
        COUNT(*) AS JOB_COUNT
    FROM FACT_JOBS f
    JOIN DIM_JOB j ON f.JOB_KEY = j.JOB_KEY
    JOIN DIM_LOCATION l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN DIM_DATE d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}
    GROUP BY WORK_TYPE
    """
)

if not remote_split.empty:
    st.bar_chart(remote_split.set_index("WORK_TYPE")["JOB_COUNT"], color=ACCENT)
    cols = st.columns(len(remote_split))
    for col, (_, row) in zip(cols, remote_split.iterrows()):
        col.metric(row["WORK_TYPE"], int(row["JOB_COUNT"]))
else:
    st.info("No remote/on-site data matches the current filters.")

st.divider()

# ============================================================
# Raw data preview (proves the pipeline actually loaded real rows)
# ============================================================

st.subheader("🔍 Sample of Loaded Job Records")
st.caption("Use the search icon in the table toolbar to filter rows, or the download icon to export.")

sample = run_query(
    f"""
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
    WHERE {WHERE_SQL}
    ORDER BY d.POSTED_DATE DESC NULLS LAST
    LIMIT 200
    """
)

if not sample.empty:
    sample["CITY"] = normalize_city(sample["CITY"]).fillna("Unknown")
    sample["EMPLOYMENT_TYPE"] = normalize_employment(sample["EMPLOYMENT_TYPE"])
st.dataframe(sample, use_container_width=True)

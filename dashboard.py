"""
Jobify — Live Job Market Dashboard (Streamlit)

Connects directly to Snowflake and queries the live star schema.
No local files, no CSVs: every number on this page comes from a SELECT
against the tables the pipeline loaded.

Credentials (never commit these):
  - Streamlit Cloud: App settings -> Secrets
  - Local: a .env file in the project root with
        SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
        SNOWFLAKE_WAREHOUSE  (optional: SNOWFLAKE_ROLE)

Run locally:
    pip install streamlit snowflake-connector-python python-dotenv pandas matplotlib altair
    streamlit run dashboard.py
"""

import os

import altair as alt
import pandas as pd
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Config
# ============================================================

# Must match the schema the pipeline loads into.
SNOWFLAKE_DATABASE = "JOBS_ANALYTICS"
SNOWFLAKE_SCHEMA = "GOLD"

LOGO_PATH = "logo.png"
HAS_LOGO = os.path.exists(LOGO_PATH)

st.set_page_config(
    page_title="Jobify Dashboard",
    page_icon=LOGO_PATH if HAS_LOGO else "📊",
    layout="wide",
)

# ============================================================
# Look & feel: navy palette matching the Jobify logo
# ============================================================

PRIMARY = "#1B2A4A"        # deep navy: bars, headers
PRIMARY_LIGHT = "#5C7DAA"  # steel blue: metric values
ACCENT = "#C99A3B"         # warm gold: remote split
INK = "#0E1626"
CARD_BG = "rgba(27, 42, 74, 0.08)"
CARD_BORDER = "rgba(27, 42, 74, 0.25)"

# IBM Plex Sans + IBM Plex Sans Arabic: one family that covers English and
# Arabic text in the same weights. Icon fonts are deliberately left alone.
st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');

        html, body, .stApp, .stApp p, .stApp label, .stApp li,
        .stApp h1, .stApp h2, .stApp h3,
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
        [data-testid="stCaptionContainer"], [data-testid="stSidebar"] label {{
            font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', system-ui, sans-serif;
        }}
        h1, h2, h3 {{
            color: {PRIMARY};
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        h1 {{ font-size: 2.1rem; }}
        @media (max-width: 640px) {{
            h1 {{ font-size: 1.5rem; }}
            h3 {{ font-size: 1.2rem; }}
        }}
        .stMetric {{
            background: {CARD_BG};
            border: 1px solid {CARD_BORDER};
            border-radius: 10px;
            padding: 12px 16px;
        }}
        [data-testid="stMetricValue"] {{ color: {PRIMARY_LIGHT}; }}
        [data-testid="stMetricLabel"] {{ color: {INK}; }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid {CARD_BORDER};
            border-radius: 8px;
        }}
        section[data-testid="stSidebar"] {{
            border-right: 1px solid {CARD_BORDER};
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Logo next to the title (skipped cleanly if logo.png isn't in the repo)
if HAS_LOGO:
    title_col1, title_col2 = st.columns([1, 8], vertical_alignment="center")
    with title_col1:
        st.image(LOGO_PATH, width=64)
    with title_col2:
        st.title("Jobify: Live Job Market Dashboard")
else:
    st.title("Jobify: Live Job Market Dashboard")

st.caption(
    f"Data source: Snowflake, {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA} "
    "(live query, not a snapshot)"
)

# ============================================================
# Text normalization (Arabic -> English)
#
# Anything not in these maps passes through unchanged. Unmapped Arabic city
# names are printed to the app logs (Manage app -> Logs) so you can add them.
# ============================================================

CITY_MAP = {
    # Arabic -> English, using the English spellings already in the data
    "الرياض": "Riyadh",
    "الدمام": "Dammam",
    "مكة": "Makkah",
    "مكة المكرمة": "Makkah",
    "جدة": "Jeddah",
    "المدينة": "Madinah",
    "المدينة المنورة": "Madinah",
    "الخبر": "Khobar",
    "الظهران": "Dhahran",
    "الهفوف": "Hofuf",
    "الأحساء": "Al Ahsa",
    "بقيق": "Abqaiq",
    "أبها": "Abha",
    "الجبيل": "Jubail",
    "ينبع": "Yanbu",
    "تبوك": "Tabuk",
    "الطائف": "Taif",
    "بريدة": "Buraydah",
    "حائل": "Hail",
    "نجران": "Najran",
    "جازان": "Jazan",
    "خميس مشيط": "Khamis Mushait",
    "حفر الباطن": "Hafar Al-Batin",
    # English spelling variants -> one label
    "Al Khobar": "Khobar",
    "Al-Khobar": "Khobar",
    "Medina": "Madinah",
    "Mecca": "Makkah",
    "Jiddah": "Jeddah",
}
CITY_DROP = {"دول"}  # not a real city: placeholder/bad data

EMPLOYMENT_MAP = {
    "دوام كامل": "Full-time",
    "دوام جزئي": "Part-time",
    "عقد": "Contract",
    "تدريب": "Internship",
    "مؤقت": "Temporary",
    "عن بُعد": "Remote",
}

# Optional sidebar toggle: skills that aren't really tech skills.
# Edit this set to match what you see in the data.
NON_TECH_SKILLS = {"Construction", "Manufacturing"}


def normalize_city(series: pd.Series) -> pd.Series:
    s = series.astype(object).str.strip()
    out = s.replace(CITY_MAP)
    return out.where(~s.isin(CITY_DROP), None)


def normalize_employment(series: pd.Series) -> pd.Series:
    return series.astype(object).str.strip().replace(EMPLOYMENT_MAP)


def sql_in(values) -> str:
    """Quote a list of strings for a SQL IN (...) clause (escapes apostrophes)."""
    return ",".join("'" + str(v).replace("'", "''") + "'" for v in values)


# ============================================================
# Snowflake connection (cached so we don't reconnect on every rerun)
# ============================================================


def _get_setting(name: str, default=None):
    """Read a setting from environment variables or Streamlit Cloud secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return default


@st.cache_resource
def get_connection():
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
    ]
    missing = [v for v in required if not _get_setting(v)]
    if missing:
        st.error(
            "Missing Snowflake settings: "
            + ", ".join(missing)
            + ". Add them to Streamlit Cloud (App settings, Secrets) "
            "or to a local .env file."
        )
        st.stop()

    return snowflake.connector.connect(
        account=_get_setting("SNOWFLAKE_ACCOUNT"),
        user=_get_setting("SNOWFLAKE_USER"),
        password=_get_setting("SNOWFLAKE_PASSWORD"),
        warehouse=_get_setting("SNOWFLAKE_WAREHOUSE"),
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=_get_setting("SNOWFLAKE_ROLE"),
        login_timeout=30,
        network_timeout=60,
        client_session_keep_alive=True,
    )


def _table(name: str) -> str:
    return f'"{SNOWFLAKE_DATABASE}"."{SNOWFLAKE_SCHEMA}"."{name}"'


@st.cache_data(ttl=600)
def run_query(sql: str, params=None) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    try:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    except snowflake.connector.errors.Error as e:
        # Details go to the app logs only, so the public page never shows
        # account, schema or query internals.
        print("Snowflake query failed:", repr(e))
        st.error(
            "Couldn't load data from Snowflake. The warehouse may be paused "
            "or unreachable. Please try again in a minute."
        )
        st.stop()
    finally:
        cur.close()


# ============================================================
# Chart helper: ranked bars (Streamlit's bar_chart sorts A-Z)
# ============================================================


def ranked_bar(df: pd.DataFrame, cat: str, val: str, horizontal=False, color=PRIMARY):
    df = df.copy()
    df[val] = pd.to_numeric(df[val])
    tooltip = [alt.Tooltip(f"{cat}:N"), alt.Tooltip(f"{val}:Q", title="Postings")]
    if horizontal:
        chart = (
            alt.Chart(df)
            .mark_bar(color=color, cornerRadiusEnd=3)
            .encode(
                x=alt.X(f"{val}:Q", title="Postings"),
                y=alt.Y(f"{cat}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                tooltip=tooltip,
            )
        )
    else:
        chart = (
            alt.Chart(df)
            .mark_bar(color=color, cornerRadiusEnd=3)
            .encode(
                x=alt.X(
                    f"{cat}:N",
                    sort="-y",
                    title=None,
                    axis=alt.Axis(labelAngle=-40, labelLimit=180),
                ),
                y=alt.Y(f"{val}:Q", title="Postings"),
                tooltip=tooltip,
            )
        )
    st.altair_chart(chart.properties(width="container"))


# ============================================================
# Sidebar filters
# ============================================================

st.sidebar.header("Filters")

# --- City (several raw spellings can map to one English name) ---
city_raw_df = run_query(
    f"SELECT DISTINCT CITY FROM {_table('DIM_LOCATION')} WHERE CITY IS NOT NULL ORDER BY CITY"
)
city_raw_df["CITY_EN"] = normalize_city(city_raw_df["CITY"])
_valid_cities = city_raw_df.dropna(subset=["CITY_EN"])
city_lookup = _valid_cities.groupby("CITY_EN")["CITY"].apply(list).to_dict()
city_choices = sorted(city_lookup)

_unmapped = sorted(
    c
    for c in city_raw_df["CITY"].dropna().unique()
    if c not in CITY_MAP and c not in CITY_DROP and any("\u0600" <= ch <= "\u06ff" for ch in c)
)
if _unmapped:
    print("Unmapped Arabic city names (add to CITY_MAP):", _unmapped)

selected_cities_en = st.sidebar.multiselect("City", city_choices, key="f_city")
selected_cities_raw = [raw for c in selected_cities_en for raw in city_lookup[c]]

# --- Employment type ---
emp_raw_df = run_query(
    f"SELECT DISTINCT EMPLOYMENT_TYPE FROM {_table('DIM_JOB')} WHERE EMPLOYMENT_TYPE IS NOT NULL ORDER BY 1"
)
emp_raw_df["EMP_EN"] = normalize_employment(emp_raw_df["EMPLOYMENT_TYPE"])
emp_lookup = emp_raw_df.groupby("EMP_EN")["EMPLOYMENT_TYPE"].apply(list).to_dict()
selected_emp_en = st.sidebar.multiselect("Employment type", sorted(emp_lookup), key="f_emp")
selected_emp = [raw for e in selected_emp_en for raw in emp_lookup[e]]

# --- Work type ---
work_type = st.sidebar.radio("Work type", ["All", "Remote", "On-site"], horizontal=True, key="f_work")

# --- Date range ---
date_bounds = run_query(
    f"""
    SELECT MIN(d.POSTED_DATE) AS MIN_D, MAX(d.POSTED_DATE) AS MAX_D
    FROM {_table('DIM_DATE')} d
    JOIN {_table('FACT_JOBS')} f ON f.DATE_KEY = d.DATE_KEY
    """
)
min_d, max_d = date_bounds["MIN_D"][0], date_bounds["MAX_D"][0]
st.session_state.setdefault("f_date", (min_d, max_d))
date_range = st.sidebar.date_input("Posted date range", min_value=min_d, max_value=max_d, key="f_date")

# --- Skills toggle ---
hide_nontech = st.sidebar.checkbox("Hide non-tech skills", value=False, key="f_tech")


def reset_filters():
    st.session_state["f_city"] = []
    st.session_state["f_emp"] = []
    st.session_state["f_work"] = "All"
    st.session_state["f_date"] = (min_d, max_d)
    st.session_state["f_tech"] = False


st.sidebar.button("Reset filters", on_click=reset_filters)

# Shared WHERE clause built from the filters above
where_clauses = ["1=1"]

if selected_cities_raw:
    where_clauses.append(f"l.CITY IN ({sql_in(selected_cities_raw)})")
if selected_emp:
    where_clauses.append(f"j.EMPLOYMENT_TYPE IN ({sql_in(selected_emp)})")
if work_type == "Remote":
    where_clauses.append("f.IS_REMOTE = TRUE")
elif work_type == "On-site":
    where_clauses.append("f.IS_REMOTE = FALSE")
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    where_clauses.append(f"d.POSTED_DATE BETWEEN '{date_range[0]}' AND '{date_range[1]}'")

WHERE_SQL = " AND ".join(where_clauses)
SKILL_FILTER_SQL = f" AND s.SKILL_NAME NOT IN ({sql_in(NON_TECH_SKILLS)})" if hide_nontech else ""

# ============================================================
# Top-line metrics (all data, not filtered) with week-over-week change
# ============================================================

counts = run_query(
    f"""
    SELECT
        (SELECT COUNT(*) FROM {_table('FACT_JOBS')})     AS total_jobs,
        (SELECT COUNT(*) FROM {_table('DIM_COMPANY')})   AS total_companies,
        (SELECT COUNT(*) FROM {_table('DIM_SKILL')})     AS total_skills
    """
)

trend = run_query(
    f"""
    SELECT
        SUM(CASE WHEN d.POSTED_DATE >= DATEADD('day', -7, CURRENT_DATE) THEN 1 ELSE 0 END) AS last_7,
        SUM(CASE WHEN d.POSTED_DATE >= DATEADD('day', -14, CURRENT_DATE)
                 AND d.POSTED_DATE < DATEADD('day', -7, CURRENT_DATE) THEN 1 ELSE 0 END) AS prior_7
    FROM {_table('FACT_JOBS')} f
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    """
)
last_7 = int(trend["LAST_7"][0] or 0)
prior_7 = int(trend["PRIOR_7"][0] or 0)
delta = last_7 - prior_7

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Job Postings", int(counts["TOTAL_JOBS"][0]), delta=f"{delta:+d} vs prior week")
c2.metric("Unique Companies", int(counts["TOTAL_COMPANIES"][0]))
c3.metric("Unique Skills", int(counts["TOTAL_SKILLS"][0]))
c4.metric("Unique Cities", len(city_choices))  # after Arabic/English merging

st.divider()

# ============================================================
# Top skills in demand (via bridge table)
# ============================================================

st.subheader("🔧 Top 10 Most In-Demand Skills")

top_skills = run_query(
    f"""
    SELECT s.SKILL_NAME, COUNT(*) AS JOB_COUNT
    FROM {_table('BRIDGE_JOB_SKILL')} b
    JOIN {_table('DIM_SKILL')} s ON b.SKILL_KEY = s.SKILL_KEY
    JOIN {_table('FACT_JOBS')} f ON b.JOB_KEY = f.JOB_KEY
    JOIN {_table('DIM_JOB')} j ON f.JOB_KEY = j.JOB_KEY
    JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}{SKILL_FILTER_SQL}
    GROUP BY s.SKILL_NAME
    ORDER BY JOB_COUNT DESC
    LIMIT 10
    """
)

if not top_skills.empty:
    ranked_bar(top_skills, "SKILL_NAME", "JOB_COUNT")
else:
    st.info("No skill data matches the current filters.")

# ============================================================
# Jobs by city
# ============================================================

st.subheader("📍 Job Postings by City")

by_city = run_query(
    f"""
    SELECT l.CITY AS CITY_RAW, COUNT(*) AS JOB_COUNT
    FROM {_table('FACT_JOBS')} f
    JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN {_table('DIM_JOB')} j ON f.JOB_KEY = j.JOB_KEY
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL} AND l.CITY IS NOT NULL
    GROUP BY l.CITY
    """
)

if not by_city.empty:
    by_city["JOB_COUNT"] = pd.to_numeric(by_city["JOB_COUNT"])
    by_city["CITY"] = normalize_city(by_city["CITY_RAW"])
    by_city = (
        by_city.dropna(subset=["CITY"])
        .groupby("CITY", as_index=False)["JOB_COUNT"]
        .sum()
        .sort_values("JOB_COUNT", ascending=False)
        .head(15)
    )
    if not by_city.empty:
        ranked_bar(by_city, "CITY", "JOB_COUNT")
    else:
        st.info("No location data matches the current filters.")
else:
    st.info("No location data matches the current filters.")

# ============================================================
# Top hiring companies
# ============================================================

st.subheader("🏢 Top 10 Hiring Companies")

top_companies = run_query(
    f"""
    SELECT c.COMPANY_NAME, COUNT(*) AS JOB_COUNT
    FROM {_table('FACT_JOBS')} f
    JOIN {_table('DIM_COMPANY')} c ON f.COMPANY_KEY = c.COMPANY_KEY
    JOIN {_table('DIM_JOB')} j ON f.JOB_KEY = j.JOB_KEY
    JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}
    GROUP BY c.COMPANY_NAME
    ORDER BY JOB_COUNT DESC
    LIMIT 10
    """
)

if not top_companies.empty:
    ranked_bar(top_companies, "COMPANY_NAME", "JOB_COUNT", horizontal=True)
else:
    st.info("No company data matches the current filters.")

# ============================================================
# Skills by city: what's in demand where
# ============================================================

st.subheader("🧭 Top Skills by City")

skills_by_city = run_query(
    f"""
    SELECT l.CITY AS CITY_RAW, s.SKILL_NAME, COUNT(*) AS JOB_COUNT
    FROM {_table('BRIDGE_JOB_SKILL')} b
    JOIN {_table('DIM_SKILL')} s ON b.SKILL_KEY = s.SKILL_KEY
    JOIN {_table('FACT_JOBS')} f ON b.JOB_KEY = f.JOB_KEY
    JOIN {_table('DIM_JOB')} j ON f.JOB_KEY = j.JOB_KEY
    JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}{SKILL_FILTER_SQL} AND l.CITY IS NOT NULL
    GROUP BY l.CITY, s.SKILL_NAME
    """
)

if not skills_by_city.empty:
    skills_by_city["JOB_COUNT"] = pd.to_numeric(skills_by_city["JOB_COUNT"])
    skills_by_city["CITY"] = normalize_city(skills_by_city["CITY_RAW"])
    skills_by_city = skills_by_city.dropna(subset=["CITY"])
    top_cities_for_pivot = (
        skills_by_city.groupby("CITY")["JOB_COUNT"].sum().sort_values(ascending=False).head(6).index
    )
    pivot = skills_by_city[skills_by_city["CITY"].isin(top_cities_for_pivot)].pivot_table(
        index="SKILL_NAME", columns="CITY", values="JOB_COUNT", aggfunc="sum", fill_value=0
    )
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).head(10).index]
    pivot = pivot[pivot.sum().sort_values(ascending=False).index]  # busiest city first
    pivot.index.name = "Skill"
    try:
        st.dataframe(pivot.style.background_gradient(cmap="Blues", axis=None), use_container_width=True)
    except ImportError:  # matplotlib missing: fall back to a plain table
        st.dataframe(pivot, use_container_width=True)
else:
    st.info("No skill/city data matches the current filters.")

# ============================================================
# Postings over time (weekly)
# ============================================================

st.subheader("📅 Postings Over Time")

by_date = run_query(
    f"""
    SELECT d.POSTED_DATE, COUNT(*) AS JOB_COUNT
    FROM {_table('FACT_JOBS')} f
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    JOIN {_table('DIM_JOB')} j ON f.JOB_KEY = j.JOB_KEY
    JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    WHERE {WHERE_SQL} AND d.POSTED_DATE IS NOT NULL
    GROUP BY d.POSTED_DATE
    ORDER BY d.POSTED_DATE
    """
)

if not by_date.empty:
    by_date["POSTED_DATE"] = pd.to_datetime(by_date["POSTED_DATE"])
    by_date["JOB_COUNT"] = pd.to_numeric(by_date["JOB_COUNT"])
    weekly = by_date.set_index("POSTED_DATE")["JOB_COUNT"].resample("W").sum().reset_index()
    weekly.columns = ["Week", "Postings"]
    weekly_chart = (
        alt.Chart(weekly)
        .mark_bar(color=PRIMARY, cornerRadiusEnd=2)
        .encode(
            x=alt.X("Week:T", title=None),
            y=alt.Y("Postings:Q", title="Postings per week"),
            tooltip=[alt.Tooltip("Week:T", title="Week ending"), alt.Tooltip("Postings:Q")],
        )
        .properties(width="container")
    )
    st.altair_chart(weekly_chart)
    st.caption(
        "Weekly counts by posting date. Older dates have very few postings in this dataset, "
        "so read early weeks as incomplete coverage rather than low hiring."
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
    FROM {_table('FACT_JOBS')} f
    JOIN {_table('DIM_JOB')} j ON f.JOB_KEY = j.JOB_KEY
    JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    JOIN {_table('DIM_DATE')} d ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}
    GROUP BY WORK_TYPE
    """
)

if not remote_split.empty:
    ranked_bar(remote_split, "WORK_TYPE", "JOB_COUNT", color=ACCENT)
    cols = st.columns(len(remote_split))
    for col, (_, row) in zip(cols, remote_split.iterrows()):
        col.metric(row["WORK_TYPE"], int(row["JOB_COUNT"]))
else:
    st.info("No remote/on-site data matches the current filters.")

st.divider()

# ============================================================
# Raw data preview (shows the pipeline loaded real rows)
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
    FROM {_table('FACT_JOBS')} f
    JOIN {_table('DIM_JOB')} j       ON f.JOB_KEY = j.JOB_KEY
    LEFT JOIN {_table('DIM_COMPANY')} c  ON f.COMPANY_KEY = c.COMPANY_KEY
    LEFT JOIN {_table('DIM_LOCATION')} l ON f.LOCATION_KEY = l.LOCATION_KEY
    LEFT JOIN {_table('DIM_DATE')} d     ON f.DATE_KEY = d.DATE_KEY
    WHERE {WHERE_SQL}
    ORDER BY d.POSTED_DATE DESC NULLS LAST
    LIMIT 200
    """
)

if not sample.empty:
    sample["CITY"] = normalize_city(sample["CITY"]).fillna("Unknown")
    sample["EMPLOYMENT_TYPE"] = normalize_employment(sample["EMPLOYMENT_TYPE"])
    sample["IS_REMOTE"] = sample["IS_REMOTE"].map({True: "Remote", False: "On-site"})
    sample = sample.rename(
        columns={
            "JOB_TITLE": "Job title",
            "COMPANY_NAME": "Company",
            "CITY": "City",
            "EMPLOYMENT_TYPE": "Employment type",
            "EXPERIENCE_LEVEL": "Experience level",
            "IS_REMOTE": "Work type",
            "POSTED_DATE": "Posted",
        }
    )
st.dataframe(sample, use_container_width=True, hide_index=True)

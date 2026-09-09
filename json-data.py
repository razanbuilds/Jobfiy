import json
import re
import pandas as pd
import spacy
from spacy.matcher import PhraseMatcher

# =========================
# Load data
# =========================

with open("data/jobs_results.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

print(type(raw))
if isinstance(raw, dict):
    print(raw.keys())

df = pd.DataFrame(raw)

# ==========================================
# Common skills (القائمة الشاملة)
# ==========================================

COMMON_SKILLS = [
    # Programming Languages
    "Python", "Java", "JavaScript", "TypeScript",
    "C", "C++", "C#", "Go", "PHP", "Ruby",
    "Scala", "Kotlin", "Swift",

    # Databases
    "SQL", "MySQL", "PostgreSQL", "Oracle",
    "SQL Server", "MongoDB", "Redis",
    "Database", "Database Management",

    # Data Engineering
    "Data Engineering", "Data Analysis",
    "Data Pipeline", "ETL", "ELT",
    "Apache Airflow", "Airflow",
    "Apache Spark", "Spark",
    "Kafka", "Apache Kafka",
    "dbt", "Snowflake",
    "Databricks", "Hadoop",
    "Data Warehouse", "Data Lake",
    "Data Modeling", "Data Quality",
    "Data Integration",

    # Cloud
    "AWS", "Amazon Web Services",
    "Azure", "Microsoft Azure",
    "Google Cloud", "GCP",
    "Cloud Computing",
    "EC2", "S3", "Lambda",
    "Azure Data Factory",

    # DevOps / Tools
    "Docker", "Kubernetes",
    "Git", "GitHub", "GitLab",
    "CI/CD", "Jenkins",
    "Linux", "Bash",
    "Terraform",

    # APIs / Web
    "REST API", "REST APIs",
    "API", "API Testing",
    "Postman",
    "JSON", "XML",
    "FastAPI", "Flask", "Django",

    # Testing & QA
    "QA", "Quality Assurance",
    "Quality Control",
    "QA Testing",
    "Manual Testing",
    "Automation Testing",
    "Automated Testing",
    "Automated Tests",
    "Software Testing",
    "Regression Testing",
    "Test Cases",
    "Test Case Design",
    "Test Plans",
    "TestNG", "JUnit",
    "Selenium", "Cypress",
    "Playwright",
    "Jira",
    "Bug Tracking",
    "Defect Management",
    "Performance Testing",
    "Integration Testing",
    "Unit Testing",

    # Software Development
    "Software Development",
    "Software Engineering",
    "Object-Oriented Programming",
    "OOP",
    "Microservices",
    "Agile",
    "Scrum",
    "SDLC",

    # Frontend
    "HTML", "CSS",
    "React", "Angular", "Vue.js",
    "Node.js",

    # BI / Analytics
    "Excel",
    "Power BI",
    "Tableau",
    "Data Visualization",
    "Business Intelligence",
    "Data Analytics",

    # AI / ML
    "Machine Learning",
    "Deep Learning",
    "Artificial Intelligence",
    "NLP",
    "Natural Language Processing",
    "scikit-learn",
    "TensorFlow",
    "PyTorch",

    # Other
    "Problem Solving",
    "Technical Documentation",
    "Requirements Analysis",
]

# ==========================================
# Functions (أكواد المعالجة والدمج)
# ==========================================

def extract_skills_from_text(text):
    if not text:
        return []
    text_lower = str(text).lower()
    found = []
    for skill in COMMON_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found

def normalize_skills(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(skill).strip() for skill in value if str(skill).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value or value.upper() == "N/A":
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(skill).strip() for skill in parsed if str(skill).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return [skill.strip() for skill in re.split(r",|;|\|", value) if skill.strip()]
    return []

def combine_skills(original_skills, extracted_skills):
    original = normalize_skills(original_skills)
    extracted = normalize_skills(extracted_skills)
    combined = []
    seen = set()
    for skill in original + extracted:
        key = skill.lower().strip()
        if key and key not in seen:
            combined.append(skill.strip())
            seen.add(key)
    return ", ".join(combined) if combined else "N/A"

# ==========================================
# Execution Pipeline
# ==========================================

# دمج النصوص لفحصها (يشمل description إذا كان موجوداً)
df["combined_text"] = (
    df["job_title"].fillna("").astype(str) + " " +
    (df["description"].fillna("").astype(str) if "description" in df.columns else "") + " " +
    df["employment_type"].fillna("").astype(str) + " " +
    df["experience_level"].fillna("").astype(str)
)

# استخراج المهارات
df["extracted_skills"] = df["combined_text"].apply(extract_skills_from_text)

# دمج المهارات الأصلية مع المستخرجة إذا كان عمود skills متوفراً
if "skills" in df.columns:
    df["final_skills"] = df.apply(
        lambda row: combine_skills(row["skills"], row["extracted_skills"]),
        axis=1
    )
    print(df[["job_title", "skills", "extracted_skills", "final_skills"]].to_string(index=False))
else:
    df["final_skills"] = df["extracted_skills"].apply(lambda s: ", ".join(s) if s else "N/A")
    print(df[["job_title", "final_skills"]].to_string(index=False))

# حفظ البيانات المثرية
output_file = "data/jobs_results_enriched.json"
df.to_json(output_file, orient="records", force_ascii=False, indent=2)
print(f"\nEnriched data saved to: {output_file}")
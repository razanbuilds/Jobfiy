import pandas as pd
import json

with open("data/jobs_results.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

# check the structure first
print(type(raw))
if isinstance(raw, dict):
    print(raw.keys())
    
df = pd.DataFrame(raw)

import spacy
from spacy.matcher import PhraseMatcher

# Add near the top with your other constants
COMMON_SKILLS = [
    "Python", "Java", "JavaScript", "SQL", "Excel", "React", "Node.js",
    "AWS", "Azure", "Docker", "Kubernetes", "Selenium", "Jira", "Agile",
    "Scrum", "Git", "C++", "C#", "Power BI", "Tableau", "REST API",
    "Machine Learning", "Data Analysis", "QA Testing", "Automation Testing",
    "Manual Testing", "TestNG", "JUnit", "Postman", "Linux", "Cloud Computing"
    # add whatever's relevant to the roles you're scraping (QA/Data roles it looks like)
]

import re

def extract_skills_from_text(text):
    if not text:
        return "N/A"
    text_lower = text.lower()
    found = [skill for skill in COMMON_SKILLS 
             if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text_lower)]
    return ", ".join(found) if found else "N/A"

df["combined_text"] = (
    df["job_title"].fillna("") + " " +
    df["employment_type"].fillna("") + " " +
    df["experience_level"].fillna("")
)
df["extracted_skills"] = df["combined_text"].apply(extract_skills_from_text)
print(df[["job_title", "extracted_skills"]])


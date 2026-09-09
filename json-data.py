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
    # Testing & QA
    "Manual Testing", "Automation Testing", "Selenium", "TestNG", "JUnit",
    "Postman", "API Testing", "Regression Testing", "Test Cases", "QA",
    "Quality Assurance", "Cypress", "Appium", "Load Testing", "Performance Testing",
    "Bug Tracking", "Test Automation Framework",

    # Data
    "SQL", "Python", "Excel", "Power BI", "Tableau", "Data Analysis",
    "Data Visualization", "ETL", "Machine Learning", "Data Cleaning",
    "Pandas", "NumPy", "R", "Statistics",

    # Dev/General tech
    "Java", "JavaScript", "C++", "C#", "Node.js", "React", "REST API",
    "Git", "GitHub", "Docker", "Kubernetes", "AWS", "Azure", "Linux",
    "Agile", "Scrum", "Jira", "CI/CD",
]

def extract_skills_from_text(text):
    if not text:
        return "N/A"
    text_lower = text.lower()
    found = [skill for skill in COMMON_SKILLS if skill.lower() in text_lower]
    return ", ".join(found) if found else "N/A"

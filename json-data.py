import pandas as pd
import json
import re
import spacy

# =========================
# Load data
# =========================

with open("data/jobs_results.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

print(type(raw))

if isinstance(raw, dict):
    print(raw.keys())

df = pd.DataFrame(raw)


# =========================
# Common skills
# =========================

COMMON_SKILLS = [

    # =========================
    # Programming Languages
    # =========================
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C programming",
    "C language",
    "C++",
    "C#",
    "Go programming",
    "Golang",
    "PHP",
    "Ruby",
    "Scala",
    "Kotlin",
    "Swift",
    "R programming",
    "R language",
    "Dart",
    "Rust",
    "Perl",
    "MATLAB",
    "Groovy",
    "Objective-C",
    "Visual Basic",
    "VBA",
    "Assembly",
    "Lua",
    "Julia",
    "Shell Scripting",
    "PowerShell",

    # =========================
    # SQL & Databases
    # =========================
    "SQL",
    "MySQL",
    "PostgreSQL",
    "Oracle",
    "Oracle Database",
    "SQL Server",
    "Microsoft SQL Server",
    "SQLite",
    "MariaDB",
    "MongoDB",
    "Redis",
    "Cassandra",
    "CouchDB",
    "DynamoDB",
    "Firebase",
    "Firestore",
    "Neo4j",
    "Elasticsearch",
    "OpenSearch",
    "Database",
    "Database Management",
    "Database Design",
    "Database Administration",
    "Relational Database",
    "NoSQL",
    "Graph Database",
    "Stored Procedures",
    "PL/SQL",
    "T-SQL",
    "Database Optimization",
    "Query Optimization",
    "Indexing",
    "Transactions",
    "ACID",
    "Data Replication",
    "Data Migration",
    "DB",

    # =========================
    # Data Engineering
    # =========================
    "Data Engineering",
    "Data Engineer",
    "Data Analysis",
    "Data Analytics",
    "Data Pipeline",
    "Data Pipelines",
    "ETL",
    "ELT",
    "Extract Transform Load",
    "Data Integration",
    "Data Ingestion",
    "Data Processing",
    "Data Transformation",
    "Data Cleaning",
    "Data Preparation",
    "Data Quality",
    "Data Validation",
    "Data Governance",
    "Data Catalog",
    "Data Lineage",
    "Data Modeling",
    "Dimensional Modeling",
    "Star Schema",
    "Snowflake Schema",
    "Data Warehouse",
    "Data Lake",
    "Data Lakehouse",
    "Data Platform",
    "Data Architecture",
    "Batch Processing",
    "Stream Processing",
    "Real-Time Data Processing",
    "Big Data",
    "Apache Airflow",
    "Airflow",
    "Apache Spark",
    "Spark",
    "PySpark",
    "Apache Kafka",
    "Kafka",
    "Kafka Streams",
    "Apache Flink",
    "Flink",
    "Hadoop",
    "HDFS",
    "Hive",
    "Apache Hive",
    "Presto",
    "Trino",
    "Apache Beam",
    "dbt",
    "dbt Cloud",
    "Databricks",
    "Delta Lake",
    "Apache NiFi",
    "Talend",
    "Informatica",
    "Fivetran",
    "Azure Data Factory",
    "AWS Glue",
    "Google Cloud Dataflow",

    # =========================
    # Cloud
    # =========================
    "AWS",
    "Amazon Web Services",
    "Microsoft Azure",
    "Azure",
    "Google Cloud",
    "GCP",
    "Cloud Computing",
    "Cloud Architecture",
    "Cloud Infrastructure",
    "Cloud Security",
    "Cloud Migration",
    "Cloud Storage",
    "Amazon S3",
    "S3",
    "Amazon EC2",
    "EC2",
    "AWS Lambda",
    "Lambda",
    "Amazon RDS",
    "AWS Redshift",
    "Amazon Redshift",
    "Amazon Athena",
    "AWS EMR",
    "AWS CloudFormation",
    "Azure Data Lake",
    "Azure Synapse",
    "Azure Databricks",
    "Azure Functions",
    "Azure Blob Storage",
    "Azure SQL",
    "Google BigQuery",
    "BigQuery",
    "Google Cloud Storage",
    "Google Cloud Functions",
    "Google Dataflow",

    # =========================
    # Data Warehouse / Analytics
    # =========================
    "Snowflake",
    "Snowflake Data Warehouse",
    "Redshift",
    "Data Mart",
    "OLAP",
    "OLTP",
    "Business Intelligence",
    "BI",
    "Power BI",
    "Tableau",
    "Looker",
    "Looker Studio",
    "Qlik",
    "Qlik Sense",
    "MicroStrategy",
    "DAX",
    "Power Query",
    "Excel",
    "Advanced Excel",
    "Pivot Tables",
    "Data Visualization",
    "Dashboard",
    "Reporting",
    "KPI",
    "Business Analytics",

    # =========================
    # DevOps / Infrastructure
    # =========================
    "Docker",
    "Docker Compose",
    "Kubernetes",
    "Amazon ECS",
    "Amazon EKS",
    "Azure Kubernetes Service",
    "Helm",
    "Terraform",
    "Ansible",
    "Jenkins",
    "GitHub Actions",
    "GitLab CI",
    "CI/CD",
    "Continuous Integration",
    "Continuous Deployment",
    "DevOps",
    "Infrastructure as Code",
    "IaC",
    "Linux",
    "Ubuntu",
    "CentOS",
    "Red Hat",
    "Unix",
    "Bash",
    "Shell",
    "PowerShell",
    "Nginx",
    "Apache",
    "Load Balancing",
    "Monitoring",
    "Logging",
    "Prometheus",
    "Grafana",
    "ELK Stack",
    "Logstash",
    "Kibana",
    "Infrastructure",

    # =========================
    # Version Control
    # =========================
    "Git",
    "GitHub",
    "GitLab",
    "Bitbucket",
    "Version Control",
    "Git Branching",
    "Git Merge",
    "Git Rebase",
    "Pull Requests",
    "Code Review",

    # =========================
    # APIs / Web Services
    # =========================
    "REST API",
    "REST APIs",
    "RESTful API",
    "GraphQL",
    "SOAP",
    "Web Services",
    "API Development",
    "API Integration",
    "API Testing",
    "Postman",
    "Swagger",
    "OpenAPI",
    "JSON",
    "XML",
    "YAML",
    "OAuth",
    "OAuth 2.0",
    "JWT",
    "Webhooks",
    "FastAPI",
    "Flask",
    "Django",
    "Django REST Framework",

    # =========================
    # Web Development
    # =========================
    "HTML",
    "HTML5",
    "CSS",
    "CSS3",
    "JavaScript",
    "TypeScript",
    "React",
    "React.js",
    "Angular",
    "Vue.js",
    "Next.js",
    "Node.js",
    "Express.js",
    "Bootstrap",
    "Tailwind CSS",
    "jQuery",
    "Webpack",
    "Vite",
    "Frontend Development",
    "Backend Development",
    "Full Stack Development",
    "Web Development",

    # =========================
    # Software Engineering
    # =========================
    "Software Development",
    "Software Engineering",
    "Software Architecture",
    "Object-Oriented Programming",
    "OOP",
    "Functional Programming",
    "Design Patterns",
    "Microservices",
    "Monolithic Architecture",
    "Distributed Systems",
    "System Design",
    "Event-Driven Architecture",
    "Service-Oriented Architecture",
    "SOLID Principles",
    "Clean Code",
    "Code Refactoring",
    "Software Development Life Cycle",
    "SDLC",
    "Agile",
    "Scrum",
    "Kanban",
    "Jira",
    "Confluence",
    "Application",
    "Application Support",

    # =========================
    # Machine Learning / AI
    # =========================
    "Artificial Intelligence",
    "Machine Learning",
    "Deep Learning",
    "Natural Language Processing",
    "NLP",
    "Computer Vision",
    "Generative AI",
    "Large Language Models",
    "LLM",
    "Prompt Engineering",
    "Machine Learning Engineering",
    "MLOps",
    "Predictive Analytics",
    "Supervised Learning",
    "Unsupervised Learning",
    "Reinforcement Learning",
    "Feature Engineering",
    "Model Training",
    "Model Evaluation",
    "Model Deployment",
    "scikit-learn",
    "TensorFlow",
    "PyTorch",
    "Keras",
    "XGBoost",
    "LightGBM",
    "Pandas",
    "NumPy",
    "SciPy",
    "Matplotlib",
    "Seaborn",
    "Jupyter",
    "Jupyter Notebook",
    "MLflow",
    "Hugging Face",
    "Transformers",
    "OpenAI",
    "LangChain",
    "Vector Database",
    "Vector Search",
    "Embeddings",
    "RAG",
    "Retrieval Augmented Generation",

    # =========================
    # QA / Testing
    # =========================
    "QA",
    "Quality Assurance",
    "QualityAssurance",
    "Quality Control",
    "QA Testing",
    "Software Testing",
    "Manual Testing",
    "Automation Testing",
    "Automated Testing",
    "Automated Tests",
    "Regression Testing",
    "Integration Testing",
    "Unit Testing",
    "System Testing",
    "Acceptance Testing",
    "Performance Testing",
    "Load Testing",
    "Stress Testing",
    "Test Cases",
    "Test Case Design",
    "Test Plans",
    "Test Automation",
    "Selenium",
    "Cypress",
    "Playwright",
    "JUnit",
    "TestNG",
    "PyTest",
    "Postman",
    "API Testing",
    "Bug Tracking",
    "Defect Management",

    # =========================
    # Cybersecurity
    # =========================
    "Cybersecurity",
    "Information Security",
    "Network Security",
    "Cloud Security",
    "Application Security",
    "Security Operations",
    "SOC",
    "SIEM",
    "Incident Response",
    "Threat Detection",
    "Threat Intelligence",
    "Vulnerability Assessment",
    "Penetration Testing",
    "Ethical Hacking",
    "Risk Assessment",
    "Security Auditing",
    "Identity and Access Management",
    "IAM",
    "Multi-Factor Authentication",
    "MFA",
    "Encryption",
    "Firewalls",
    "VPN",
    "Zero Trust",
    "OWASP",

    # =========================
    # Networking
    # =========================
    "Networking",
    "Computer Networking",
    "Network",
    "TCP/IP",
    "DNS",
    "DHCP",
    "HTTP",
    "HTTPS",
    "SSH",
    "FTP",
    "SFTP",
    "SMTP",
    "IP Addressing",
    "IPv4",
    "IPv6",
    "Routing",
    "Switching",
    "LAN",
    "WAN",
    "Wi-Fi",
    "Network Administration",
    "Network Monitoring",
    "Cisco",
    "Cisco Networking",
    "Cisco IOS",

    # =========================
    # Operating Systems
    # =========================
    "Windows",
    "Windows Server",
    "Linux",
    "Ubuntu",
    "Red Hat Linux",
    "CentOS",
    "macOS",
    "Unix",
    "Android",
    "iOS",

    # =========================
    # Mobile Development
    # =========================
    "Mobile Development",
    "Android Development",
    "iOS Development",
    "Android Studio",
    "Kotlin",
    "Swift",
    "SwiftUI",
    "Flutter",
    "Dart",
    "React Native",
    "Xcode",
    "Mobile App",
    "Mobile Application",

    # =========================
    # Tools / Platforms
    # =========================
    "Microsoft Office",
    "Microsoft 365",
    "Word",
    "PowerPoint",
    "SharePoint",
    "ServiceNow",
    "Salesforce",
    "SAP",
    "Oracle ERP",
    "ERP",
    "CRM",
    "n8n",
    "Zapier",
    "Automation",
    "Workflow Automation",

    # =========================
    # Hardware / Technical Support
    # =========================
    "Hardware",
    "Hardware Troubleshooting",
    "Software Troubleshooting",
    "Technical Repair",
    "Component Repair",
    "HDMI",
    "Technical Support",
    "IT Support",
    "System Administration",
    "Troubleshooting",
    "Troubleshoot",
    "Root Cause Analysis",
    "Incident Management",

    # =========================
    # General Technical Skills
    # =========================
    "Technical Documentation",
    "Requirements Analysis",
    "Requirements Gathering",
    "Problem Solving",
    "IT Infrastructure",
    "Systems Integration",
    "Process Automation",
    "Technical Analysis",
    "Business Analysis",
    "Data Security",
    "Data Privacy",
    "Compliance",
    "ISO",
    "ISO 9001",
    "Manufacturing"

    # =========================
    # Additional Skills Found in Job Data
    # =========================

    "SPC",
    "Six Sigma",
    "UAT",
    "Quality Center",
    "ClearQuest",
    "Requisite Pro",
    "Test Director",
    "QTP",
    "PL/SQL",
    "CMM",
    "GD&T",
    "Google Analytics",
    "SEO",
    "PPC",
    "Manual Testing",
    "Lean",
    "MRP",
]
# =========================
# Skill Normalization
# =========================
# Standardize different names or aliases of the same skill
# to one canonical skill name and remove duplicate skills.
# Map skill aliases to a standardized/canonical skill name
SKILL_NORMALIZATION = {
    "DB": "Database",
    "QA": "Quality Assurance",
    "Troubleshoot": "Troubleshooting",
    "Automation": "Automation Testing",
    "Automated Testing": "Automation Testing",
    "Automated Tests": "Automation Testing",
    "R programming": "R",
    "R language": "R",
    "Azure": "Microsoft Azure",
    "AWS": "Amazon Web Services",
    "GCP": "Google Cloud",
    "React.js": "React",
    "Node.js": "Node.js",
    "ISO9001": "ISO 9001",
    "QualityAssurance": "Quality Assurance",
}
# =========================
# Extract skills from text
# =========================

def extract_skills_from_text(text):
    if not text:
        return []

    # Remove HTML tags
    text_clean = re.sub(r"<[^>]+>", " ", str(text))

    # Replace HTML entities
    text_clean = text_clean.replace("&nbsp;", " ")
    text_clean = text_clean.replace("&amp;", "&")
    text_clean = text_clean.replace("&lt;", "<")
    text_clean = text_clean.replace("&gt;", ">")

    # Normalize spaces
    text_clean = re.sub(r"<[^>]+>", " ", str(text))

    text_lower = text_clean.lower()

    found = []

    for skill in COMMON_SKILLS:
        pattern = r"(?<!\w)" + re.escape(skill.lower()) + r"(?!\w)"

        if re.search(pattern, text_lower):
            found.append(skill)

    return list(dict.fromkeys(found))


# =========================
# Combine original + extracted skills
# =========================

def normalize_skills(value):
    """
    Convert skills from different formats into a list.
    """

    if value is None:
        return []

    if isinstance(value, list):
        return [str(skill).strip() for skill in value if str(skill).strip()]

    if isinstance(value, str):
        value = value.strip()

        if not value or value.upper() == "N/A":
            return []

        # Try JSON list if stored as a string
        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return [
                    str(skill).strip()
                    for skill in parsed
                    if str(skill).strip()
                ]
        except (json.JSONDecodeError, TypeError):
            pass

        # Otherwise split common separators
        return [
            skill.strip()
            for skill in re.split(r",|;|\|", value)
            if skill.strip()
        ]

    return []

# Normalize extracted skills using the canonical skill names
def normalize_extracted_skills(skills):
    normalized = []

    for skill in skills:
        skill = SKILL_NORMALIZATION.get(skill, skill)

        if skill not in normalized:
            normalized.append(skill)

    return normalized


# Combine original and extracted skills, then normalize and remove duplicates
# Combine original and extracted skills, then normalize and remove duplicates
def combine_skills(original_skills, extracted_skills):
    skills = []

    if original_skills and original_skills != "N/A":
        skills.extend(
            [s.strip() for s in original_skills.split(",")]
        )

    skills.extend(extracted_skills)

    normalized = []

    for skill in skills:
        skill = SKILL_NORMALIZATION.get(skill, skill)

        if skill not in normalized:
            normalized.append(skill)

    return ", ".join(normalized) if normalized else "N/A"


# =========================
# Build combined text
# =========================

df["combined_text"] = (
    df["job_title"].fillna("").astype(str) + " " +
    df["description"].fillna("").astype(str) + " " +
    df["employment_type"].fillna("").astype(str) + " " +
    df["experience_level"].fillna("").astype(str)
)


# =========================
# Extract skills
# =========================

# Extract skills from job text
df["extracted_skills"] = df["combined_text"].apply(
    extract_skills_from_text
)

# Normalize extracted skills
df["extracted_skills"] = df["extracted_skills"].apply(
    normalize_extracted_skills
)


# =========================
# Combine original skills
# with extracted skills
# =========================

df["final_skills"] = df.apply(
    lambda row: combine_skills(
        row["skills"],
        row["extracted_skills"]
    ),
    axis=1
)


# =========================
# Display results
# =========================

print("\n===== RESULTS =====\n")

print(
    df[
        [
            "job_title",
            "skills",
            "extracted_skills",
            "final_skills"
        ]
    ].to_string(index=False)
)


# =========================
# Save enriched data
# =========================

output_file = "data/jobs_results_enriched.json"

df.to_json(
    output_file,
    orient="records",
    force_ascii=False,
    indent=2
)


print(f"\nEnriched data saved to: {output_file}")
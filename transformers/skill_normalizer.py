"""
Normalisation des compétences techniques (skills/technos) pour la recherche
d'emploi et le système de recommandation.

Deux objectifs :
1. Canoniser : "js", "JS", "javascript", "JavaScript" -> "JavaScript".
2. Catégoriser : Power BI -> "BI", Python -> "Programmation",
   Kubernetes -> "DevOps/Infra", etc. ; sert à `dim_technologie.categorie`.

Pas de dépendance externe — listes maintenues à la main, ce qui colle bien
aux données scrapées (Adzuna FR + Rekrute MA + Emploi-Public MA, focus tech).
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- #
# Catégories : 1 catégorie = N skills canoniques
# --------------------------------------------------------------------------- #

CATEGORIES: dict[str, list[str]] = {
    "Programmation": [
        "Python", "Java", "Scala", "R", "C", "C++", "C#", ".NET", "JavaScript",
        "TypeScript", "Go", "Kotlin", "Swift", "PHP", "Ruby", "Rust",
        "PowerShell", "Bash", "Shell", "PL/SQL", "VBA", "MATLAB",
    ],
    "Big Data": [
        "Hadoop", "Spark", "Kafka", "Hive", "HBase", "Flink", "Storm",
        "Databricks", "Snowflake", "Redshift", "BigQuery", "Teradata",
        "Synapse", "Delta Lake",
    ],
    "Bases de données": [
        "MySQL", "PostgreSQL", "Oracle", "MongoDB", "Cassandra", "Redis",
        "Elasticsearch", "SQL Server", "MariaDB", "Neo4j", "DynamoDB",
        "SQLite", "Couchbase",
    ],
    "Cloud": [
        "AWS", "Azure", "GCP", "OpenStack", "Heroku", "Cloudflare",
        "Vercel", "DigitalOcean",
    ],
    "DevOps/Infra": [
        "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "GitLab",
        "GitHub Actions", "CircleCI", "Helm", "ArgoCD", "Prometheus",
        "Grafana", "ELK", "CI/CD", "Nginx", "Apache", "VMware", "Hyper-V",
    ],
    "Data Science / ML": [
        "TensorFlow", "PyTorch", "Scikit-Learn", "Keras", "Pandas", "NumPy",
        "XGBoost", "LightGBM", "Hugging Face", "MLflow", "MLOps",
        "Machine Learning", "Deep Learning", "Computer Vision", "NLP",
        "GPT", "LLM", "Rasa", "Dialogflow",
    ],
    "BI / Visualisation": [
        "Power BI", "Tableau", "QlikView", "Qlik Sense", "Looker", "SAP BO",
        "Cognos", "Matplotlib", "Seaborn", "Plotly", "Superset",
    ],
    "Data Engineering": [
        "Airflow", "Talend", "Informatica", "Collibra", "ETL", "ELT", "DBT",
        "NiFi", "Data Vault", "MDM", "Fivetran",
    ],
    "Sécurité": [
        "SIEM", "SOC", "Splunk", "Qualys", "Nessus", "Wireshark", "Burp Suite",
        "OWASP", "ISO 27001", "Pentesting", "PKI", "IAM", "Active Directory",
        "Azure AD",
    ],
    "Réseau / Système": [
        "Linux", "Unix", "Windows", "TCP/IP", "DNS", "SAN", "NAS", "VPN",
        "Cisco", "Juniper", "Fortinet", "Palo Alto",
    ],
    "Web / Frontend": [
        "React", "Angular", "Vue", "Vue.js", "Next.js", "Nuxt", "Svelte",
        "HTML", "CSS", "Tailwind", "Bootstrap", "jQuery", "Redux",
    ],
    "Backend / Frameworks": [
        "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "Express",
        "NestJS", "Node.js", "Laravel", "Symfony", "Rails", ".NET Core",
    ],
    "Mobile": [
        "Android", "iOS", "Flutter", "React Native", "Xamarin", "Ionic",
    ],
    "Outils": [
        "Git", "Jira", "Confluence", "SAP", "Salesforce", "ServiceNow",
        "Notion", "Postman", "Figma",
    ],
    "Méthodologies": [
        "Agile", "Scrum", "Kanban", "TDD", "BDD", "DevSecOps",
    ],
    "SQL & autres": [
        "SQL", "NoSQL",
    ],
}

# --------------------------------------------------------------------------- #
# Aliases : forme variantes -> forme canonique
# --------------------------------------------------------------------------- #

ALIASES: dict[str, str] = {
    # Programmation
    "js":              "JavaScript",
    "javascript":      "JavaScript",
    "ecmascript":      "JavaScript",
    "ts":              "TypeScript",
    "typescript":      "TypeScript",
    "py":              "Python",
    "python3":         "Python",
    "csharp":          "C#",
    "c-sharp":         "C#",
    "cpp":             "C++",
    "c plus plus":     "C++",
    "dotnet":          ".NET",
    ".net":            ".NET",
    "golang":          "Go",
    "ps":              "PowerShell",
    "powershell":      "PowerShell",
    "plsql":           "PL/SQL",
    "pl/sql":          "PL/SQL",
    # Cloud
    "amazon web services": "AWS",
    "aws":             "AWS",
    "google cloud":    "GCP",
    "google cloud platform": "GCP",
    "gcp":             "GCP",
    "microsoft azure": "Azure",
    "azure":           "Azure",
    # DevOps
    "k8s":             "Kubernetes",
    "kubernetes":      "Kubernetes",
    "docker":          "Docker",
    "tf":              "Terraform",
    "terraform":       "Terraform",
    # Big Data
    "apache spark":    "Spark",
    "pyspark":         "Spark",
    "apache kafka":    "Kafka",
    "apache airflow":  "Airflow",
    "elastic search":  "Elasticsearch",
    "elastic":         "Elasticsearch",
    # ML
    "ml":              "Machine Learning",
    "machine learning": "Machine Learning",
    "dl":              "Deep Learning",
    "deep learning":   "Deep Learning",
    "nlp":             "NLP",
    "natural language processing": "NLP",
    "cv":              "Computer Vision",  # ambiguë mais OK dans contexte tech
    "computer vision": "Computer Vision",
    "scikit-learn":    "Scikit-Learn",
    "scikit learn":    "Scikit-Learn",
    "sklearn":         "Scikit-Learn",
    "pytorch":         "PyTorch",
    "tensorflow":      "TensorFlow",
    "tf2":             "TensorFlow",
    "huggingface":     "Hugging Face",
    "hugging face":    "Hugging Face",
    # BI
    "powerbi":         "Power BI",
    "power bi":        "Power BI",
    "power-bi":        "Power BI",
    "qlik":            "QlikView",
    "qlikview":        "QlikView",
    "qlik view":       "QlikView",
    "qlik sense":      "Qlik Sense",
    # DB
    "postgres":        "PostgreSQL",
    "postgresql":      "PostgreSQL",
    "mongo":           "MongoDB",
    "mongodb":         "MongoDB",
    "ms sql":          "SQL Server",
    "mssql":           "SQL Server",
    "sql server":      "SQL Server",
    # Web
    "reactjs":         "React",
    "react.js":        "React",
    "react":           "React",
    "vuejs":           "Vue.js",
    "vue.js":          "Vue.js",
    "vue":             "Vue.js",
    "nodejs":          "Node.js",
    "node.js":         "Node.js",
    "node":            "Node.js",
    "next.js":         "Next.js",
    "nextjs":          "Next.js",
    # Frameworks
    "spring boot":     "Spring Boot",
    "springboot":      "Spring Boot",
    # Méthodo
    "ci/cd":           "CI/CD",
    "cicd":            "CI/CD",
    "ci-cd":           "CI/CD",
    "tdd":             "TDD",
    "scrum":           "Scrum",
    "agile":           "Agile",
}

# Index inverse : skill canonique -> catégorie
_SKILL_TO_CAT: dict[str, str] = {}
for cat, skills in CATEGORIES.items():
    for s in skills:
        _SKILL_TO_CAT[s.lower()] = cat


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #

def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def canonicalize(skill: str) -> str | None:
    """Renvoie la forme canonique d'un skill (ou None si vide / unknown)."""
    if not skill:
        return None
    raw = skill.strip()
    if not raw:
        return None
    k = _key(raw)
    if k in ALIASES:
        return ALIASES[k]
    # Fallback : si déjà connu (insensible à la casse), garder la forme officielle.
    if k in _SKILL_TO_CAT:
        # Retrouve la forme exacte définie dans CATEGORIES.
        for cat, skills in CATEGORIES.items():
            for s in skills:
                if s.lower() == k:
                    return s
    # Inconnu : on garde la forme reçue mais nettoyée.
    return raw[:64]


def category_of(skill_canonical: str) -> str:
    """Catégorie d'un skill canonique. 'Autre' si inconnu."""
    if not skill_canonical:
        return "Autre"
    return _SKILL_TO_CAT.get(skill_canonical.lower(), "Autre")


def normalize_skills(skills) -> list[str]:
    """Liste de skills canoniques, dédupliquée en gardant l'ordre."""
    if not skills:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for s in skills:
        c = canonicalize(s)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out

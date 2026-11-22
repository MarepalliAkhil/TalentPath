"""40 hand-labelled synthetic job/resume pairs for evaluating the fit score.

Labels were written by judgement BEFORE running the scorer, from the brief:
Strong = all required skills shown with real evidence and enough experience;
Good = most required skills, decent evidence; Partial = some required skills or
thin evidence; Low = little overlap. "tune" pairs may guide weight changes;
"holdout" pairs are only measured, never used for tuning.
"""

JOBS = {
    "backend": {
        "required": ["Python", "Django", "PostgreSQL", "REST API Design"],
        "nice": ["Docker", "Redis"],
        "level": 30,
    },
    "frontend": {
        "required": ["React", "TypeScript", "CSS"],
        "nice": ["Jest", "Web Accessibility"],
        "level": 30,
    },
    "data": {"required": ["Python", "SQL", "Apache Spark"], "nice": ["Apache Airflow", "dbt"], "level": 30},
    "devops": {
        "required": ["Docker", "Kubernetes", "CI/CD", "Linux"],
        "nice": ["Terraform", "AWS"],
        "level": 40,
    },
    "intern": {"required": ["Python", "Git", "SQL"], "nice": ["JavaScript"], "level": 10},
    "sales": {"required": ["B2B Sales", "Negotiation", "CRM"], "nice": ["Salesforce"], "level": 40},
    "hr": {
        "required": ["Talent Acquisition", "Sourcing", "Interviewing"],
        "nice": ["HR Analytics"],
        "level": 30,
    },
    "pm": {
        "required": ["Product Management", "Stakeholder Management", "Data Analysis"],
        "nice": ["SQL", "A/B Testing"],
        "level": 40,
    },
}


def cv(skills="", experience="", projects="", extra=""):
    parts = ["Sample Person", "Hyderabad", ""]
    if skills:
        parts += ["SKILLS", skills, ""]
    if experience:
        parts += ["EXPERIENCE", *experience.split("\n"), ""]
    if projects:
        parts += ["PROJECTS", *projects.split("\n"), ""]
    if extra:
        parts += extra.split("\n")
    return "\n".join(parts)


PAIRS = [
    # ---------------------------------------------------------------- tune (20)
    (
        "tune",
        "backend",
        "strong",
        cv(
            "Python, Django, PostgreSQL, REST, Docker",
            "Backend Engineer - Acme (2021 - present)\nBuilt REST APIs with Django and PostgreSQL on Python; RESTful APIs for payments; Docker deploys",
        ),
    ),
    (
        "tune",
        "backend",
        "good",
        cv(
            "Python, Django, PostgreSQL",
            "Developer - Beta (2022 - present)\nMaintained Django services in Python",
        ),
    ),
    (
        "tune",
        "backend",
        "partial",
        cv("Python, Flask", "Junior Developer - Gamma (2024 - present)\nWrote Python scripts"),
    ),
    (
        "tune",
        "backend",
        "low",
        cv("Excel, Communication", "Sales Associate - Delta (2020 - present)\nHandled retail customers"),
    ),
    (
        "tune",
        "frontend",
        "strong",
        cv(
            "React, TypeScript, CSS, Jest",
            "Frontend Engineer - Acme (2021 - present)\nShipped React and TypeScript screens; CSS design system; Jest tests",
        ),
    ),
    (
        "tune",
        "frontend",
        "good",
        cv("React, TypeScript, CSS", "UI Developer - Beta (2023 - present)\nBuilt pages in React"),
    ),
    (
        "tune",
        "frontend",
        "partial",
        cv("HTML, CSS, JavaScript", "Web Designer - Gamma (2023 - present)\nBuilt landing pages with CSS"),
    ),
    (
        "tune",
        "frontend",
        "low",
        cv("Java, Spring Boot", "Backend Developer - Delta (2022 - present)\nJava services"),
    ),
    (
        "tune",
        "data",
        "strong",
        cv(
            "Python, SQL, Spark, Airflow",
            "Data Engineer - Acme (2021 - present)\nBuilt Apache Spark pipelines in Python and SQL, scheduled with Airflow",
        ),
    ),
    (
        "tune",
        "data",
        "partial",
        cv("Python, Pandas", "Analyst - Beta (2023 - present)\nPython notebooks and Pandas reports"),
    ),
    (
        "tune",
        "data",
        "low",
        cv("Figma, UI Design", "Designer - Gamma (2021 - present)\nDesigned mobile screens in Figma"),
    ),
    (
        "tune",
        "devops",
        "strong",
        cv(
            "Docker, Kubernetes, CI/CD, Linux, Terraform",
            "DevOps Engineer - Acme (2019 - present)\nRan Kubernetes clusters on Linux; Docker images; CI/CD with GitHub Actions; Terraform for AWS",
        ),
    ),
    (
        "tune",
        "devops",
        "partial",
        cv("Docker, Linux", "Support Engineer - Beta (2023 - present)\nManaged Linux servers"),
    ),
    (
        "tune",
        "devops",
        "good",
        cv(
            "Docker, Kubernetes, CI/CD, Linux",
            "Platform Engineer - Gamma (2023 - present)\nDocker and Kubernetes deployments, CI/CD pipelines on Linux",
        ),
    ),
    (
        "tune",
        "intern",
        "strong",
        cv(
            "Python, Git, SQL, JavaScript",
            "",
            "Library system in Python with SQL storage, versioned in Git\nQuiz app in JavaScript",
        ),
    ),
    ("tune", "intern", "partial", cv("Python", "", "Calculator in Python")),
    (
        "tune",
        "sales",
        "strong",
        cv(
            "B2B Sales, Negotiation, CRM, Salesforce",
            "Account Executive - Acme (2018 - present)\nClosed B2B Sales deals; contract negotiation; pipeline in Salesforce CRM",
        ),
    ),
    ("tune", "sales", "low", cv("Python, Django", "Developer - Beta (2021 - present)\nDjango apps")),
    (
        "tune",
        "hr",
        "good",
        cv(
            "Talent Acquisition, Sourcing, Interviewing",
            "Recruiter - Acme (2024 - present)\nSourcing and interviewing for tech roles",
        ),
    ),
    (
        "tune",
        "pm",
        "partial",
        cv("Product Management, Communication", "Associate PM - Beta (2024 - present)\nWrote product specs"),
    ),
    # ------------------------------------------------------------- holdout (20)
    (
        "holdout",
        "backend",
        "strong",
        cv(
            "Python, Django, PostgreSQL, REST API Design, Redis",
            "Senior Developer - Kappa (2020 - present)\nDesigned RESTful APIs in Django with PostgreSQL and Redis caching",
            "Internal tool in Python",
        ),
    ),
    (
        "holdout",
        "backend",
        "partial",
        cv("Python, MySQL", "Intern - Lambda (Jan 2025 - Jun 2025)\nPython data cleanup"),
    ),
    (
        "holdout",
        "backend",
        "good",
        cv(
            "Python, Django, REST, PostgreSQL",
            "Developer - Mu (2024 - present)\nDjango and PostgreSQL features",
        ),
    ),
    (
        "holdout",
        "backend",
        "low",
        cv("Tally, Accounting", "Accountant - Nu (2019 - present)\nBookkeeping in Tally"),
    ),
    (
        "holdout",
        "frontend",
        "strong",
        cv(
            "ReactJS, TS, CSS3, Jest, a11y",
            "Frontend Developer - Xi (2022 - present)\nReact.js and TypeScript UI, CSS layouts, Jest unit tests, WCAG fixes",
        ),
    ),
    ("holdout", "frontend", "partial", cv("React", "Freelancer (2024 - present)\nSmall React sites")),
    (
        "holdout",
        "frontend",
        "good",
        cv("React, TypeScript, CSS", "Developer - Omicron (2023 - present)\nReact and TypeScript dashboards"),
    ),
    (
        "holdout",
        "data",
        "good",
        cv("Python, SQL, Spark", "Data Engineer - Pi (2024 - present)\nSpark jobs and SQL models"),
    ),
    (
        "holdout",
        "data",
        "low",
        cv("Content Marketing, SEO", "Writer - Rho (2021 - present)\nBlog content and SEO"),
    ),
    (
        "holdout",
        "data",
        "strong",
        cv(
            "Python, SQL, PySpark, Airflow, dbt",
            "Senior Data Engineer - Sigma (2019 - present)\nPySpark and SQL pipelines in Python, Airflow DAGs, dbt models",
        ),
    ),
    (
        "holdout",
        "devops",
        "partial",
        cv("Linux, Bash", "System Admin - Tau (2018 - present)\nLinux administration"),
    ),
    ("holdout", "devops", "low", cv("Figma, Prototyping", "Designer - Upsilon (2022 - present)\nPrototypes")),
    (
        "holdout",
        "devops",
        "strong",
        cv(
            "Docker, K8s, CI/CD, Linux, AWS, Terraform",
            "SRE - Phi (2018 - present)\nKubernetes on AWS, Docker builds, CI/CD with Jenkins, Linux hardening, Terraform",
        ),
    ),
    ("holdout", "intern", "good", cv("Python, Git, SQL", "", "")),
    ("holdout", "intern", "low", cv("Photoshop", "", "Poster designs")),
    (
        "holdout",
        "sales",
        "good",
        cv("B2B Sales, Negotiation, CRM", "Sales Executive - Chi (2021 - present)\nB2B sales for SaaS"),
    ),
    (
        "holdout",
        "sales",
        "partial",
        cv("Inside Sales, Communication", "Tele-caller - Psi (2024 - present)\nInside sales calls"),
    ),
    (
        "holdout",
        "hr",
        "strong",
        cv(
            "Recruiting, Boolean search, Structured interviewing, People analytics",
            "Talent Partner - Omega (2019 - present)\nRan Talent Acquisition end to end: Sourcing, Interviewing panels, HR Analytics reports",
        ),
    ),
    ("holdout", "hr", "low", cv("Java, Python", "Engineer - Alpha2 (2020 - present)\nJava services")),
    (
        "holdout",
        "pm",
        "good",
        cv(
            "Product Management, Stakeholder Management, Data Analysis",
            "Product Manager - Beta2 (2022 - present)\nOwned roadmap, aligned stakeholders",
        ),
    ),
]

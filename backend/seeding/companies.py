# ruff: noqa: E501  (plain seed text: long sentences read better unwrapped)
"""Prompt 1 seed (D-84, D-85): five fictional companies with Indian offices, long realistic
job pages, screening questions and synthetic application forms.

Every company here is invented. tests/test_companies.py checks the names against a
blocklist of well-known real companies. Re-running is safe: only empty fields are filled.
"""

import hashlib
import json
import random
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from seeding import demo_data as D

HIRING_PROCESS = [
    {
        "step": "Shortlist",
        "detail": "A recruiter reads every application and shortlists within about a week.",
    },
    {
        "step": "Assignment",
        "detail": "A short online assignment (5 to 10 questions) sent to your email; take it when it suits you within three days.",
    },
    {
        "step": "Technical interview",
        "detail": "A 45 to 60 minute video interview with the team; HIRA offers slots that fit everyone's calendar.",
    },
    {
        "step": "HR round",
        "detail": "A conversation with HR about the role, compensation, notice period and joining.",
    },
    {"step": "Offer", "detail": "A written offer with the full terms, accepted online."},
    {"step": "Onboarding", "detail": "Documents, a buddy and a first-week plan, all before day one."},
]

COMPANIES = [
    {
        "slug": "lumina-works",
        "name": "Lumina Works Pvt. Ltd.",
        "tagline": "Software that helps people find work they love.",
        "industry": "HR technology",
        "size": "1,000 to 5,000 employees",
        "founded": 2012,
        "headquarters": "Hyderabad, Telangana",
        "offices": [
            "Hyderabad (HITEC City)",
            "Bengaluru (Koramangala)",
            "Vijayawada (Benz Circle)",
            "Remote across India",
        ],
        "about": (
            "Lumina Works builds hiring and people software used by mid-sized Indian companies, from the "
            "career site a candidate first sees to the onboarding checklist on their first day. Our product "
            "teams sit next to recruiters and HR teams, and we ship small improvements every week."
        ),
        "culture": (
            "Small, cross-functional squads own a problem end to end. We write things down, review each "
            "other's work kindly and measure what we ship. Flexible hours around a shared core from 11:00 to 16:00 IST."
        ),
        "benefits": [
            "Health insurance for you, your spouse, children and parents (₹5 lakh cover)",
            "Hybrid work: three office days a week, laptop and home-office allowance",
            "₹50,000 yearly learning budget for courses, books and certifications",
            "24 days of paid leave plus festival holidays",
            "Employee stock options for every full-time role",
        ],
        "website": "https://lumina-works.example",
        "logo_initials": "LW",
        "logo_color": "#0B6E78",
    },
    {
        "slug": "nimbus-analytics",
        "name": "Nimbus Analytics Pvt. Ltd.",
        "tagline": "Clear answers from messy data.",
        "industry": "Data and analytics services",
        "size": "200 to 500 employees",
        "founded": 2016,
        "headquarters": "Hyderabad, Telangana",
        "offices": ["Hyderabad (Gachibowli)", "Bengaluru (Whitefield)", "Remote across India"],
        "about": (
            "Nimbus Analytics helps retail, logistics and healthcare companies turn their data into decisions: "
            "forecasting demand, finding drop-offs in customer journeys and building the dashboards leaders read every morning."
        ),
        "culture": (
            "We value careful thinking over clever tricks. Every model ships with a note on its data, its "
            "assumptions and where it might be wrong. Friday afternoons are for learning and demos."
        ),
        "benefits": [
            "Health insurance with parents' cover",
            "Cloud credits and a GPU workstation budget for experiments",
            "Conference travel once a year",
            "Quarterly wellness allowance",
            "Hybrid work with two office days a week",
        ],
        "website": "https://nimbus-analytics.example",
        "logo_initials": "NA",
        "logo_color": "#3B5BA9",
    },
    {
        "slug": "deccan-cloudworks",
        "name": "Deccan CloudWorks Pvt. Ltd.",
        "tagline": "Reliable cloud platforms for growing businesses.",
        "industry": "Cloud infrastructure and security",
        "size": "500 to 1,000 employees",
        "founded": 2014,
        "headquarters": "Pune, Maharashtra",
        "offices": ["Pune (Hinjawadi)", "Hyderabad (Madhapur)", "Bengaluru (Bellandur)", "Chennai (OMR)"],
        "about": (
            "Deccan CloudWorks runs and secures cloud platforms for Indian fintech, e-commerce and SaaS companies. "
            "We automate everything we can, so our engineers spend their time on hard problems instead of repetitive tickets."
        ),
        "culture": (
            "Blameless incident reviews, written runbooks and a 24x7 on-call rotation with fair compensation. "
            "We pair often and rotate people across teams once a year."
        ),
        "benefits": [
            "On-call allowance and a day off after every busy night",
            "Health insurance and annual health check-ups",
            "Paid cloud and security certifications",
            "Night-shift transport within city limits",
            "Performance bonus paid twice a year",
        ],
        "website": "https://deccan-cloudworks.example",
        "logo_initials": "DC",
        "logo_color": "#5B4B8A",
    },
    {
        "slug": "kaveri-finserve",
        "name": "Kaveri FinServe Technologies Pvt. Ltd.",
        "tagline": "Simple, fair financial products for small businesses.",
        "industry": "Financial technology",
        "size": "500 to 1,000 employees",
        "founded": 2018,
        "headquarters": "Bengaluru, Karnataka",
        "offices": ["Bengaluru (HSR Layout)", "Chennai (Guindy)", "Pune (Baner)", "Hyderabad (Begumpet)"],
        "about": (
            "Kaveri FinServe offers working-capital loans, payments and bookkeeping tools to small businesses "
            "across South and West India. We combine careful credit decisions with software shop owners can use on a phone."
        ),
        "culture": (
            "Customers first, then compliance, then speed. Teams meet merchants every quarter, and every "
            "feature starts with a conversation with someone who will use it."
        ),
        "benefits": [
            "Health and accident insurance",
            "Annual performance bonus",
            "Meal cards and a commute allowance",
            "Two volunteering days a year",
            "Flexible start times between 8:00 and 11:00",
        ],
        "website": "https://kaveri-finserve.example",
        "logo_initials": "KF",
        "logo_color": "#1B6B41",
    },
    {
        "slug": "saptagiri-healthtech",
        "name": "Saptagiri HealthTech Pvt. Ltd.",
        "tagline": "Better care, closer to home.",
        "industry": "Healthcare technology",
        "size": "200 to 500 employees",
        "founded": 2019,
        "headquarters": "Chennai, Tamil Nadu",
        "offices": [
            "Chennai (Taramani)",
            "Hyderabad (Kondapur)",
            "Vijayawada (Labbipet)",
            "Remote across India",
        ],
        "about": (
            "Saptagiri HealthTech builds apps that connect patients in smaller towns with clinics and diagnostic "
            "labs: appointments, reports and follow-up reminders in eight Indian languages."
        ),
        "culture": (
            "We design for patients who are new to smartphones. Teams test with real clinic staff every "
            "sprint, and privacy reviews are part of every release."
        ),
        "benefits": [
            "Family health insurance including parents",
            "Free annual health check-up at partner labs",
            "Language-learning allowance",
            "Remote-first with quarterly team meet-ups",
            "Paid parental leave beyond the legal minimum",
        ],
        "website": "https://saptagiri-healthtech.example",
        "logo_initials": "SH",
        "logo_color": "#B8400A",
    },
]

# Which company posts each seeded job. Internal jobs (employees only) are all Lumina Works,
# the company the seeded employees work for.
JOB_COMPANY = {
    "Senior Backend Engineer (Python)": "lumina-works",
    "Frontend Engineer (React)": "lumina-works",
    "Full Stack Engineer": "lumina-works",
    "Software Engineering Intern": "lumina-works",
    "Product Manager, Candidate Experience": "lumina-works",
    "Associate Product Manager": "lumina-works",
    "Product Designer": "lumina-works",
    "UX Researcher": "lumina-works",
    "Talent Acquisition Partner (Tech)": "lumina-works",
    "HR Operations Specialist": "lumina-works",
    "Data Scientist": "nimbus-analytics",
    "Data Engineer": "nimbus-analytics",
    "Machine Learning Engineer (NLP)": "nimbus-analytics",
    "Business Intelligence Analyst": "nimbus-analytics",
    "DevOps Engineer": "deccan-cloudworks",
    "Site Reliability Engineer": "deccan-cloudworks",
    "Application Security Engineer": "deccan-cloudworks",
    "QA Automation Engineer": "deccan-cloudworks",
    "Java Backend Engineer": "kaveri-finserve",
    "Enterprise Account Executive": "kaveri-finserve",
    "Inside Sales Representative": "kaveri-finserve",
    "Financial Analyst": "kaveri-finserve",
    "Mobile Engineer (Flutter)": "saptagiri-healthtech",
    "Content Marketing Manager": "saptagiri-healthtech",
    "Customer Success Manager": "saptagiri-healthtech",
}

TEAM_TEXT = {
    "Engineering": "The {team} squad is {n} engineers, a product manager and a designer. You will ship to production in your first two weeks, with a buddy who reviews your first pull requests.",
    "Data & AI": "The data team of {n} people works with product, operations and leadership. Every analysis comes with a short write-up of what the data can and cannot tell us.",
    "Platform & Security": "The platform team of {n} engineers keeps services fast, safe and cheap to run. We share an on-call rotation and improve the runbooks after every incident.",
    "Product": "Product managers here own outcomes, not feature lists. You will work with a squad of {n} and talk to customers every week.",
    "Design": "A design team of {n} covering research, interaction and visual design, working in a shared design system.",
    "Sales": "The sales team of {n} works with mid-sized customers across India, with a pre-sales engineer and a customer success manager on every account.",
    "Marketing": "A small marketing team of {n} writing guides, case studies and newsletters that customers actually read.",
    "Customer Success": "Customer success is {n} people who help customers adopt the product, run quarterly reviews and bring feedback to product teams.",
    "People & HR": "The people team of {n} looks after hiring, onboarding, leave and policies for colleagues across offices.",
    "Finance": "The finance team of {n} runs planning, reporting and controls, and partners with every department on budgets.",
}

EXTRA_RESPONSIBILITIES = {
    "Engineering": [
        "Take part in code reviews and design discussions.",
        "Improve test coverage, monitoring and documentation as you go.",
    ],
    "Data & AI": [
        "Build and maintain reliable data pipelines and models.",
        "Present findings to non-technical colleagues clearly.",
    ],
    "Platform & Security": [
        "Join the on-call rotation after your first month.",
        "Write and improve runbooks for common incidents.",
    ],
    "Product": [
        "Write clear problem statements and success measures.",
        "Prioritise the roadmap with engineering and design.",
    ],
    "Design": [
        "Run usability tests with real users every sprint.",
        "Contribute components to the shared design system.",
    ],
    "Sales": [
        "Build and manage a healthy pipeline in the CRM.",
        "Work with pre-sales on demos and proposals.",
    ],
    "Marketing": [
        "Plan and publish a monthly content calendar.",
        "Measure what works and share learnings with the team.",
    ],
    "Customer Success": [
        "Run onboarding and quarterly business reviews for your accounts.",
        "Spot risks early and work on renewals with sales.",
    ],
    "People & HR": [
        "Keep records accurate and processes compliant.",
        "Improve the experience of candidates and new joiners.",
    ],
    "Finance": [
        "Prepare monthly reports and variance analysis.",
        "Support audits and keep controls documented.",
    ],
}

LEVEL_YEARS = {
    "Intern": "Final-year students or recent graduates",
    "Associate": "0 to 2 years",
    "Mid-level": "2 to 5 years",
    "Senior": "5 to 8 years",
    "Lead": "7 or more years",
    "Manager": "6 or more years, including people management",
}

QUESTIONS = {
    "Engineering": [
        ("How many years have you written production code professionally?", "number"),
        ("Are you comfortable with a take-home assignment of about two hours?", "yes_no"),
    ],
    "Data & AI": [
        ("How many years have you worked with SQL?", "number"),
        ("Briefly, what is one analysis you are proud of?", "text"),
    ],
    "Platform & Security": [
        ("Are you comfortable with a weekly on-call rotation, including some nights?", "yes_no"),
        ("Which cloud platform have you used most?", "text"),
    ],
    "Product": [("How many years have you worked as a product manager or analyst?", "number")],
    "Design": [("Share a link to your portfolio or a case study.", "text")],
    "Sales": [
        ("Are you comfortable with regular travel to customer sites?", "yes_no"),
        ("What was your last annual sales target, in lakhs?", "number"),
    ],
    "Marketing": [("Share a link to something you have written.", "text")],
    "Customer Success": [("Are you comfortable with rotational shifts (including some evenings)?", "yes_no")],
    "People & HR": [("Have you used an applicant tracking system before?", "yes_no")],
    "Finance": [("Are you a CA, CMA or pursuing either?", "yes_no")],
}

CTC_BANDS = {  # lakhs per annum, by level
    "Intern": (Decimal("3.0"), Decimal("4.2")),
    "Associate": (Decimal("6.0"), Decimal("9.0")),
    "Mid-level": (Decimal("12.0"), Decimal("18.0")),
    "Senior": (Decimal("20.0"), Decimal("30.0")),
    "Lead": (Decimal("28.0"), Decimal("40.0")),
    "Manager": (Decimal("30.0"), Decimal("45.0")),
}


def seed_companies() -> dict:
    from org.models import Company

    out = {}
    for spec in COMPANIES:
        company, created = Company.objects.get_or_create(
            slug=spec["slug"], defaults={**spec, "hiring_process": HIRING_PROCESS}
        )
        if not created and not company.about:
            for key, value in spec.items():
                setattr(company, key, value)
            company.hiring_process = HIRING_PROCESS
            company.save()
        out[spec["slug"]] = company
    return out


def _questions(job) -> list[dict]:
    rows = list(QUESTIONS.get(job.department.name, []))
    if job.work_mode == "hybrid":
        rows.insert(0, (f"Can you work from our {job.location.name} office three days a week?", "yes_no"))
    elif job.work_mode == "onsite":
        rows.insert(0, (f"Can you work from our {job.location.name} office five days a week?", "yes_no"))
    return [
        {"id": f"q{i}", "text": text, "kind": kind, "required": True}
        for i, (text, kind) in enumerate(rows[:3], 1)
    ]


def enrich_jobs(companies: dict) -> int:
    """Fill the long job page for seeded jobs (only empty fields, so admins' edits survive)."""
    from jobs.models import Job

    lumina = companies["lumina-works"]
    changed = 0
    for job in Job.objects.select_related("department", "location", "level", "company").prefetch_related(
        "required_skills", "nice_to_have_skills"
    ):
        slug = "lumina-works" if job.audience == "internal" else JOB_COMPANY.get(job.title, "lumina-works")
        company = companies.get(slug, lumina)
        dept = job.department.name
        rng = random.Random(int(hashlib.sha256(job.slug.encode()).hexdigest()[:8], 16))
        fields = {}
        if job.company_id is None or (
            job.company_id == lumina.id and slug != "lumina-works" and not job.about_team
        ):
            fields["company"] = company
        if not job.about_team:
            team = job.title.split("(")[0].split(",")[0].strip()
            fields["about_team"] = TEAM_TEXT.get(dept, TEAM_TEXT["Engineering"]).format(
                team=team, n=rng.randint(5, 14)
            )
        if not job.responsibilities:
            required = [s.name for s in job.required_skills.all()]
            fields["responsibilities"] = [
                *D.DEPARTMENT_DUTIES.get(dept, [])[:3],
                *EXTRA_RESPONSIBILITIES.get(dept, []),
                *(
                    [f"Use {', '.join(required[:3])} every day, and help others get better at them."]
                    if required
                    else []
                ),
            ]
        if not job.required_qualifications:
            required = [s.name for s in job.required_skills.all()]
            fields["required_qualifications"] = [
                f"Experience: {LEVEL_YEARS.get(job.level.name, 'Relevant experience')}.",
                *([f"Working knowledge of {', '.join(required)}."] if required else []),
                "Clear written and spoken English; another Indian language is a plus.",
                "A degree or equivalent practical experience (we do not filter on college names).",
            ]
        if not job.preferred_qualifications:
            nice = [s.name for s in job.nice_to_have_skills.all()]
            fields["preferred_qualifications"] = [
                *([f"Hands-on time with {', '.join(nice)}."] if nice else []),
                "Experience working with distributed teams across Indian cities.",
            ]
        if job.ctc_min_lpa is None:
            low, high = CTC_BANDS.get(job.level.name, (Decimal("8.0"), Decimal("14.0")))
            fields["ctc_min_lpa"], fields["ctc_max_lpa"] = low, high
        if not job.screening_questions:
            fields["screening_questions"] = _questions(job)
        if fields:
            Job.objects.filter(pk=job.pk).update(**fields)
            changed += 1
    return changed


def attach_employees(companies: dict) -> int:
    from hr.models import Employee

    return Employee.objects.filter(company__isnull=True).update(company=companies["lumina-works"])


def _form_for(application, rng: random.Random) -> dict:
    from applications.form import NOTICE_PERIODS

    candidate = application.candidate
    profile = candidate.profile
    years = (
        float(application.parsed_profile.experience_years)
        if hasattr(application, "parsed_profile") and application.parsed_profile.experience_years
        else 0.0
    )
    fresher = years < 0.5
    current = Decimal("0") if fresher else Decimal(str(round(3 + years * rng.uniform(1.6, 2.6), 1)))
    expected = (
        (current * Decimal(str(round(rng.uniform(1.2, 1.45), 2)))).quantize(Decimal("0.1"))
        if current
        else Decimal(str(rng.choice([4.5, 6.0, 7.5])))
    )
    joining = timezone.localdate() + timedelta(days=rng.choice([15, 30, 45, 60, 90]))
    answers = {}
    for q in application.job.screening_questions or []:
        answers[q["id"]] = {
            "yes_no": rng.choice(["yes", "yes", "no"]),
            "number": str(rng.randint(1, 8)),
            "text": "Happy to share details in the interview.",
        }[q["kind"]]
    return {
        "personal": {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": profile.phone or "+91 55501 00000",
            "current_city": profile.location_text or rng.choice(D.CITIES),
            "willing_to_relocate": rng.random() < 0.6,
            "date_of_birth": profile.date_of_birth,
        },
        "education": {
            "highest_qualification": "Bachelor's degree",
            "college": rng.choice(D.COLLEGES),
            "branch": rng.choice(
                [
                    "Computer Science",
                    "Information Technology",
                    "Electronics",
                    "Commerce",
                    "Business Administration",
                ]
            ),
            "graduation_year": date.today().year - max(0, int(years)) - 1,
            "score_type": "cgpa",
            "score": str(round(rng.uniform(6.8, 9.4), 2)),
            "tenth_percentage": str(round(rng.uniform(75, 97), 1)),
            "twelfth_percentage": str(round(rng.uniform(70, 96), 1)),
        },
        "experience": {
            "status": "fresher" if fresher else "experienced",
            "roles": []
            if fresher
            else [
                {
                    "company": rng.choice(D.COMPANIES),
                    "title": application.job.title.split("(")[0].strip(),
                    "start": f"{date.today().year - max(1, int(years))}-06",
                    "end": "present",
                    "responsibilities": "Synthetic demo history.",
                }
            ],
            "total_years": str(round(years, 1)),
        },
        "compensation": {
            "current_ctc_lpa": str(current),
            "expected_ctc_lpa": str(expected),
            "notice_period": rng.choice(list(NOTICE_PERIODS)),
            "earliest_joining": joining.isoformat(),
        },
        "links": {"linkedin_url": "", "github_url": "", "portfolio_url": ""},
        "answers": answers,
        "use_profile_resume": False,
        "cover_letter": application.cover_note,
    }


def seed_application_forms() -> int:
    """Synthetic application forms for seeded applications, so recruiters see CTC and answers."""
    from accounts.models import Profile
    from applications.form import TERMS_VERSION
    from applications.models import Application, ApplicationForm

    made = 0
    apps = Application.objects.filter(
        form__isnull=True, candidate__email__endswith=".example"
    ).select_related("candidate__profile", "job", "parsed_profile")
    for application in apps:
        rng = random.Random(
            int(hashlib.sha256(str(application.candidate_id).encode()).hexdigest()[:8], 16)
            + application.job.title.__len__()
        )
        profile, _ = Profile.objects.get_or_create(user=application.candidate)
        if not profile.date_of_birth:
            born = date(date.today().year - rng.randint(21, 38), rng.randint(1, 12), rng.randint(1, 28))
            profile.date_of_birth = born.isoformat()
            profile.save(update_fields=["date_of_birth", "updated_at"])
        ApplicationForm.objects.create(
            application=application,
            data=json.dumps(_form_for(application, rng), default=str),
            declared_at=application.created_at,
            terms_version=TERMS_VERSION,
        )
        made += 1
    return made


def seed_prompt1() -> dict:
    companies = seed_companies()
    return {
        "companies": len(companies),
        "jobs_enriched": enrich_jobs(companies),
        "employees_attached": attach_employees(companies),
        "application_forms": seed_application_forms(),
    }

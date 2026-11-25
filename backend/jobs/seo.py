"""SEO data for public job pages: title, meta description, JSON-LD JobPosting."""

import html
import textwrap
from datetime import timedelta

from django.conf import settings

from core.brand import get_brand

from .models import EmploymentType, Job, WorkMode

EMPLOYMENT_LD = {
    EmploymentType.FULL_TIME: "FULL_TIME",
    EmploymentType.PART_TIME: "PART_TIME",
    EmploymentType.CONTRACT: "CONTRACTOR",
    EmploymentType.INTERNSHIP: "INTERN",
}


def employer(job: Job) -> str:
    """The hiring company's name (D-84), else the brand's employer name."""
    return job.company.name if job.company_id else get_brand()["employerName"]


def page_title(job: Job) -> str:
    return f"{job.title} · {job.department.name}, {job.location.name} | {get_brand()['name']}"


def meta_description(job: Job) -> str:
    skills = ", ".join(s.name for s in list(job.required_skills.all())[:4])
    text = (
        f"{job.title} ({job.level.name}) in {job.department.name} at {employer(job)}, "
        f"{job.location.name} · {job.get_work_mode_display()}. Key skills: {skills}. "
        f"Apply in minutes."
    )
    return textwrap.shorten(text, width=160, placeholder="…")


def description_html(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)


def job_posting_ld(job: Job) -> dict:
    posted = job.published_at or job.created_at
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": description_html(job.description),
        "identifier": {"@type": "PropertyValue", "name": employer(job), "value": job.slug},
        "datePosted": posted.date().isoformat(),
        "validThrough": (posted + timedelta(days=90)).isoformat(),
        "employmentType": EMPLOYMENT_LD.get(job.employment_type, "OTHER"),
        "hiringOrganization": {
            "@type": "Organization",
            "name": employer(job),
            "sameAs": settings.SITE_URL,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.location.name,
                "addressCountry": job.location.country,
            },
        },
        "skills": ", ".join(s.name for s in job.required_skills.all()),
        "occupationalCategory": job.department.name,
        "directApply": True,
        "url": f"{settings.SITE_URL}/jobs/{job.slug}",
        "totalJobOpenings": job.openings,
    }
    if job.ctc_min_lpa is not None and job.ctc_max_lpa is not None:
        lakh = 100000
        data["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": "INR",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": int(job.ctc_min_lpa * lakh),
                "maxValue": int(job.ctc_max_lpa * lakh),
                "unitText": "YEAR",
            },
        }
    if job.work_mode == WorkMode.REMOTE:
        data["jobLocationType"] = "TELECOMMUTE"
        data["applicantLocationRequirements"] = {"@type": "Country", "name": job.location.country}
    return data


def seo_block(job: Job) -> dict:
    return {
        "title": page_title(job),
        "description": meta_description(job),
        "canonical": f"{settings.SITE_URL}/jobs/{job.slug}",
        "json_ld": job_posting_ld(job),
    }

"""Prompt 1, part E: fictional companies and long, realistic job pages (D-84, D-85)."""

import io

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from jobs.models import Job
from org.fictional import REAL_COMPANY_BLOCKLIST, looks_real
from org.models import Company
from seeding import companies as seed_companies
from seeding import demo_data as D

# An independent list for the test, so the guard and its test cannot drift together.
WELL_KNOWN = {
    "google",
    "microsoft",
    "amazon",
    "infosys",
    "tcs",
    "wipro",
    "accenture",
    "deloitte",
    "flipkart",
    "zoho",
    "freshworks",
    "phenom",
    "turbohire",
    "darwinbox",
    "keka",
    "swiggy",
    "zomato",
    "paytm",
}


def _names_in_seed() -> list[str]:
    return [c["name"] for c in seed_companies.COMPANIES] + list(D.COMPANIES) + list(D.COLLEGES)


def test_seed_companies_and_employers_are_fictional():
    assert WELL_KNOWN <= set(REAL_COMPANY_BLOCKLIST)
    for name in _names_in_seed():
        words = " " + name.lower().replace(".", " ").replace(",", " ") + " "
        assert not any(f" {real} " in words for real in WELL_KNOWN), name
        assert looks_real(name) == "", name
    for spec in seed_companies.COMPANIES:
        assert spec["website"].endswith(".example")  # placeholder addresses only


def test_five_companies_with_indian_offices():
    assert len(seed_companies.COMPANIES) == 5
    for spec in seed_companies.COMPANIES:
        assert spec["about"] and spec["culture"] and len(spec["benefits"]) >= 4
        assert any(city in spec["headquarters"] for city in ("Hyderabad", "Bengaluru", "Pune", "Chennai"))
    assert [step["step"] for step in seed_companies.HIRING_PROCESS] == [
        "Shortlist",
        "Assignment",
        "Technical interview",
        "HR round",
        "Offer",
        "Onboarding",
    ]


@pytest.mark.django_db
def test_seed_gives_every_open_job_a_company_and_a_long_page():
    call_command("seed", stdout=io.StringIO())
    assert Company.objects.count() == 5
    open_jobs = Job.objects.open().select_related("company")
    assert open_jobs.count() >= 25
    for job in open_jobs:
        assert job.company is not None, job.title
        assert job.about_team and len(job.responsibilities) >= 4, job.title
        assert job.required_qualifications and job.ctc_min_lpa and job.ctc_max_lpa >= job.ctc_min_lpa
        assert 1 <= len(job.screening_questions) <= 3
    assert len({j.company_id for j in open_jobs}) == 5
    detail = APIClient().get(f"/api/public/jobs/{open_jobs.exclude(audience='internal').first().slug}").data
    for key in (
        "about_team",
        "responsibilities",
        "required_qualifications",
        "preferred_qualifications",
        "benefits",
        "hiring_process",
        "ctc",
    ):
        assert detail[key], key
    assert detail["company"]["about"] and detail["company"]["hiring_process"]
    assert [s["step"] for s in detail["hiring_process"]][:3] == [
        "Shortlist",
        "Assignment",
        "Technical interview",
    ]
    assert detail["ctc"]["label"].startswith("₹") and detail["ctc"]["label"].endswith("LPA")
    assert detail["screening_question_count"] >= 1
    # Seeded applications carry a synthetic form, so recruiters see CTC in the demo.
    from applications.models import Application

    assert not Application.objects.filter(form__isnull=True, candidate__email__endswith=".example").exists()


def test_job_page_json_ld_names_the_hiring_company_and_salary(open_job):
    company = Company.objects.create(name="Testwell Fictional Pvt. Ltd.", about="Makes tests.")
    Job.objects.filter(pk=open_job.pk).update(company=company, ctc_min_lpa=12, ctc_max_lpa=18)
    data = APIClient().get(f"/api/public/jobs/{open_job.slug}").data
    from jobs.seo import job_posting_ld

    ld = job_posting_ld(Job.objects.select_related("company").get(pk=open_job.pk))
    assert ld["hiringOrganization"]["name"] == "Testwell Fictional Pvt. Ltd."
    assert ld["baseSalary"]["value"]["minValue"] == 1200000 and ld["baseSalary"]["currency"] == "INR"
    assert data["company"]["name"] == "Testwell Fictional Pvt. Ltd."
    assert "Testwell Fictional" in data["seo"]["description"]


def test_admin_manages_companies_and_real_names_are_refused(client_for):
    admin = client_for("admin")
    created = admin.post(
        "/api/companies",
        {
            "name": "Tamarind Grove Robotics Pvt. Ltd.",
            "industry": "Robotics",
            "website": "https://tamarind-grove.example",
            "hiring_process": [{"step": "Shortlist", "detail": "We read every application."}],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    assert created.data["logo_initials"] == "TG"
    real = admin.post("/api/companies", {"name": "Infosys Limited"}, format="json")
    assert real.status_code == 400 and "fictional" in str(real.data)
    site = admin.post(
        "/api/companies", {"name": "Some Fictional Co", "website": "https://realsite.com"}, format="json"
    )
    assert site.status_code == 400 and "website" in site.data
    assert client_for("hr").post("/api/companies", {"name": "Another One"}, format="json").status_code == 403
    assert client_for("anonymous").get("/api/companies").status_code == 200


def test_career_search_filters_by_company(make_job):
    a = Company.objects.create(name="Alpha Fictional Pvt. Ltd.")
    job = make_job(title="Alpha Role")
    Job.objects.filter(pk=job.pk).update(company=a)
    make_job(title="Other Role")
    titles = [j["title"] for j in APIClient().get(f"/api/public/jobs?company={a.slug}").data["results"]]
    assert titles == ["Alpha Role"]

from datetime import date

import pytest

from core.brand import get_brand
from jobs.models import JobStatus


@pytest.fixture
def jobs(make_job, org):
    return {
        "backend": make_job(title="Backend Engineer"),
        "frontend": make_job(
            title="Frontend Engineer", required=("javascript", "react"), nice=(), work_mode="onsite"
        ),
        "remote": make_job(
            title="Platform Engineer",
            location=org["location2"],
            department=org["department2"],
            work_mode="remote",
            required=("kubernetes",),
            nice=(),
        ),
        "draft": make_job(title="Secret Draft", status=JobStatus.DRAFT),
        "closed": make_job(title="Old Closed", status=JobStatus.CLOSED),
    }


def slugs(resp):
    return {j["slug"] for j in resp.data["results"]}


def test_only_open_jobs_are_public(client_for, jobs):
    resp = client_for("anonymous").get("/api/public/jobs")
    assert resp.status_code == 200
    assert slugs(resp) == {jobs[k].slug for k in ("backend", "frontend", "remote")}
    assert "created_by" not in resp.data["results"][0]
    assert "hiring_manager" not in resp.data["results"][0]


@pytest.mark.parametrize(
    "query,expected",
    [
        ("department=sales", {"remote"}),
        ("location=hyderabad", {"backend", "frontend"}),
        ("work_mode=onsite", {"frontend"}),
        ("skill=JS", {"frontend"}),
        ("skill=k8s", {"remote"}),
        ("skill=postgresql", {"backend"}),
        ("skill=unknown-skill", set()),
        ("q=frontend", {"frontend"}),
        ("location=hyderabad&skill=python", {"backend"}),
    ],
)
def test_career_filters(client_for, jobs, query, expected):
    resp = client_for("anonymous").get(f"/api/public/jobs?{query}")
    assert resp.status_code == 200
    assert slugs(resp) == {jobs[k].slug for k in expected}


def test_invalid_work_mode_is_rejected(client_for, jobs):
    assert client_for("anonymous").get("/api/public/jobs?work_mode=moon").status_code == 400


def test_job_detail_has_unique_seo_tags(client_for, jobs):
    client = client_for("anonymous")
    a = client.get(f"/api/public/jobs/{jobs['backend'].slug}").data
    b = client.get(f"/api/public/jobs/{jobs['frontend'].slug}").data
    assert a["seo"]["title"] != b["seo"]["title"]
    assert a["seo"]["description"] != b["seo"]["description"]
    assert "Backend Engineer" in a["seo"]["title"] and get_brand()["name"] in a["seo"]["title"]
    assert 50 <= len(a["seo"]["description"]) <= 160
    assert a["seo"]["canonical"].endswith(f"/jobs/{jobs['backend'].slug}")


def test_hidden_jobs_have_no_detail_page(client_for, jobs):
    client = client_for("anonymous")
    assert client.get(f"/api/public/jobs/{jobs['draft'].slug}").status_code == 404
    assert client.get(f"/api/public/jobs/{jobs['closed'].slug}").status_code == 404


def test_slugs_are_clean_and_unique(make_job):
    first = make_job(title="Data Analyst (Hiring Insights)")
    second = make_job(title="Data Analyst (Hiring Insights)")
    assert first.slug == "data-analyst-hiring-insights-hyderabad"
    assert second.slug == "data-analyst-hiring-insights-hyderabad-2"


def test_jobposting_json_ld_shape(client_for, jobs):
    ld = client_for("anonymous").get(f"/api/public/jobs/{jobs['backend'].slug}").data["seo"]["json_ld"]
    assert ld["@context"] == "https://schema.org"
    assert ld["@type"] == "JobPosting"
    assert ld["title"] == "Backend Engineer"
    assert ld["description"].startswith("<p>")
    date.fromisoformat(ld["datePosted"])
    assert ld["validThrough"] > ld["datePosted"]
    assert ld["employmentType"] == "FULL_TIME"
    assert ld["hiringOrganization"] == {
        "@type": "Organization",
        "name": get_brand()["employerName"],
        "sameAs": "https://careers.test",
    }
    assert ld["jobLocation"]["@type"] == "Place"
    assert ld["jobLocation"]["address"]["addressLocality"] == "Hyderabad"
    assert ld["jobLocation"]["address"]["addressCountry"] == "India"
    assert ld["directApply"] is True
    assert ld["identifier"]["value"] == jobs["backend"].slug
    assert "jobLocationType" not in ld


def test_remote_jobposting_marks_telecommute(client_for, jobs):
    ld = client_for("anonymous").get(f"/api/public/jobs/{jobs['remote'].slug}").data["seo"]["json_ld"]
    assert ld["jobLocationType"] == "TELECOMMUTE"
    assert ld["applicantLocationRequirements"] == {"@type": "Country", "name": "India"}


def test_sitemap_lists_open_jobs_only(client_for, jobs):
    resp = client_for("anonymous").get("/sitemap.xml", HTTP_ACCEPT="application/xml")
    body = resp.content.decode()
    assert resp.status_code == 200 and resp["Content-Type"].startswith("application/xml")
    assert "<urlset" in body and "https://careers.test/jobs</loc>" in body
    assert f"/jobs/{jobs['backend'].slug}</loc>" in body
    assert jobs["draft"].slug not in body and jobs["closed"].slug not in body


def test_robots_txt(client_for, db):
    body = client_for("anonymous").get("/robots.txt", HTTP_ACCEPT="text/plain").content.decode()
    assert "Sitemap: https://careers.test/sitemap.xml" in body
    assert "Disallow: /api/" in body and "Disallow: /admin" in body

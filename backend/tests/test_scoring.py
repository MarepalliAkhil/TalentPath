import pytest

from applications.services import move_application
from matching.models import FitScore
from matching.scoring import JobRequirements, ScoringInput, score
from matching.services import ensure_fresh
from matching.weights import BANDS, SCORER_VERSION, WEIGHTS

REQ = JobRequirements(
    required=(("python", "Python"), ("sql", "SQL"), ("django", "Django")),
    nice=(("docker", "Docker"),),
    level_rank=30,
)


def test_weights_and_bands_are_documented_constants():
    assert sum(WEIGHTS.values()) == 100
    assert WEIGHTS["required"] == max(WEIGHTS.values())
    assert [(m, k) for m, k, _ in BANDS] == [(80, "strong"), (60, "good"), (40, "partial"), (0, "low")]


@pytest.mark.parametrize(
    "value,band",
    [
        (100, "strong"),
        (80, "strong"),
        (79, "good"),
        (60, "good"),
        (59, "partial"),
        (40, "partial"),
        (39, "low"),
        (0, "low"),
    ],
)
def test_band_boundaries(value, band):
    from matching.scoring import _band

    assert _band(value)[0] == band


def test_full_match_is_100_and_empty_is_low():
    full = score(
        ScoringInput(
            (
                ("python", "experience"),
                ("sql", "projects"),
                ("django", "experience"),
                ("docker", "experience"),
            ),
            5.0,
        ),
        REQ,
    )
    assert full.score == 100 and full.band == "strong"
    empty = score(ScoringInput((), 5.0), REQ)
    assert empty.band == "low" and empty.score == 15  # only the experience component


def test_explanation_chips_and_raise_score():
    result = score(
        ScoringInput((("python", "projects"), ("django", "skills"), ("docker", "experience")), 3.0), REQ
    )
    labels = [c["label"] for c in result.explanation["chips"]]
    assert "Has Python (projects)" in labels
    assert "Has Django" in labels
    assert "Missing required: SQL" in labels
    assert "Nice to have: Docker" in labels
    assert result.explanation["raise_score"] == ["Add evidence of SQL"]
    assert sum(b["points"] for b in result.explanation["breakdown"]) == pytest.approx(result.score, abs=1)


def test_evidence_strength_rewards_projects_over_listing():
    listed = score(ScoringInput((("python", "skills"), ("sql", "skills"), ("django", "skills")), 3.0), REQ)
    shown = score(
        ScoringInput((("python", "projects"), ("sql", "experience"), ("django", "experience")), 3.0), REQ
    )
    assert shown.score > listed.score


def test_unknown_experience_is_neutral_and_entry_level_needs_none():
    known = score(ScoringInput((("python", "skills"),), 3.0), REQ)
    unknown = score(ScoringInput((("python", "skills"),), None), REQ)
    assert unknown.score < known.score
    assert "Experience not stated (neutral)" in [c["label"] for c in unknown.explanation["chips"]]
    intern = JobRequirements(required=REQ.required, nice=(), level_rank=10)
    assert score(ScoringInput((), None), intern).explanation["breakdown"][-1]["component"] == "experience"


def test_component_without_data_is_dropped_and_reweighted():
    no_nice = JobRequirements(required=(("python", "Python"),), nice=(), level_rank=10)
    result = score(ScoringInput((("python", "experience"),), None), no_nice)
    assert result.score == 100
    assert "nice" not in {b["component"] for b in result.explanation["breakdown"]}


def test_score_is_deterministic():
    a = score(ScoringInput((("python", "skills"),), 2.0), REQ)
    b = score(ScoringInput((("python", "skills"),), 2.0), REQ)
    assert a == b and a.version == SCORER_VERSION


def test_score_computed_when_application_arrives(application):
    fit = FitScore.objects.get(application=application)
    assert fit.version == SCORER_VERSION and fit.band in {"strong", "good", "partial", "low"}
    assert fit.explanation["chips"]


def test_rescored_when_job_skills_change(client_for, application, skills):
    before = FitScore.objects.get(application=application).score
    resp = client_for("recruiter").patch(
        f"/api/jobs/{application.job_id}", {"required_skills": [str(skills["kubernetes"].id)]}, format="json"
    )
    assert resp.status_code == 200
    after = FitScore.objects.get(application=application)
    assert after.score < before
    assert "Missing required: Kubernetes" in [c["label"] for c in after.explanation["chips"]]


def test_rescored_when_scorer_version_changes(application):
    FitScore.objects.filter(application=application).update(version=0, score=1)
    app = type(application).objects.select_related("job__level").get(pk=application.pk)
    ensure_fresh([app])
    fit = FitScore.objects.get(application=application)
    assert fit.version == SCORER_VERSION and fit.score != 1


def test_ranked_list_orders_by_score_and_filters(
    client_for, open_job, make_user, upload, docx_bytes, pdf_bytes
):
    from applications.services import apply_to_job
    from seeding.docgen import make_pdf

    strong = apply_to_job(candidate=make_user("candidate"), job=open_job, filename="a.pdf", data=pdf_bytes)
    weak_text = make_pdf(["Someone", "SKILLS", "Excel, Communication"])
    weak = apply_to_job(candidate=make_user("candidate"), job=open_job, filename="b.pdf", data=weak_text)
    client = client_for("recruiter")
    rows = client.get(f"/api/jobs/{open_job.id}/applications").data["results"]
    assert [r["id"] for r in rows] == [str(strong.id), str(weak.id)]
    assert rows[0]["fit"]["score"] >= rows[1]["fit"]["score"]
    assert rows[0]["fit"]["explanation"]["chips"]
    band = rows[1]["fit"]["band"]
    banded = client.get(f"/api/jobs/{open_job.id}/applications?band={band}").data["results"]
    assert str(weak.id) in [r["id"] for r in banded]
    by_skill = client.get(f"/api/jobs/{open_job.id}/applications?skill=Postgres").data["results"]
    assert [r["id"] for r in by_skill] == [str(strong.id)]
    move_application(strong, "screening", strong.job.created_by)
    staged = client.get(f"/api/jobs/{open_job.id}/applications?status=screening").data["results"]
    assert [r["id"] for r in staged] == [str(strong.id)]

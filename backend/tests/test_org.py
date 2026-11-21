import pytest

from org.models import Skill
from org.taxonomy import resolve_skill


@pytest.mark.django_db
def test_taxonomy_is_seeded_with_tech_and_non_tech_skills():
    assert Skill.objects.count() >= 150
    assert Skill.objects.filter(kind="tech").count() >= 75
    assert Skill.objects.filter(kind="non_tech").count() >= 50


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term,name",
    [
        ("JS", "JavaScript"),
        ("js", "JavaScript"),
        ("javascript", "JavaScript"),
        ("k8s", "Kubernetes"),
        ("ReactJS", "React"),
        ("golang", "Go"),
        ("C#", "C#"),
        ("cpp", "C++"),
        ("Postgres", "PostgreSQL"),
        ("L&D", "Learning and Development"),
        ("postgresql", "PostgreSQL"),
    ],
)
def test_synonyms_resolve_to_canonical_skills(term, name):
    assert resolve_skill(term).name == name


@pytest.mark.django_db
def test_unknown_skill_resolves_to_none():
    assert resolve_skill("underwater basket weaving") is None
    assert resolve_skill("") is None


def test_public_skill_search(client_for):
    names = {s["name"] for s in client_for("anonymous").get("/api/skills?q=java").data}
    assert {"Java", "JavaScript"} <= names


def test_hr_admin_manages_departments(client_for, open_job):
    client = client_for("hr_admin")
    created = client.post("/api/departments", {"name": "Research & Development"}, format="json")
    assert created.status_code == 201 and created.data["slug"] == "research-development"
    dup = client.post("/api/departments", {"name": "research & development"}, format="json")
    assert dup.status_code == 400
    used = open_job.department
    assert client.delete(f"/api/departments/{used.id}").status_code == 409
    assert client.delete(f"/api/departments/{created.data['id']}").status_code == 204


def test_hr_admin_adds_skill_with_synonyms(client_for):
    resp = client_for("hr_admin").post(
        "/api/skills",
        {"name": "Elixir", "kind": "tech", "category": "Programming languages", "synonyms": ["ex"]},
        format="json",
    )
    assert resp.status_code == 201
    assert resolve_skill("EX").name == "Elixir"

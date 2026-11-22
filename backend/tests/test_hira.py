import pytest
from rest_framework.test import APIClient

from applications.models import ApplicationNote
from applications.services import add_note, apply_to_job, move_application
from hira.services import answer, build_context


def ask(client, message):
    resp = client.post("/api/hira/ask", {"message": message}, format="json")
    assert resp.status_code == 200, resp.data
    return resp.data


@pytest.fixture
def other_app(make_user, open_job, pdf_bytes):
    stranger = make_user("candidate", name="Zara Stranger")
    app = apply_to_job(candidate=stranger, job=open_job, filename="z.pdf", data=pdf_bytes)
    move_application(app, "screening", open_job.created_by)
    add_note(app, open_job.hiring_manager, body="Internal: very strong", vote="up")
    return app


def test_status_shows_only_own_applications_in_safe_words(client_for, application, other_app):
    data = ask(client_for("candidate"), "what is my application status")
    assert data["intent"] == "application_status"
    assert [a["id"] for a in data["applications"]] == [str(application.id)]
    assert data["applications"][0]["status_label"] == "Received"
    blob = str(data)
    for leak in ("Zara", str(other_app.id), "Internal", "very strong", "score", "Candidate #"):
        assert leak not in blob


def test_logged_out_visitors_get_search_and_faqs_only(db, application):
    client = APIClient()
    for question in ("what is my application status", "jobs that match my skills", "talk to a recruiter"):
        data = ask(client, question)
        assert data["needs_sign_in"] is True and data["applications"] == [] and data["action"] is None
    jobs = ask(client, "find python jobs in hyderabad")
    assert jobs["intent"] == "job_search" and jobs["jobs"][0]["slug"] == application.job.slug
    faq = ask(client, "what is the interview process")
    assert faq["intent"] == "faq" and "skills conversation" in faq["answer"]
    assert "What is my application status?" not in faq["chips"]


def test_job_search_with_filters_and_typos(client_for, open_job, make_job, org):
    make_job(
        title="Remote Kubernetes Engineer",
        location=org["location2"],
        work_mode="remote",
        required=("kubernetes",),
        nice=(),
    )
    client = client_for("candidate")
    react = ask(client, "find jobs for kubernets")  # typo corrected
    assert react["intent"] == "job_search" and [j["title"] for j in react["jobs"]] == [
        "Remote Kubernetes Engineer"
    ]
    hyd = ask(client, "hyd mein python naukri")  # Hinglish
    assert hyd["intent"] == "job_search" and [j["slug"] for j in hyd["jobs"]] == [open_job.slug]
    none = ask(client, "find golang jobs in chennai")
    assert none["jobs"] == []


def test_jobs_that_match_my_skills_use_the_parsed_profile(client_for, application, make_job):
    match = make_job(title="Python Platform Role", required=("python", "postgresql"), nice=())
    make_job(title="Frontend Only", required=("react",), nice=())
    data = ask(client_for("candidate"), "jobs that match my skills")
    titles = [j["title"] for j in data["jobs"]]
    assert data["intent"] == "matching_jobs" and titles[0] == match.title and "Frontend Only" not in titles
    assert application.job.title not in titles  # already applied


@pytest.mark.parametrize(
    "question,intent",
    [
        ("how does matching work", "how_matching_works"),
        ("is the screening fair", "is_screening_fair"),
        ("how do i withdraw", "how_withdraw"),
        ("hello", "greeting"),
        ("what is the salary", "faq"),
        ("asdkjh qwe", "fallback"),
    ],
)
def test_each_intent_answers(client_for, application, question, intent):
    data = ask(client_for("candidate"), question)
    assert data["intent"] == intent and data["answer"]


def test_fairness_answer_is_plain_and_does_not_reveal_redaction_rules(client_for, application):
    data = ask(client_for("candidate"), "is the screening fair")
    assert "candidate number" in data["answer"]
    for internal in ("regex", "[hidden]", "IIT", "pattern", "University|"):
        assert internal not in data["answer"]


def test_talk_to_recruiter_flow(client_for, application, users):
    client = client_for("candidate")
    data = ask(client, "recruiter se baat karni hai")
    assert data["intent"] == "talk_to_recruiter" and data["action"] == {"type": "message_recruiter"}
    assert [a["id"] for a in data["applications"]] == [str(application.id)]
    sent = client.post(
        "/api/hira/message", {"application": str(application.id), "message": "Can we talk?"}, format="json"
    )
    assert sent.status_code == 201
    assert ApplicationNote.objects.get(application=application).body == "Can we talk?"


def test_cannot_message_about_someone_elses_application(client_for, other_app):
    resp = client_for("candidate").post(
        "/api/hira/message", {"application": str(other_app.id), "message": "hi"}, format="json"
    )
    assert resp.status_code == 404
    assert (
        client_for("candidate")
        .post("/api/hira/message", {"application": str(other_app.id)}, format="json")
        .status_code
        == 404
    )


def test_staff_get_no_personal_answers(client_for, application):
    data = ask(client_for("recruiter"), "what is my application status")
    assert data["applications"] == [] and "candidate accounts" in data["answer"]


def test_validation(client_for, db):
    client = client_for("anonymous")
    assert client.post("/api/hira/ask", {"message": ""}, format="json").status_code == 400
    assert client.post("/api/hira/ask", {"message": "x" * 501}, format="json").status_code == 400


def test_engine_measured_accuracy_does_not_regress(db):
    from hira.management.commands.evaluate_hira import run

    assert run("tune")["correct"] >= 40  # 44/44 measured
    assert run("holdout")["correct"] >= 33  # 35/44 measured


def test_matching_eval_does_not_regress(db):
    from matching.management.commands.evaluate_matching import run

    assert run("tune")["correct"] >= 17  # 18/20 measured
    assert run("holdout")["correct"] >= 15  # 16/20 measured


def test_answer_function_without_http(db, application, users):
    data = answer("my status", users["candidate"], build_context())
    assert data["applications"][0]["title"] == application.job.title

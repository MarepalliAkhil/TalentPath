"""python manage.py seed [--reset]

Creates clearly fictional demo data: organisation basics, staff for every role,
25 open jobs (+1 draft, +1 closed), 60 synthetic candidates with generated
PDF/DOCX resumes, and applications in various statuses. Safe to run twice.
"""

import os
import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Profile, Role, User
from accounts.services import set_phone
from applications.models import Application
from applications.models import ApplicationStatus as S
from applications.services import apply_to_job, move_application, withdraw_application
from core.brand import get_brand
from files.models import StoredFile
from jobs.models import Job, JobStatus
from jobs.services import unique_job_slug
from notifications.models import EmailOutbox, Notification
from org.models import Department, JobLevel, Location, Skill
from org.taxonomy_data import SKILLS, skill_slug
from seeding import demo_data as D
from seeding.docgen import make_docx, make_pdf

DEFAULT_DEMO_PASSWORD = "Demo@Pass2026"
PATHS = {
    S.APPLIED: [],
    S.SCREENING: [S.SCREENING],
    S.INTERVIEW: [S.SCREENING, S.INTERVIEW],
    S.OFFER: [S.SCREENING, S.INTERVIEW, S.OFFER],
    S.REJECTED: [S.SCREENING, S.REJECTED],
}


class Command(BaseCommand):
    help = "Seed fictional demo data (idempotent). Use --reset to wipe demo data first."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete demo data first.")

    def handle(self, *args, **options):
        self.rng = random.Random(2026)
        self.password_hash = make_password(os.environ.get("DEMO_PASSWORD") or DEFAULT_DEMO_PASSWORD)
        if options["reset"]:
            self.reset()
        with transaction.atomic():
            self.seed_org()
            staff = self.seed_staff()
            jobs = self.seed_jobs(staff)
        created = self.seed_candidates(jobs)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {Job.objects.open().count()} open jobs, "
                f"{User.objects.filter(role=Role.CANDIDATE).count()} candidates, "
                f"{Application.objects.count()} applications ({created} new)."
            )
        )

    # ------------------------------------------------------------------ reset
    def reset(self):
        """Remove only demo data: *.example users, their jobs and related records."""
        demo_users = User.objects.filter(email__endswith=".example")
        demo_jobs = Job.objects.filter(created_by__in=demo_users)
        Application.objects.filter(Q(job__in=demo_jobs) | Q(candidate__in=demo_users)).delete()
        demo_jobs.delete()
        StoredFile.objects.filter(owner__in=demo_users).delete()
        Notification.objects.filter(user__in=demo_users).delete()
        EmailOutbox.objects.filter(to_email__endswith=".example").delete()
        demo_users.delete()
        self.stdout.write("Demo data removed.")

    # -------------------------------------------------------------------- org
    def seed_org(self):
        for name, kind, category, synonyms in SKILLS:
            Skill.objects.get_or_create(
                slug=skill_slug(name),
                defaults={"name": name, "kind": kind, "category": category, "synonyms": synonyms},
            )
        for name in D.DEPARTMENTS:
            if not Department.objects.filter(name=name).exists():
                Department.objects.create(name=name)
        for name, country in D.LOCATIONS:
            if not Location.objects.filter(name=name).exists():
                Location.objects.create(name=name, country=country)
        for name, rank in D.LEVELS:
            JobLevel.objects.get_or_create(name=name, defaults={"rank": rank})

    # ------------------------------------------------------------------ users
    def _user(self, email, full_name, role):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create(
                email=email, full_name=full_name, role=role, password=self.password_hash
            )
        Profile.objects.get_or_create(user=user)
        return user

    def seed_staff(self):
        staff = {}
        for key, local, name, role in D.STAFF:
            user = self._user(f"{local}@{D.DEMO_DOMAIN}", name, role)
            profile = user.profile
            if not profile.headline:
                profile.headline = f"{user.get_role_display()} at {get_brand()['employerName']}"
                profile.location_text = "Hyderabad"
                profile.save()
            staff[key] = user
        return staff

    # ------------------------------------------------------------------- jobs
    def _description(self, summary, dept, required, nice, employer):
        duties = "\n".join(f"- {d}" for d in D.DEPARTMENT_DUTIES[dept])
        return (
            f"About the role\n{summary} You will join the {dept} team at {employer}.\n\n"
            f"What you will do\n{duties}\n\n"
            f"What you will bring\n- Practical experience with {', '.join(required)}.\n"
            f"- Nice to have: {', '.join(nice) if nice else 'curiosity and a growth mindset'}.\n"
            "- Clear written communication and care for the people who use our work.\n\n"
            "How we hire\nApplication review, a skills conversation, a short practical exercise "
            "and a team conversation. We assess skills, not pedigree: your college, age, gender "
            "or photo are never used to rank you.\n\n"
            "This is a fictional job posted for demonstration purposes."
        )

    def _create_job(self, spec, owner, manager, status, days_ago):
        title, dept, loc, mode, level, required, nice, openings, summary = spec[:9]
        location = Location.objects.get(name=loc)
        existing = Job.objects.filter(title=title, location=location).first()
        if existing:
            return existing
        employer = get_brand()["employerName"]
        job = Job.objects.create(
            slug=unique_job_slug(title, location.name),
            title=title,
            department=Department.objects.get(name=dept),
            location=location,
            level=JobLevel.objects.get(name=level),
            work_mode=mode,
            employment_type="internship" if level == "Intern" else "full_time",
            description=self._description(summary, dept, required, nice, employer),
            openings=openings,
            status=status,
            created_by=owner,
            hiring_manager=manager,
        )
        job.required_skills.set(Skill.objects.filter(name__in=required))
        job.nice_to_have_skills.set(Skill.objects.filter(name__in=nice))
        if status != JobStatus.DRAFT:
            published = timezone.now() - timedelta(days=days_ago, hours=self.rng.randint(0, 20))
            Job.objects.filter(pk=job.pk).update(
                published_at=published,
                closed_at=timezone.now() if status == JobStatus.CLOSED else None,
            )
            job.refresh_from_db()
        return job

    def seed_jobs(self, staff):
        recruiters = [staff["recruiter"], staff["recruiter2"], staff["recruiter3"]]
        jobs = []
        for i, spec in enumerate(D.JOBS):
            manager = staff[D.DEPARTMENT_MANAGER[spec[1]]]
            jobs.append(self._create_job(spec, recruiters[i % 3], manager, JobStatus.OPEN, i + 1))
        for spec in D.EXTRA_JOBS:
            manager = staff[D.DEPARTMENT_MANAGER[spec[1]]]
            self._create_job(spec, staff["recruiter"], manager, spec[9], 40)
        return jobs

    # ------------------------------------------------------------- candidates
    def _resume_lines(self, name, email, phone, city, track, skills):
        headline = D.TRACKS[track][0]
        years = self.rng.randint(0, 9) if track != "intern" else 0
        companies = self.rng.sample(D.COMPANIES, 2)
        lines = [
            name,
            f"{headline} | {city}",
            f"Email: {email} | Phone: {phone}",
            "",
            "SUMMARY",
            f"{headline} with {years or 'less than one'} year(s) of hands-on experience. "
            f"Enjoys solving real problems with {skills[0]} and {skills[1]}.",
            "",
            "SKILLS",
            ", ".join(skills),
            "",
            "EXPERIENCE",
        ]
        if track == "intern":
            lines += [
                "Student Developer - Campus Coding Club (2024-present)",
                f"- Built a timetable app using {skills[0]} and {skills[1]}.",
                "- Ran weekly peer-learning sessions for 40 students.",
            ]
        else:
            lines += [
                f"{headline} - {companies[0]} ({2026 - max(years, 1)}-present)",
                f"- Delivered features using {skills[0]}, {skills[1]} and {skills[2]}.",
                "- Reduced turnaround time for a key workflow by about 30 percent.",
                f"Junior {headline} - {companies[1]} ({2026 - years - 2}-{2026 - max(years, 1)})",
                f"- Supported the team with {skills[-1]} and documentation.",
            ]
        lines += [
            "",
            "EDUCATION",
            "Bachelor's degree - details withheld in this synthetic profile",
            "",
            "Synthetic resume generated for a demo. This person does not exist.",
        ]
        return lines

    def seed_candidates(self, jobs):
        tracks = list(D.TRACKS)
        combos = [(f, last) for f in D.FIRST_NAMES for last in D.LAST_NAMES]
        random.Random(7).shuffle(combos)
        created = 0
        for n in range(60):
            # One RNG per candidate keeps re-runs deterministic and idempotent.
            self.rng = rng = random.Random(1000 + n)
            first, last = combos[n]
            track = "backend" if n == 0 else tracks[n % len(tracks)]
            if n == 0:
                email = f"candidate@{D.DEMO_DOMAIN}"
            else:
                email = f"{first.lower()}.{last.lower()}{n}@{D.CANDIDATE_DOMAIN}"
            city = rng.choice(D.CITIES)
            user = self._user(email, f"{first} {last}", Role.CANDIDATE)
            if user.applications.exists():
                continue
            pool = D.TRACKS[track][1]
            skills = rng.sample(pool, k=min(len(pool), rng.randint(5, 8)))
            phone = f"+91 55501 {n:05d}"
            profile = user.profile
            profile.headline = D.TRACKS[track][0]
            profile.location_text = city
            profile.address = f"{n + 1} Sample Street, Demo Nagar, {city}"
            set_phone(profile, phone)
            profile.save()
            lines = self._resume_lines(user.full_name, email, phone, city, track, skills)
            as_pdf = n % 2 == 0
            data = make_pdf(lines) if as_pdf else make_docx(lines)
            filename = f"{first}_{last}_resume.{'pdf' if as_pdf else 'docx'}"
            targets = D.TRACKS[track][2]
            if n == 0:
                picks = [(0, S.INTERVIEW), (2, S.SCREENING), (3, S.APPLIED)]
            else:
                chosen = rng.sample(targets, k=min(len(targets), rng.randint(1, 3)))
                picks = [(j, self._random_status()) for j in chosen]
            for job_index, target in picks:
                job = jobs[job_index]
                loud = n == 0  # the demo candidate gets real notifications
                application = apply_to_job(
                    candidate=user,
                    job=job,
                    filename=filename,
                    data=data,
                    silent=not loud,
                    cover_note="I would love to contribute to this team." if rng.random() < 0.5 else "",
                )
                created += 1
                self._advance(application, target, job.created_by, silent=not loud)
        return created

    def _random_status(self):
        roll = self.rng.random()
        if roll < 0.45:
            return S.APPLIED
        if roll < 0.70:
            return S.SCREENING
        if roll < 0.82:
            return S.INTERVIEW
        if roll < 0.87:
            return S.OFFER
        if roll < 0.96:
            return S.REJECTED
        return S.WITHDRAWN

    def _advance(self, application, target, actor, silent):
        if target == S.WITHDRAWN:
            withdraw_application(application, application.candidate)
            return
        for step in PATHS[target]:
            move_application(application, step, actor, silent=silent)

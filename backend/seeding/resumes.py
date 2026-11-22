"""Synthetic resume text. Used by the seed command and by the fairness tests."""

from seeding import demo_data as D


def resume_lines(rng, *, name, email, phone, city, track, skills, college, pronoun, with_projects=True):
    headline = D.TRACKS[track][0]
    years = rng.randint(0, 9) if track != "intern" else 0
    companies = rng.sample(D.COMPANIES, 2)
    subject = {"she": "She", "he": "He", "they": "They"}[pronoun]
    verb = "enjoy" if pronoun == "they" else "enjoys"
    lines = [
        name,
        f"{headline} | {city}",
        f"Email: {email} | Phone: {phone}",
        "",
        "SUMMARY",
        f"{headline} with {years or 'less than one'} year(s) of hands-on experience. "
        f"{subject} {verb} solving real problems with {skills[0]} and {skills[1]}.",
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
    if with_projects and len(skills) >= 4:
        idea = rng.choice(D.PROJECT_IDEAS)
        lines += ["", "PROJECTS", idea.format(a=skills[3], b=skills[1])]
    if rng.random() < 0.5:
        lines += ["", "CERTIFICATIONS", rng.choice(D.CERTIFICATIONS).format(a=skills[-1])]
    lines += [
        "",
        "EDUCATION",
        f"Bachelor's degree, {college}, {2026 - years - 6}-{2026 - years - 2}",
        "",
        "Synthetic resume generated for a demo. This person does not exist.",
    ]
    return lines

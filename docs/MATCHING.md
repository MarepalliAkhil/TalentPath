# Matching: how the fit score works

The fit score helps recruiters read a pile of applications faster. It is
deterministic (same input, same output), explainable (every score comes with
its reasons) and versioned. It never decides anything: people move candidates.

Code: `backend/matching/` (`extract.py`, `scoring.py`, `weights.py`, `services.py`).

## 1. Profile extraction (`matching/extract.py`, extractor v1)

Standard library only. Runs on the resume text already extracted on upload.

| Step | What it does |
| --- | --- |
| Sections | A short line that matches a known heading starts a section: skills, experience (including "Internships"), projects, education, certifications, summary. Lines before the first heading are "other". |
| Skills | Text is split into tokens (case and punctuation insensitive: `React.js` = `reactjs` = `ReactJS`), then matched longest-first against every skill name and synonym in the taxonomy (1 to 4 word n-grams). `JS` → JavaScript, `k8s` → Kubernetes, `Postgres` → PostgreSQL. |
| Ambiguous words | Aliases that are also everyday words or very short (Go, R, C, Ruby, Swift, Spark, Excel, Agile…) only count inside a skills section, so "go to market" or a person named Ruby is not read as a skill. |
| Evidence | Each skill keeps its strongest section (experience > projects > certifications > skills > summary > education) and a short snippet. Snippets are resume text, so they are stored encrypted. |
| Experience | Date ranges in the experience section only: `Jan 2024 - Present`, `03/2021 – 06/2023`, `2023-2025`, `March 2020 to February 2022`. Overlaps are merged. Lines with intern, internship, trainee or apprentice, or under an "Internships" heading, are counted separately as internship months. No ranges found → **unknown**, never guessed. |

Results are stored per application as a `ParsedProfile` with the extractor
version. `python manage.py reparse_profiles` re-parses anything older than the
current version (`--all` re-parses everything).

Job side: the recruiter's required and nice-to-have skills (from the taxonomy)
plus any other taxonomy skill mentioned in the job description, which is added
to the nice-to-have pool.

## 2. The score (`matching/scoring.py`, scorer v1)

All numbers live in `backend/matching/weights.py`.

| Component | Weight | How it is measured |
| --- | ---: | --- |
| Required skills | 50 | share of the job's required skills found anywhere in the resume |
| Nice-to-have skills | 15 | share of nice-to-have and description-mentioned skills found |
| Evidence strength | 20 | average strength of matched skills: experience or projects 1.0, certification 0.75, only listed 0.5 |
| Experience fit | 15 | full-time years ÷ years the level needs (capped at 1). Unknown → 0.5 (neutral). Intern and Associate need 0 years. |

Level → years needed: Intern 0, Associate 0, Mid-level 2, Senior 5, Lead 7, Manager 6.

If a component does not apply (for example the job has no nice-to-have
skills), it is dropped and the remaining weights are scaled back to 100.

| Band | Score |
| --- | --- |
| Strong | 80 and above |
| Good | 60 to 79 |
| Partial | 40 to 59 |
| Low | below 40 |

Every score is stored with its explanation:

- **Reason chips**: "Has Python (projects)", "Has React", "Missing required: SQL", "Nice to have: Docker", "4 yrs experience (needs 2+)", "Experience not stated (neutral)".
- **What would raise this score**: one line per missing required skill.
- **Breakdown**: points per component.

Recompute triggers:

| Trigger | What happens |
| --- | --- |
| Application arrives | parsed and scored straight away |
| Job's skills, description or level change | every application for that job is re-scored |
| Scorer or extractor version changes | stale results are recomputed the next time they are read; `python manage.py rescore` or `reparse_profiles` does it all at once |

## 3. What the scorer is not allowed to see

The scorer receives a `ScoringInput` with exactly two fields: `skills`
(skill slug and section) and `experience_years`. That object is built in one
place (`matching.services.scoring_input`) from the parsed profile. Name, email,
phone, photo, gender, age or date of birth, address, location or city, college
or university, and any free text never reach it.

This is enforced by tests in `backend/tests/test_fairness.py`, which run in CI:

- the scoring module may import only `dataclasses` and its own `weights`;
- its code (outside docstrings) may not mention any protected word: name, email, phone, photo, gender, age, birth, address, city, location, college, university, religion, caste, candidate, user, profile, resume text and more (the only allowed hit is a skill's display name);
- `ScoringInput` must have exactly the two allowed fields, and the gate function may only read them.

## 4. Counterfactual fairness test

**Method.** Take a resume and make copies that change only:

- the person's name (in every place it appears);
- gendered words and pronouns (he/she/they, his/her/their, Mr/Ms/Mx, male/female);
- the college or university;
- the city.

Run every copy through the real extractor and scorer, and require the score,
band and full explanation to be identical to the original.

| Where | Scope | Result (measured 2026-11-21) |
| --- | --- | --- |
| CI (`test_counterfactual_scores_identical_for_every_variant`) | 24 synthetic resumes × 25 demo jobs × 5 variants | 3,000 variants, 0 changes |
| hr_admin "Fairness check" page | first 40 current applications × 3 variants | 120 variants, 0 changes (seeded demo data) |
| Same check over the whole demo data set (`?limit=200`) | 200 applications × 3 variants | 600 variants, 0 changes |

Variants exist in memory only. No real demographic data is stored or used.

**Limits, stated honestly.**

- It proves the scorer ignores these details. It does **not** prove that a job's requirements are fair: a requirement can itself exclude people.
- It covers the kinds of change listed above. It does not cover, for example, gaps in employment, writing style, or names of past employers.
- Skills people list depend on access and opportunity; matching on skills does not remove that.
- The evaluation set is small and synthetic (below), written by the developer.

## 5. Evaluation

`backend/matching/eval_data.py` holds 40 hand-labelled synthetic job and
resume pairs across 8 job types. Each label was written by judgement before
running the scorer. Half are for tuning, half are held out and only measured.

Run it: `python manage.py evaluate_matching --verbose`

Measured on 2026-11-21 with scorer v1 (weights unchanged after the tuning run):

| Split | In the expected band |
| --- | --- |
| Tune (20) | **18 / 20 (90%)** |
| Holdout (20) | **16 / 20 (80%)** |

Holdout confusion (rows = expected, columns = scorer):

| expected \ got | strong | good | partial | low |
| --- | ---: | ---: | ---: | ---: |
| strong | 5 | 0 | 0 | 0 |
| good | 2 | 4 | 0 | 0 |
| partial | 0 | 0 | 2 | 2 |
| low | 0 | 0 | 0 | 5 |

All misses are one band away. On the holdout the scorer is a little generous
at the top (two "Good" resumes scored Strong, both had every required skill but
thinner evidence) and a little harsh in the middle (two "Partial" resumes
scored Low, both had adjacent skills the taxonomy does not count as the
required one, for example Inside Sales for B2B Sales). These were not tuned
away, because tuning on the holdout would make the number meaningless.

CI guards against regressions: `test_matching_eval_does_not_regress` fails if
tune drops below 17/20 or holdout below 15/20.

# Ask HIRA (candidate assistant)

"Ask HIRA" is the chat widget on the career site and the candidate dashboard.
It is rule-based and deterministic: no LLM. The assistant name and subtitle
("HIRA · Hiring Intelligence & Recruiting Assistant") come from
`shared/brand.json`.

Code: `backend/hira/` (`engine.py`, `services.py`, `knowledge.py`).
API: `POST /api/hira/ask` (anyone) and `POST /api/hira/message` (candidates).

## How a question is understood

1. **Normalise**: lowercase, then map common Hinglish and chat words written in English letters to English (`mera` → my, `kya` → what, `naukri` → jobs, `wapas` → withdraw, `baat` → talk, `hyd` → Hyderabad, `blr`/`bangalore` → Bengaluru, `wfh` → remote…).
2. **Spell-correct** each unknown word of 4+ letters against a vocabulary built from the skill taxonomy, locations, intent keywords and knowledge entries (`kubernets` → kubernetes, `aplication` → application).
3. **Intent scoring**: weighted keywords and short phrases per intent. A skill, city or work mode in the question adds weight to job search.
4. **Knowledge retrieval**: if no intent is clear, BM25 ranks the knowledge entries (question and keywords weighted twice, plus the answer). Too weak a match gives a polite fallback with suggestions.

## What it answers

| Intent | Signed-in candidate | Logged-out visitor |
| --- | --- | --- |
| Application status | Their own applications only, in customer-safe words: Received, Under review, Interview stage, Offer stage, Not progressing, Withdrawn | Asked to sign in |
| Find jobs ("React jobs in Hyderabad") | Job cards filtered by skill, city and work mode | Same |
| Jobs that match my skills | Open jobs ranked by overlap with skills from their latest parsed resume, excluding jobs already applied to | Asked to sign in |
| How matching works / is the screening fair | Plain explanation (skills and experience only; blind screening until interview; regular counterfactual testing) | Same |
| How to withdraw | Steps, plus their withdrawable applications | Steps |
| Talk to a recruiter | Choose an active application and write a message; it is saved as a note the recruiter sees, and the recruiter gets a bell notification (without the message text) | Asked to sign in |
| Company and process FAQs | 17 knowledge entries (interview process, timeline, resume format, privacy, remote work, internships, salary, offers, accessibility…) | Same |

Never revealed: other candidates, anyone's score (including the candidate's
own), internal notes, rejection reasons, or how redaction works internally.
Staff who open the widget get no personal answers. Nothing typed into the chat
is stored, except a message the candidate explicitly sends to a recruiter.

Accessibility: a labelled launcher button, a dialog with a live conversation
log, suggestion chips as real buttons, Escape to close (focus returns to the
launcher), a bottom sheet on small screens, and no motion when the user prefers
reduced motion.

## Evaluation

`backend/hira/eval_data.py` holds 88 candidate questions written before
measuring, including typos and Hinglish, split 44 tuning / 44 holdout. A FAQ
question only counts as correct if the right knowledge entry is chosen.

Run it: `python manage.py evaluate_hira --verbose` (after `seed` or `migrate`, which loads the knowledge entries).

Measured on 2026-11-21:

| Split | Intent accuracy |
| --- | --- |
| Tune (44), first run | 41 / 44 (93%) |
| Tune (44), after fixing the three tuning misses | **44 / 44 (100%)** |
| Holdout (44), measured once after tuning | **35 / 44 (80%)** |

The tuning changes were: "thanks" weighted as a greeting, "cancel my" added as
a withdraw phrase, and the word "many" removed from the "apply to more than one
job" entry's keywords (it pulled "how many rounds" to the wrong answer).

Holdout misses (not tuned away):

| Question | Expected | Got |
| --- | --- | --- |
| have i been selected? | application status | fallback |
| sales positions | job search | fallback |
| are you hiring designers | job search | FAQ: interview process |
| show jobs matching my resume | jobs that match my skills | job search |
| do you look at my college or caste | is the screening fair | FAQ: is the screening fair (same answer text) |
| i want to take back my application | how to withdraw | application status |
| can someone call me | talk to a recruiter | fallback |
| when will i hear back | FAQ: hiring timeline | application status |
| what package do you offer | FAQ: salary | FAQ: offer process |

Patterns: role nouns that are not skills in the taxonomy ("sales positions",
"designers") are not recognised as a search; "take back" and "hear back" lose
to the word "application". CI guards against regressions
(`test_engine_measured_accuracy_does_not_regress`: tune ≥ 40, holdout ≥ 33).

An optional LLM layer could rephrase answers later. It stays off by default
and would never see other candidates' data.

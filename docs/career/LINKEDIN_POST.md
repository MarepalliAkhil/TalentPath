# LinkedIn post

Paste as is, then add the two links. It tags no one and names no company. Post it with a 30-60 second screen recording of the demo (see DEMO_SCRIPT.md), not a screenshot.

---

I spent four weeks building TalentPath, a hire-to-onboard HR platform, on my own.

One person's journey runs through the whole thing: a candidate applies with a resume, the recruiter sees an explainable fit score, an assistant books the interviews, the offer goes through two approvals, one click turns the candidate into an employee, and the same login then applies for leave.

A few things I'm proud of:

🔹 Explainable matching with no language model: every score shows its reasons and what would raise it. 16 of 20 correct on a held-out set I never tuned on.
🔹 A fairness check that changes only names, gendered words, colleges and cities: 120 variants, 0 score changes.
🔹 Interview scheduling where the database itself refuses double bookings.
🔹 One deny-by-default permission file shared by the API and the UI, with a test that calls every endpoint as every role.
🔹 1,374 backend tests, plus unit and end-to-end tests in CI.
🔹 Deployed entirely on free tiers, and designed so a missed scheduled job never changes what a user sees.

What I learned: measure instead of claiming, and write decisions down as you go. The repo has 78 of them.

All the data is synthetic. Try it with the "Try as" buttons:

Live demo: <vercel link>
Code and docs: https://github.com/MarepalliAkhil/TalentPath

I'm a final-year-track B.Tech CSE student at KL University looking for software and infrastructure roles. Feedback is very welcome.

#SoftwareEngineering #Django #React #HRTech #FullStack #OpenToWork

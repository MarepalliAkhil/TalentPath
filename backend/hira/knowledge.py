"""Ask HIRA knowledge entries (company and process FAQs). Plain data.

Answers never describe redaction internals, other candidates or scores of others.
"""

ENTRIES = [
    {
        "key": "how-matching-works",
        "question": "How does matching work?",
        "keywords": "matching score fit rank ranking algorithm ai explain match work",
        "answer": (
            "We read the skills on your resume and compare them with the skills the job asks for. "
            "Skills you used in work experience or projects count a little more than skills only listed. "
            "Years of experience are compared with the job level. Every score comes with plain reasons, "
            "and recruiters always make the decision, not the score."
        ),
        "link": "",
    },
    {
        "key": "is-screening-fair",
        "question": "Is the screening fair?",
        "keywords": "fair fairness bias biased discrimination blind anonymous gender caste religion college age name photo",
        "answer": (
            "Matching only looks at skills and years of experience. It never uses your name, gender, age, "
            "photo, religion, caste, address, city or college. While screening is blind, recruiters see a "
            "candidate number instead of your name and contact details until the interview stage. "
            "We test this regularly by changing those details on sample resumes and checking that scores "
            "stay exactly the same."
        ),
        "link": "",
    },
    {
        "key": "how-withdraw",
        "question": "How do I withdraw my application?",
        "keywords": "withdraw cancel remove delete take back application stop",
        "answer": (
            "Open My applications, find the role and choose Withdraw. You can withdraw any time before a "
            "final decision. Withdrawing cannot be undone for that job."
        ),
        "link": "/candidate",
    },
    {
        "key": "interview-process",
        "question": "What is the interview process?",
        "keywords": "interview process round rounds steps stages exercise assessment hiring process",
        "answer": (
            "Most roles have four steps: application review, a skills conversation, a short practical "
            "exercise and a team conversation. Your recruiter will tell you what to expect before each step."
        ),
        "link": "",
    },
    {
        "key": "hiring-timeline",
        "question": "How long does the hiring process take?",
        "keywords": "how long time timeline days weeks when hear back response wait",
        "answer": (
            "Most applications are reviewed within 10 working days, and the full process usually takes "
            "three to five weeks. You will see every update under the bell and by email."
        ),
        "link": "",
    },
    {
        "key": "resume-format",
        "question": "What resume format should I upload?",
        "keywords": "resume cv format pdf docx word file size upload photo",
        "answer": (
            "Upload a PDF or DOCX up to 5 MB. A simple layout with clear Skills, Experience, Projects and "
            "Education headings works best. You do not need a photo."
        ),
        "link": "",
    },
    {
        "key": "apply-multiple",
        "question": "Can I apply to more than one job?",
        "keywords": "apply multiple more than one several jobs roles same time",
        "answer": "Yes. You can apply to as many open roles as you like, once per role.",
        "link": "/jobs",
    },
    {
        "key": "reapply",
        "question": "Can I apply again to the same job?",
        "keywords": "reapply apply again same job second time rejected withdrawn",
        "answer": (
            "Each person can apply once per job. If a role was not the right fit, look at other open "
            "roles: new ones are posted every week."
        ),
        "link": "/jobs",
    },
    {
        "key": "update-resume",
        "question": "How do I update my resume?",
        "keywords": "update change edit replace new resume cv upload again",
        "answer": (
            "Your resume is attached to each application when you apply. To use a newer resume, apply to "
            "new roles with the updated file, or send a message to the recruiter of an existing application."
        ),
        "link": "",
    },
    {
        "key": "data-privacy",
        "question": "How is my personal data protected?",
        "keywords": "privacy data personal protected secure security encrypted safe phone address delete account",
        "answer": (
            "Your phone number, address and resume are encrypted when stored. Only the recruiting team for "
            "a job can see your application, and every view of a resume is logged."
        ),
        "link": "",
    },
    {
        "key": "remote-work",
        "question": "Do you offer remote or hybrid jobs?",
        "keywords": "remote hybrid work from home wfh onsite office location flexible",
        "answer": "Yes. Each job shows its work mode: on-site, hybrid or remote. Filter by work mode on the jobs page.",
        "link": "/jobs?work_mode=remote",
    },
    {
        "key": "internships",
        "question": "Do you have internships for students?",
        "keywords": "internship intern student fresher graduate campus college entry level trainee",
        "answer": "Yes. Internships and entry-level roles are listed with the other jobs. Search for Intern.",
        "link": "/jobs?q=intern",
    },
    {
        "key": "salary",
        "question": "What is the salary for a role?",
        "keywords": "salary pay ctc package compensation money stipend lpa",
        "answer": (
            "Pay depends on the role and level. Your recruiter shares the range during the process; feel "
            "free to ask them early."
        ),
        "link": "",
    },
    {
        "key": "account-password",
        "question": "I forgot my password",
        "keywords": "password forgot reset login sign in account locked",
        "answer": "Use Forgot your password on the sign-in page. The reset link works for one hour.",
        "link": "/forgot-password",
    },
    {
        "key": "about-company",
        "question": "What does the company do?",
        "keywords": "company about who are you what do you do business product culture team",
        "answer": (
            "We build software that helps companies hire fairly and look after their people, from the "
            "first job search to the first day at work. (This is a fictional demo company.)"
        ),
        "link": "/",
    },
    {
        "key": "accessibility",
        "question": "I need an adjustment for the interview",
        "keywords": "accessibility adjustment accommodation disability support help interview needs",
        "answer": (
            "Tell your recruiter what would help, for example extra time or a different format. "
            "Adjustments never count against you."
        ),
        "link": "",
    },
    {
        "key": "offer-process",
        "question": "What happens after an offer?",
        "keywords": "offer letter joining onboarding after offer accept start date documents",
        "answer": (
            "Your recruiter sends the offer details. After you accept, onboarding tasks and your start date "
            "appear in your account."
        ),
        "link": "",
    },
]

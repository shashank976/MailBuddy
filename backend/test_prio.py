
from agents.priority_agent import classify_email


PRIORITIES = """
I'm a university student looking for
software engineering internships.

Prioritize:
- Recruiting and interview requests
- Academic deadlines and announcements
- Important personal and security emails

Treat promotional emails and routine
social notifications as low priority.
"""


test_emails = [
    {
        "sender": "recruiter@example.com",
        "subject": "Interview Invitation",
        "body": (
            "We'd like to interview you tomorrow. "
            "Please confirm your availability."
        )
    },
    {
        "sender": "careers@example.com",
        "subject": "Application Update",
        "body": (
            "Thank you for applying. Unfortunately, "
            "we will not be moving forward with "
            "your application at this time."
        )
    },
    {
        "sender": "professor@umd.edu",
        "subject": "Assignment Deadline",
        "body": (
            "Your assignment is due November 12 "
            "at 11:59 PM. Please submit it on ELMS."
        )
    },
    {
        "sender": "offers@store.com",
        "subject": "50% Off This Weekend!",
        "body": (
            "Shop our biggest sale of the year. "
            "Get 50% off selected clothing."
        )
    }
]


for index, email in enumerate(test_emails, start=1):
    print(f"\n--- EMAIL {index} ---")

    result = classify_email(
        sender=email["sender"],
        subject=email["subject"],
        body=email["body"],
        user_priorities=PRIORITIES
    )

    print(result.model_dump_json(indent=2))

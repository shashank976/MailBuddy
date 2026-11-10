from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from email_parser import extract_email_body, clean_email_text

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def authenticate_gmail():
    creds = None

    # Check whether we already have saved login credentials
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    # If credentials are missing or expired
    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            # Refresh an expired access token
            creds.refresh(Request())

        else:
            # First-time Google login
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )

            creds = flow.run_local_server(port=0)

        # Save authorization locally
        TOKEN_FILE.write_text(creds.to_json())
        TOKEN_FILE.chmod(0o600)

    return build("gmail", "v1", credentials=creds)

def get_recent_emails():
    service = authenticate_gmail()

    # Find the timestamp exactly 24 hours ago
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    response = service.users().messages().list(
        userId="me",
        q=f"after:{int(cutoff.timestamp())}",
        maxResults=100
    ).execute()

    messages = response.get("messages", [])
    emails = []

    for message in messages:
        email = service.users().messages().get(
            userId="me",
            id=message["id"],
            format="full"
        ).execute()

        # Ensure message is actually within the last 24 hours
        received_ms = int(email["internalDate"])
        if received_ms < int(cutoff.timestamp() * 1000):
            continue

        headers = email["payload"].get("headers", [])

        def get_header(name):
            return next(
                (
                    h["value"] for h in headers
                    if h["name"].lower() == name.lower()
                ),
                ""
            )

        body = extract_email_body(email.get("payload", {}))
        clean_body = clean_email_text(body)
        emails.append({
            "id": email["id"],
            "thread_id": email["threadId"],
            "sender": get_header("From"),
            "subject": get_header("Subject"),
            "date": get_header("Date"),
            "snippet": email.get("snippet", ""),
            "body": clean_body
        })

    return emails
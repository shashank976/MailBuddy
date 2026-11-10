
from pathlib import Path
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from email_parser import extract_email_body, clean_email_text


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def authenticate_gmail():
    """Authenticate with Gmail using the existing OAuth setup."""

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(TOKEN_FILE),
            SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())
        TOKEN_FILE.chmod(0o600)

    return build(
        "gmail",
        "v1",
        credentials=creds,
    )


def get_header(payload: dict, name: str) -> str:
    """Find a MIME header regardless of capitalization."""

    headers = payload.get("headers", [])

    return next(
        (
            header.get("value", "")
            for header in headers
            if header.get("name", "").lower() == name.lower()
        ),
        "",
    )


def parse_gmail_message(message: dict) -> dict:
    """
    Convert a Gmail API message into MailBuddy's
    standard email dictionary.
    """

    payload = message.get("payload", {})

    raw_body = extract_email_body(payload)
    cleaned_body = clean_email_text(raw_body)

    labels = message.get("labelIds", [])

    return {
        "id": message["id"],
        "thread_id": message["threadId"],
        "received_at_ms": int(message["internalDate"]),

        "sender": get_header(payload, "From"),
        "recipient": get_header(payload, "To"),
        "subject": get_header(payload, "Subject"),
        "date": get_header(payload, "Date"),

        "snippet": message.get("snippet", ""),
        "body": cleaned_body,

        "is_sent": "SENT" in labels,
        "is_unread": "UNREAD" in labels,
        "label_ids": labels,

        "has_list_unsubscribe": bool(
            get_header(payload, "List-Unsubscribe")
        ),
    }


def get_recent_threads(
    hours: int = 24,
    max_threads: int = 20,
    service=None,
) -> list[dict]:
    """
    Discover Gmail conversations with activity
    in the last `hours`, then retrieve their
    complete available message histories.

    Returns one dictionary per conversation,
    containing a list of parsed messages.

    Does not modify Gmail.
    """

    if hours <= 0:
        raise ValueError("hours must be positive")

    if max_threads <= 0:
        raise ValueError("max_threads must be positive")

    if service is None:
        service = authenticate_gmail()

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=hours
    )

    # Search by the recent-activity window.
    # Older messages in matching threads will
    # still be retrieved through threads.get().
    query = f"after:{int(cutoff.timestamp())}"

    discovered = []
    seen_thread_ids = set()

    page_token = None

    while len(discovered) < max_threads:
        remaining = max_threads - len(discovered)

        params = {
            "userId": "me",
            "q": query,
            "maxResults": min(remaining, 100),
        }

        if page_token:
            params["pageToken"] = page_token

        response = (
            service.users()
            .threads()
            .list(**params)
            .execute()
        )

        for item in response.get("threads", []):
            thread_id = item["id"]

            if thread_id not in seen_thread_ids:
                seen_thread_ids.add(thread_id)
                discovered.append(thread_id)

            if len(discovered) >= max_threads:
                break

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    conversations = []

    for thread_id in discovered:
        thread = (
            service.users()
            .threads()
            .get(
                userId="me",
                id=thread_id,
                format="full",
            )
            .execute()
        )

        parsed_messages = []

        for message in thread.get("messages", []):
            parsed_messages.append(
                parse_gmail_message(message)
            )

        if not parsed_messages:
            continue

        # Do not depend on the API response order.
        parsed_messages.sort(
            key=lambda item: item["received_at_ms"]
        )

        # Keep the actual message-level timestamps.
        # Only include threads with activity during
        # our requested time window.
        if parsed_messages[-1]["received_at_ms"] < int(
            cutoff.timestamp() * 1000
        ):
            continue

        conversations.append({
            "thread_id": thread_id,
            "message_count": len(parsed_messages),
            "latest_received_at_ms": (
                parsed_messages[-1]["received_at_ms"]
            ),
            "messages": parsed_messages,
        })

    # Newest conversations first.
    conversations.sort(
        key=lambda thread: thread["latest_received_at_ms"],
        reverse=True,
    )

    return conversations


def get_recent_emails(
    hours: int = 24,
    max_threads: int = 20,
) -> list[dict]:
    """
    Compatibility wrapper for the existing
    /emails endpoint.

    Returns individual recent messages, not
    complete conversations.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=hours
    )

    cutoff_ms = int(cutoff.timestamp() * 1000)

    threads = get_recent_threads(
        hours=hours,
        max_threads=max_threads,
    )

    emails = []

    for thread in threads:
        for message in thread["messages"]:
            if message["received_at_ms"] >= cutoff_ms:
                emails.append(message)

    emails.sort(
        key=lambda item: item["received_at_ms"],
        reverse=True,
    )

    return emails

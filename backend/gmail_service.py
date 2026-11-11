
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
    max_threads: int | None = None,
    service=None,
) -> list[dict]:
    """
    Find Gmail threads with activity in the requested
    time window and retrieve their complete histories.

    max_threads=None means fetch all matching threads.

    This function only reads Gmail. It does not
    delete, archive, or modify messages.
    """

    if hours <= 0:
        raise ValueError("hours must be positive")

    if max_threads is not None and max_threads <= 0:
        raise ValueError(
            "max_threads must be positive or None"
        )

    if service is None:
        service = authenticate_gmail()

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=hours)
    )

    cutoff_ms = int(cutoff.timestamp() * 1000)

    # Unix timestamps provide an exact rolling
    # time window rather than calendar-day boundaries.
    query = f"after:{int(cutoff.timestamp())}"

    discovered = []
    seen_thread_ids = set()

    page_token = None

    # -----------------------------------
    # DISCOVER ALL MATCHING THREADS
    # -----------------------------------

    while True:
        remaining = (
            None
            if max_threads is None
            else max_threads - len(discovered)
        )

        if remaining is not None and remaining <= 0:
            break

        params = {
            "userId": "me",
            "q": query,
            "maxResults": (
                100
                if remaining is None
                else min(remaining, 100)
            ),
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
            thread_id = item.get("id")

            if not thread_id:
                continue

            if thread_id in seen_thread_ids:
                continue

            seen_thread_ids.add(thread_id)
            discovered.append(thread_id)

            if (
                max_threads is not None
                and len(discovered) >= max_threads
            ):
                break

        if (
            max_threads is not None
            and len(discovered) >= max_threads
        ):
            break

        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

        page_token = next_page_token

    # -----------------------------------
    # FETCH COMPLETE THREAD HISTORIES
    # -----------------------------------

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

        parsed_messages.sort(
            key=lambda item: item["received_at_ms"]
        )

        # Keep complete histories, but only include
        # conversations containing recent activity.
        if parsed_messages[-1]["received_at_ms"] < cutoff_ms:
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
    max_threads: int | None = 20,
) -> list[dict]:
    """
    Compatibility wrapper.

    Return individual recent messages, not
    complete conversation histories.
    """

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=hours)
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

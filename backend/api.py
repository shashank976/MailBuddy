
import logging
import threading
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.inbox_loader import load_inbox_messages
from services.dashboard_store import (
    load_dashboard_cards,
    save_dashboard_cards,
)

from workflows.inbox_workflow import analyze_inbox


logger = logging.getLogger("mailbuddy.api")

app = FastAPI(
    title="MailBuddy API",
    description="Local-first AI Gmail assistant",
    version="0.1.0",
)

# React development servers only.
# Do not use "*" for a local API that handles email data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Protect against multiple Analyze Inbox requests.
# This lock is shared by requests in this process.
scan_lock = threading.Lock()


class AnalyzeRequest(BaseModel):
    hours: int = Field(
        default=24,
        ge=1,
        le=168,
    )

    max_threads: int = Field(
        default=5,
        ge=1,
        le=100,
    )

    max_workers: int = Field(
        default=2,
        ge=1,
        le=4,
    )

    user_priorities: str = Field(
        default=(
            "Prioritize emails requiring a reply, "
            "important deadlines, security alerts, "
            "and relevant personal updates. "
            "Treat routine promotions as low priority."
        ),
        max_length=2000,
    )


def check_ollama() -> bool:
    """
    Check the local Ollama HTTP server.

    Does not send email content or make
    any calls to an external service.
    """

    try:
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/tags",
            method="GET",
        )

        with urllib.request.urlopen(
            request,
            timeout=2,
        ) as response:
            return response.status == 200

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ):
        return False


@app.get("/")
def root():
    return {
        "name": "MailBuddy",
        "version": "0.1.0",
        "message": "Local-first email intelligence",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """
    Check backend and Ollama.

    The API can be healthy even if Ollama
    is unavailable, but scans may fail.
    """

    return {
        "backend": "ok",
        "ollama_available": check_ollama(),
        "scan_running": scan_lock.locked(),
    }


@app.get("/conversations")
def get_conversations():
    """
    Return saved dashboard cards.

    Does not fetch Gmail or run inference.
    """

    return load_dashboard_cards()


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    """
    Run Gmail retrieval + analysis and save
    the resulting conversation cards.

    Only one scan may run at a time.
    """

    if not scan_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="An inbox analysis is already running.",
        )

    try:
        # 1. Fetch complete Gmail conversations.
        emails = load_inbox_messages(
            hours=request.hours,
            max_threads=request.max_threads,
        )

        # 2. Analyze messages using SQLite cache
        #    and bounded concurrent Ollama workers.
        cards = analyze_inbox(
            emails=emails,
            user_priorities=request.user_priorities,
            max_workers=request.max_workers,
        )

        # 3. Persist successful dashboard results.
        analyzed_at = save_dashboard_cards(cards)

        return {
            "status": "completed",
            "last_analyzed_at": analyzed_at,
            "messages_processed": len(emails),
            "conversation_count": len(cards),
            "cards": cards,
        }

    except Exception as error:
        # Do not log email contents or credentials.
        logger.error(
            "Inbox analysis failed: %s",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Inbox analysis failed. "
                "Check the local backend logs."
            ),
        ) from None

    finally:
        scan_lock.release()

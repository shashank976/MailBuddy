
import logging
import threading
import time
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.inbox_loader import load_inbox_messages
from services.inbox_batcher import create_thread_batches
from services.dashboard_store import (
    load_dashboard_cards,
    save_dashboard_cards,
)
from services.reset_service import reset_mailbuddy_data
from services.feedback_service import (
    save_feedback,
    get_feedback,
    get_learned_preferences,
    apply_feedback,
)
from workflows.inbox_workflow import analyze_inbox


# -----------------------------------
# LOGGING
# -----------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger("mailbuddy.api")


# -----------------------------------
# INTERNAL SCAN CONFIGURATION
# -----------------------------------

# These are implementation settings, not
# preferences the user needs to configure.

SCAN_HOURS = 24
BATCH_SIZE = 5
MAX_WORKERS = 2


# -----------------------------------
# FASTAPI
# -----------------------------------

app = FastAPI(
    title="MailBuddy API",
    description="Local-first AI Gmail assistant",
    version="0.2.0",
)

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


# -----------------------------------
# LOCKS AND SCAN PROGRESS
# -----------------------------------

scan_lock = threading.Lock()
progress_lock = threading.Lock()

scan_progress = {
    "status": "idle",
    "stage": "idle",
    "total_batches": 0,
    "completed_batches": 0,
    "total_conversations": 0,
    "processed_conversations": 0,
    "messages_processed": 0,
    "elapsed_seconds": 0.0,
}


def update_progress(**changes):
    with progress_lock:
        scan_progress.update(changes)


def get_progress_snapshot():
    with progress_lock:
        return dict(scan_progress)


# -----------------------------------
# REQUEST SCHEMAS
# -----------------------------------

class AnalyzeRequest(BaseModel):
    """
    The frontend sends personalized context.

    Legacy scan settings are accepted for
    compatibility but deliberately ignored.
    The backend controls scan performance.
    """

    user_priorities: str = Field(
        default="",
        max_length=6000,
    )

    hours: int | None = Field(
        default=None,
        ge=1,
        le=168,
    )

    max_threads: int | None = Field(
        default=None,
        ge=1,
    )

    max_workers: int | None = Field(
        default=None,
        ge=1,
        le=4,
    )

    batch_size: int | None = Field(
        default=None,
        ge=1,
        le=20,
    )


class FeedbackRequest(BaseModel):
    thread_id: str = Field(
        min_length=1,
        max_length=255,
    )

    priority: str = Field(
        pattern="^(critical|high|medium|low)$"
    )

    category: str = Field(
        pattern=(
            "^(career|academics|personal|financial|"
            "security|news|promotion|social|other)$"
        )
    )

    note: str = Field(
        default="",
        max_length=500,
    )

    remember_preference: bool = False


# -----------------------------------
# OLLAMA HEALTH
# -----------------------------------

def check_ollama() -> bool:
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


# -----------------------------------
# BASIC ROUTES
# -----------------------------------

@app.get("/")
def root():
    return {
        "name": "MailBuddy",
        "version": "0.2.0",
        "message": "Local-first email intelligence",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "backend": "ok",
        "ollama_available": check_ollama(),
        "scan_running": scan_lock.locked(),
    }


@app.get("/conversations")
def get_conversations():
    dashboard = load_dashboard_cards()

    return {
        **dashboard,
        "cards": apply_feedback(
            dashboard["cards"]
        ),
    }


@app.get("/scan-status")
def get_scan_status():
    return get_progress_snapshot()


# -----------------------------------
# ANALYZE INBOX
# -----------------------------------

@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    if not scan_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="An inbox analysis is already running.",
        )

    start_time = time.perf_counter()

    update_progress(
        status="running",
        stage="fetching",
        total_batches=0,
        completed_batches=0,
        total_conversations=0,
        processed_conversations=0,
        messages_processed=0,
        elapsed_seconds=0.0,
    )

    try:
        # -----------------------------------
        # FETCH ALL RECENT GMAIL CONVERSATIONS
        # -----------------------------------

        logger.info(
            "[1/3] Fetching all Gmail conversations "
            "from the last %d hours...",
            SCAN_HOURS,
        )

        emails = load_inbox_messages(
            hours=SCAN_HOURS,
            max_threads=None,
        )

        logger.info(
            "[1/3] Fetched %d messages",
            len(emails),
        )

        # -----------------------------------
        # CREATE THREAD-SAFE BATCHES
        # -----------------------------------

        batches = create_thread_batches(
            emails=emails,
            batch_size=BATCH_SIZE,
        )

        total_batches = len(batches)

        total_conversations = len({
            email["thread_id"]
            for email in emails
        })

        logger.info(
            "[2/3] Processing %d conversations "
            "in %d batches using %d workers",
            total_conversations,
            total_batches,
            MAX_WORKERS,
        )

        update_progress(
            stage="analyzing",
            total_batches=total_batches,
            total_conversations=total_conversations,
            messages_processed=len(emails),
        )

        # -----------------------------------
        # PREPARE PERSONALIZED CONTEXT
        # -----------------------------------

        # The frontend supplies the profile.
        effective_priorities = request.user_priorities

        # Feedback preferences are explicitly
        # approved by the user and stored locally.
        learned = get_learned_preferences()

        if learned:
            feedback_context = (
                "\n\nADDITIONAL SAVED USER PREFERENCES:\n"
                + "\n".join(
                    f"- {preference}"
                    for preference in learned
                )
            )

            effective_priorities += feedback_context

        # -----------------------------------
        # PROCESS BATCHES
        # -----------------------------------

        all_cards = []
        processed_conversations = 0

        for batch_index, batch in enumerate(
            batches,
            start=1,
        ):
            batch_start = time.perf_counter()

            batch_thread_count = len({
                email["thread_id"]
                for email in batch
            })

            logger.info(
                "[Batch %d/%d] Starting %d "
                "conversations (%d messages)",
                batch_index,
                total_batches,
                batch_thread_count,
                len(batch),
            )

            cards = analyze_inbox(
                emails=batch,
                user_priorities=effective_priorities,
                max_workers=MAX_WORKERS,
            )

            all_cards.extend(cards)

            processed_conversations += (
                batch_thread_count
            )

            # Persist after every successful batch.
            # A failure in a later batch does not
            # erase earlier completed results.
            save_dashboard_cards(all_cards)

            elapsed = time.perf_counter() - start_time

            update_progress(
                completed_batches=batch_index,
                processed_conversations=(
                    processed_conversations
                ),
                elapsed_seconds=round(elapsed, 2),
            )

            logger.info(
                "[Batch %d/%d] Saved %d cards "
                "in %.2fs",
                batch_index,
                total_batches,
                len(cards),
                time.perf_counter() - batch_start,
            )

        # -----------------------------------
        # FINISH SCAN
        # -----------------------------------

        update_progress(stage="saving")

        # Also saves an empty dashboard when
        # no conversations match the time window.
        analyzed_at = save_dashboard_cards(
            all_cards
        )

        total_duration = (
            time.perf_counter() - start_time
        )

        update_progress(
            status="completed",
            stage="completed",
            elapsed_seconds=round(
                total_duration,
                2,
            ),
        )

        logger.info(
            "[3/3] Scan completed: %d conversations "
            "in %.2fs",
            len(all_cards),
            total_duration,
        )

        return {
            "status": "completed",
            "last_analyzed_at": analyzed_at,
            "messages_processed": len(emails),
            "conversation_count": len(all_cards),
            "cards": apply_feedback(all_cards),
        }

    except Exception:
        elapsed = time.perf_counter() - start_time

        update_progress(
            status="failed",
            stage="failed",
            elapsed_seconds=round(elapsed, 2),
        )

        # Local development diagnostic.
        # Production logging should be configured
        # to avoid exposing sensitive email content.
        logger.exception("Inbox scan failed")

        raise HTTPException(
            status_code=500,
            detail=(
                "Inbox scan failed. "
                "Previously completed batches "
                "remain saved locally."
            ),
        ) from None

    finally:
        scan_lock.release()


# -----------------------------------
# RESET
# -----------------------------------

@app.post("/reset")
def reset_mailbuddy():
    """
    Clear local analysis cache and dashboard.

    Preserve Gmail messages, OAuth credentials,
    user feedback, and saved preferences.
    """

    if not scan_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot reset while an inbox "
                "scan is running."
            ),
        )

    try:
        reset_mailbuddy_data()

        update_progress(
            status="idle",
            stage="idle",
            total_batches=0,
            completed_batches=0,
            total_conversations=0,
            processed_conversations=0,
            messages_processed=0,
            elapsed_seconds=0.0,
        )

        logger.info(
            "MailBuddy local cache and dashboard cleared."
        )

        return {
            "status": "reset",
            "message": (
                "Local cache and dashboard cleared."
            ),
        }

    except Exception:
        logger.exception("MailBuddy reset failed")

        raise HTTPException(
            status_code=500,
            detail="Failed to reset local MailBuddy data.",
        ) from None

    finally:
        scan_lock.release()


# -----------------------------------
# FEEDBACK
# -----------------------------------

@app.get("/feedback/{thread_id}")
def read_feedback(thread_id: str):
    return get_feedback(thread_id)


@app.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        return save_feedback(
            thread_id=request.thread_id,
            priority=request.priority,
            category=request.category,
            note=request.note,
            remember_preference=(
                request.remember_preference
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None


import logging
import math
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
from workflows.inbox_workflow import analyze_inbox


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger("mailbuddy.api")

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
        default=1,
        ge=1,
        le=4,
    )

    batch_size: int = Field(
        default=5,
        ge=1,
        le=20,
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


def update_progress(**changes):
    with progress_lock:
        scan_progress.update(changes)


def get_progress_snapshot():
    with progress_lock:
        return dict(scan_progress)


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
    return load_dashboard_cards()


@app.get("/scan-status")
def get_scan_status():
    return get_progress_snapshot()


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
        # FETCH GMAIL
        # -----------------------------------

        logger.info(
            "[1/3] Fetching Gmail conversations..."
        )

        emails = load_inbox_messages(
            hours=request.hours,
            max_threads=request.max_threads,
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
            batch_size=request.batch_size,
        )

        total_batches = len(batches)

        total_conversations = len({
            email["thread_id"]
            for email in emails
        })

        logger.info(
            "[2/3] Processing %d conversations "
            "in %d batches",
            total_conversations,
            total_batches,
        )

        update_progress(
            stage="analyzing",
            total_batches=total_batches,
            total_conversations=total_conversations,
            messages_processed=len(emails),
        )

        all_cards = []
        processed_conversations = 0

        # -----------------------------------
        # SEQUENTIAL BATCH PROCESSING
        # -----------------------------------

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

            # Reuse existing LangGraph workflow,
            # cache, agents, and user preferences.
            cards = analyze_inbox(
                emails=batch,
                user_priorities=request.user_priorities,
                max_workers=request.max_workers,
            )

            # Do not change cards returned
            # by the existing workflow.
            all_cards.extend(cards)

            processed_conversations += (
                batch_thread_count
            )

            # Save after every successful batch.
            # Earlier completed batches survive
            # a failure in a later batch.
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
        # FINISH
        # -----------------------------------

        update_progress(stage="saving")

        # Handle empty inboxes as well.
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
            "cards": all_cards,
        }

    except Exception as error:
        elapsed = time.perf_counter() - start_time

        previous = get_progress_snapshot()

        update_progress(
            status="failed",
            stage="failed",
            elapsed_seconds=round(elapsed, 2),
        )

        # Avoid logging private email content.
        logger.error(
            "Inbox scan failed: %s after %.2fs. "
            "Completed batches: %d/%d",
            type(error).__name__,
            elapsed,
            previous["completed_batches"],
            previous["total_batches"],
        )

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

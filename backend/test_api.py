
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import services.cache_service as cache_service
from api import app, scan_lock


client = TestClient(app)


def main():
    # Use a temporary database so the test does
    # not modify your actual MailBuddy dashboard.
    with tempfile.TemporaryDirectory() as temp_dir:
        temporary_db = Path(temp_dir) / "test_mailbuddy.db"

        with patch.object(
            cache_service,
            "DB_PATH",
            temporary_db,
        ):
            test_endpoints()


def test_endpoints():
    print("\n--- TEST 1: ROOT ---")

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "MailBuddy"

    print("Root endpoint passed.")

    print("\n--- TEST 2: HEALTH ---")

    with patch("api.check_ollama", return_value=True):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["backend"] == "ok"
    assert response.json()["ollama_available"] is True

    print("Health endpoint passed.")

    print("\n--- TEST 3: EMPTY DASHBOARD ---")

    response = client.get("/conversations")

    assert response.status_code == 200
    assert response.json()["cards"] == []
    assert response.json()["last_analyzed_at"] is None

    print("Empty dashboard passed.")

    print("\n--- TEST 4: ANALYZE ---")

    with (
        patch(
            "api.load_inbox_messages",
            return_value=[],
        ) as gmail_mock,
        patch(
            "api.analyze_inbox",
            return_value=[],
        ) as analysis_mock,
    ):
        response = client.post(
            "/analyze",
            json={
                "hours": 24,
                "max_threads": 5,
                "max_workers": 2,
                "user_priorities": "Prioritize interviews.",
            },
        )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "completed"
    assert data["messages_processed"] == 0
    assert data["conversation_count"] == 0

    gmail_mock.assert_called_once()
    analysis_mock.assert_called_once()

    print("Analyze endpoint passed.")

    print("\n--- TEST 5: PERSISTENCE ---")

    response = client.get("/conversations")

    assert response.status_code == 200
    assert response.json()["cards"] == []
    assert response.json()["last_analyzed_at"] is not None

    print("Dashboard persistence passed.")

    print("\n--- TEST 6: DUPLICATE SCANS ---")

    scan_lock.acquire()

    try:
        response = client.post(
            "/analyze",
            json={},
        )

        assert response.status_code == 409
    finally:
        scan_lock.release()

    print("Duplicate scan protection passed.")

    print("\n--- TEST 7: INPUT VALIDATION ---")

    response = client.post(
        "/analyze",
        json={
            "hours": -1,
            "max_workers": 100,
        },
    )

    assert response.status_code == 422

    print("Input validation passed.")

    print("\nAll API tests passed!")


if __name__ == "__main__":
    main()

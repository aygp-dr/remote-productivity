"""Tests for RemoteProductivityOptimizer."""

import json

import pytest
from markupsafe import escape

from main import QUIZ_QUESTIONS, app


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary database."""
    db_path = str(tmp_path / "test.db")
    app.config["TESTING"] = True
    app.config["DB_PATH"] = db_path

    import main
    original_db_path = main.DB_PATH
    original_data_dir = main.DATA_DIR
    main.DB_PATH = db_path
    main.DATA_DIR = str(tmp_path)

    with app.test_client() as c:
        with app.app_context():
            main.get_db()
        yield c

    main.DB_PATH = original_db_path
    main.DATA_DIR = original_data_dir


class TestDashboard:
    def test_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data

    def test_shows_zero_stats_initially(self, client):
        resp = client.get("/")
        assert b"0" in resp.data


class TestTimer:
    def test_loads(self, client):
        resp = client.get("/timer")
        assert resp.status_code == 200
        assert b"Focus Timer" in resp.data

    def test_shows_pomodoro_controls(self, client):
        resp = client.get("/timer")
        assert b"Start" in resp.data
        assert b"Reset" in resp.data
        assert b"25" in resp.data


class TestTasks:
    def test_loads(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert b"Task List" in resp.data

    def test_create_task(self, client):
        resp = client.post(
            "/tasks",
            data={"title": "Write tests", "priority": "high"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Write tests" in resp.data
        assert b"high" in resp.data

    def test_create_task_medium_priority(self, client):
        resp = client.post(
            "/tasks",
            data={"title": "Review code", "priority": "medium"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Review code" in resp.data

    def test_create_task_low_priority(self, client):
        resp = client.post(
            "/tasks",
            data={"title": "Clean desk", "priority": "low"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Clean desk" in resp.data

    def test_empty_title_rejected(self, client):
        client.post("/tasks", data={"title": "", "priority": "medium"}, follow_redirects=True)
        resp = client.get("/tasks")
        # No task should be created with empty title
        assert b"No active tasks" in resp.data

    def test_invalid_priority_rejected(self, client):
        client.post(
            "/tasks",
            data={"title": "Bad priority", "priority": "critical"},
            follow_redirects=True,
        )
        resp = client.get("/tasks")
        assert b"Bad priority" not in resp.data

    def test_complete_task(self, client):
        client.post("/tasks", data={"title": "Finish report", "priority": "high"})
        resp = client.post("/tasks/1/complete", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Finish report" in resp.data
        assert b"Recently Completed" in resp.data

    def test_delete_task(self, client):
        client.post("/tasks", data={"title": "Remove me", "priority": "low"})
        resp = client.post("/tasks/1/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Remove me" not in resp.data

    def test_priority_filter(self, client):
        client.post("/tasks", data={"title": "Urgent item", "priority": "high"})
        client.post("/tasks", data={"title": "Chill item", "priority": "low"})

        resp = client.get("/tasks?priority=high")
        assert b"Urgent item" in resp.data
        assert b"Chill item" not in resp.data

        resp = client.get("/tasks?priority=low")
        assert b"Chill item" in resp.data
        assert b"Urgent item" not in resp.data


class TestQuiz:
    def test_loads(self, client):
        resp = client.get("/quiz")
        assert resp.status_code == 200
        assert b"Workspace Assessment" in resp.data

    def test_all_questions_present(self, client):
        resp = client.get("/quiz")
        for q in QUIZ_QUESTIONS:
            assert str(escape(q["text"])).encode() in resp.data

    def test_has_10_questions(self):
        assert len(QUIZ_QUESTIONS) == 10

    def test_submit(self, client):
        data = {q["id"]: "3" for q in QUIZ_QUESTIONS}
        resp = client.post("/quiz", data=data)
        assert resp.status_code == 200
        assert b"Results" in resp.data
        assert b"60%" in resp.data  # 30/50 = 60%

    def test_submit_all_fives(self, client):
        data = {q["id"]: "5" for q in QUIZ_QUESTIONS}
        resp = client.post("/quiz", data=data)
        assert resp.status_code == 200
        assert b"100%" in resp.data

    def test_submit_all_ones(self, client):
        data = {q["id"]: "1" for q in QUIZ_QUESTIONS}
        resp = client.post("/quiz", data=data)
        assert resp.status_code == 200
        assert b"20%" in resp.data

    def test_values_clamped(self, client):
        data = {q["id"]: "99" for q in QUIZ_QUESTIONS}
        resp = client.post("/quiz", data=data)
        assert resp.status_code == 200
        assert b"100%" in resp.data  # clamped to 5

    def test_results_show_tips(self, client):
        data = {q["id"]: "2" for q in QUIZ_QUESTIONS}
        resp = client.post("/quiz", data=data)
        assert resp.status_code == 200
        # Should contain tips text
        for q in QUIZ_QUESTIONS:
            assert q["tips"][2].encode() in resp.data

    def test_quiz_saved_to_db(self, client):
        data = {q["id"]: "4" for q in QUIZ_QUESTIONS}
        client.post("/quiz", data=data)
        # Dashboard should show the quiz score
        resp = client.get("/")
        assert b"40" in resp.data  # total score 40
        assert b"50" in resp.data  # max score 50


class TestTimerAPI:
    def test_complete_focus(self, client):
        resp = client.post(
            "/api/timer/complete",
            json={"duration": 25, "type": "focus"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_complete_updates_stats(self, client):
        client.post(
            "/api/timer/complete",
            json={"duration": 25, "type": "focus"},
            content_type="application/json",
        )
        resp = client.get("/api/stats")
        stats = resp.get_json()
        assert len(stats) == 1
        assert stats[0]["pomodoros_completed"] == 1
        assert stats[0]["focus_minutes"] == 25

    def test_multiple_sessions_accumulate(self, client):
        for _ in range(3):
            client.post(
                "/api/timer/complete",
                json={"duration": 25, "type": "focus"},
                content_type="application/json",
            )
        resp = client.get("/api/stats")
        stats = resp.get_json()
        assert stats[0]["pomodoros_completed"] == 3
        assert stats[0]["focus_minutes"] == 75

    def test_break_does_not_update_stats(self, client):
        client.post(
            "/api/timer/complete",
            json={"duration": 5, "type": "short_break"},
            content_type="application/json",
        )
        resp = client.get("/api/stats")
        stats = resp.get_json()
        assert len(stats) == 0

    def test_long_break(self, client):
        resp = client.post(
            "/api/timer/complete",
            json={"duration": 15, "type": "long_break"},
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_invalid_type_defaults_to_focus(self, client):
        client.post(
            "/api/timer/complete",
            json={"duration": 25, "type": "invalid"},
            content_type="application/json",
        )
        resp = client.get("/api/stats")
        stats = resp.get_json()
        assert len(stats) == 1
        assert stats[0]["pomodoros_completed"] == 1

    def test_duration_clamped(self, client):
        resp = client.post(
            "/api/timer/complete",
            json={"duration": 999, "type": "focus"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        stats = client.get("/api/stats").get_json()
        assert stats[0]["focus_minutes"] == 120  # clamped to max


class TestStatsAPI:
    def test_empty_stats(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_stats_after_activity(self, client):
        client.post(
            "/api/timer/complete",
            json={"duration": 25, "type": "focus"},
            content_type="application/json",
        )
        client.post("/tasks", data={"title": "Test", "priority": "medium"})
        client.post("/tasks/1/complete", follow_redirects=True)

        resp = client.get("/api/stats")
        stats = resp.get_json()
        assert len(stats) == 1
        assert stats[0]["pomodoros_completed"] == 1
        assert stats[0]["tasks_completed"] == 1
        assert stats[0]["focus_minutes"] == 25

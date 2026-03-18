"""RemoteProductivityOptimizer - helps remote workers optimize productivity."""

import json
import os
import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

QUIZ_QUESTIONS = [
    {
        "id": "lighting",
        "text": "How would you rate your workspace lighting?",
        "labels": ["Very dim/poor", "Somewhat dim", "Adequate", "Good", "Excellent"],
        "tips": {
            1: "Add a desk lamp with adjustable brightness. Position your desk near a window for natural light.",
            2: "Consider a second light source. Bias lighting behind your monitor reduces eye strain.",
            3: "Your lighting is decent. Add bias lighting behind your monitor and ensure light comes from the side.",
            4: "Good lighting. Fine-tune by ensuring no glare on your screen. Aim for 300-500 lux at desk level.",
            5: "Excellent lighting setup. Maintain it and adjust seasonally as daylight hours change.",
        },
    },
    {
        "id": "monitor_position",
        "text": "Is your monitor at eye level and arm's length away?",
        "labels": ["Not at all", "Poorly positioned", "Somewhat", "Mostly correct", "Perfectly positioned"],
        "tips": {
            1: "Use a monitor stand or stack of books to raise your screen. Top of screen should be at or slightly below eye level.",
            2: "Adjust your monitor height so your eyes align with the top third. Keep it 20-26 inches from your face.",
            3: "Almost there. Fine-tune the tilt angle so you look slightly downward. Consider a monitor arm.",
            4: "Good positioning. Double-check distance (arm's length is ideal) and adjust tilt to minimize neck strain.",
            5: "Perfect monitor setup. Remember the 20-20-20 rule: every 20 min, look 20 feet away for 20 seconds.",
        },
    },
    {
        "id": "chair_comfort",
        "text": "How supportive is your chair for long work sessions?",
        "labels": ["Very uncomfortable", "Uncomfortable after 1hr", "Okay for a few hours", "Comfortable most of day", "Excellent all-day support"],
        "tips": {
            1: "Invest in an ergonomic chair with lumbar support. Meantime, use a rolled towel behind your lower back.",
            2: "Add a lumbar support cushion and ensure your feet are flat on the floor. Consider a seat cushion.",
            3: "Adjust chair height so thighs are parallel to the floor. A footrest helps if your desk is too high.",
            4: "Good setup. Ensure armrests allow your shoulders to relax. Take standing breaks every 45-60 minutes.",
            5: "Great chair setup. Maintain good posture habits and alternate between sitting and standing if possible.",
        },
    },
    {
        "id": "desk_space",
        "text": "Do you have adequate desk space for your work?",
        "labels": ["Very cramped", "Barely enough", "Adequate", "Spacious", "Very spacious and organized"],
        "tips": {
            1: "Declutter aggressively. Use vertical organizers and monitor arms to free desk space.",
            2: "Use cable management solutions and desk organizers. Move non-essential items off the desk.",
            3: "Good space. Add a small organizer for frequently used items. Keep only current task materials visible.",
            4: "Nice workspace. Consider zones: primary work area, reference area, and personal area.",
            5: "Excellent desk setup. Keep maintaining this organization for sustained focus.",
        },
    },
    {
        "id": "noise_level",
        "text": "How would you rate the noise level in your workspace?",
        "labels": ["Very noisy", "Frequently noisy", "Occasional disruptions", "Mostly quiet", "Very quiet"],
        "tips": {
            1: "Invest in noise-canceling headphones. Use white noise or brown noise apps. Consider acoustic panels.",
            2: "Try noise-canceling earbuds for calls. Use a 'do not disturb' sign during focus hours.",
            3: "Use background sounds (lo-fi, nature) to mask occasional noise. Close your door during focus sessions.",
            4: "Good noise environment. For deep focus, try complete silence or consistent background sounds.",
            5: "Excellent quiet workspace. Use this advantage for demanding cognitive work during peak hours.",
        },
    },
    {
        "id": "temperature",
        "text": "Is your workspace temperature comfortable for working?",
        "labels": ["Very uncomfortable", "Often too hot/cold", "Varies throughout day", "Usually comfortable", "Always comfortable"],
        "tips": {
            1: "Use a personal fan or space heater if you can't control room temperature. Dress in layers.",
            2: "Try a small desk fan or heater. Optimal work temperature is 68-72F (20-22C).",
            3: "Track when temperature shifts happen and proactively adjust. A desk thermometer helps.",
            4: "Good temperature control. Stay hydrated as dehydration makes temperature feel more extreme.",
            5: "Perfect climate control. Consistent temperature is a real productivity advantage.",
        },
    },
    {
        "id": "air_quality",
        "text": "How is the ventilation and air quality in your workspace?",
        "labels": ["Stuffy/poor", "Below average", "Adequate", "Good airflow", "Excellent fresh air"],
        "tips": {
            1: "Open a window regularly. Add an air purifier. Snake plants and pothos improve air quality naturally.",
            2: "Set a reminder to ventilate every 2 hours. A small air purifier makes a significant difference.",
            3: "Add 2-3 air-purifying plants. Open windows during breaks. Monitor humidity (aim for 40-60%).",
            4: "Good air quality. Add a humidity monitor and maintain 40-60% for optimal comfort.",
            5: "Excellent ventilation. Fresh air supports sustained cognitive performance and focus.",
        },
    },
    {
        "id": "break_frequency",
        "text": "How regularly do you take breaks during work?",
        "labels": ["Rarely/never", "Only when exhausted", "Occasionally", "Every 1-2 hours", "Regular scheduled breaks"],
        "tips": {
            1: "Start with the Pomodoro Technique: 25 min work, 5 min break. Use our Focus Timer!",
            2: "Set hourly reminders to stand and stretch. Short frequent breaks beat long rare ones.",
            3: "Structure your breaks: walk, stretch, hydrate. Avoid social media during breaks.",
            4: "Good break habits. Add movement: walks, stretches, or light exercises. Avoid screens during breaks.",
            5: "Excellent break discipline. Vary activities: short walks, stretching, eye exercises, mindfulness.",
        },
    },
    {
        "id": "work_boundaries",
        "text": "How well separated is your workspace from your living space?",
        "labels": ["No separation", "Same room, same desk", "Same room, dedicated corner", "Separate room, shared", "Dedicated home office"],
        "tips": {
            1: "Create a symbolic boundary: a specific chair or ritual that signals 'work mode'. End-of-day shutdown ritual is crucial.",
            2: "Use visual cues: a desk divider, different lighting, or dedicated surface. Pack away work materials after hours.",
            3: "Good start. Strengthen with a consistent start/stop routine. Consider a room divider or curtain.",
            4: "Nice separation. Add a 'shutdown complete' ritual: close work tabs, turn off notifications, leave the room.",
            5: "Ideal setup. Maintain the boundary strictly. Never bring personal activities into the office.",
        },
    },
    {
        "id": "digital_organization",
        "text": "How organized is your digital workspace (files, apps, notifications)?",
        "labels": ["Very cluttered", "Disorganized", "Somewhat organized", "Well organized", "Highly optimized"],
        "tips": {
            1: "Turn off all non-essential notifications. Create a simple folder structure. Close unused browser tabs.",
            2: "Batch notifications to 2-3 times daily. Use consistent file naming. Limit tabs to 5 during focus work.",
            3: "Good foundation. Add keyboard shortcuts for common actions. Schedule weekly digital cleanup.",
            4: "Well organized. Consider automation: auto-filing rules, text expansion, clipboard managers.",
            5: "Excellent digital hygiene. Share your system with teammates to multiply productivity.",
        },
    },
]


def get_db():
    """Get database connection, creating tables if needed."""
    if "db" not in g:
        db_path = app.config.get("DB_PATH", DB_PATH)
        data_dir = os.path.dirname(db_path)
        os.makedirs(data_dir, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        _init_db(g.db)
    return g.db


def _init_db(db):
    """Create all database tables."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            duration_minutes INTEGER NOT NULL DEFAULT 25,
            session_type TEXT NOT NULL DEFAULT 'focus',
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quiz_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            responses TEXT NOT NULL,
            total_score INTEGER NOT NULL,
            max_score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date DATE NOT NULL UNIQUE,
            pomodoros_completed INTEGER DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            focus_minutes INTEGER DEFAULT 0
        );
    """)


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db:
        db.close()


def _update_daily_stat(db, field, increment=1):
    """Increment a daily stat field for today."""
    today = date.today().isoformat()
    db.execute(
        f"""INSERT INTO daily_stats (stat_date, {field})
            VALUES (?, ?)
            ON CONFLICT(stat_date) DO UPDATE SET {field} = {field} + ?""",
        (today, increment, increment),
    )
    db.commit()


@app.route("/")
def dashboard():
    db = get_db()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    week_stats = db.execute(
        """SELECT COALESCE(SUM(pomodoros_completed), 0) as pomodoros,
                  COALESCE(SUM(tasks_completed), 0) as tasks,
                  COALESCE(SUM(focus_minutes), 0) as minutes
           FROM daily_stats WHERE stat_date >= ?""",
        (week_start.isoformat(),),
    ).fetchone()

    daily = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        row = db.execute(
            "SELECT * FROM daily_stats WHERE stat_date = ?",
            (d.isoformat(),),
        ).fetchone()
        daily.append({
            "date": d.strftime("%a"),
            "full_date": d.isoformat(),
            "pomodoros": row["pomodoros_completed"] if row else 0,
            "tasks": row["tasks_completed"] if row else 0,
            "minutes": row["focus_minutes"] if row else 0,
        })

    max_minutes = max((d["minutes"] for d in daily), default=1) or 1

    latest_quiz = db.execute(
        "SELECT * FROM quiz_responses ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    active_tasks = db.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE status = 'active'"
    ).fetchone()["c"]

    return render_template(
        "dashboard.html",
        week_stats=week_stats,
        daily=daily,
        max_minutes=max_minutes,
        latest_quiz=latest_quiz,
        active_tasks=active_tasks,
        quiz_count=len(QUIZ_QUESTIONS),
    )


@app.route("/timer")
def timer():
    db = get_db()
    today_stats = db.execute(
        "SELECT * FROM daily_stats WHERE stat_date = ?",
        (date.today().isoformat(),),
    ).fetchone()
    return render_template(
        "timer.html",
        today_pomodoros=today_stats["pomodoros_completed"] if today_stats else 0,
        today_minutes=today_stats["focus_minutes"] if today_stats else 0,
    )


@app.route("/tasks", methods=["GET", "POST"])
def tasks():
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        priority = request.form.get("priority", "medium")
        if title and priority in ("high", "medium", "low"):
            db.execute(
                "INSERT INTO tasks (title, priority) VALUES (?, ?)",
                (title, priority),
            )
            db.commit()
        return redirect(url_for("tasks"))

    priority_filter = request.args.get("priority", "all")
    if priority_filter in ("high", "medium", "low"):
        active = db.execute(
            """SELECT * FROM tasks WHERE status = 'active' AND priority = ?
               ORDER BY created_at DESC""",
            (priority_filter,),
        ).fetchall()
    else:
        active = db.execute(
            """SELECT * FROM tasks WHERE status = 'active'
               ORDER BY CASE priority
                   WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
                   created_at DESC"""
        ).fetchall()

    completed = db.execute(
        """SELECT * FROM tasks WHERE status = 'completed'
           ORDER BY completed_at DESC LIMIT 20"""
    ).fetchall()

    return render_template(
        "tasks.html",
        active_tasks=active,
        completed_tasks=completed,
        priority_filter=priority_filter,
    )


@app.route("/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    db = get_db()
    db.execute(
        "UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (task_id,),
    )
    db.commit()
    _update_daily_stat(db, "tasks_completed")
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return redirect(url_for("tasks"))


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":
        responses = {}
        total_score = 0
        for q in QUIZ_QUESTIONS:
            val = int(request.form.get(q["id"], 3))
            val = max(1, min(5, val))
            responses[q["id"]] = val
            total_score += val

        db = get_db()
        db.execute(
            "INSERT INTO quiz_responses (responses, total_score, max_score) VALUES (?, ?, ?)",
            (json.dumps(responses), total_score, len(QUIZ_QUESTIONS) * 5),
        )
        db.commit()

        tips = []
        for q in QUIZ_QUESTIONS:
            score = responses[q["id"]]
            tips.append({
                "question": q["text"],
                "category": q["id"].replace("_", " ").title(),
                "score": score,
                "tip": q["tips"][score],
            })

        tips.sort(key=lambda t: t["score"])

        return render_template(
            "results.html",
            tips=tips,
            total_score=total_score,
            max_score=len(QUIZ_QUESTIONS) * 5,
            percentage=round(total_score / (len(QUIZ_QUESTIONS) * 5) * 100),
        )

    return render_template("quiz.html", questions=QUIZ_QUESTIONS)


@app.route("/api/timer/complete", methods=["POST"])
def api_timer_complete():
    data = request.get_json(silent=True) or {}
    duration = int(data.get("duration", 25))
    session_type = data.get("type", "focus")
    if session_type not in ("focus", "short_break", "long_break"):
        session_type = "focus"
    duration = max(1, min(120, duration))

    db = get_db()
    db.execute(
        "INSERT INTO pomodoro_sessions (duration_minutes, session_type) VALUES (?, ?)",
        (duration, session_type),
    )
    db.commit()

    if session_type == "focus":
        _update_daily_stat(db, "pomodoros_completed")
        _update_daily_stat(db, "focus_minutes", duration)

    return jsonify({"status": "ok"})


@app.route("/api/stats")
def api_stats():
    db = get_db()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    stats = db.execute(
        "SELECT * FROM daily_stats WHERE stat_date >= ? ORDER BY stat_date",
        (week_start.isoformat(),),
    ).fetchall()
    return jsonify([dict(s) for s in stats])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

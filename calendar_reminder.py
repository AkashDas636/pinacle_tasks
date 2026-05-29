#!/usr/bin/env python3
"""
📅 Standalone Calendar & Reminder Web App
A beautiful, modern single-page web application for managing your schedule and tasks.

Run:  python calendar_reminder.py
Visit: http://localhost:8080
"""

import os
import sys
import sqlite3
import datetime
import calendar
import webbrowser
import threading
from flask import Flask, jsonify, request, render_template

# Force UTF-8 encoding for standard output on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ─── Database Setup ────────────────────────────────────────────────────────────

DB_FILE = "calendar_reminders.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            date     TEXT NOT NULL,
            title    TEXT NOT NULL,
            note     TEXT,
            time     TEXT,
            done     INTEGER DEFAULT 0,
            category TEXT DEFAULT 'General'
        )
    """)
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

# ─── Flask App Setup ───────────────────────────────────────────────────────────

# Flask default template_folder is 'templates'
app = Flask(__name__)
app.secret_key = "calendar-reminder-app-secret-2026"

# ─── Core Routing ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    init_db()
    return render_template("index.html")

# ─── API: Calendar & Reminders ─────────────────────────────────────────────────

@app.route("/api/calendar")
def api_calendar():
    y = int(request.args.get("year", datetime.date.today().year))
    m = int(request.args.get("month", datetime.date.today().month))
    
    # Calculate days grid
    cal = calendar.Calendar(firstweekday=6) # Start weeks on Sunday for standard view
    weeks = cal.monthdatescalendar(y, m)
    grid = []
    for week in weeks:
        row = []
        for d in week:
            # If day belongs to the target month, keep date, otherwise pass 0 or formatted string
            row.append(d.strftime("%Y-%m-%d") if d.month == m else "")
        grid.append(row)
        
    # Get distinct reminder dates that are not completed
    dates_rows = query_db("SELECT DISTINCT date FROM reminders WHERE done=0")
    reminder_dates = [row["date"] for row in dates_rows]
    
    return jsonify({
        "year": y,
        "month": m,
        "month_name": calendar.month_name[m],
        "days": grid,
        "reminder_dates": reminder_dates
    })

@app.route("/api/reminders", methods=["GET"])
def api_get_reminders():
    date = request.args.get("date", "")
    if not date:
        return jsonify([])
    rows = query_db("SELECT id, title, note, time, done, category FROM reminders WHERE date=? ORDER BY time ASC, id ASC", (date,))
    return jsonify([dict(r) for r in rows])

@app.route("/api/reminders", methods=["POST"])
def api_add_reminder():
    data = request.json or {}
    date = data.get("date", "")
    title = data.get("title", "").strip()
    note = data.get("note", "").strip()
    time_ = data.get("time", "").strip()
    category = data.get("category", "General").strip()
    
    if not date or not title:
        return jsonify({"success": False, "error": "Missing date or title"}), 400
        
    execute_db("INSERT INTO reminders (date, title, note, time, category) VALUES (?, ?, ?, ?, ?)",
               (date, title, note, time_, category))
    return jsonify({"success": True})

@app.route("/api/reminders/<int:rid>/done", methods=["POST"])
def api_mark_reminder_done(rid):
    # Toggle completed status or set it based on a query parameter or toggle it
    data = request.json or {}
    done_val = data.get("done", 1)
    execute_db("UPDATE reminders SET done=? WHERE id=?", (done_val, rid))
    return jsonify({"success": True})

@app.route("/api/reminders/<int:rid>", methods=["DELETE"])
def api_delete_reminder(rid):
    execute_db("DELETE FROM reminders WHERE id=?", (rid,))
    return jsonify({"success": True})

@app.route("/api/stats")
def api_stats():
    pending = query_db("SELECT COUNT(*) as c FROM reminders WHERE done=0", one=True)["c"]
    done = query_db("SELECT COUNT(*) as c FROM reminders WHERE done=1", one=True)["c"]
    return jsonify({"pending": pending, "done": done, "total": pending + done})

# ─── Launcher Engine ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = 8080
    print("=" * 66)
    print("  📅  CALENDAR & REMINDER WEB APP")
    print(f"  ✨  Server live at: http://localhost:{port}")
    print("=" * 66)

    if "--no-browser" not in sys.argv:
        try:
            threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
        except Exception:
            pass

    app.run(debug=False, host="0.0.0.0", port=port)

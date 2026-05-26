"""
⏰ Alarm Clock App — Premium Flask Web Edition
Set, manage, and snooze alarms with a stunning glassmorphic dark UI.
Run:  python alarm_clock.py            (Flask web on port 5003)
      python alarm_clock.py --gui      (original Tkinter GUI)
"""

import sys
import os
import time
import datetime
import threading
import sqlite3
import webbrowser

# ─── Sound Helper ──────────────────────────────────────────────────────────────

def play_alarm_sound(duration: int = 3):
    """Ring an audible alarm using system beep (cross-platform)."""
    for _ in range(duration * 2):
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(1000, 500)
            else:
                sys.stdout.write("\a")
                sys.stdout.flush()
                os.system(
                    "command -v paplay &>/dev/null && paplay "
                    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga "
                    "2>/dev/null || true"
                )
        except Exception:
            pass
        time.sleep(0.5)


# ─── Color Palette ─────────────────────────────────────────────────────────────

C = {
    "bg":       "#0D1117",
    "card":     "#161B22",
    "accent":   "#F78166",
    "green":    "#3FB950",
    "yellow":   "#D29922",
    "text":     "#E6EDF3",
    "muted":    "#8B949E",
    "border":   "#30363D",
    "white":    "#FFFFFF",
    "red":      "#F85149",
}


# ─── Alarm Data Class ─────────────────────────────────────────────────────────

class Alarm:
    _id_counter = 0

    def __init__(self, hour: int, minute: int, label: str, repeat: bool = False,
                 alarm_id: int | None = None, active: bool = True,
                 snoozed_until: datetime.datetime | None = None):
        if alarm_id is not None:
            self.id = alarm_id
        else:
            Alarm._id_counter += 1
            self.id = Alarm._id_counter
        self.hour = hour
        self.minute = minute
        self.label = label
        self.repeat = repeat
        self.active = active
        self.snoozed_until = snoozed_until

    @property
    def time_str(self):
        return f"{self.hour:02d}:{self.minute:02d}"

    @property
    def status(self):
        if not self.active:
            return "OFF"
        if self.snoozed_until:
            return f"💤 {self.snoozed_until.strftime('%H:%M')}"
        return "ON"

    def to_dict(self):
        return {
            "id": self.id,
            "hour": self.hour,
            "minute": self.minute,
            "label": self.label,
            "repeat": self.repeat,
            "active": self.active,
            "time_str": self.time_str,
            "status": self.status,
            "snoozed_until": self.snoozed_until.isoformat() if self.snoozed_until else None,
        }


# ─── Database Layer ────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alarms.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour INTEGER NOT NULL,
            minute INTEGER NOT NULL,
            label TEXT NOT NULL DEFAULT 'Alarm',
            repeat INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            snoozed_until TEXT
        )
    """)
    conn.commit()
    conn.close()

def db_get_all_alarms():
    conn = get_db()
    rows = conn.execute("SELECT * FROM alarms ORDER BY hour, minute").fetchall()
    conn.close()
    alarms = []
    for r in rows:
        snoozed = None
        if r["snoozed_until"]:
            try:
                snoozed = datetime.datetime.fromisoformat(r["snoozed_until"])
            except Exception:
                snoozed = None
        alarms.append(Alarm(
            hour=r["hour"], minute=r["minute"], label=r["label"],
            repeat=bool(r["repeat"]), alarm_id=r["id"],
            active=bool(r["active"]), snoozed_until=snoozed,
        ))
    return alarms

def db_add_alarm(hour, minute, label, repeat):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO alarms (hour, minute, label, repeat) VALUES (?, ?, ?, ?)",
        (hour, minute, label, int(repeat)),
    )
    alarm_id = cur.lastrowid
    conn.commit()
    conn.close()
    return alarm_id

def db_toggle_alarm(alarm_id):
    conn = get_db()
    conn.execute("UPDATE alarms SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?", (alarm_id,))
    conn.commit()
    conn.close()

def db_snooze_alarm(alarm_id, minutes=5):
    snoozed = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    conn = get_db()
    conn.execute("UPDATE alarms SET snoozed_until=? WHERE id=?", (snoozed.isoformat(), alarm_id))
    conn.commit()
    conn.close()

def db_dismiss_alarm(alarm_id):
    conn = get_db()
    row = conn.execute("SELECT repeat FROM alarms WHERE id=?", (alarm_id,)).fetchone()
    if row:
        if row["repeat"]:
            conn.execute("UPDATE alarms SET snoozed_until=NULL WHERE id=?", (alarm_id,))
        else:
            conn.execute("UPDATE alarms SET active=0, snoozed_until=NULL WHERE id=?", (alarm_id,))
    conn.commit()
    conn.close()

def db_delete_alarm(alarm_id):
    conn = get_db()
    conn.execute("DELETE FROM alarms WHERE id=?", (alarm_id,))
    conn.commit()
    conn.close()

def db_clear_snooze(alarm_id):
    conn = get_db()
    conn.execute("UPDATE alarms SET snoozed_until=NULL WHERE id=?", (alarm_id,))
    conn.commit()
    conn.close()


# ─── Flask Application ────────────────────────────────────────────────────────

SNOOZE_MINUTES = 5

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>⏰ Alarm Clock</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #0a0e17;
    --card: rgba(16, 22, 36, 0.7);
    --accent: #f78166;
    --text: #e6edf3;
    --muted: #8b949e;
    --border: rgba(255,255,255,0.07);
    --success: #3fb950;
    --danger: #f85149;
    --glow: rgba(247, 129, 102, 0.25);
    --glass-blur: 18px;
}

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

html { font-size: 16px; }

body {
    font-family: 'Outfit', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
    position: relative;
}

/* Background gradient orbs */
body::before, body::after {
    content: '';
    position: fixed;
    border-radius: 50%;
    filter: blur(120px);
    z-index: 0;
    pointer-events: none;
}
body::before {
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(247,129,102,0.12) 0%, transparent 70%);
    top: -120px; right: -80px;
}
body::after {
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(63,185,80,0.08) 0%, transparent 70%);
    bottom: -80px; left: -60px;
}

.container {
    max-width: 640px;
    margin: 0 auto;
    padding: 32px 20px 60px;
    position: relative;
    z-index: 1;
}

/* ─── Header ─── */
.header {
    text-align: center;
    margin-bottom: 10px;
}
.header h1 {
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 3px;
    text-transform: uppercase;
}
.header h1 span { color: var(--accent); }

/* ─── Clock Display ─── */
.clock-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 40px 20px 30px;
    text-align: center;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.clock-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 24px;
    background: radial-gradient(ellipse at 50% 0%, var(--glow) 0%, transparent 60%);
    pointer-events: none;
}
.clock-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 5rem;
    font-weight: 700;
    color: var(--accent);
    text-shadow: 0 0 40px var(--glow), 0 0 80px rgba(247,129,102,0.1);
    line-height: 1;
    letter-spacing: 4px;
    position: relative;
}
.clock-seconds {
    font-size: 2rem;
    font-weight: 400;
    color: var(--muted);
    vertical-align: super;
    margin-left: 4px;
}
.clock-date {
    font-size: 1rem;
    color: var(--muted);
    margin-top: 10px;
    font-weight: 400;
    letter-spacing: 1px;
}

/* ─── Glass Card ─── */
.glass-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 18px;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    padding: 24px;
    margin-bottom: 20px;
}

.section-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title .icon { font-size: 1rem; }

/* ─── Form ─── */
.form-row {
    display: flex;
    gap: 12px;
    align-items: flex-end;
    flex-wrap: wrap;
    margin-bottom: 14px;
}
.form-group {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.form-group label {
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 500;
}
.form-group input[type="number"],
.form-group input[type="text"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    padding: 10px 14px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    width: 100%;
}
.form-group input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(247,129,102,0.15);
}
.form-group.time-input { width: 72px; }
.form-group.label-input { flex: 1; min-width: 140px; }
.time-colon {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    color: var(--muted);
    padding-bottom: 6px;
    user-select: none;
}

.checkbox-group {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 8px;
}
.checkbox-group input[type="checkbox"] {
    appearance: none;
    width: 18px; height: 18px;
    border: 2px solid var(--muted);
    border-radius: 5px;
    cursor: pointer;
    position: relative;
    transition: all 0.2s;
    flex-shrink: 0;
}
.checkbox-group input[type="checkbox"]:checked {
    background: var(--accent);
    border-color: var(--accent);
}
.checkbox-group input[type="checkbox"]:checked::after {
    content: '✓';
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
}
.checkbox-group label {
    font-size: 0.85rem;
    color: var(--muted);
    cursor: pointer;
}

.btn-add {
    width: 100%;
    padding: 13px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--accent) 0%, #e5603a 100%);
    color: #fff;
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s, box-shadow 0.2s;
    letter-spacing: 0.5px;
}
.btn-add:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(247,129,102,0.3);
}
.btn-add:active { transform: translateY(0); }

/* ─── Alarm List ─── */
.alarm-list { display: flex; flex-direction: column; gap: 10px; }

.alarm-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 18px;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--border);
    border-radius: 14px;
    transition: all 0.3s ease, opacity 0.3s ease;
    animation: slideIn 0.35s ease-out forwards;
}
@keyframes slideIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
.alarm-item:hover {
    background: rgba(255,255,255,0.04);
    border-color: rgba(255,255,255,0.12);
}
.alarm-item.inactive { opacity: 0.45; }

.alarm-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text);
    min-width: 75px;
}
.alarm-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
    overflow: hidden;
}
.alarm-label {
    font-size: 0.9rem;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.alarm-meta {
    display: flex;
    gap: 8px;
    align-items: center;
}
.badge {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.badge-on { background: rgba(63,185,80,0.15); color: var(--success); }
.badge-off { background: rgba(248,81,73,0.15); color: var(--danger); }
.badge-snooze { background: rgba(210,153,34,0.15); color: #d29922; }
.badge-repeat { background: rgba(247,129,102,0.12); color: var(--accent); font-size: 0.6rem; }

.alarm-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
}
.btn-action {
    width: 34px; height: 34px;
    border: 1px solid var(--border);
    border-radius: 9px;
    background: rgba(255,255,255,0.03);
    color: var(--muted);
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}
.btn-action:hover {
    background: rgba(255,255,255,0.08);
    color: var(--text);
    border-color: rgba(255,255,255,0.15);
}
.btn-action.toggle-btn:hover { color: var(--success); border-color: rgba(63,185,80,0.3); }
.btn-action.snooze-btn:hover { color: #d29922; border-color: rgba(210,153,34,0.3); }
.btn-action.delete-btn:hover { color: var(--danger); border-color: rgba(248,81,73,0.3); }

.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--muted);
    font-size: 0.9rem;
}
.empty-state .icon { font-size: 2.5rem; margin-bottom: 10px; display: block; opacity: 0.4; }

/* ─── Alarm Overlay ─── */
.alarm-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: none;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.7);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    animation: fadeIn 0.3s ease;
}
.alarm-overlay.active { display: flex; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.alarm-popup {
    background: var(--card);
    border: 1px solid rgba(248,81,73,0.3);
    border-radius: 24px;
    padding: 40px 36px 32px;
    text-align: center;
    max-width: 380px;
    width: 90%;
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    animation: popIn 0.4s cubic-bezier(0.175,0.885,0.32,1.275) forwards;
    box-shadow: 0 0 60px rgba(248,81,73,0.15);
    position: relative;
    overflow: hidden;
}
.alarm-popup::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 24px;
    background: radial-gradient(ellipse at 50% 0%, rgba(248,81,73,0.12) 0%, transparent 60%);
    pointer-events: none;
}
@keyframes popIn {
    from { opacity: 0; transform: scale(0.85) translateY(20px); }
    to   { opacity: 1; transform: scale(1) translateY(0); }
}
.alarm-popup .ring-icon {
    font-size: 3.5rem;
    animation: ring 0.6s ease-in-out infinite alternate;
    display: inline-block;
    margin-bottom: 12px;
}
@keyframes ring {
    0%   { transform: rotate(-15deg); }
    100% { transform: rotate(15deg); }
}
.alarm-popup h2 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--danger);
    margin-bottom: 6px;
}
.alarm-popup .popup-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2.4rem;
    font-weight: 700;
    color: var(--text);
    margin: 8px 0;
}
.alarm-popup .popup-label {
    font-size: 1rem;
    color: var(--muted);
    margin-bottom: 24px;
}
.popup-buttons {
    display: flex;
    gap: 10px;
    justify-content: center;
}
.btn-dismiss, .btn-snooze-popup {
    padding: 12px 28px;
    border: none;
    border-radius: 12px;
    font-family: 'Outfit', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s, box-shadow 0.2s;
}
.btn-dismiss {
    background: linear-gradient(135deg, var(--danger) 0%, #c52f29 100%);
    color: #fff;
}
.btn-dismiss:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(248,81,73,0.3); }
.btn-snooze-popup {
    background: rgba(210,153,34,0.15);
    color: #d29922;
    border: 1px solid rgba(210,153,34,0.3);
}
.btn-snooze-popup:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(210,153,34,0.2); }

/* ─── Toast ─── */
.toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 24px;
    border-radius: 12px;
    font-size: 0.85rem;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 2000;
    opacity: 0;
    transition: all 0.35s cubic-bezier(0.175,0.885,0.32,1.275);
    pointer-events: none;
}
.toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }

/* ─── Responsive ─── */
@media (max-width: 500px) {
    .clock-time { font-size: 3.2rem; }
    .clock-seconds { font-size: 1.4rem; }
    .form-row { flex-direction: column; gap: 10px; }
    .form-group.time-input { width: 100%; }
    .alarm-item { flex-wrap: wrap; gap: 10px; }
    .alarm-actions { width: 100%; justify-content: flex-end; }
    .container { padding: 20px 14px 40px; }
}
</style>
</head>
<body>

<div class="container">
    <!-- Header -->
    <div class="header">
        <h1><span>⏰</span> Alarm Clock</h1>
    </div>

    <!-- Clock Display -->
    <div class="clock-card">
        <div class="clock-time" id="clockTime">
            00:00<span class="clock-seconds" id="clockSec">00</span>
        </div>
        <div class="clock-date" id="clockDate">Loading...</div>
    </div>

    <!-- Set Alarm Form -->
    <div class="glass-card">
        <div class="section-title"><span class="icon">➕</span> Set New Alarm</div>
        <form id="alarmForm" onsubmit="return addAlarm(event)">
            <div class="form-row">
                <div class="form-group time-input">
                    <label>Hour</label>
                    <input type="number" id="inputHour" min="0" max="23" value="7" required>
                </div>
                <div class="time-colon">:</div>
                <div class="form-group time-input">
                    <label>Min</label>
                    <input type="number" id="inputMin" min="0" max="59" value="0" required>
                </div>
                <div class="form-group label-input">
                    <label>Label</label>
                    <input type="text" id="inputLabel" value="Wake up!" maxlength="40">
                </div>
            </div>
            <div class="form-row" style="margin-bottom:16px;">
                <div class="checkbox-group">
                    <input type="checkbox" id="inputRepeat">
                    <label for="inputRepeat">Repeat Daily</label>
                </div>
            </div>
            <button type="submit" class="btn-add">Add Alarm</button>
        </form>
    </div>

    <!-- Alarm List -->
    <div class="glass-card">
        <div class="section-title"><span class="icon">🔔</span> Alarms</div>
        <div class="alarm-list" id="alarmList">
            <div class="empty-state">
                <span class="icon">⏰</span>
                No alarms set yet
            </div>
        </div>
    </div>
</div>

<!-- Alarm Overlay -->
<div class="alarm-overlay" id="alarmOverlay">
    <div class="alarm-popup">
        <div class="ring-icon">🔔</div>
        <h2>ALARM!</h2>
        <div class="popup-time" id="popupTime">07:00</div>
        <div class="popup-label" id="popupLabel">Wake up!</div>
        <div class="popup-buttons">
            <button class="btn-snooze-popup" onclick="snoozeRinging()">💤 Snooze 5m</button>
            <button class="btn-dismiss" onclick="dismissRinging()">Dismiss</button>
        </div>
    </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// ─── Web Audio Alarm Synth ───
let audioCtx = null;
let alarmOsc = null;
let alarmGain = null;
let alarmInterval = null;

function startAlarmSound() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    stopAlarmSound();
    alarmGain = audioCtx.createGain();
    alarmGain.connect(audioCtx.destination);
    alarmGain.gain.value = 0;
    let playing = false;
    alarmInterval = setInterval(() => {
        if (playing) {
            alarmGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.05);
            playing = false;
        } else {
            if (alarmOsc) { try { alarmOsc.stop(); } catch(e){} }
            alarmOsc = audioCtx.createOscillator();
            alarmOsc.type = 'triangle';
            alarmOsc.frequency.value = 880;
            alarmOsc.connect(alarmGain);
            alarmOsc.start();
            alarmGain.gain.setTargetAtTime(0.3, audioCtx.currentTime, 0.02);
            // frequency sweep
            alarmOsc.frequency.setTargetAtTime(1100, audioCtx.currentTime, 0.15);
            playing = true;
        }
    }, 400);
}

function stopAlarmSound() {
    if (alarmInterval) { clearInterval(alarmInterval); alarmInterval = null; }
    if (alarmOsc) { try { alarmOsc.stop(); } catch(e){} alarmOsc = null; }
    if (alarmGain) { try { alarmGain.disconnect(); } catch(e){} alarmGain = null; }
}

// ─── Clock ───
function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('clockTime').innerHTML =
        h + ':' + m + '<span class="clock-seconds">' + s + '</span>';
    const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('clockDate').textContent = now.toLocaleDateString('en-US', opts);
}
setInterval(updateClock, 1000);
updateClock();

// ─── Toast ───
let toastTimer = null;
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2500);
}

// ─── API helpers ───
async function api(url, method='GET', body=null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    return res.json();
}

// ─── Alarm CRUD ───
let ringingAlarmId = null;

async function loadAlarms() {
    const data = await api('/api/alarms');
    renderAlarms(data.alarms || []);
}

function renderAlarms(alarms) {
    const list = document.getElementById('alarmList');
    if (!alarms.length) {
        list.innerHTML = '<div class="empty-state"><span class="icon">⏰</span>No alarms set yet</div>';
        return;
    }
    list.innerHTML = alarms.map((a, i) => {
        const isOff = !a.active;
        const isSnoozed = a.snoozed_until && a.active;
        let badgeClass = a.active ? 'badge-on' : 'badge-off';
        let badgeText = a.active ? 'ON' : 'OFF';
        if (isSnoozed) { badgeClass = 'badge-snooze'; badgeText = '💤 SNOOZE'; }
        const repeatBadge = a.repeat ? '<span class="badge badge-repeat">🔁 REPEAT</span>' : '';
        return `
        <div class="alarm-item${isOff ? ' inactive' : ''}" style="animation-delay:${i*60}ms">
            <div class="alarm-time">${a.time_str}</div>
            <div class="alarm-info">
                <div class="alarm-label">${escapeHtml(a.label)}</div>
                <div class="alarm-meta">
                    <span class="badge ${badgeClass}">${badgeText}</span>
                    ${repeatBadge}
                </div>
            </div>
            <div class="alarm-actions">
                <button class="btn-action toggle-btn" onclick="toggleAlarm(${a.id})" title="Toggle">
                    ${a.active ? '🔔' : '🔕'}
                </button>
                <button class="btn-action snooze-btn" onclick="snoozeAlarm(${a.id})" title="Snooze 5m">
                    💤
                </button>
                <button class="btn-action delete-btn" onclick="deleteAlarm(${a.id})" title="Delete">
                    🗑
                </button>
            </div>
        </div>`;
    }).join('');
}

function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
}

async function addAlarm(e) {
    e.preventDefault();
    const hour = parseInt(document.getElementById('inputHour').value);
    const minute = parseInt(document.getElementById('inputMin').value);
    const label = document.getElementById('inputLabel').value.trim() || 'Alarm';
    const repeat = document.getElementById('inputRepeat').checked;
    if (isNaN(hour) || hour < 0 || hour > 23 || isNaN(minute) || minute < 0 || minute > 59) {
        showToast('⚠️ Invalid time');
        return false;
    }
    await api('/api/alarms', 'POST', { hour, minute, label, repeat });
    showToast('✅ Alarm added for ' + String(hour).padStart(2,'0') + ':' + String(minute).padStart(2,'0'));
    loadAlarms();
    return false;
}

async function toggleAlarm(id) {
    await api('/api/alarms/' + id + '/toggle', 'POST');
    showToast('🔔 Alarm toggled');
    loadAlarms();
}

async function snoozeAlarm(id) {
    await api('/api/alarms/' + id + '/snooze', 'POST');
    showToast('💤 Snoozed for 5 minutes');
    loadAlarms();
}

async function deleteAlarm(id) {
    await api('/api/alarms/' + id, 'DELETE');
    showToast('🗑️ Alarm deleted');
    loadAlarms();
}

// ─── Polling for ringing ───
async function pollAlarms() {
    try {
        const data = await api('/api/poll');
        if (data.ringing && data.alarm) {
            if (ringingAlarmId !== data.alarm.id) {
                ringingAlarmId = data.alarm.id;
                document.getElementById('popupTime').textContent = data.alarm.time_str;
                document.getElementById('popupLabel').textContent = data.alarm.label;
                document.getElementById('alarmOverlay').classList.add('active');
                startAlarmSound();
            }
        }
    } catch(e) {}
}

async function dismissRinging() {
    stopAlarmSound();
    if (ringingAlarmId) {
        await api('/api/alarms/' + ringingAlarmId + '/dismiss', 'POST');
    }
    ringingAlarmId = null;
    document.getElementById('alarmOverlay').classList.remove('active');
    showToast('✅ Alarm dismissed');
    loadAlarms();
}

async function snoozeRinging() {
    stopAlarmSound();
    if (ringingAlarmId) {
        await api('/api/alarms/' + ringingAlarmId + '/snooze', 'POST');
    }
    ringingAlarmId = null;
    document.getElementById('alarmOverlay').classList.remove('active');
    showToast('💤 Snoozed for 5 minutes');
    loadAlarms();
}

// Initial load + polling
loadAlarms();
setInterval(pollAlarms, 5000);
setInterval(loadAlarms, 15000);  // refresh list periodically
</script>
</body>
</html>
"""


def create_flask_app():
    from flask import Flask, jsonify, request, render_template_string

    app = Flask(__name__)

    init_db()

    # Track which alarms are currently ringing (server-side)
    ringing_alarm = {"id": None, "suppressed_until": None}

    @app.route("/")
    def index():
        return render_template_string(HTML_TEMPLATE)

    @app.route("/api/alarms", methods=["GET"])
    def get_alarms():
        alarms = db_get_all_alarms()
        return jsonify({"alarms": [a.to_dict() for a in alarms]})

    @app.route("/api/alarms", methods=["POST"])
    def add_alarm():
        data = request.get_json(force=True)
        hour = int(data.get("hour", 0))
        minute = int(data.get("minute", 0))
        label = str(data.get("label", "Alarm")).strip() or "Alarm"
        repeat = bool(data.get("repeat", False))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return jsonify({"error": "Invalid time"}), 400
        alarm_id = db_add_alarm(hour, minute, label, repeat)
        return jsonify({"success": True, "id": alarm_id})

    @app.route("/api/alarms/<int:alarm_id>/toggle", methods=["POST"])
    def toggle_alarm(alarm_id):
        db_toggle_alarm(alarm_id)
        return jsonify({"success": True})

    @app.route("/api/alarms/<int:alarm_id>/snooze", methods=["POST"])
    def snooze_alarm(alarm_id):
        db_snooze_alarm(alarm_id, SNOOZE_MINUTES)
        # If this alarm was ringing, clear the ringing state
        if ringing_alarm["id"] == alarm_id:
            ringing_alarm["id"] = None
        return jsonify({"success": True})

    @app.route("/api/alarms/<int:alarm_id>/dismiss", methods=["POST"])
    def dismiss_alarm(alarm_id):
        db_dismiss_alarm(alarm_id)
        if ringing_alarm["id"] == alarm_id:
            ringing_alarm["id"] = None
            # Suppress re-triggering for 60s
            ringing_alarm["suppressed_until"] = datetime.datetime.now() + datetime.timedelta(seconds=65)
        return jsonify({"success": True})

    @app.route("/api/alarms/<int:alarm_id>", methods=["DELETE"])
    def delete_alarm(alarm_id):
        db_delete_alarm(alarm_id)
        if ringing_alarm["id"] == alarm_id:
            ringing_alarm["id"] = None
        return jsonify({"success": True})

    @app.route("/api/poll", methods=["GET"])
    def poll():
        now = datetime.datetime.now()

        # Check suppression
        if ringing_alarm["suppressed_until"] and now < ringing_alarm["suppressed_until"]:
            return jsonify({"ringing": False})
        if ringing_alarm["suppressed_until"] and now >= ringing_alarm["suppressed_until"]:
            ringing_alarm["suppressed_until"] = None

        # If already ringing, keep returning it
        if ringing_alarm["id"]:
            alarms = db_get_all_alarms()
            for a in alarms:
                if a.id == ringing_alarm["id"] and a.active:
                    return jsonify({"ringing": True, "alarm": a.to_dict()})
            # Alarm was deleted or deactivated
            ringing_alarm["id"] = None

        # Check all alarms for triggering
        alarms = db_get_all_alarms()
        for a in alarms:
            if not a.active:
                continue
            if a.snoozed_until:
                if now >= a.snoozed_until:
                    db_clear_snooze(a.id)
                    ringing_alarm["id"] = a.id
                    return jsonify({"ringing": True, "alarm": a.to_dict()})
                continue
            if now.hour == a.hour and now.minute == a.minute:
                ringing_alarm["id"] = a.id
                # Play server-side sound in background
                threading.Thread(target=play_alarm_sound, args=(2,), daemon=True).start()
                return jsonify({"ringing": True, "alarm": a.to_dict()})

        return jsonify({"ringing": False})

    return app


# ─── Original Tkinter GUI (preserved) ─────────────────────────────────────────

def launch_tkinter_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    class AlarmClockApp(tk.Tk):
        SNOOZE_MINUTES = 5

        def __init__(self):
            super().__init__()
            self.title("⏰ Alarm Clock")
            self.geometry("560x660")
            self.configure(bg=C["bg"])
            self.resizable(False, True)
            self.alarms: list[Alarm] = []
            self.ringing: Alarm | None = None
            self._build_ui()
            self._tick()
            self._start_alarm_thread()

        def _build_ui(self):
            self.clock_var = tk.StringVar(value="00:00:00")
            clock_frame = tk.Frame(self, bg=C["bg"])
            clock_frame.pack(fill="x", pady=(20, 0))
            self.clock_lbl = tk.Label(
                clock_frame, textvariable=self.clock_var,
                font=("Courier", 52, "bold"), bg=C["bg"], fg=C["accent"]
            )
            self.clock_lbl.pack()
            self.date_lbl = tk.Label(
                clock_frame, text="", font=("Helvetica", 12),
                bg=C["bg"], fg=C["muted"]
            )
            self.date_lbl.pack(pady=(0, 6))
            tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)
            add_card = tk.Frame(self, bg=C["card"], bd=0)
            add_card.pack(fill="x", padx=20, pady=4)
            tk.Label(add_card, text="Set New Alarm", font=("Helvetica", 12, "bold"),
                     bg=C["card"], fg=C["text"]).grid(row=0, column=0, columnspan=4,
                     sticky="w", padx=14, pady=(10, 4))
            lbl_style = dict(bg=C["card"], fg=C["muted"], font=("Helvetica", 10))
            spin_style = dict(bg=C["bg"], fg=C["text"], font=("Courier", 14, "bold"),
                              relief="flat", bd=4, insertbackground=C["text"], width=3)
            tk.Label(add_card, text="HH", **lbl_style).grid(row=1, column=0, padx=(14, 2))
            self.hour_spin = tk.Spinbox(add_card, from_=0, to=23, wrap=True,
                                        format="%02.0f", **spin_style)
            self.hour_spin.grid(row=1, column=1, padx=2)
            tk.Label(add_card, text="MM", **lbl_style).grid(row=1, column=2, padx=2)
            self.min_spin = tk.Spinbox(add_card, from_=0, to=59, wrap=True,
                                       format="%02.0f", **spin_style)
            self.min_spin.grid(row=1, column=3, padx=2)
            tk.Label(add_card, text="Label", **lbl_style).grid(row=2, column=0,
                     padx=(14, 2), pady=(6, 0))
            self.label_entry = tk.Entry(add_card, bg=C["bg"], fg=C["text"],
                                        insertbackground=C["text"], relief="flat",
                                        bd=4, font=("Helvetica", 11), width=20)
            self.label_entry.insert(0, "Wake up!")
            self.label_entry.grid(row=2, column=1, columnspan=2, pady=(6, 0), sticky="w")
            self.repeat_var = tk.BooleanVar(value=False)
            tk.Checkbutton(add_card, text="Repeat Daily", variable=self.repeat_var,
                           bg=C["card"], fg=C["muted"], selectcolor=C["bg"],
                           activebackground=C["card"], font=("Helvetica", 10)
                           ).grid(row=2, column=3, padx=6, pady=(6, 0))
            tk.Button(
                add_card, text="  ➕ Add Alarm  ", command=self._add_alarm,
                bg=C["accent"], fg=C["white"], font=("Helvetica", 11, "bold"),
                relief="flat", cursor="hand2", pady=6
            ).grid(row=3, column=0, columnspan=4, pady=12)
            tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=20, pady=4)
            tk.Label(self, text="🔔  Alarms", font=("Helvetica", 12, "bold"),
                     bg=C["bg"], fg=C["text"]).pack(anchor="w", padx=24, pady=(4, 2))
            list_frame = tk.Frame(self, bg=C["bg"])
            list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
            sb = tk.Scrollbar(list_frame)
            sb.pack(side="right", fill="y")
            self.alarm_listbox = tk.Listbox(
                list_frame, yscrollcommand=sb.set,
                bg=C["card"], fg=C["text"], font=("Courier", 11),
                selectbackground=C["accent"], relief="flat", bd=0,
                activestyle="none", height=8
            )
            self.alarm_listbox.pack(fill="both", expand=True)
            sb.config(command=self.alarm_listbox.yview)
            btn_row = tk.Frame(self, bg=C["bg"])
            btn_row.pack(fill="x", padx=20, pady=(0, 16))
            bstyle = dict(font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2", pady=5)
            tk.Button(btn_row, text="🔕 Toggle ON/OFF", command=self._toggle_alarm,
                      bg=C["yellow"], fg=C["bg"], **bstyle).pack(side="left", expand=True, padx=2)
            tk.Button(btn_row, text="💤 Snooze", command=self._snooze_alarm,
                      bg=C["green"], fg=C["bg"], **bstyle).pack(side="left", expand=True, padx=2)
            tk.Button(btn_row, text="🗑 Delete", command=self._delete_alarm,
                      bg=C["red"], fg=C["white"], **bstyle).pack(side="left", expand=True, padx=2)

        def _tick(self):
            now = datetime.datetime.now()
            self.clock_var.set(now.strftime("%H:%M:%S"))
            self.date_lbl.config(text=now.strftime("%A, %d %B %Y"))
            self.after(1000, self._tick)

        def _start_alarm_thread(self):
            def checker():
                while True:
                    now = datetime.datetime.now()
                    for alarm in self.alarms:
                        if not alarm.active:
                            continue
                        if alarm.snoozed_until:
                            if now >= alarm.snoozed_until:
                                alarm.snoozed_until = None
                                self.after(0, lambda a=alarm: self._ring_alarm(a))
                            continue
                        if now.hour == alarm.hour and now.minute == alarm.minute and now.second == 0:
                            self.after(0, lambda a=alarm: self._ring_alarm(a))
                    time.sleep(1)
            threading.Thread(target=checker, daemon=True).start()

        def _ring_alarm(self, alarm):
            self.ringing = alarm
            self._refresh_list()
            self.clock_lbl.config(fg=C["red"])
            self.after(1000, lambda: self.clock_lbl.config(fg=C["accent"]))
            threading.Thread(target=play_alarm_sound, args=(4,), daemon=True).start()
            answer = messagebox.askquestion(
                "⏰ ALARM!",
                f"Alarm: {alarm.label}\nTime: {alarm.time_str}\n\nSnooze for {self.SNOOZE_MINUTES} min?",
                icon="warning"
            )
            if answer == "yes":
                self._snooze_alarm(alarm)
            else:
                if not alarm.repeat:
                    alarm.active = False
                self.ringing = None
            self._refresh_list()

        def _add_alarm(self):
            try:
                hour = int(self.hour_spin.get())
                minute = int(self.min_spin.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid hour or minute.")
                return
            label = self.label_entry.get().strip() or "Alarm"
            repeat = self.repeat_var.get()
            alarm = Alarm(hour, minute, label, repeat)
            self.alarms.append(alarm)
            self._refresh_list()

        def _get_selected_alarm(self):
            sel = self.alarm_listbox.curselection()
            if not sel:
                messagebox.showinfo("Select", "Please select an alarm first.")
                return None
            idx = sel[0]
            if idx < len(self.alarms):
                return self.alarms[idx]
            return None

        def _toggle_alarm(self):
            alarm = self._get_selected_alarm()
            if alarm:
                alarm.active = not alarm.active
                self._refresh_list()

        def _snooze_alarm(self, alarm=None):
            a = alarm or self._get_selected_alarm()
            if a:
                a.snoozed_until = datetime.datetime.now() + datetime.timedelta(minutes=self.SNOOZE_MINUTES)
                self._refresh_list()

        def _delete_alarm(self):
            alarm = self._get_selected_alarm()
            if alarm and messagebox.askyesno("Delete", f"Delete alarm '{alarm.label}'?"):
                self.alarms.remove(alarm)
                self._refresh_list()

        def _refresh_list(self):
            self.alarm_listbox.delete(0, tk.END)
            if not self.alarms:
                self.alarm_listbox.insert(tk.END, "  No alarms set.")
                return
            for a in self.alarms:
                repeat_tag = " 🔁" if a.repeat else ""
                line = f"  {'🔔' if a.active else '🔕'}  {a.time_str}   {a.label:<20} [{a.status}]{repeat_tag}"
                self.alarm_listbox.insert(tk.END, line)

    app = AlarmClockApp()
    app.mainloop()


# ─── Entry Point ───────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║               ⏰  ALARM CLOCK  — Web Edition             ║
║══════════════════════════════════════════════════════════║
║  Server   : http://127.0.0.1:5003                       ║
║  Database : alarms.db (SQLite)                           ║
║  Mode     : Flask Web UI                                 ║
║  Stop     : Ctrl+C                                       ║
╚══════════════════════════════════════════════════════════╝
"""

if __name__ == "__main__":
    if "--gui" in sys.argv:
        launch_tkinter_gui()
    else:
        print(BANNER)
        flask_app = create_flask_app()
        # Auto-open browser after a short delay
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5003")).start()
        flask_app.run(host="127.0.0.1", port=5003, debug=False)

#!/usr/bin/env python3
"""
============================================================
  PROJECT 3: Online Quiz Platform (QuizVault)
  Customizable quizzes, scoring, leaderboard & analytics
  Flask Web UI on port 5004 with SQLite persistence
============================================================
"""

import json
import random
import datetime
import time
import sys
import os
import sqlite3
import hashlib
import threading
import webbrowser
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from collections import defaultdict
from flask import Flask, request, jsonify, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

# Ensure UTF-8 output on Windows consoles to support emojis
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith('cp'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        # Fallback for older Python versions
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

# ── Data Models ────────────────────────────────────────────────

@dataclass
class Question:
    id          : int
    text        : str
    options     : List[str]
    answer_index: int                # 0-based index into options
    category    : str  = "General"
    difficulty  : str  = "Medium"   # Easy | Medium | Hard
    explanation : str  = ""
    points      : int  = 10

    def is_correct(self, choice: int) -> bool:
        return choice == self.answer_index

    def correct_answer(self) -> str:
        return self.options[self.answer_index]


@dataclass
class Quiz:
    id         : int
    title      : str
    description: str
    questions  : List[Question] = field(default_factory=list)
    time_limit : int  = 0       # seconds; 0 = no limit
    shuffle    : bool = True
    category   : str  = "General"
    created_by : str  = "Admin"
    created_at : str  = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def total_points(self) -> int:
        return sum(q.points for q in self.questions)

    def add_question(self, question: Question):
        self.questions.append(question)


@dataclass
class QuizResult:
    quiz_id      : int
    quiz_title   : str
    username     : str
    score        : int
    total_points : int
    correct      : int
    total_q      : int
    time_taken   : float          # seconds
    timestamp    : str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    answers      : List[int] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        return (self.score / self.total_points * 100) if self.total_points else 0

    @property
    def grade(self) -> str:
        p = self.percentage
        if p >= 90: return "A+"
        if p >= 80: return "A"
        if p >= 70: return "B"
        if p >= 60: return "C"
        if p >= 50: return "D"
        return "F"

    def summary(self) -> str:
        mins, secs = divmod(int(self.time_taken), 60)
        return (f"  Quiz:     {self.quiz_title}\n"
                f"  Score:    {self.score}/{self.total_points} ({self.percentage:.1f}%) — Grade: {self.grade}\n"
                f"  Correct:  {self.correct}/{self.total_q}\n"
                f"  Time:     {mins}m {secs}s\n"
                f"  Date:     {self.timestamp[:10]}")


# ── Question Bank ──────────────────────────────────────────────

class QuestionBank:
    """Pre-built questions across multiple categories."""

    @staticmethod
    def python_questions() -> List[Question]:
        data = [
            (1, "What keyword defines a function in Python?",
             ["function", "def", "fun", "define"], 1, "Easy", 5,
             "'def' is the keyword used to define functions in Python."),
            (2, "Which data structure is ordered and mutable?",
             ["tuple", "set", "list", "frozenset"], 2, "Easy", 5,
             "Lists are ordered and mutable; tuples are ordered but immutable."),
            (3, "What does 'len([1,2,3])' return?",
             ["2", "3", "4", "1"], 1, "Easy", 5,
             "len() returns the number of elements in the list."),
            (4, "Which is NOT a Python built-in data type?",
             ["list", "dict", "array", "tuple"], 2, "Medium", 10,
             "'array' is not built-in; it needs import array or numpy."),
            (5, "What does __init__ do in a class?",
             ["Deletes the object", "Initializes object attributes",
              "Defines class methods", "Imports modules"], 1, "Medium", 10,
             "__init__ is the constructor called when an object is created."),
            (6, "What is the output of: print(type(1.0))?",
             ["<class 'int'>", "<class 'str'>", "<class 'float'>", "<class 'num'>"],
             2, "Easy", 5, "1.0 is a float literal."),
            (7, "Which decorator makes a function run only once at import?",
             ["@staticmethod", "@classmethod", "@property", "None — use module level"],
             3, "Hard", 15, "Module-level code runs once at import time."),
            (8, "What does 'yield' do?",
             ["Returns a value and exits", "Pauses and produces a value",
              "Raises an exception", "Imports a module"], 1, "Medium", 10,
             "'yield' turns a function into a generator."),
        ]
        return [Question(id=d[0], text=d[1], options=d[2], answer_index=d[3],
                          category="Python", difficulty=d[4], points=d[5],
                          explanation=d[6]) for d in data]

    @staticmethod
    def science_questions() -> List[Question]:
        data = [
            (9,  "What is the chemical symbol for water?",
             ["WA", "H2O", "HO", "H2"], 1, "Easy", 5,
             "Water is H2O — two hydrogen atoms and one oxygen atom."),
            (10, "How many planets are in our solar system?",
             ["7", "8", "9", "10"], 1, "Easy", 5,
             "8 planets after Pluto was reclassified in 2006."),
            (11, "What gas do plants absorb from the atmosphere?",
             ["Oxygen", "Nitrogen", "Carbon Dioxide", "Hydrogen"], 2, "Easy", 5,
             "Plants absorb CO2 for photosynthesis."),
            (12, "What is the speed of light (approx.)?",
             ["300,000 km/s", "150,000 km/s", "500,000 km/s", "1,000 km/s"],
             0, "Medium", 10,
             "Light travels at approximately 299,792 km/s."),
            (13, "DNA stands for?",
             ["Dynamic Nuclear Acid", "Deoxyribonucleic Acid",
              "Dinitrogen Acid", "Deoxyribose Nitrogen Atom"], 1, "Medium", 10,
             "DNA = Deoxyribonucleic Acid."),
            (14, "What force keeps planets in orbit?",
             ["Magnetism", "Nuclear force", "Gravity", "Friction"], 2, "Easy", 5,
             "Gravity provides the centripetal force for orbital motion."),
        ]
        return [Question(id=d[0], text=d[1], options=d[2], answer_index=d[3],
                          category="Science", difficulty=d[4], points=d[5],
                          explanation=d[6]) for d in data]

    @staticmethod
    def math_questions() -> List[Question]:
        data = [
            (15, "What is the square root of 144?",
             ["11", "12", "13", "14"], 1, "Easy", 5, "12 × 12 = 144."),
            (16, "Solve: 2x + 4 = 12  →  x = ?",
             ["3", "4", "5", "6"], 1, "Medium", 10, "2x = 8, x = 4."),
            (17, "What is the value of π (pi) to 2 decimal places?",
             ["3.12", "3.14", "3.16", "3.41"], 1, "Easy", 5,
             "π ≈ 3.14159..."),
            (18, "What is 15% of 200?",
             ["20", "25", "30", "35"], 2, "Medium", 10, "200 × 0.15 = 30."),
            (19, "A triangle has angles 60°, 70°, and ___°?",
             ["40", "50", "60", "70"], 1, "Easy", 5,
             "Angles in a triangle sum to 180°: 180-60-70=50."),
            (20, "log₁₀(1000) = ?",
             ["2", "3", "4", "10"], 1, "Medium", 10,
             "10³ = 1000, so log₁₀(1000) = 3."),
        ]
        return [Question(id=d[0], text=d[1], options=d[2], answer_index=d[3],
                          category="Math", difficulty=d[4], points=d[5],
                          explanation=d[6]) for d in data]

    @classmethod
    def all_questions(cls) -> List[Question]:
        return cls.python_questions() + cls.science_questions() + cls.math_questions()


# ── Quiz Platform ──────────────────────────────────────────────

class QuizPlatform:
    def __init__(self):
        self.quizzes  : dict[int, Quiz]        = {}
        self.results  : List[QuizResult]       = []
        self.users    : dict[str, dict]        = {}
        self._next_quiz_id = 1
        self._load_default_quizzes()

    # ── Setup ──────────────────────────────────────────────────

    def _load_default_quizzes(self):
        bank = QuestionBank()

        q1 = Quiz(id=self._next_quiz_id, title="Python Fundamentals",
                  description="Test your Python programming knowledge.",
                  time_limit=120, category="Programming", created_by="Admin")
        for q in bank.python_questions():
            q1.add_question(q)
        self.quizzes[q1.id] = q1
        self._next_quiz_id += 1

        q2 = Quiz(id=self._next_quiz_id, title="Science Explorer",
                  description="Explore the wonders of science!",
                  time_limit=90, category="Science", created_by="Admin")
        for q in bank.science_questions():
            q2.add_question(q)
        self.quizzes[q2.id] = q2
        self._next_quiz_id += 1

        q3 = Quiz(id=self._next_quiz_id, title="Math Mastery",
                  description="Challenge your mathematical skills.",
                  time_limit=120, category="Math", created_by="Admin")
        for q in bank.math_questions():
            q3.add_question(q)
        self.quizzes[q3.id] = q3
        self._next_quiz_id += 1

        q4 = Quiz(id=self._next_quiz_id, title="Mixed Challenge",
                  description="Python + Science + Math — the ultimate test!",
                  time_limit=180, category="Mixed", created_by="Admin")
        
        # Pull 10 random questions safely (make sure we don't exceed length)
        all_qs = QuestionBank.all_questions()
        sample = random.sample(all_qs, min(10, len(all_qs)))
        for q in sample:
            q4.add_question(q)
        self.quizzes[q4.id] = q4
        self._next_quiz_id += 1

    def create_quiz(self, title: str, description: str, category: str,
                    time_limit: int, questions: List[Question],
                    created_by: str = "User") -> Quiz:
        quiz = Quiz(id=self._next_quiz_id, title=title,
                    description=description, category=category,
                    time_limit=time_limit, created_by=created_by)
        for q in questions:
            quiz.add_question(q)
        self.quizzes[quiz.id] = quiz
        self._next_quiz_id += 1
        return quiz

    def register_user(self, username: str):
        if username not in self.users:
            self.users[username] = {
                "username": username,
                "joined":   datetime.datetime.now().isoformat(),
                "quizzes_taken": 0,
                "total_score":   0,
                "best_grade":    "N/A",
            }

    # ── Take a Quiz ────────────────────────────────────────────

    def take_quiz(self, quiz_id: int, username: str,
                  auto_answers: Optional[List[int]] = None) -> Optional[QuizResult]:
        """
        Take a quiz. If auto_answers provided (for demo), answers automatically.
        Otherwise prompts the user interactively.
        """
        quiz = self.quizzes.get(quiz_id)
        if not quiz:
            print(f"  ❌ Quiz #{quiz_id} not found.")
            return None

        self.register_user(username)
        questions = list(quiz.questions)
        if quiz.shuffle:
            random.shuffle(questions)

        answers    = []
        score      = 0
        correct    = 0
        start_time = time.time()

        if auto_answers is None:
            # Interactive mode
            print(f"\n{'='*56}")
            print(f"  📝 {quiz.title}")
            print(f"  {quiz.description}")
            if quiz.time_limit:
                print(f"  ⏱  Time Limit: {quiz.time_limit // 60}m {quiz.time_limit % 60}s")
            print(f"  Questions: {len(questions)}  |  Max Score: {quiz.total_points()}")
            print(f"{'='*56}\n")

            for i, q in enumerate(questions, 1):
                elapsed = time.time() - start_time
                if quiz.time_limit and elapsed >= quiz.time_limit:
                    print("\n  ⏰ Time's up!")
                    break

                diff_icon = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(q.difficulty, "⚪")
                print(f"  Q{i}/{len(questions)} {diff_icon} [{q.category}] ({q.points} pts)")
                print(f"  {q.text}")
                for j, opt in enumerate(q.options, 1):
                    print(f"    {j}. {opt}")

                while True:
                    try:
                        raw = input(f"\n  Your answer (1-{len(q.options)}): ").strip()
                        choice = int(raw) - 1
                        if 0 <= choice < len(q.options):
                            break
                        print(f"  ❌ Enter a number between 1 and {len(q.options)}.")
                    except ValueError:
                        print("  ❌ Please enter a number.")

                answers.append(choice)
                if q.is_correct(choice):
                    score += q.points
                    correct += 1
                    print("  ✅ Correct!")
                else:
                    print(f"  ❌ Wrong! Correct answer: {q.correct_answer()}")
                if q.explanation:
                    print(f"  💡 {q.explanation}")
                print()
        else:
            # Automated mode (demo)
            ans_iter = iter(auto_answers + [0] * len(questions))
            for q in questions:
                choice = next(ans_iter)
                answers.append(choice)
                if q.is_correct(choice):
                    score += q.points
                    correct += 1

        time_taken = time.time() - start_time
        result = QuizResult(
            quiz_id=quiz_id, quiz_title=quiz.title,
            username=username, score=score,
            total_points=quiz.total_points(),
            correct=correct, total_q=len(questions),
            time_taken=time_taken, answers=answers,
        )

        self.results.append(result)
        u = self.users[username]
        u['quizzes_taken'] += 1
        u['total_score']   += score
        # Update best grade based on ranking
        def _grade_rank(g):
            return {"A+":5, "A":4, "B":3, "C":2, "D":1, "F":0}.get(g, -1)
        if u['best_grade'] == 'N/A' or _grade_rank(result.grade) > _grade_rank(u['best_grade']):
            u['best_grade'] = result.grade

        return result

    # ── Leaderboard ────────────────────────────────────────────

    def leaderboard(self, quiz_id: Optional[int] = None, top_n: int = 10) -> List[dict]:
        results = [r for r in self.results if (quiz_id is None or r.quiz_id == quiz_id)]
        best    = {}
        for r in results:
            key = (r.username, r.quiz_id)
            if key not in best or r.percentage > best[key].percentage:
                best[key] = r
        board = sorted(best.values(), key=lambda r: (-r.percentage, r.time_taken))
        return [
            {"rank": i+1, "user": r.username,
             "quiz": r.quiz_title, "score": r.score,
             "total": r.total_points, "pct": r.percentage,
             "grade": r.grade, "time": r.time_taken}
            for i, r in enumerate(board[:top_n])
        ]

    def print_leaderboard(self, quiz_id: Optional[int] = None):
        board = self.leaderboard(quiz_id)
        title = f"Quiz #{quiz_id}" if quiz_id else "All Quizzes"
        print(f"\n  🏆 LEADERBOARD — {title}")
        print(f"  {'Rank':<5} {'User':<12} {'Quiz':<24} {'Score':<10} {'%':<7} {'Grade':<6} {'Time'}")
        print("  " + "-" * 75)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for e in board:
            mins, secs = divmod(int(e['time']), 60)
            medal = medals.get(e['rank'], f"  {e['rank']}")
            print(f"  {medal:<5} {e['user']:<12} {e['quiz']:<24} "
                  f"{e['score']}/{e['total']:<7} {e['pct']:<7.1f} {e['grade']:<6} {mins}m{secs}s")

    def print_quiz_stats(self, quiz_id: int):
        results = [r for r in self.results if r.quiz_id == quiz_id]
        if not results:
            print("  No results for this quiz yet.")
            return
        quiz = self.quizzes[quiz_id]
        avg_pct  = sum(r.percentage for r in results) / len(results)
        avg_time = sum(r.time_taken for r in results) / len(results)
        best     = max(results, key=lambda r: r.percentage)
        print(f"\n  📊 Stats for '{quiz.title}':")
        print(f"     Attempts:   {len(results)}")
        print(f"     Avg Score:  {avg_pct:.1f}%")
        print(f"     Best Score: {best.percentage:.1f}% by {best.username}")
        print(f"     Avg Time:   {avg_time:.1f}s")


# ── Demo & CLI Verification ───────────────────────────────────

def run_demo():
    print("=" * 56)
    print("  📝  ONLINE QUIZ PLATFORM — DEMO")
    print("=" * 56)

    platform = QuizPlatform()

    # Show available quizzes
    print(f"\n  📚 Available Quizzes ({len(platform.quizzes)}):")
    for qid, q in platform.quizzes.items():
        tl = f"{q.time_limit}s" if q.time_limit else "No limit"
        print(f"     [{qid}] {q.title:<28} | {len(q.questions)} Qs | {tl} | {q.category}")

    # Simulate attempts
    scenarios = [
        ("Alice",   [1, 2, 1, 2, 1, 0, 3, 1]),
        ("Bob",     [1, 2, 1, 1, 1, 2, 1, 1]),
        ("Charlie", [0, 0, 0, 0, 0, 0, 0, 0]),
    ]
    for name, auto_ans in scenarios:
        platform.take_quiz(1, name, auto_answers=auto_ans)

    platform.print_leaderboard(quiz_id=1)
    platform.print_quiz_stats(1)
    print("\n  ✅ CLI Demo complete!")


def run_interactive():
    platform = QuizPlatform()
    print("\n  Welcome to the Online Quiz Platform!")
    username = input("  Enter your username: ").strip() or "Guest"
    platform.register_user(username)

    while True:
        print(f"\n  ── Menu ──────────────────────────────")
        print(f"  [1] Take a Quiz")
        print(f"  [2] View Leaderboard")
        print(f"  [3] View Quizzes")
        print(f"  [0] Exit")
        choice = input("  Choice: ").strip()

        if choice == '0':
            print(f"  Goodbye, {username}! 👋")
            break
        elif choice == '1':
            print("\n  Available Quizzes:")
            for qid, q in platform.quizzes.items():
                print(f"    [{qid}] {q.title}")
            try:
                qid = int(input("  Select quiz ID: ").strip())
                result = platform.take_quiz(qid, username)
                if result:
                    print(f"\n  ─── Your Result ───")
                    print(result.summary())
            except (ValueError, KeyError):
                print("  ❌ Invalid quiz ID.")
        elif choice == '2':
            platform.print_leaderboard()
        elif choice == '3':
            for qid, q in platform.quizzes.items():
                print(f"  [{qid}] {q.title} — {len(q.questions)} questions")


# ══════════════════════════════════════════════════════════════════
#  FLASK WEB APPLICATION
# ══════════════════════════════════════════════════════════════════

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz_platform.db")
platform = QuizPlatform()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            quiz_title TEXT NOT NULL,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_points INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            total_q INTEGER NOT NULL,
            time_taken REAL NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            answers TEXT DEFAULT '[]',
            timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS custom_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'Custom',
            time_limit INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'User',
            questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()

    # Load saved results into platform memory
    rows = conn.execute("SELECT * FROM quiz_results ORDER BY id").fetchall()
    for r in rows:
        result = QuizResult(
            quiz_id=r["quiz_id"], quiz_title=r["quiz_title"],
            username=r["username"], score=r["score"],
            total_points=r["total_points"], correct=r["correct"],
            total_q=r["total_q"], time_taken=r["time_taken"],
            timestamp=r["timestamp"], answers=json.loads(r["answers"])
        )
        platform.results.append(result)

    # Load saved custom quizzes
    crows = conn.execute("SELECT * FROM custom_quizzes ORDER BY id").fetchall()
    for cr in crows:
        qs_data = json.loads(cr["questions_json"])
        questions = [Question(**qd) for qd in qs_data]
        platform.create_quiz(
            title=cr["title"], description=cr["description"],
            category=cr["category"], time_limit=cr["time_limit"],
            questions=questions, created_by=cr["created_by"]
        )

    conn.close()


def save_result_to_db(result: QuizResult):
    conn = get_db()
    conn.execute("""
        INSERT INTO quiz_results (quiz_id, quiz_title, username, score, total_points,
            correct, total_q, time_taken, percentage, grade, answers, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (result.quiz_id, result.quiz_title, result.username, result.score,
          result.total_points, result.correct, result.total_q, result.time_taken,
          result.percentage, result.grade, json.dumps(result.answers), result.timestamp))
    conn.commit()
    conn.close()


# ── HTML Template ──────────────────────────────────────────────
# Built as a gorgeous modern single-page-app with rich aesthetics.

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuizVault — Ultimate Online Quiz & Assessment Platform</title>
<meta name="description" content="Take quizzes, compete on leaderboards, check dynamic statistics and download official verified certificates.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
<!-- Chart.js CDN -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

:root {
  --accent: #8b5cf6;
  --accent-light: #a78bfa;
  --accent-dim: #6d28d9;
  --accent-glow: rgba(139, 92, 246, 0.3);
  --bg-deep: #09090c;
  --bg-surface: #121217;
  --bg-card: rgba(255, 255, 255, 0.03);
  --bg-card-hover: rgba(255, 255, 255, 0.06);
  --glass-border: rgba(255, 255, 255, 0.06);
  --glass-border-hover: rgba(139, 92, 246, 0.35);
  --text-primary: #fafafa;
  --text-secondary: rgba(250, 250, 250, 0.6);
  --text-tertiary: rgba(250, 250, 250, 0.35);
  --green: #10b981;
  --green-dim: rgba(16, 185, 129, 0.1);
  --red: #ef4444;
  --red-dim: rgba(239, 68, 68, 0.1);
  --yellow: #f59e0b;
  --yellow-dim: rgba(245, 158, 11, 0.1);
  --blue: #3b82f6;
  --blue-dim: rgba(59, 130, 246, 0.1);
  --radius: 20px;
  --radius-sm: 12px;
  --radius-xs: 8px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  --shadow-lg: 0 20px 40px rgba(0, 0, 0, 0.5);
}

html { font-size: 15px; scroll-behavior: smooth; }

body {
  font-family: 'Outfit', sans-serif;
  background: var(--bg-deep);
  color: var(--text-primary);
  min-height: 100vh;
  overflow-x: hidden;
  position: relative;
}

body::before {
  content: '';
  position: fixed; inset: 0;
  background:
    radial-gradient(ellipse 70% 50% at 10% 10%, rgba(139,92,246,0.09) 0%, transparent 60%),
    radial-gradient(ellipse 55% 45% at 90% 90%, rgba(59,130,246,0.05) 0%, transparent 60%),
    radial-gradient(ellipse 50% 50% at 50% 50%, rgba(9,9,12,0.96) 0%, transparent 100%);
  pointer-events: none; z-index: 0;
}

.mono { font-family: 'JetBrains Mono', monospace; }

/* Confetti Canvas */
#confetti-canvas { position: fixed; inset: 0; pointer-events: none; z-index: 9999; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.2); border-radius: 99px; }

/* Navbar */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(9,9,12,0.75);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border-bottom: 1px solid var(--glass-border);
  padding: 0 24px;
}
.navbar-inner {
  max-width: 1100px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  height: 65px;
}
.nav-brand {
  display: flex; align-items: center; gap: 10px;
  font-size: 1.35rem; font-weight: 800;
  background: linear-gradient(135deg, var(--accent-light) 0%, #c084fc 50%, #818cf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text; cursor: default;
}
.nav-brand-icon {
  width: 34px; height: 34px;
  background: linear-gradient(135deg, var(--accent), #818cf8);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.15rem; font-weight: 800;
  color: #fff;
  -webkit-text-fill-color: white;
}
.nav-tabs { display: flex; gap: 6px; }
.nav-tab {
  padding: 8px 16px; border-radius: var(--radius-xs);
  background: transparent; border: none;
  color: var(--text-secondary);
  font-family: inherit; font-size: 0.88rem; font-weight: 600;
  cursor: pointer; transition: var(--transition);
  display: flex; align-items: center; gap: 8px;
}
.nav-tab:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }
.nav-tab.active {
  background: rgba(139,92,246,0.12); color: var(--accent-light);
  border: 1px solid rgba(139,92,246,0.2);
}
.nav-user { display: flex; align-items: center; gap: 12px; }
.nav-avatar {
  width: 36px; height: 36px;
  border-radius: 50%; border: 2px solid var(--accent);
  background: linear-gradient(135deg, var(--accent-dim), #4f46e5);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.95rem; font-weight: 700; color: #fff;
}
.nav-username { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
.nav-logout {
  padding: 6px 14px; border-radius: var(--radius-xs);
  background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
  color: var(--text-secondary); font-size: 0.78rem; font-weight: 600;
  cursor: pointer; transition: var(--transition);
  font-family: inherit;
}
.nav-logout:hover { background: var(--red-dim); color: var(--red); border-color: rgba(239,68,68,0.3); }

/* App Shell */
.app-shell {
  position: relative; z-index: 1;
  max-width: 1100px; margin: 0 auto;
  padding: 32px 24px 60px;
}

/* Glass Card */
.glass {
  background: var(--bg-card);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  backdrop-filter: blur(24px) saturate(1.2);
  -webkit-backdrop-filter: blur(24px) saturate(1.2);
  transition: var(--transition);
}
.glass:hover {
  background: var(--bg-card-hover);
  border-color: var(--glass-border-hover);
}

/* Auth Card */
.auth-container {
  display: flex; align-items: center; justify-content: center;
  min-height: 70vh; animation: fadeSlideUp 0.5s ease;
}
.auth-card {
  width: 100%; max-width: 420px; padding: 40px 32px;
  border-radius: var(--radius); text-align: center;
}
.auth-icon { font-size: 3rem; margin-bottom: 16px; display: inline-block; }
.auth-card h2 { font-size: 1.75rem; font-weight: 800; margin-bottom: 8px; }
.auth-card p { font-size: 0.92rem; color: var(--text-secondary); margin-bottom: 28px; }
.auth-form-group { text-align: left; margin-bottom: 20px; }
.auth-form-group label {
  display: block; font-size: 0.78rem; font-weight: 700;
  color: var(--text-secondary); text-transform: uppercase;
  letter-spacing: 0.8px; margin-bottom: 6px;
}
.auth-form-group input {
  width: 100%; padding: 12px 16px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  background: rgba(0,0,0,0.2); color: var(--text-primary);
  font-family: inherit; font-size: 0.95rem; outline: none;
  transition: var(--transition);
}
.auth-form-group input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.auth-btn { width: 100%; padding: 12px; margin-top: 10px; }
.auth-switch {
  margin-top: 20px; font-size: 0.88rem; color: var(--text-secondary);
}
.auth-switch a { color: var(--accent-light); text-decoration: none; font-weight: 600; cursor: pointer; }
.auth-switch a:hover { text-decoration: underline; }

/* Grid views */
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 24px; flex-wrap: wrap; gap: 12px;
}
.section-title {
  font-size: 1.3rem; font-weight: 800;
  display: flex; align-items: center; gap: 10px;
}
.section-title .icon { font-size: 1.4rem; }
.section-badge {
  padding: 4px 12px; border-radius: 20px;
  font-size: 0.72rem; font-weight: 700;
  background: rgba(139,92,246,0.12); color: var(--accent-light);
  border: 1px solid rgba(139,92,246,0.2);
}

/* Search Bar */
.search-row {
  display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap;
}
.search-input-wrap { position: relative; flex: 1; min-width: 250px; }
.search-input {
  width: 100%; padding: 12px 16px 12px 42px;
  background: var(--bg-card); border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm); color: #fff; font-family: inherit;
  outline: none; transition: var(--transition);
}
.search-input:focus { border-color: var(--accent); box-shadow: 0 0 15px var(--accent-glow); }
.search-icon-svg {
  position: absolute; left: 16px; top: 50%; transform: translateY(-50%);
  fill: var(--text-secondary); width: 16px; height: 16px;
}
.filter-select {
  padding: 0 16px; background: var(--bg-card); border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm); color: var(--text-primary); font-family: inherit;
  outline: none; cursor: pointer; min-width: 150px;
}

/* Quiz Card */
.quiz-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 24px; margin-bottom: 40px;
}
.quiz-card {
  padding: 28px; cursor: default;
  animation: fadeSlideUp 0.5s ease both;
  position: relative; overflow: hidden;
  display: flex; flex-direction: column; justify-content: space-between;
}
.quiz-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
  background: linear-gradient(90deg, var(--accent), #818cf8);
  opacity: 0; transition: opacity var(--transition);
}
.quiz-card:hover::before { opacity: 1; }
.quiz-card .card-cat {
  display: inline-block; align-self: flex-start;
  padding: 3px 10px; border-radius: 20px;
  font-size: 0.72rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.8px;
  background: rgba(139,92,246,0.12); color: var(--accent-light);
  margin-bottom: 16px;
  border: 1px solid rgba(139,92,246,0.15);
}
.quiz-card h3 { font-size: 1.3rem; font-weight: 800; margin-bottom: 8px; }
.quiz-card .card-desc {
  font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.5;
}
.quiz-card .card-creator {
  font-size: 0.76rem; color: var(--text-tertiary); margin-bottom: 16px;
}
.quiz-card .card-meta {
  display: flex; gap: 16px; flex-wrap: wrap;
  font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 24px;
  border-top: 1px solid rgba(255,255,255,0.04); padding-top: 16px;
}
.quiz-card .card-meta span { display: flex; align-items: center; gap: 6px; }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 10px 22px; border: none; border-radius: var(--radius-sm);
  font-family: inherit; font-size: 0.9rem; font-weight: 700;
  cursor: pointer; transition: var(--transition);
  text-decoration: none; outline: none;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #7c3aed);
  color: #fff; box-shadow: 0 4px 18px var(--accent-glow);
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(139,92,246,0.45);
}
.btn-secondary {
  background: rgba(255,255,255,0.06); color: var(--text-primary);
  border: 1px solid var(--glass-border);
}
.btn-secondary:hover {
  background: rgba(255,255,255,0.1); border-color: var(--glass-border-hover);
}
.btn-danger {
  background: var(--red-dim); color: var(--red);
  border: 1px solid rgba(239,68,68,0.2);
}
.btn-danger:hover { background: rgba(239,68,68,0.18); }
.btn-sm { padding: 8px 16px; font-size: 0.8rem; border-radius: var(--radius-xs); }
.btn-start { width: 100%; }

/* Play View Layout */
.play-layout {
  display: grid; grid-template-columns: 1fr 280px; gap: 24px;
  animation: fadeSlideUp 0.4s ease both;
}
@media (max-width: 850px) {
  .play-layout { grid-template-columns: 1fr; }
}
.quiz-play-box { padding: 32px; }
.qp-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
}
.qp-title { font-size: 1.3rem; font-weight: 800; }
.qp-timer {
  font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 700;
  color: var(--accent-light); display: flex; align-items: center; gap: 6px;
  background: rgba(139,92,246,0.1); padding: 4px 12px; border-radius: 20px;
  border: 1px solid rgba(139,92,246,0.2);
}
.qp-timer.warning { color: var(--red); animation: pulse 1s ease-in-out infinite; background: var(--red-dim); border-color: rgba(239,68,68,0.2); }

.progress-wrap {
  width: 100%; height: 6px; background: rgba(255,255,255,0.06);
  border-radius: 3px; margin-bottom: 28px; overflow: hidden;
}
.progress-bar {
  height: 100%; background: linear-gradient(90deg, var(--accent), #818cf8, var(--accent));
  background-size: 200% 100%; transition: width 0.4s ease;
  animation: shimmer 2.5s linear infinite;
}
.qp-counter {
  font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; font-weight: 700;
  color: var(--text-tertiary); margin-bottom: 12px; letter-spacing: 1.2px; text-transform: uppercase;
}
.qp-question {
  font-size: 1.5rem; font-weight: 800; line-height: 1.45; margin-bottom: 28px;
}
.options-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;
}
@media (max-width: 600px) { .options-grid { grid-template-columns: 1fr; } }
.opt-btn {
  padding: 16px 20px; border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm); background: var(--bg-card);
  color: var(--text-primary); font-family: inherit; font-size: 0.95rem;
  font-weight: 500; cursor: pointer; transition: var(--transition);
  text-align: left; display: flex; align-items: center; gap: 12px;
  position: relative; overflow: hidden;
}
.opt-btn .opt-label {
  width: 28px; height: 28px; min-width: 28px; border-radius: 8px;
  background: rgba(139,92,246,0.1); display: flex; align-items: center;
  justify-content: center; font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem; font-weight: 700; color: var(--accent-light);
  transition: var(--transition);
}
.opt-btn:hover {
  border-color: var(--accent); background: rgba(139,92,246,0.06);
  box-shadow: 0 0 20px var(--accent-glow); transform: translateY(-1px);
}
.opt-btn:hover .opt-label { background: var(--accent); color: #fff; }
.opt-btn.selected {
  border-color: var(--accent-light); background: rgba(139,92,246,0.15);
  box-shadow: 0 0 20px rgba(139,92,246,0.25);
}
.opt-btn.selected .opt-label { background: var(--accent-light); color: var(--bg-deep); }
.opt-btn.correct {
  border-color: var(--green); background: rgba(16, 185, 129, 0.08);
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.2);
}
.opt-btn.correct .opt-label { background: var(--green); color: #fff; }
.opt-btn.wrong {
  border-color: var(--red); background: rgba(239, 68, 68, 0.08);
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.15);
}
.opt-btn.wrong .opt-label { background: var(--red); color: #fff; }
.opt-btn.disabled { pointer-events: none; opacity: 0.65; }

.explanation-box {
  padding: 16px 20px; border-radius: var(--radius-sm);
  background: rgba(139,92,246,0.06); border-left: 4px solid var(--accent-light);
  color: var(--text-secondary); font-size: 0.88rem; line-height: 1.6;
  margin-top: 12px; animation: fadeSlideUp 0.3s ease both;
}

/* Exam Nav Sidebar */
.exam-sidebar { padding: 24px; height: fit-content; }
.exam-sidebar h3 { font-size: 1.05rem; font-weight: 800; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px; }
.exam-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 24px; }
.exam-cell {
  aspect-ratio: 1; border-radius: var(--radius-xs); border: 1px solid var(--glass-border);
  background: rgba(0,0,0,0.15); color: var(--text-secondary); font-size: 0.85rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center; cursor: pointer; transition: var(--transition);
  font-family: 'JetBrains Mono', monospace;
}
.exam-cell:hover { border-color: var(--accent); color: #fff; }
.exam-cell.active { border-color: var(--accent-light); box-shadow: 0 0 10px var(--accent-glow); color: #fff; border-width: 2px; }
.exam-cell.answered { background: var(--accent-dim); color: #fff; border-color: var(--accent); }
.exam-cell.marked { background: var(--yellow-dim); color: var(--yellow); border-color: var(--yellow); }
.exam-actions-stack { display: flex; flex-direction: column; gap: 10px; }
.exam-btn-nav { width: 100%; display: flex; justify-content: space-between; gap: 8px; }

/* Leaderboard view */
.lb-wrap { margin-bottom: 40px; overflow: hidden; }
.lb-table { width: 100%; border-collapse: collapse; }
.lb-table thead th {
  text-align: left; padding: 14px 20px;
  font-size: 0.74rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1.2px;
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--glass-border);
  background: rgba(255,255,255,0.015);
}
.lb-table tbody td {
  padding: 14px 20px; font-size: 0.9rem;
  border-bottom: 1px solid rgba(255,255,255,0.02);
  color: var(--text-secondary);
}
.lb-table tbody tr:hover td { color: var(--text-primary); background: rgba(139,92,246,0.03); }
.lb-rank { font-family: 'JetBrains Mono', monospace; font-weight: 800; color: var(--accent-light); }
.lb-grade {
  display: inline-block; padding: 3px 8px; border-radius: 6px;
  font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.78rem;
}
.grade-ap { background: var(--green-dim); color: var(--green); }
.grade-a { background: var(--green-dim); color: var(--green); }
.grade-b { background: var(--yellow-dim); color: var(--yellow); }
.grade-c { background: rgba(59,130,246,0.1); color: var(--blue); }
.grade-d { background: var(--red-dim); color: var(--red); }
.grade-f { background: var(--red-dim); color: var(--red); }
.lb-empty { text-align: center; padding: 48px 24px; color: var(--text-tertiary); font-size: 0.92rem; }

/* My Stats view */
.stats-cards {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px;
}
@media (max-width: 768px) {
  .stats-cards { grid-template-columns: repeat(2, 1fr); }
}
.stats-card {
  padding: 24px 20px; border-radius: var(--radius); text-align: center;
}
.stats-card .sc-icon { font-size: 1.8rem; margin-bottom: 6px; }
.stats-card .sc-value {
  font-family: 'JetBrains Mono', monospace; font-size: 1.8rem; font-weight: 800;
  background: linear-gradient(135deg, var(--accent-light), #c084fc);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.stats-card .sc-label {
  font-size: 0.72rem; color: var(--text-tertiary); text-transform: uppercase;
  letter-spacing: 0.8px; margin-top: 4px;
}
.stats-visuals-grid {
  display: grid; grid-template-columns: 1.6fr 1fr; gap: 24px; margin-bottom: 32px;
}
@media (max-width: 850px) {
  .stats-visuals-grid { grid-template-columns: 1fr; }
}
.chart-box { padding: 24px; min-height: 300px; display: flex; flex-direction: column; justify-content: center; }
.achievements-box { padding: 24px; }
.achievements-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(70px, 1fr)); gap: 12px; margin-top: 16px; }
.badge-slot {
  aspect-ratio: 1; border-radius: var(--radius-sm); border: 1px solid var(--glass-border);
  background: rgba(0,0,0,0.15); display: flex; flex-direction: column; align-items: center;
  justify-content: center; cursor: pointer; position: relative; transition: var(--transition);
  filter: grayscale(1) opacity(0.4);
}
.badge-slot.unlocked {
  filter: grayscale(0) opacity(1); border-color: rgba(245,158,11,0.3);
  background: radial-gradient(circle, rgba(245,158,11,0.08) 0%, rgba(0,0,0,0.2) 100%);
}
.badge-slot.unlocked:hover {
  transform: scale(1.08) translateY(-2px); border-color: var(--yellow);
  box-shadow: 0 0 15px rgba(245,158,11,0.25);
}
.badge-icon { font-size: 1.8rem; }
.badge-tooltip {
  position: absolute; bottom: 105%; left: 50%; transform: translateX(-50%) translateY(5px);
  background: #111115; border: 1px solid var(--glass-border); color: #fff;
  padding: 6px 10px; border-radius: var(--radius-xs); font-size: 0.72rem; width: 140px;
  text-align: center; opacity: 0; pointer-events: none; transition: var(--transition);
  box-shadow: var(--shadow-lg); z-index: 10;
}
.badge-slot:hover .badge-tooltip { opacity: 1; transform: translateX(-50%) translateY(0); }
.badge-title { font-weight: 700; margin-bottom: 2px; color: var(--yellow); }

/* Results view */
.results-view { text-align: center; animation: fadeSlideUp 0.5s ease both; padding: 40px 24px; }
.result-grade-ring {
  width: 160px; height: 160px; margin: 0 auto 24px; border-radius: 50%;
  background: conic-gradient(var(--accent) calc(var(--pct) * 3.6deg), rgba(255,255,255,0.05) 0);
  display: flex; align-items: center; justify-content: center;
  animation: scaleIn 0.6s ease both;
}
.result-grade-inner {
  width: 132px; height: 132px; border-radius: 50%; background: var(--bg-deep);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.result-grade-letter {
  font-family: 'JetBrains Mono', monospace; font-size: 3rem; font-weight: 900;
  background: linear-gradient(135deg, var(--accent-light), #c084fc);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.result-pct { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: var(--text-secondary); }
.result-title { font-size: 1.65rem; font-weight: 800; margin-bottom: 8px; }
.result-subtitle { color: var(--text-secondary); font-size: 0.95rem; margin-bottom: 32px; }
.result-stats {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
  margin: 0 auto 32px; max-width: 480px;
}
.review-area { text-align: left; margin-top: 40px; display: none; }
.review-area h3 { font-size: 1.25rem; font-weight: 800; margin-bottom: 20px; color: var(--accent-light); text-align: center; }
.review-card {
  padding: 20px 24px; margin-bottom: 14px; border-radius: var(--radius-sm);
  background: var(--bg-card); border: 1px solid var(--glass-border);
}
.review-card h4 { font-size: 0.98rem; font-weight: 700; margin-bottom: 10px; }
.review-answer { font-size: 0.86rem; margin-top: 6px; color: var(--text-secondary); }
.review-correct { color: var(--green); font-weight: 700; }
.review-wrong { color: var(--red); font-weight: 700; }

/* Modals */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.75);
  backdrop-filter: blur(10px); z-index: 1000;
  display: none; align-items: center; justify-content: center; padding: 24px;
}
.modal-overlay.active { display: flex; }
.modal {
  background: var(--bg-surface); border: 1px solid var(--glass-border);
  border-radius: var(--radius); padding: 32px; width: 100%; max-width: 580px;
  max-height: 85vh; overflow-y: auto; animation: scaleIn 0.3s ease both;
}
.modal h2 { font-size: 1.4rem; font-weight: 800; margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
.modal label {
  display: block; font-size: 0.78rem; font-weight: 700;
  color: var(--text-secondary); margin-bottom: 6px; margin-top: 16px;
  text-transform: uppercase; letter-spacing: 0.8px;
}
.modal input, .modal textarea, .modal select {
  width: 100%; padding: 10px 14px; border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm); background: rgba(255,255,255,0.03);
  color: var(--text-primary); font-family: inherit; font-size: 0.9rem;
  outline: none; transition: var(--transition);
}
.modal input:focus, .modal textarea:focus, .modal select:focus {
  border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow);
}
.modal textarea { resize: vertical; min-height: 70px; }
.question-block {
  border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
  padding: 16px; margin-top: 16px; background: rgba(255,255,255,0.015);
}
.question-block h4 { font-size: 0.9rem; margin-bottom: 12px; color: var(--accent-light); display: flex; justify-content: space-between; }
.modal-actions { display: flex; gap: 12px; margin-top: 24px; justify-content: flex-end; }

/* Start Mode Selector Modal */
.mode-card {
  border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
  padding: 16px; display: flex; align-items: center; gap: 16px; cursor: pointer;
  background: var(--bg-card); transition: var(--transition); margin-bottom: 12px;
}
.mode-card:hover { border-color: var(--accent); background: rgba(139,92,246,0.05); }
.mode-card.selected {
  border-color: var(--accent-light); background: rgba(139,92,246,0.12);
  box-shadow: 0 0 15px var(--accent-glow);
}
.mode-card .mode-icon { font-size: 2rem; }
.mode-card .mode-details h3 { font-size: 0.95rem; font-weight: 700; margin-bottom: 2px; }
.mode-card .mode-details p { font-size: 0.78rem; color: var(--text-secondary); line-height: 1.4; }

/* Footer */
.footer {
  text-align: center; padding: 24px; color: var(--text-tertiary); font-size: 0.78rem;
  border-top: 1px solid var(--glass-border); margin-top: 40px;
}
.footer a { color: var(--accent-light); text-decoration: none; }
.footer a:hover { text-decoration: underline; }

/* Toast */
.toast-container { position: fixed; top: 80px; right: 24px; z-index: 2000; display: flex; flex-direction: column; gap: 8px; }
.toast {
  padding: 12px 20px; border-radius: var(--radius-xs); background: var(--bg-surface);
  border: 1px solid var(--glass-border); color: var(--text-primary); font-size: 0.88rem;
  font-weight: 600; box-shadow: var(--shadow-lg); animation: slideInRight 0.3s ease both;
  display: flex; align-items: center; gap: 10px;
}
.toast.success { border-color: rgba(16, 185, 129, 0.4); }
.toast.error { border-color: rgba(239, 68, 68, 0.4); }

/* Animations */
@keyframes fadeSlideUp { from { opacity:0; transform: translateY(20px); } to { opacity:1; transform: translateY(0); } }
@keyframes fadeSlideDown { from { opacity:0; transform: translateY(-16px); } to { opacity:1; transform: translateY(0); } }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes scaleIn { from { opacity:0; transform: scale(0.92); } to { opacity:1; transform: scale(1); } }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
@keyframes pulse { 0%, 100% { opacity:1; } 50% { opacity:0.5; } }
@keyframes slideInRight { from { opacity:0; transform: translateX(60px); } to { opacity:1; transform: translateX(0); } }

.delay-1 { animation-delay: 0.05s; }
.delay-2 { animation-delay: 0.1s; }
.delay-3 { animation-delay: 0.15s; }
.delay-4 { animation-delay: 0.2s; }
</style>
</head>
<body>

<canvas id="confetti-canvas"></canvas>
<div class="toast-container" id="toast-container"></div>

<!-- NAVBAR -->
<nav class="navbar" id="main-navbar" style="display:none;">
  <div class="navbar-inner">
    <div class="nav-brand">
      <div class="nav-brand-icon">QV</div>
      QuizVault
    </div>
    <div class="nav-tabs">
      <button class="nav-tab active" id="tab-quizzes" onclick="navigateTo('hall')">Quizzes</button>
      <button class="nav-tab" id="tab-leaderboard" onclick="navigateTo('leaderboard')">Leaderboard</button>
      <button class="nav-tab" id="tab-stats" onclick="navigateTo('stats')">My Stats</button>
    </div>
    <div class="nav-user">
      <div class="nav-avatar" id="nav-avatar">U</div>
      <span class="nav-username" id="nav-username">Username</span>
      <button class="nav-logout" onclick="logout()">Sign Out</button>
    </div>
  </div>
</nav>

<div class="app-shell">

  <!-- ================= VIEW: AUTH ================= -->
  <div id="view-auth" class="auth-container">
    <div class="glass auth-card">
      <div class="auth-icon">🔐</div>
      <h2 id="auth-title">Welcome to QuizVault</h2>
      <p id="auth-subtitle">Sign in to track your scores, unlock badges, and rank on leaderboards.</p>
      
      <div class="auth-form-group">
        <label>Username</label>
        <input type="text" id="auth-username" placeholder="Enter username" maxlength="20">
      </div>
      <div class="auth-form-group">
        <label>Password</label>
        <input type="password" id="auth-password" placeholder="Enter password" onkeydown="if(event.key==='Enter') submitAuth()">
      </div>
      
      <button class="btn btn-primary auth-btn" onclick="submitAuth()" id="auth-btn-text">Sign In</button>
      
      <div class="auth-switch" id="auth-switch-text">
        Don't have an account? <a onclick="toggleAuthMode(true)">Sign Up</a>
      </div>
    </div>
  </div>

  <!-- ================= VIEW: QUIZ HALL ================= -->
  <div id="view-hall" style="display:none;">
    <div class="section-header">
      <div class="section-title"><span class="icon">📚</span> Available Assessments</div>
      <button class="btn btn-primary btn-sm" onclick="openCreateModal()">+ Create Custom Quiz</button>
    </div>

    <!-- Search/Filter Controls -->
    <div class="search-row">
      <div class="search-input-wrap">
        <svg class="search-icon-svg" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        <input type="text" class="search-input" id="search-quiz" placeholder="Search quizzes by title or category..." oninput="filterQuizzes()">
      </div>
      <select class="filter-select" id="filter-category" onchange="filterQuizzes()">
        <option value="all">All Categories</option>
      </select>
    </div>

    <div class="quiz-grid" id="quiz-grid"></div>
  </div>

  <!-- ================= VIEW: QUIZ PLAY ================= -->
  <div id="view-play" style="display:none;">
    <div class="play-layout">
      <!-- Main Question Panel -->
      <div class="glass quiz-play-box">
        <div class="qp-header">
          <div class="qp-title" id="qp-title">Quiz Title</div>
          <div class="qp-timer" id="qp-timer">⏱ --:--</div>
        </div>
        <div class="progress-wrap"><div class="progress-bar" id="progress-bar" style="width:0%;"></div></div>
        <div class="qp-counter" id="qp-counter">Question 1 of 10</div>
        <div class="qp-question" id="qp-question">Question text here?</div>
        <div class="options-grid" id="options-grid"></div>
        <div id="explanation-area"></div>
      </div>

      <!-- Exam Mode Navigation Panel -->
      <div class="glass exam-sidebar" id="exam-sidebar" style="display:none;">
        <h3>Exam Board</h3>
        <div class="exam-grid" id="exam-grid"></div>
        <div class="exam-actions-stack">
          <div class="exam-btn-nav">
            <button class="btn btn-secondary btn-sm" onclick="prevQuestion()" id="exam-btn-prev">◀ Prev</button>
            <button class="btn btn-secondary btn-sm" onclick="nextQuestion()" id="exam-btn-next">Next ▶</button>
          </div>
          <button class="btn btn-secondary btn-sm" onclick="toggleMarkForReview()" id="exam-btn-mark" style="color:var(--yellow); border-color:rgba(245,158,11,0.2);">⭐️ Flag Review</button>
          <button class="btn btn-primary" onclick="submitExamPrompt()" style="margin-top:12px;">Submit Exam 📤</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ================= VIEW: RESULTS ================= -->
  <div id="view-results" style="display:none;">
    <div class="glass results-view">
      <div class="result-grade-ring" id="result-ring" style="--pct:0;">
        <div class="result-grade-inner">
          <div class="result-grade-letter" id="result-grade">A+</div>
          <div class="result-pct" id="result-pct">95%</div>
        </div>
      </div>
      <div class="result-title" id="result-title">Quiz Title Completed</div>
      <div class="result-subtitle" id="result-subtitle">Awesome score message!</div>
      
      <div class="result-stats">
        <div class="glass stat-card"><div class="stat-value" id="stat-score">--/--</div><div class="stat-label">Score</div></div>
        <div class="glass stat-card"><div class="stat-value" id="stat-correct">--/--</div><div class="stat-label">Correct Qs</div></div>
        <div class="glass stat-card"><div class="stat-value" id="stat-time">--s</div><div class="stat-label">Time</div></div>
      </div>

      <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
        <button class="btn btn-primary" onclick="navigateTo('hall')">← Dashboard</button>
        <button class="btn btn-secondary" onclick="toggleReview()">🔍 Review Answers</button>
        <button class="btn btn-secondary" onclick="retakeQuiz()">🔁 Retake</button>
        <button class="btn btn-secondary" onclick="downloadCertificate()" style="border-color:rgba(245,158,11,0.3); color:var(--yellow);"><span style="font-size:1.15rem;">📜</span> Certificate</button>
      </div>

      <div class="review-area" id="review-area"></div>
    </div>
  </div>

  <!-- ================= VIEW: LEADERBOARD ================= -->
  <div id="view-leaderboard" style="display:none;">
    <div class="section-header">
      <div class="section-title"><span class="icon">🏆</span> Leaderboard Rankings</div>
      <div style="display:flex; gap:10px; align-items:center;">
        <span class="section-badge">Top 10 Records</span>
        <select class="filter-select" id="lb-quiz-select" onchange="loadLeaderboard()" style="padding:6px 12px; min-width:200px;">
          <option value="all">Global (All Quizzes)</option>
        </select>
      </div>
    </div>
    
    <div class="glass lb-wrap">
      <table class="lb-table" id="lb-table">
        <thead>
          <tr>
            <th>Rank</th><th>User</th><th>Quiz</th><th>Points</th><th>Accuracy</th><th>Grade</th><th>Duration</th>
          </tr>
        </thead>
        <tbody id="lb-body"></tbody>
      </table>
      <div class="lb-empty" id="lb-empty" style="display:none;">No scores logged for this category yet. Be the first to rank!</div>
    </div>
  </div>

  <!-- ================= VIEW: STATS ================= -->
  <div id="view-stats" style="display:none;">
    <div class="section-header">
      <div class="section-title"><span class="icon">📊</span> Assessment Analytics</div>
    </div>

    <!-- Top Stats Cards -->
    <div class="stats-cards">
      <div class="glass stats-card"><div class="sc-icon">📝</div><div class="sc-value" id="stats-total-quizzes">0</div><div class="sc-label">Completed</div></div>
      <div class="glass stats-card"><div class="sc-icon">📈</div><div class="sc-value" id="stats-average-score">0%</div><div class="sc-label">Average %</div></div>
      <div class="glass stats-card"><div class="sc-icon">🏆</div><div class="sc-value" id="stats-best-grade">N/A</div><div class="sc-label">Best Grade</div></div>
      <div class="glass stats-card"><div class="sc-icon">⭐</div><div class="sc-value" id="stats-total-points">0</div><div class="sc-label">Total Points</div></div>
    </div>

    <div class="stats-visuals-grid">
      <!-- Chart.js Score History -->
      <div class="glass chart-box">
        <h3 style="font-size:1.05rem; font-weight:800; margin-bottom:16px;">Performance Timeline</h3>
        <canvas id="stats-chart" style="width:100%; max-height:260px;"></canvas>
      </div>

      <!-- Achievements & Badges -->
      <div class="glass achievements-box">
        <h3 style="font-size:1.05rem; font-weight:800;">Badges & Milestones</h3>
        <p style="font-size:0.8rem; color:var(--text-tertiary); margin-bottom:10px;">Unlock exclusive titles as you complete quizzes.</p>
        <div class="achievements-grid" id="achievements-grid">
          <!-- Populated by JS -->
        </div>
      </div>
    </div>

    <!-- History Table -->
    <div class="section-title" style="margin-bottom:16px;"><span class="icon">⏱</span> Assessment History</div>
    <div class="glass lb-wrap">
      <table class="lb-table" id="history-table">
        <thead>
          <tr>
            <th>Quiz</th><th>Points</th><th>Accuracy</th><th>Grade</th><th>Duration</th><th>Completed On</th>
          </tr>
        </thead>
        <tbody id="history-body"></tbody>
      </table>
      <div class="lb-empty" id="history-empty" style="display:none;">No historical attempts found. Take a quiz to initialize your dashboard!</div>
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer" id="app-footer" style="display:none;">
    <p>QuizVault &copy; 2026 &mdash; Built with Python &amp; Flask &mdash; <a onclick="navigateTo('hall')">Browse Assessments</a></p>
    <p style="margin-top:4px;">Challenge your mind, analyze performance data, and climb the leaderboard.</p>
  </div>
</div>

<!-- ================= MODAL: START QUIZ OPTIONS ================= -->
<div class="modal-overlay" id="mode-modal">
  <div class="modal" style="max-width:440px;">
    <h2 id="mode-modal-title">🏁 Launch Quiz</h2>
    
    <div class="mode-card selected" id="mode-card-practice" onclick="setSelectMode('practice')">
      <div class="mode-icon">📖</div>
      <div class="mode-details">
        <h3>Practice Mode</h3>
        <p>Instant answers, corrective indicators, and helper explanations after every question.</p>
      </div>
    </div>

    <div class="mode-card" id="mode-card-exam" onclick="setSelectMode('exam')">
      <div class="mode-icon">⏱️</div>
      <div class="mode-details">
        <h3>Exam Mode</h3>
        <p>Silent evaluation. Complete the questionnaire, skip/flag questions, submit at the end.</p>
      </div>
    </div>

    <div class="modal-actions" style="margin-top:20px;">
      <button class="btn btn-secondary btn-sm" onclick="closeModeModal()">Cancel</button>
      <button class="btn btn-primary btn-sm" onclick="beginQuiz()" style="min-width:130px;">Begin 🚀</button>
    </div>
  </div>
</div>

<!-- ================= MODAL: CREATE QUIZ ================= -->
<div class="modal-overlay" id="create-modal">
  <div class="modal">
    <h2>🛠 Create Custom Quiz</h2>
    <label>Quiz Title</label>
    <input type="text" id="cq-title" placeholder="My Assessment Title" maxlength="50">
    
    <label>Description</label>
    <textarea id="cq-desc" placeholder="Provide a summary for this assessment..."></textarea>
    
    <div style="display:flex; gap:16px;">
      <div style="flex:1;">
        <label>Category</label>
        <input type="text" id="cq-category" placeholder="General" value="Custom">
      </div>
      <div style="flex:1;">
        <label>Time Limit (seconds, 0 = none)</label>
        <input type="number" id="cq-time" value="120" min="0">
      </div>
    </div>

    <div id="cq-questions"></div>
    
    <button class="btn btn-secondary" onclick="addQuestionBlock()" style="margin-top:16px; width:100%;">+ Add Question Form</button>
    
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeCreateModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitCustomQuiz()">Save Quiz</button>
    </div>
  </div>
</div>

<script>
// ─── App Configurations ───
const ALL_VIEWS = ['view-auth', 'view-hall', 'view-play', 'view-results', 'view-leaderboard', 'view-stats'];
const NAV_TABS = { 'hall': 'tab-quizzes', 'leaderboard': 'tab-leaderboard', 'stats': 'tab-stats' };
const BADGES = {
  pioneer: { title: "Pioneer", desc: "Successfully registered profile", icon: "🏆" },
  first_step: { title: "First Step", desc: "Completed 1st assessment", icon: "🎓" },
  scholar: { title: "Scholar", desc: "Completed 5 assessments", icon: "📚" },
  perfectionist: { title: "Perfectionist", desc: "Scored 100% on a quiz", icon: "🎯" },
  speed_runner: { title: "Speed Demon", desc: "Completed in under 30s", icon: "⚡" },
  quiz_master: { title: "Quiz Master", desc: "Created a custom quiz", icon: "🛠️" }
};

// ─── Core State ───
let currentUser = '';
let isSignUpMode = false;
let quizzes = [];
let targetQuizId = null;
let activeQuiz = null;
let quizQuestions = [];
let currentQIndex = 0;
let quizMode = 'practice'; // 'practice' | 'exam'
let answers = []; // Stores Practice Mode and overall submission responses
let examAnswers = []; // Stores selected indices in Exam Mode
let examFlags = []; // Flags questions for review in Exam Mode
let quizStartTime = 0;
let timerInterval = null;
let questionBlockCount = 0;
let chartInstance = null;

// ─── Sound System (Web Audio API) ───
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function ensureAudio() { if (!audioCtx) audioCtx = new AudioCtx(); }
function playTone(freq, duration, type='sine') {
  try {
    ensureAudio();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, audioCtx.currentTime);
    g.gain.setValueAtTime(0.08, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
    o.connect(g); g.connect(audioCtx.destination);
    o.start(); o.stop(audioCtx.currentTime + duration);
  } catch(e){}
}
function correctSound() { playTone(880, 0.15); setTimeout(() => playTone(1100, 0.2), 120); }
function wrongSound()   { playTone(220, 0.25, 'sawtooth'); setTimeout(() => playTone(180, 0.35, 'sawtooth'), 180); }

// ─── Confetti System ───
const canvas = document.getElementById('confetti-canvas');
const ctx = canvas.getContext('2d');
let particles = [];
let confettiRunning = false;
function resizeCanvas() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
window.addEventListener('resize', resizeCanvas); resizeCanvas();

function launchConfetti() {
  particles = [];
  const colors = ['#8b5cf6','#a78bfa','#c084fc','#818cf8','#10b981','#f59e0b','#ef4444','#3b82f6'];
  for(let i=0; i<150; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: -10 - Math.random()*200,
      w: 6 + Math.random()*6,
      h: 4 + Math.random()*4,
      color: colors[Math.floor(Math.random() * colors.length)],
      vx: (Math.random() - 0.5) * 6,
      vy: 2 + Math.random() * 4,
      rot: Math.random() * 360,
      rv: (Math.random() - 0.5) * 8,
      g: 0.08 + Math.random() * 0.04,
      op: 1
    });
  }
  confettiRunning = true;
  animateConfetti();
}
function animateConfetti() {
  if(!confettiRunning) return;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  let active = 0;
  particles.forEach(p => {
    if(p.op <= 0) return;
    active++;
    p.x += p.vx; p.vy += p.g; p.y += p.vy; p.rot += p.rv;
    if(p.y > canvas.height + 10) { p.op = 0; return; }
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate(p.rot * Math.PI / 180);
    ctx.globalAlpha = p.op;
    ctx.fillStyle = p.color;
    ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
    ctx.restore();
  });
  if(active > 0) requestAnimationFrame(animateConfetti);
  else confettiRunning = false;
}

// ─── Toasts ───
function showToast(msg, type='success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type==='success'?'✔':'✖'}</span> <span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(60px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ─── Navigation ───
function showView(viewId) {
  ALL_VIEWS.forEach(v => document.getElementById(v).style.display = 'none');
  const viewEl = document.getElementById('view-' + viewId);
  if(viewEl) viewEl.style.display = viewId === 'auth' ? 'flex' : 'block';

  // Manage Nav Highlight
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  const activeTabId = NAV_TABS[viewId];
  if(activeTabId) {
    const tabEl = document.getElementById(activeTabId);
    if(tabEl) tabEl.classList.add('active');
  }

  // Hide footer during quiz-play to avoid scrolling distractions
  const footer = document.getElementById('app-footer');
  footer.style.display = viewId === 'play' ? 'none' : 'block';
}

async function navigateTo(view) {
  if (!currentUser) { showView('auth'); return; }
  
  if (view === 'hall') {
    await loadQuizzes();
    showView('hall');
  } else if (view === 'leaderboard') {
    await loadLeaderboard();
    showView('leaderboard');
  } else if (view === 'stats') {
    await loadStats();
    showView('stats');
  }
}

// ─── Authentication Controller ───
function toggleAuthMode(signUp) {
  isSignUpMode = signUp;
  document.getElementById('auth-title').textContent = signUp ? "Create Profile" : "Welcome to QuizVault";
  document.getElementById('auth-subtitle').textContent = signUp ? "Sign up to track grades, unlock milestones and publish custom quizzes." : "Sign in to track your scores, unlock badges, and rank on leaderboards.";
  document.getElementById('auth-btn-text').textContent = signUp ? "Sign Up" : "Sign In";
  document.getElementById('auth-switch-text').innerHTML = signUp ? "Already registered? <a onclick='toggleAuthMode(false)'>Sign In</a>" : "Don't have an account? <a onclick='toggleAuthMode(true)'>Sign Up</a>";
}

async function submitAuth() {
  const username = document.getElementById('auth-username').value.trim();
  const password = document.getElementById('auth-password').value.trim();

  if(!username || !password) {
    showToast("Please provide both Username and Password.", "error");
    return;
  }

  const endpoint = isSignUpMode ? '/api/auth/register' : '/api/auth/login';
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if(res.ok) {
      currentUser = username;
      localStorage.setItem('quiz_username', username);
      showToast(isSignUpMode ? "Registration successful!" : "Welcome back!", "success");
      
      // Update UI
      document.getElementById('main-navbar').style.display = 'block';
      document.getElementById('app-footer').style.display = 'block';
      document.getElementById('nav-username').textContent = currentUser;
      document.getElementById('nav-avatar').textContent = currentUser.charAt(0).toUpperCase();
      
      // Reset fields
      document.getElementById('auth-username').value = '';
      document.getElementById('auth-password').value = '';
      
      navigateTo('hall');
    } else {
      showToast(data.error || "Authentication failed.", "error");
    }
  } catch(e) {
    showToast("Network/Server connection failed.", "error");
  }
}

function logout() {
  currentUser = '';
  localStorage.removeItem('quiz_username');
  document.getElementById('main-navbar').style.display = 'none';
  document.getElementById('app-footer').style.display = 'none';
  showView('auth');
}

// ─── Data Loaders ───
async function loadQuizzes() {
  try {
    const res = await fetch('/api/quizzes');
    quizzes = await res.json();
    
    // Populate filter category options
    const catSelect = document.getElementById('filter-category');
    const lbSelect = document.getElementById('lb-quiz-select');
    
    // Reset but keep first option
    catSelect.innerHTML = '<option value="all">All Categories</option>';
    lbSelect.innerHTML = '<option value="all">Global (All Quizzes)</option>';
    
    const categories = new Set();
    quizzes.forEach(q => {
      if(q.category) categories.add(q.category);
      lbSelect.insertAdjacentHTML('beforeend', `<option value="${q.id}">${q.title}</option>`);
    });
    
    categories.forEach(c => {
      catSelect.insertAdjacentHTML('beforeend', `<option value="${c}">${c}</option>`);
    });

    renderQuizGrid(quizzes);
  } catch(e) {
    showToast("Failed to fetch quizzes.", "error");
  }
}

function renderQuizGrid(items) {
  const grid = document.getElementById('quiz-grid');
  const catIcons = { Programming: '🐍', Science: '🔬', Math: '📐', Mixed: '🎲', Custom: '🛠' };
  
  if(items.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding:48px; color:var(--text-secondary);">No quizzes matched your search.</div>';
    return;
  }

  grid.innerHTML = items.map((q, i) => {
    const icon = catIcons[q.category] || '📝';
    const min = Math.floor(q.time_limit / 60);
    const sec = q.time_limit % 60;
    const timeStr = q.time_limit ? `${min}m ${sec}s` : 'No Limit';
    return `
      <div class="glass quiz-card delay-${(i % 4) + 1}">
        <div>
          <span class="card-cat">${icon} ${q.category}</span>
          <h3>${q.title}</h3>
          <p class="card-desc">${q.description}</p>
        </div>
        <div>
          <div class="card-creator">Created by ${q.created_by}</div>
          <div class="card-meta">
            <span>📋 ${q.questions.length} Qs</span>
            <span>⏱ ${timeStr}</span>
            <span>⭐ ${q.total_points} Pts</span>
          </div>
          <button class="btn btn-primary btn-start" onclick="openModeModal(${q.id})">Take Assessment →</button>
        </div>
      </div>
    `;
  }).join('');
}

function filterQuizzes() {
  const query = document.getElementById('search-quiz').value.toLowerCase().trim();
  const category = document.getElementById('filter-category').value;
  
  const filtered = quizzes.filter(q => {
    const matchesQuery = q.title.toLowerCase().includes(query) || q.category.toLowerCase().includes(query);
    const matchesCategory = category === 'all' || q.category === category;
    return matchesQuery && matchesCategory;
  });
  
  renderQuizGrid(filtered);
}

async function loadLeaderboard() {
  const quizId = document.getElementById('lb-quiz-select').value;
  let url = '/api/leaderboard';
  if(quizId !== 'all') url += `?quiz_id=${quizId}`;
  
  try {
    const res = await fetch(url);
    const data = await res.json();
    renderLeaderboardTable(data);
  } catch(e) {
    showToast("Failed to fetch leaderboard data.", "error");
  }
}

function renderLeaderboardTable(records) {
  const tbody = document.getElementById('lb-body');
  const empty = document.getElementById('lb-empty');
  const table = document.getElementById('lb-table');
  
  if(records.length === 0) {
    tbody.innerHTML = '';
    table.style.display = 'none';
    empty.style.display = 'block';
    return;
  }
  
  table.style.display = 'table';
  empty.style.display = 'none';
  
  const medals = { 1: '🥇', 2: '🥈', 3: '🥉' };
  tbody.innerHTML = records.map(r => {
    const m = Math.floor(r.time / 60);
    const s = Math.floor(r.time % 60);
    const gradeClass = getGradeClass(r.grade);
    const rankLabel = medals[r.rank] || `<span class="mono">${r.rank}</span>`;
    return `
      <tr>
        <td class="lb-rank">${rankLabel}</td>
        <td><strong>${r.user}</strong></td>
        <td>${r.quiz}</td>
        <td class="mono">${r.score}/${r.total}</td>
        <td class="mono"><strong>${r.pct.toFixed(1)}%</strong></td>
        <td><span class="lb-grade ${gradeClass}">${r.grade}</span></td>
        <td class="mono">${m}m ${s}s</td>
      </tr>
    `;
  }).join('');
}

function getGradeClass(grade) {
  if (grade.startsWith('A')) return 'grade-a';
  if (grade.startsWith('B')) return 'grade-b';
  if (grade.startsWith('C')) return 'grade-c';
  if (grade.startsWith('D')) return 'grade-d';
  return 'grade-f';
}

async function loadStats() {
  try {
    const [statsRes, histRes] = await Promise.all([
      fetch(`/api/user/stats?username=${encodeURIComponent(currentUser)}`),
      fetch(`/api/user/history?username=${encodeURIComponent(currentUser)}`)
    ]);
    
    if(!statsRes.ok || !histRes.ok) throw new Error("Failed to load");
    
    const stats = await statsRes.json();
    const history = await histRes.json();
    
    // Update Stats Cards
    document.getElementById('stats-total-quizzes').textContent = stats.attempts;
    document.getElementById('stats-average-score').textContent = stats.average_percentage.toFixed(1) + '%';
    document.getElementById('stats-best-grade').textContent = stats.best_grade;
    document.getElementById('stats-total-points').textContent = stats.total_score;
    
    // Render History Table
    const tbody = document.getElementById('history-body');
    const empty = document.getElementById('history-empty');
    const table = tbody.closest('table');
    
    if(history.length === 0) {
      tbody.innerHTML = '';
      table.style.display = 'none';
      empty.style.display = 'block';
    } else {
      table.style.display = 'table';
      empty.style.display = 'none';
      tbody.innerHTML = history.map(h => {
        const m = Math.floor(h.time_taken / 60);
        const s = Math.floor(h.time_taken % 60);
        const dateStr = h.timestamp ? h.timestamp.substring(0, 10) + ' ' + h.timestamp.substring(11, 16) : '--';
        return `
          <tr>
            <td><strong>${h.quiz_title}</strong></td>
            <td class="mono">${h.score}/${h.total_points}</td>
            <td class="mono"><strong>${h.percentage.toFixed(1)}%</strong></td>
            <td><span class="lb-grade ${getGradeClass(h.grade)}">${h.grade}</span></td>
            <td class="mono">${m}m ${s}s</td>
            <td>${dateStr}</td>
          </tr>
        `;
      }).join('');
    }
    
    // Render Badges Dashboard
    const grid = document.getElementById('achievements-grid');
    const userBadges = stats.badges || ['pioneer'];
    
    grid.innerHTML = Object.keys(BADGES).map(key => {
      const b = BADGES[key];
      const isUnlocked = userBadges.includes(key);
      return `
        <div class="badge-slot ${isUnlocked ? 'unlocked' : ''}">
          <div class="badge-icon">${b.icon}</div>
          <div class="badge-tooltip">
            <div class="badge-title">${b.title}</div>
            <div style="font-size:0.65rem; color:var(--text-secondary);">${b.desc}</div>
            <div style="font-size:0.62rem; margin-top:4px; font-weight:bold; color:${isUnlocked?'var(--green)':'var(--text-tertiary)'};">
              ${isUnlocked ? 'Unlocked ✔' : 'Locked'}
            </div>
          </div>
        </div>
      `;
    }).join('');
    
    // Render Chart.js Performance Graph
    renderPerformanceChart(history);
  } catch(e) {
    showToast("Failed to fetch dashboard stats.", "error");
  }
}

function renderPerformanceChart(history) {
  const canvasEl = document.getElementById('stats-chart');
  if(!canvasEl) return;
  
  if(chartInstance) {
    chartInstance.destroy();
  }
  
  if(history.length === 0) {
    const ctxChart = canvasEl.getContext('2d');
    ctxChart.clearRect(0,0,canvasEl.width,canvasEl.height);
    return;
  }
  
  // Reverse history so we see earliest first
  const dataPoints = [...history].reverse();
  const labels = dataPoints.map((h, i) => `T${i+1}`);
  const scores = dataPoints.map(h => h.percentage);
  const titles = dataPoints.map(h => h.quiz_title);
  
  const ctxChart = canvasEl.getContext('2d');
  chartInstance = new Chart(ctxChart, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Accuracy %',
        data: scores,
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.08)',
        fill: true,
        tension: 0.35,
        borderWidth: 3,
        pointBackgroundColor: '#8b5cf6',
        pointBorderColor: '#fff',
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function(context) {
              const idx = context[0].dataIndex;
              return titles[idx];
            },
            label: function(context) {
              return ` Accuracy: ${context.parsed.y.toFixed(1)}%`;
            }
          }
        }
      },
      scales: {
        y: {
          min: 0, max: 100,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: 'rgba(255, 255, 255, 0.4)', font: { family: 'Outfit' } }
        },
        x: {
          grid: { display: false },
          ticks: { color: 'rgba(255, 255, 255, 0.4)', font: { family: 'Outfit' } }
        }
      }
    }
  });
}

// ─── Play Logic ───
function openModeModal(quizId) {
  targetQuizId = quizId;
  document.getElementById('mode-modal').classList.add('active');
}
function closeModeModal() {
  document.getElementById('mode-modal').classList.remove('active');
}
function setSelectMode(mode) {
  quizMode = mode;
  document.getElementById('mode-card-practice').classList.toggle('selected', mode === 'practice');
  document.getElementById('mode-card-exam').classList.toggle('selected', mode === 'exam');
}

function beginQuiz() {
  closeModeModal();
  if(!targetQuizId) return;
  
  const quiz = quizzes.find(q => q.id === targetQuizId);
  if(!quiz) return;
  
  activeQuiz = quiz;
  quizQuestions = [...quiz.questions];
  if(quiz.shuffle) {
    quizQuestions.sort(() => Math.random() - 0.5);
  }
  
  currentQIndex = 0;
  answers = [];
  examAnswers = Array(quizQuestions.length).fill(null);
  examFlags = Array(quizQuestions.length).fill(false);
  quizStartTime = Date.now();
  
  showView('play');
  document.getElementById('qp-title').textContent = quiz.title;
  
  // Set Exam Sidebar display
  const sidebar = document.getElementById('exam-sidebar');
  if(quizMode === 'exam') {
    sidebar.style.display = 'block';
    renderExamGrid();
  } else {
    sidebar.style.display = 'none';
  }
  
  startTimer(quiz.time_limit);
  renderQuestion();
}

function startTimer(limit) {
  clearInterval(timerInterval);
  const el = document.getElementById('qp-timer');
  if(!limit) {
    el.innerHTML = '⏱ ∞';
    return;
  }
  const endTime = Date.now() + limit * 1000;
  timerInterval = setInterval(() => {
    const rem = Math.max(0, Math.floor((endTime - Date.now()) / 1000));
    const m = Math.floor(rem / 60), s = rem % 60;
    el.innerHTML = `⏱ ${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    
    if(rem <= 15) {
      el.className = 'qp-timer warning';
    } else {
      el.className = 'qp-timer';
    }
    
    if(rem <= 0) {
      clearInterval(timerInterval);
      showToast("Time expired! Submitting assessment automatically.", "error");
      finishQuiz();
    }
  }, 250);
}

function renderQuestion() {
  if(currentQIndex >= quizQuestions.length) {
    if(quizMode === 'practice') {
      finishQuiz();
    }
    return;
  }
  
  const q = quizQuestions[currentQIndex];
  const total = quizQuestions.length;
  
  // Progress Bar
  const pct = (currentQIndex / total) * 100;
  document.getElementById('progress-bar').style.width = pct + '%';
  
  // Counter & Question
  document.getElementById('qp-counter').textContent = `Question ${currentQIndex + 1} of ${total}  ·  ${q.difficulty}  ·  ${q.points} Pts`;
  document.getElementById('qp-question').textContent = q.text;
  
  document.getElementById('explanation-area').innerHTML = '';
  
  const labels = ['A','B','C','D','E','F'];
  const grid = document.getElementById('options-grid');
  
  // Render options depending on Mode
  grid.innerHTML = q.options.map((opt, i) => {
    let optionClass = "opt-btn";
    let clickHandler = `selectOption(${i})`;
    
    if(quizMode === 'exam') {
      if(examAnswers[currentQIndex] === i) {
        optionClass += " selected";
      }
    }
    
    return `
      <button class="${optionClass}" onclick="${clickHandler}" data-idx="${i}">
        <span class="opt-label">${labels[i]}</span>
        <span>${opt}</span>
      </button>
    `;
  }).join('');
  
  // If in Exam mode, update sidebar highlighting
  if(quizMode === 'exam') {
    updateExamSidebarHighlight();
  }
}

// ─── Practice Mode Answer Selection ───
function selectOption(idx) {
  if(quizMode === 'exam') {
    // Exam mode behavior: select but don't submit/validate yet
    examAnswers[currentQIndex] = idx;
    
    // Update highlighted button class
    document.querySelectorAll('.opt-btn').forEach((btn, i) => {
      btn.classList.toggle('selected', i === idx);
    });
    
    // Update exam sidebar
    renderExamGrid();
    return;
  }

  // Practice mode behavior: validate immediately
  const q = quizQuestions[currentQIndex];
  const btns = document.querySelectorAll('.opt-btn');
  btns.forEach(b => b.classList.add('disabled'));
  
  const correctIdx = q.answer_index;
  btns[correctIdx].classList.add('correct');
  
  const correct = (idx === correctIdx);
  if(correct) {
    correctSound();
  } else {
    wrongSound();
    btns[idx].classList.add('wrong');
  }
  
  answers.push({ index: idx, correct: correct, points: correct ? q.points : 0, question: q });
  
  if(q.explanation) {
    document.getElementById('explanation-area').innerHTML = `
      <div class="explanation-box">💡 <strong>Explanation:</strong> ${q.explanation}</div>
    `;
  }
  
  setTimeout(() => {
    currentQIndex++;
    if(currentQIndex >= quizQuestions.length) {
      finishQuiz();
    } else {
      renderQuestion();
    }
  }, 2200);
}

// ─── Exam Mode Navigation & Sidebar ───
function renderExamGrid() {
  const grid = document.getElementById('exam-grid');
  grid.innerHTML = quizQuestions.map((_, i) => {
    let cellClass = "exam-cell";
    if(i === currentQIndex) cellClass += " active";
    else if(examFlags[i]) cellClass += " marked";
    else if(examAnswers[i] !== null) cellClass += " answered";
    
    return `<div class="${cellClass}" onclick="jumpToQuestion(${i})">${i+1}</div>`;
  }).join('');
}

function updateExamSidebarHighlight() {
  const cells = document.querySelectorAll('.exam-cell');
  cells.forEach((cell, i) => {
    cell.classList.remove('active', 'marked', 'answered');
    if(i === currentQIndex) cell.classList.add('active');
    else if(examFlags[i]) cell.classList.add('marked');
    else if(examAnswers[i] !== null) cell.classList.add('answered');
  });
}

function jumpToQuestion(idx) {
  currentQIndex = idx;
  renderQuestion();
}

function prevQuestion() {
  if(currentQIndex > 0) {
    currentQIndex--;
    renderQuestion();
  }
}

function nextQuestion() {
  if(currentQIndex < quizQuestions.length - 1) {
    currentQIndex++;
    renderQuestion();
  }
}

function toggleMarkForReview() {
  examFlags[currentQIndex] = !examFlags[currentQIndex];
  
  const flagBtn = document.getElementById('exam-btn-mark');
  if(examFlags[currentQIndex]) {
    flagBtn.style.background = 'var(--yellow)';
    flagBtn.style.color = '#000';
  } else {
    flagBtn.style.background = 'transparent';
    flagBtn.style.color = 'var(--yellow)';
  }
  
  renderExamGrid();
}

function submitExamPrompt() {
  const unansweredCount = examAnswers.filter(a => a === null).length;
  let confirmMsg = "Are you sure you want to submit your exam?";
  if(unansweredCount > 0) {
    confirmMsg += `\n⚠️ You have left ${unansweredCount} questions unanswered.`;
  }
  
  if(confirm(confirmMsg)) {
    finishQuiz();
  }
}

// ─── Finish & Review ───
async function finishQuiz() {
  clearInterval(timerInterval);
  const timeTaken = (Date.now() - quizStartTime) / 1000;
  
  let score = 0;
  let correctCount = 0;
  
  if(quizMode === 'exam') {
    // Grade exam mode selections
    answers = [];
    quizQuestions.forEach((q, i) => {
      const idx = examAnswers[i];
      const correct = (idx === q.answer_index);
      if(correct) {
        score += q.points;
        correctCount++;
      }
      answers.push({ index: idx, correct: correct, points: correct ? q.points : 0, question: q });
    });
  } else {
    // Practice mode uses accumulator
    score = answers.reduce((s, a) => s + a.points, 0);
    correctCount = answers.filter(a => a.correct).length;
  }
  
  const totalQ = quizQuestions.length;
  const totalPts = quizQuestions.reduce((s, q) => s + q.points, 0);
  const pct = totalPts > 0 ? (score / totalPts * 100) : 0;
  const grade = pct >= 90 ? 'A+' : pct >= 80 ? 'A' : pct >= 70 ? 'B' : pct >= 60 ? 'C' : pct >= 50 ? 'D' : 'F';
  
  // Custom congratulations subtitles
  const congratulations = {
    'A+': "Perfect score! Outstanding achievements logged. 🏆",
    'A': "Brilliant job! Exceptional accuracy. 🎖️",
    'B': "Well done! Consistent and precise. 👍",
    'C': "Good attempt. Keep reviewing to refine parameters.",
    'D': "Passed, but review exercises are recommended.",
    'F': "Assessment incomplete. Retake suggested."
  };
  
  const subtitle = congratulations[grade] || "Review results details below.";

  try {
    const response = await fetch('/api/quiz/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        quiz_id: activeQuiz.id,
        quiz_title: activeQuiz.title,
        username: currentUser,
        score: score,
        total_points: totalPts,
        correct: correctCount,
        total_q: totalQ,
        time_taken: timeTaken,
        answers: answers.map(a => a.index === null ? -1 : a.index)
      })
    });
  } catch(e) {
    console.error("Failed to submit score to server database.", e);
  }

  showView('results');
  document.getElementById('result-grade').textContent = grade;
  document.getElementById('result-pct').textContent = pct.toFixed(1) + '%';
  document.getElementById('result-title').textContent = activeQuiz.title;
  document.getElementById('result-subtitle').textContent = subtitle;
  document.getElementById('stat-score').textContent = `${score}/${totalPts}`;
  document.getElementById('stat-correct').textContent = `${correctCount}/${totalQ}`;
  
  const tm = Math.floor(timeTaken / 60);
  const ts = Math.floor(timeTaken % 60);
  document.getElementById('stat-time').textContent = `${tm}m ${ts}s`;
  
  // Set percentage color animation ring
  setTimeout(() => {
    document.getElementById('result-ring').style.setProperty('--pct', pct);
  }, 100);
  
  if(pct >= 60) {
    launchConfetti();
    playTone(660, 0.2);
    setTimeout(() => playTone(880, 0.3), 150);
  } else {
    playTone(180, 0.4, 'sawtooth');
  }

  // Clear review list initially
  document.getElementById('review-area').style.display = 'none';
  document.getElementById('review-area').innerHTML = '';
}

function toggleReview() {
  const area = document.getElementById('review-area');
  if(area.style.display === 'block') {
    area.style.display = 'none';
    return;
  }
  
  area.style.display = 'block';
  area.innerHTML = '<h3>Detailed Question Review</h3>' + answers.map((a, i) => {
    const q = a.question;
    const labels = ['A','B','C','D','E','F'];
    const chosenAns = a.index === null || a.index === -1 ? '<i>Unanswered</i>' : q.options[a.index];
    const correctAns = q.options[q.answer_index];
    
    return `
      <div class="review-card">
        <h4>Question ${i+1}: ${q.text}</h4>
        <div class="review-answer">
          Selected answer: <span class="${a.correct ? 'review-correct' : 'review-wrong'}">${chosenAns} ${a.correct ? '✔ Correct' : '✖ Wrong'}</span>
        </div>
        ${!a.correct ? `<div class="review-answer">Correct answer: <span class="review-correct">${correctAns}</span></div>` : ''}
        ${q.explanation ? `<div class="review-answer" style="margin-top:8px; color:var(--accent-light);">💡 <strong>Explanation:</strong> ${q.explanation}</div>` : ''}
      </div>
    `;
  }).join('');
  
  // Scroll to review area smoothly
  setTimeout(() => {
    area.scrollIntoView({ behavior: 'smooth' });
  }, 150);
}

function retakeQuiz() {
  if(activeQuiz) {
    openModeModal(activeQuiz.id);
  }
}

// ─── Certificate Generation (HTML5 Canvas) ───
function downloadCertificate() {
  if(!activeQuiz || !currentUser) return;
  
  const scoreText = document.getElementById('stat-score').textContent;
  const pctText = document.getElementById('result-pct').textContent;
  const gradeText = document.getElementById('result-grade').textContent;
  
  // Set up canvas
  const canvasCert = document.createElement('canvas');
  canvasCert.width = 1200;
  canvasCert.height = 800;
  const ctxCert = canvasCert.getContext('2d');
  
  // 1. Draw elegant dark background
  const grad = ctxCert.createRadialGradient(600, 400, 100, 600, 400, 700);
  grad.addColorStop(0, '#151522');
  grad.addColorStop(1, '#09090d');
  ctxCert.fillStyle = grad;
  ctxCert.fillRect(0, 0, 1200, 800);
  
  // 2. Draw gold borders
  ctxCert.lineWidth = 14;
  ctxCert.strokeStyle = '#c5a880'; // Muted gold
  ctxCert.strokeRect(30, 30, 1140, 740);
  
  ctxCert.lineWidth = 3;
  ctxCert.strokeStyle = '#e5c090'; // Shiny gold
  ctxCert.strokeRect(45, 45, 1110, 710);
  
  // Draw corner ornaments
  const corners = [
    [45, 45, 1, 1], [1155, 45, -1, 1],
    [45, 755, 1, -1], [1155, 755, -1, -1]
  ];
  ctxCert.fillStyle = '#e5c090';
  corners.forEach(c => {
    ctxCert.beginPath();
    ctxCert.moveTo(c[0], c[1]);
    ctxCert.lineTo(c[0] + c[2]*40, c[1]);
    ctxCert.lineTo(c[0], c[1] + c[3]*40);
    ctxCert.closePath();
    ctxCert.fill();
  });
  
  // 3. Draw Brand logo & Certificate header
  ctxCert.shadowColor = 'rgba(0,0,0,0.5)';
  ctxCert.shadowBlur = 10;
  
  ctxCert.font = 'bold 36px "Outfit"';
  ctxCert.fillStyle = '#a78bfa'; // Purple
  ctxCert.textAlign = 'center';
  ctxCert.fillText("Q U I Z V A U L T   A C A D E M Y", 600, 140);
  
  ctxCert.font = '900 68px "Outfit"';
  ctxCert.fillStyle = '#ffffff';
  ctxCert.fillText("CERTIFICATE OF COMPLETION", 600, 230);
  
  // Subtitle
  ctxCert.font = '300 24px "Outfit"';
  ctxCert.fillStyle = 'rgba(255,255,255,0.6)';
  ctxCert.fillText("This is officially awarded to", 600, 310);
  
  // Recipient Name
  ctxCert.font = 'bold 52px "Outfit"';
  ctxCert.fillStyle = '#e5c090'; // Gold
  ctxCert.fillText(currentUser, 600, 390);
  
  // Context details
  ctxCert.font = '300 20px "Outfit"';
  ctxCert.fillStyle = 'rgba(255,255,255,0.6)';
  ctxCert.fillText("for successfully completing and passing the master assessment of", 600, 460);
  
  // Quiz Title
  ctxCert.font = 'bold 34px "Outfit"';
  ctxCert.fillStyle = '#ffffff';
  ctxCert.fillText(`"${activeQuiz.title}"`, 600, 520);
  
  // Grade details
  ctxCert.font = '500 22px "Outfit"';
  ctxCert.fillStyle = '#10b981'; // Green
  ctxCert.fillText(`Grade achieved: ${gradeText} (${pctText} Accuracy) with Score ${scoreText}`, 600, 575);
  
  // Gold Seal Emblem
  ctxCert.beginPath();
  ctxCert.arc(600, 680, 45, 0, Math.PI * 2);
  ctxCert.fillStyle = '#c5a880';
  ctxCert.fill();
  ctxCert.beginPath();
  ctxCert.arc(600, 680, 38, 0, Math.PI * 2);
  ctxCert.strokeStyle = '#e5c090';
  ctxCert.lineWidth = 3;
  ctxCert.stroke();
  
  ctxCert.fillStyle = '#09090d';
  ctxCert.font = 'bold 22px "Outfit"';
  ctxCert.fillText("PASS", 600, 688);
  
  // Ribbon details
  ctxCert.fillStyle = '#c5a880';
  ctxCert.beginPath();
  ctxCert.moveTo(570, 715);
  ctxCert.lineTo(550, 755);
  ctxCert.lineTo(580, 745);
  ctxCert.lineTo(590, 725);
  ctxCert.closePath();
  ctxCert.fill();
  
  ctxCert.beginPath();
  ctxCert.moveTo(630, 715);
  ctxCert.lineTo(650, 755);
  ctxCert.lineTo(620, 745);
  ctxCert.lineTo(610, 725);
  ctxCert.closePath();
  ctxCert.fill();
  
  // Date & Signature columns
  ctxCert.fillStyle = 'rgba(255,255,255,0.4)';
  ctxCert.font = '300 16px "Outfit"';
  ctxCert.fillText(`DATE: ${new Date().toLocaleDateString()}`, 250, 680);
  ctxCert.fillText("---------------------------", 250, 660);
  
  ctxCert.fillText("ISSUED BY: QuizVault Evaluator", 950, 680);
  ctxCert.fillText("---------------------------", 950, 660);
  
  // Trigger local PNG download
  const image = canvasCert.toDataURL("image/png");
  const link = document.createElement('a');
  link.download = `${currentUser}_${activeQuiz.title.replace(/\s+/g, '_')}_Certificate.png`;
  link.href = image;
  link.click();
  showToast("Certificate downloaded successfully!", "success");
}

// ─── Create Custom Quiz Modal ───
function openCreateModal() {
  questionBlockCount = 1;
  document.getElementById('cq-questions').innerHTML = makeQuestionBlock(0);
  document.getElementById('cq-title').value = '';
  document.getElementById('cq-desc').value = '';
  document.getElementById('cq-category').value = 'Custom';
  document.getElementById('cq-time').value = '120';
  document.getElementById('create-modal').classList.add('active');
}
function closeCreateModal() {
  document.getElementById('create-modal').classList.remove('active');
}
function addQuestionBlock() {
  document.getElementById('cq-questions').insertAdjacentHTML('beforeend', makeQuestionBlock(questionBlockCount));
  questionBlockCount++;
}
function deleteQuestionBlock(btn) {
  const block = btn.closest('.question-block');
  if(block) {
    block.remove();
    // Reindex headers
    const blocks = document.querySelectorAll('.question-block');
    blocks.forEach((b, i) => {
      b.dataset.qi = i;
      b.querySelector('.question-idx-title').textContent = `Question ${i + 1}`;
    });
    questionBlockCount = blocks.length;
  }
}
function makeQuestionBlock(idx) {
  return `
    <div class="question-block" data-qi="${idx}">
      <h4 class="question-idx-title">
        <span>Question ${idx + 1}</span>
        ${idx > 0 ? `<button class="btn btn-danger btn-sm" onclick="deleteQuestionBlock(this)" style="padding:2px 8px; font-size:0.7rem;">Delete</button>` : ''}
      </h4>
      <label>Question text</label>
      <input type="text" class="cqq-text" placeholder="What is the output of print(2**3)?" required>
      
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:8px;">
        <div><label>Option A</label><input type="text" class="cqq-opt-a" placeholder="8" required></div>
        <div><label>Option B</label><input type="text" class="cqq-opt-b" placeholder="6" required></div>
        <div><label>Option C</label><input type="text" class="cqq-opt-c" placeholder="9" required></div>
        <div><label>Option D</label><input type="text" class="cqq-opt-d" placeholder="5" required></div>
      </div>
      
      <div style="display:flex; gap:16px; margin-top:8px;">
        <div style="flex:1;">
          <label>Correct Answer Index</label>
          <select class="cqq-correct">
            <option value="0">Option A</option>
            <option value="1">Option B</option>
            <option value="2">Option C</option>
            <option value="3">Option D</option>
          </select>
        </div>
        <div style="flex:1;">
          <label>Difficulty</label>
          <select class="cqq-difficulty">
            <option value="Easy">Easy</option>
            <option value="Medium" selected>Medium</option>
            <option value="Hard">Hard</option>
          </select>
        </div>
      </div>
      
      <label>Helpful Explanation</label>
      <input type="text" class="cqq-expl" placeholder="2 raised to the power 3 is 8.">
    </div>
  `;
}

async function submitCustomQuiz() {
  const title = document.getElementById('cq-title').value.trim();
  const desc = document.getElementById('cq-desc').value.trim();
  const category = document.getElementById('cq-category').value.trim() || 'Custom';
  const timeLimit = parseInt(document.getElementById('cq-time').value) || 0;

  if(!title) {
    showToast("Please enter a quiz title.", "error");
    return;
  }

  const blocks = document.querySelectorAll('.question-block');
  const questions = [];
  let valid = true;

  blocks.forEach((b, i) => {
    const text = b.querySelector('.cqq-text').value.trim();
    const optA = b.querySelector('.cqq-opt-a').value.trim();
    const optB = b.querySelector('.cqq-opt-b').value.trim();
    const optC = b.querySelector('.cqq-opt-c').value.trim();
    const optD = b.querySelector('.cqq-opt-d').value.trim();
    const correctIdx = parseInt(b.querySelector('.cqq-correct').value);
    const difficulty = b.querySelector('.cqq-difficulty').value;
    const explanation = b.querySelector('.cqq-expl').value.trim();

    if(!text || !optA || !optB || !optC || !optD) {
      valid = false;
      return;
    }

    questions.push({
      id: 1000 + i,
      text: text,
      options: [optA, optB, optC, optD],
      answer_index: correctIdx,
      category: category,
      difficulty: difficulty,
      explanation: explanation,
      points: 10
    });
  });

  if(!valid || questions.length === 0) {
    showToast("Please fill in all question fields.", "error");
    return;
  }

  try {
    const res = await fetch('/api/quiz/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        description: desc,
        category: category,
        time_limit: timeLimit,
        questions,
        created_by: currentUser
      })
    });
    
    if(res.ok) {
      showToast(`Quiz "${title}" created successfully!`, "success");
      closeCreateModal();
      navigateTo('hall');
    } else {
      const data = await res.json();
      showToast(data.error || "Failed to create quiz.", "error");
    }
  } catch(e) {
    showToast("Server communication failed.", "error");
  }
}

// ─── App Initialization ───
document.addEventListener('DOMContentLoaded', () => {
  const savedUser = localStorage.getItem('quiz_username');
  if(savedUser) {
    currentUser = savedUser;
    
    // Update UI elements for logged-in user
    document.getElementById('main-navbar').style.display = 'block';
    document.getElementById('app-footer').style.display = 'block';
    document.getElementById('nav-username').textContent = currentUser;
    document.getElementById('nav-avatar').textContent = currentUser.charAt(0).toUpperCase();
    
    navigateTo('hall');
  } else {
    showView('auth');
  }
});
</script>
</body>
</html>
"""

# ── Flask Authentication Routes ───────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json()
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Missing username or password"}), 400

    username = data["username"].strip()
    password = data["password"].strip()

    if not username or not password:
        return jsonify({"error": "Username/Password cannot be empty"}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user:
        conn.close()
        return jsonify({"error": "Username already exists"}), 400

    pwd_hash = generate_password_hash(password)
    conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                 (username, pwd_hash, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

    # Automatically register user in platform dynamic dict
    platform.register_user(username)

    return jsonify({"status": "ok"})


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json()
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Missing username or password"}), 400

    username = data["username"].strip()
    password = data["password"].strip()

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    # Ensure user registered in-memory too
    platform.register_user(username)

    return jsonify({"status": "ok"})


# ── Flask Quiz Platform Routes ─────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/quizzes")
def api_quizzes():
    result = []
    for qid, quiz in platform.quizzes.items():
        result.append({
            "id": quiz.id,
            "title": quiz.title,
            "description": quiz.description,
            "category": quiz.category,
            "time_limit": quiz.time_limit,
            "created_by": quiz.created_by,
            "total_points": quiz.total_points(),
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "options": q.options,
                    "answer_index": q.answer_index,
                    "category": q.category,
                    "difficulty": q.difficulty,
                    "explanation": q.explanation,
                    "points": q.points,
                }
                for q in quiz.questions
            ],
        })
    return jsonify(result)


@app.route("/api/leaderboard")
def api_leaderboard():
    quiz_id_str = request.args.get('quiz_id')
    quiz_id = int(quiz_id_str) if (quiz_id_str and quiz_id_str.isdigit()) else None
    return jsonify(platform.leaderboard(quiz_id=quiz_id))


@app.route("/api/quiz/submit", methods=["POST"])
def api_submit():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    result = QuizResult(
        quiz_id=data["quiz_id"],
        quiz_title=data["quiz_title"],
        username=data.get("username", "Guest"),
        score=data["score"],
        total_points=data["total_points"],
        correct=data["correct"],
        total_q=data["total_q"],
        time_taken=data["time_taken"],
        answers=data.get("answers", []),
    )

    platform.results.append(result)
    platform.register_user(result.username)
    u = platform.users[result.username]
    u["quizzes_taken"] += 1
    u["total_score"] += result.score

    def _grade_rank(g):
        return {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1, "F": 0}.get(g, -1)
    if u["best_grade"] == "N/A" or _grade_rank(result.grade) > _grade_rank(u["best_grade"]):
        u["best_grade"] = result.grade

    save_result_to_db(result)

    return jsonify({
        "status": "ok",
        "grade": result.grade,
        "percentage": result.percentage,
    })


@app.route("/api/user/stats")
def api_user_stats():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "username required"}), 400
    
    conn = get_db()
    # Check if user exists in db
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        conn.close()
        # Fallback to local profile check if using interactive modes
        if username in platform.users:
            user_results = [r for r in platform.results if r.username == username]
            attempts = len(user_results)
            avg_pct = sum(r.percentage for r in user_results) / attempts if attempts else 0
            best_grade = max((r.grade for r in user_results), default="N/A")
            total_score = sum(r.score for r in user_results)
            return jsonify({
                "username": username,
                "attempts": attempts,
                "average_percentage": avg_pct,
                "best_grade": best_grade,
                "total_score": total_score,
                "badges": ["pioneer", "first_step"] if attempts >= 1 else ["pioneer"]
            })
        return jsonify({"error": "User profile not found"}), 404
        
    user_results = conn.execute("SELECT * FROM quiz_results WHERE username = ?", (username,)).fetchall()
    customs = conn.execute("SELECT * FROM custom_quizzes WHERE created_by = ?", (username,)).fetchall()
    conn.close()
    
    attempts = len(user_results)
    total_score = sum(r["score"] for r in user_results)
    avg_pct = sum(r["percentage"] for r in user_results) / attempts if attempts else 0

    def _grade_rank(g):
        return {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1, "F": 0}.get(g, -1)
    best_grade = "N/A"
    for r in user_results:
        if best_grade == "N/A" or _grade_rank(r["grade"]) > _grade_rank(best_grade):
            best_grade = r["grade"]

    # Achievements logic
    badges = ["pioneer"]
    if attempts >= 1:
        badges.append("first_step")
    if attempts >= 5:
        badges.append("scholar")
    for r in user_results:
        if r["percentage"] >= 100:
            if "perfectionist" not in badges:
                badges.append("perfectionist")
        if r["time_taken"] < 30:
            if "speed_runner" not in badges:
                badges.append("speed_runner")
    if len(customs) >= 1:
        badges.append("quiz_master")

    return jsonify({
        "username": username,
        "attempts": attempts,
        "average_percentage": avg_pct,
        "best_grade": best_grade,
        "total_score": total_score,
        "badges": badges
    })


@app.route("/api/user/history")
def api_user_history():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "username required"}), 400
        
    conn = get_db()
    rows = conn.execute("SELECT * FROM quiz_results WHERE username = ? ORDER BY timestamp DESC", (username,)).fetchall()
    conn.close()
    
    history = [
        {
            "quiz_id": r["quiz_id"],
            "quiz_title": r["quiz_title"],
            "score": r["score"],
            "total_points": r["total_points"],
            "percentage": r["percentage"],
            "grade": r["grade"],
            "time_taken": r["time_taken"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]
    return jsonify(history)


@app.route("/api/quiz/create", methods=["POST"])
def api_create_quiz():
    data = request.get_json()
    if not data or "title" not in data or "questions" not in data:
        return jsonify({"error": "Missing title or questions"}), 400

    questions = []
    for i, qd in enumerate(data["questions"]):
        questions.append(Question(
            id=qd.get("id", 1000 + i),
            text=qd["text"],
            options=qd["options"],
            answer_index=qd["answer_index"],
            category=qd.get("category", "Custom"),
            difficulty=qd.get("difficulty", "Medium"),
            explanation=qd.get("explanation", ""),
            points=qd.get("points", 10),
        ))

    quiz = platform.create_quiz(
        title=data["title"],
        description=data.get("description", ""),
        category=data.get("category", "Custom"),
        time_limit=data.get("time_limit", 0),
        questions=questions,
        created_by=data.get("created_by", "User"),
    )

    # Save to DB
    conn = get_db()
    conn.execute("""
        INSERT INTO custom_quizzes (title, description, category, time_limit, created_by, questions_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (quiz.title, quiz.description, quiz.category, quiz.time_limit,
          quiz.created_by, json.dumps([asdict(q) for q in questions]),
          quiz.created_at))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "quiz_id": quiz.id, "title": quiz.title})


# ── Entry Point ────────────────────────────────────────────────

if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_demo()
    elif "--interactive" in sys.argv:
        run_interactive()
    else:
        init_db()
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5004")).start()
        print("=" * 56)
        print("  ⚡  QuizVault Server Launched — http://127.0.0.1:5004")
        print("  Use --cli for demo mode, --interactive for CLI mode")
        print("=" * 56)
        app.run(host="127.0.0.1", port=5004, debug=False)

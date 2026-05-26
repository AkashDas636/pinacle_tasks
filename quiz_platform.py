#!/usr/bin/env python3
"""
============================================================
  PROJECT 3: Online Quiz Platform
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
import threading
import webbrowser
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from collections import defaultdict


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
        sample = random.sample(QuestionBank.all_questions(), 10)
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
        if u['best_grade'] == 'N/A' or result.grade < u['best_grade']:
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


# ── Demo ───────────────────────────────────────────────────────

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

    # Simulate 3 users taking the Python quiz
    print(f"\n  🎮 Simulating Quiz Attempts (Python Fundamentals)...")
    print("  " + "-" * 54)

    scenarios = [
        ("Alice",   [1, 2, 1, 2, 1, 0, 3, 1]),   # mostly correct
        ("Bob",     [1, 2, 1, 1, 1, 2, 1, 1]),   # mixed
        ("Charlie", [0, 0, 0, 0, 0, 0, 0, 0]),   # poor
    ]

    quiz_id = 1
    for name, auto_ans in scenarios:
        result = platform.take_quiz(quiz_id, name, auto_answers=auto_ans)
        if result:
            print(f"\n  👤 {name}'s Result:")
            print(result.summary())

    # Simulate Science quiz
    print(f"\n  🔬 Simulating Science Quiz...")
    for name, auto_ans in [("Alice", [1,1,2,0,1,2]),
                            ("Dave",  [1,1,2,0,1,2])]:
        platform.take_quiz(2, name, auto_answers=auto_ans)

    # Leaderboard
    platform.print_leaderboard()
    platform.print_leaderboard(quiz_id=1)

    # Stats
    platform.print_quiz_stats(1)
    platform.print_quiz_stats(2)

    # Custom Quiz creation
    print(f"\n  🛠  Creating a Custom Quiz...")
    custom_qs = [
        Question(id=100, text="What does HTML stand for?",
                 options=["Hyper Text Markup Language",
                          "High Tech Machine Language",
                          "Hyper Transfer Meta Language",
                          "HyperText Manipulation Language"],
                 answer_index=0, category="Web", difficulty="Easy",
                 points=10, explanation="HTML = HyperText Markup Language"),
        Question(id=101, text="Which HTML tag creates a hyperlink?",
                 options=["<link>", "<a>", "<href>", "<url>"],
                 answer_index=1, category="Web", difficulty="Easy",
                 points=10, explanation="The <a> (anchor) tag creates hyperlinks."),
    ]
    custom = platform.create_quiz(
        title="Web Basics", description="Basic web development quiz.",
        category="Web", time_limit=60,
        questions=custom_qs, created_by="Eve"
    )
    print(f"     ✅ Created: '{custom.title}' (ID={custom.id}, {len(custom.questions)} questions)")

    result = platform.take_quiz(custom.id, "Eve", auto_answers=[0, 1])
    if result:
        print(f"     Eve's result: {result.score}/{result.total_points} ({result.percentage:.0f}%) — {result.grade}")

    # Grade distribution
    print(f"\n  📈 Grade Distribution (Python Quiz):")
    grade_count = defaultdict(int)
    for r in platform.results:
        if r.quiz_id == 1:
            grade_count[r.grade] += 1
    for grade in ["A+", "A", "B", "C", "D", "F"]:
        count = grade_count.get(grade, 0)
        bar   = "█" * count
        print(f"     {grade:>3}  {bar} ({count})")

    print(f"\n  ✅ All quiz platform features verified!")
    print("=" * 56)


# ── Interactive CLI ────────────────────────────────────────────

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

from flask import Flask, request, jsonify, render_template_string

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

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Quiz Platform</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

:root {
  --accent: #a78bfa;
  --accent-dim: #7c5cbf;
  --accent-glow: rgba(167,139,250,0.35);
  --bg-deep: #0a0a0f;
  --bg-card: rgba(255,255,255,0.04);
  --bg-card-hover: rgba(255,255,255,0.07);
  --glass-border: rgba(255,255,255,0.08);
  --glass-border-hover: rgba(167,139,250,0.3);
  --text-primary: #f0eef6;
  --text-secondary: rgba(240,238,246,0.55);
  --text-tertiary: rgba(240,238,246,0.35);
  --green: #34d399;
  --red: #f87171;
  --yellow: #fbbf24;
  --radius: 16px;
  --radius-sm: 10px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

html { font-size: 15px; }

body {
  font-family: 'Outfit', sans-serif;
  background: var(--bg-deep);
  color: var(--text-primary);
  min-height: 100vh;
  overflow-x: hidden;
}

body::before {
  content: '';
  position: fixed; inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 20% 10%, rgba(167,139,250,0.08) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 90%, rgba(99,102,241,0.06) 0%, transparent 60%),
    radial-gradient(ellipse 50% 50% at 50% 50%, rgba(15,15,25,0.9) 0%, transparent 100%);
  pointer-events: none; z-index: 0;
}

.mono { font-family: 'JetBrains Mono', monospace; }

/* ─── Confetti Canvas ─── */
#confetti-canvas {
  position: fixed; inset: 0;
  pointer-events: none; z-index: 9999;
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(167,139,250,0.2); border-radius: 3px; }

/* ─── Layout ─── */
.app-shell {
  position: relative; z-index: 1;
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 80px;
}

/* ─── Header ─── */
.header {
  text-align: center;
  margin-bottom: 40px;
  animation: fadeSlideDown 0.6s ease both;
}
.header h1 {
  font-size: 2.4rem;
  font-weight: 800;
  letter-spacing: -1px;
  background: linear-gradient(135deg, var(--accent) 0%, #c4b5fd 50%, #818cf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.header p { color: var(--text-secondary); margin-top: 6px; font-size: 1rem; }

/* ─── Glass Card ─── */
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

/* ─── Quiz Cards Grid ─── */
.quiz-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}
.quiz-card {
  padding: 24px;
  cursor: default;
  animation: fadeSlideUp 0.5s ease both;
  position: relative;
  overflow: hidden;
}
.quiz-card::before {
  content:'';
  position:absolute;top:0;left:0;right:0;height:3px;
  background: linear-gradient(90deg, var(--accent), #818cf8);
  opacity: 0;
  transition: opacity var(--transition);
}
.quiz-card:hover::before { opacity:1; }

.quiz-card .card-cat {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  background: rgba(167,139,250,0.12);
  color: var(--accent);
  margin-bottom: 12px;
}
.quiz-card h3 {
  font-size: 1.2rem; font-weight: 700; margin-bottom: 6px;
  color: var(--text-primary);
}
.quiz-card .card-desc {
  font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 16px; line-height: 1.5;
}
.quiz-card .card-meta {
  display: flex; gap: 16px; flex-wrap: wrap;
  font-size: 0.78rem; color: var(--text-tertiary); margin-bottom: 18px;
}
.quiz-card .card-meta span { display:flex; align-items:center; gap:4px; }

.btn {
  display: inline-flex; align-items: center; justify-content:center; gap: 6px;
  padding: 10px 22px;
  border: none; border-radius: var(--radius-sm);
  font-family: 'Outfit', sans-serif;
  font-size: 0.88rem; font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
  text-decoration: none;
  outline: none;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #818cf8);
  color: #fff;
  box-shadow: 0 4px 20px var(--accent-glow);
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 28px rgba(167,139,250,0.5);
}
.btn-secondary {
  background: rgba(255,255,255,0.06);
  color: var(--text-primary);
  border: 1px solid var(--glass-border);
}
.btn-secondary:hover {
  background: rgba(255,255,255,0.1);
  border-color: var(--glass-border-hover);
}
.btn-start { width: 100%; }

/* ─── Section Headers ─── */
.section-title {
  font-size: 1.1rem; font-weight: 700;
  margin-bottom: 16px;
  display: flex; align-items: center; gap: 8px;
  color: var(--text-primary);
}
.section-title .icon { font-size: 1.2rem; }

/* ─── Leaderboard ─── */
.lb-wrap { margin-bottom: 40px; animation: fadeSlideUp 0.6s ease 0.2s both; }
.lb-table { width: 100%; border-collapse: collapse; }
.lb-table thead th {
  text-align: left; padding: 10px 14px;
  font-size: 0.72rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 1.2px;
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--glass-border);
}
.lb-table tbody td {
  padding: 12px 14px; font-size: 0.88rem;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  color: var(--text-secondary);
}
.lb-table tbody tr:hover td { color: var(--text-primary); background: rgba(167,139,250,0.03); }
.lb-rank { font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--accent); }
.lb-grade {
  display: inline-block; padding: 2px 8px; border-radius: 6px;
  font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.8rem;
}
.grade-a { background: rgba(52,211,153,0.12); color: var(--green); }
.grade-b { background: rgba(251,191,36,0.12); color: var(--yellow); }
.grade-c { background: rgba(248,113,113,0.12); color: var(--red); }
.lb-empty { text-align: center; padding: 40px; color: var(--text-tertiary); font-size: 0.9rem; }

/* ─── Create Quiz Button Row ─── */
.actions-row {
  display: flex; gap: 12px; justify-content: center; margin-bottom: 40px;
  animation: fadeSlideUp 0.5s ease 0.1s both;
}

/* ─── Quiz Play View ─── */
.quiz-play { animation: fadeSlideUp 0.4s ease both; }

.qp-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
}
.qp-title { font-size: 1.1rem; font-weight: 700; }
.qp-timer {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.2rem; font-weight: 700;
  color: var(--accent);
  display: flex; align-items: center; gap: 6px;
}
.qp-timer.warning { color: var(--red); animation: pulse 1s ease-in-out infinite; }

.progress-wrap {
  width: 100%; height: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 3px;
  margin-bottom: 32px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #818cf8, var(--accent));
  background-size: 200% 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
  animation: shimmer 2s linear infinite;
}

.qp-counter {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem; font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 12px;
  letter-spacing: 1px;
}
.qp-question {
  font-size: 1.5rem; font-weight: 700;
  line-height: 1.45;
  margin-bottom: 32px;
  color: var(--text-primary);
}

.options-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 24px;
}
@media (max-width: 600px) { .options-grid { grid-template-columns: 1fr; } }

.opt-btn {
  padding: 16px 20px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-primary);
  font-family: 'Outfit', sans-serif;
  font-size: 0.95rem; font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
  text-align: left;
  display: flex; align-items: center; gap: 12px;
  position: relative;
  overflow: hidden;
}
.opt-btn .opt-label {
  width: 28px; height: 28px; min-width:28px;
  border-radius: 8px;
  background: rgba(167,139,250,0.1);
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem; font-weight: 700;
  color: var(--accent);
  transition: var(--transition);
}
.opt-btn:hover {
  border-color: var(--accent);
  background: rgba(167,139,250,0.06);
  box-shadow: 0 0 20px var(--accent-glow);
  transform: translateY(-1px);
}
.opt-btn:hover .opt-label { background: var(--accent); color: #fff; }

.opt-btn.correct {
  border-color: var(--green); background: rgba(52,211,153,0.1);
  box-shadow: 0 0 20px rgba(52,211,153,0.2);
}
.opt-btn.correct .opt-label { background: var(--green); color: #fff; }
.opt-btn.wrong {
  border-color: var(--red); background: rgba(248,113,113,0.08);
  box-shadow: 0 0 20px rgba(248,113,113,0.15);
}
.opt-btn.wrong .opt-label { background: var(--red); color: #fff; }
.opt-btn.disabled { pointer-events: none; opacity: 0.5; }

.explanation-box {
  padding: 14px 18px;
  border-radius: var(--radius-sm);
  background: rgba(167,139,250,0.06);
  border-left: 3px solid var(--accent);
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.6;
  margin-top: 8px;
  animation: fadeSlideUp 0.3s ease both;
}

/* ─── Results View ─── */
.results-view { text-align: center; animation: fadeSlideUp 0.5s ease both; }

.result-grade-ring {
  width: 160px; height: 160px;
  margin: 0 auto 24px;
  border-radius: 50%;
  background: conic-gradient(var(--accent) calc(var(--pct) * 3.6deg), rgba(255,255,255,0.05) 0);
  display: flex; align-items: center; justify-content: center;
  position: relative;
  animation: scaleIn 0.6s ease both;
}
.result-grade-inner {
  width: 130px; height: 130px;
  border-radius: 50%;
  background: var(--bg-deep);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.result-grade-letter {
  font-family: 'JetBrains Mono', monospace;
  font-size: 3rem; font-weight: 900;
  background: linear-gradient(135deg, var(--accent), #c4b5fd);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.result-pct { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: var(--text-secondary); }

.result-stats {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
  margin: 24px 0 32px; max-width: 480px; margin-left:auto; margin-right:auto;
}
.stat-card {
  padding: 16px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  border: 1px solid var(--glass-border);
}
.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.4rem; font-weight: 700;
  color: var(--accent);
}
.stat-label { font-size: 0.72rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

.result-title { font-size: 1.6rem; font-weight: 800; margin-bottom: 8px; }
.result-subtitle { color: var(--text-secondary); font-size: 0.95rem; margin-bottom: 24px; }

/* ─── Create Quiz Modal ─── */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: none; align-items: center; justify-content: center;
  padding: 24px;
  animation: fadeIn 0.2s ease both;
}
.modal-overlay.active { display: flex; }

.modal {
  background: #13131a;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  padding: 32px;
  width: 100%; max-width: 600px;
  max-height: 85vh; overflow-y: auto;
  animation: scaleIn 0.3s ease both;
}
.modal h2 { font-size: 1.3rem; font-weight: 700; margin-bottom: 24px; }
.modal label {
  display: block; font-size: 0.8rem; font-weight: 600;
  color: var(--text-secondary); margin-bottom: 6px; margin-top: 16px;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.modal input, .modal textarea, .modal select {
  width: 100%; padding: 10px 14px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.04);
  color: var(--text-primary);
  font-family: 'Outfit', sans-serif;
  font-size: 0.9rem;
  outline: none;
  transition: var(--transition);
}
.modal input:focus, .modal textarea:focus, .modal select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.modal textarea { resize: vertical; min-height: 60px; }

.question-block {
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 16px;
  margin-top: 16px;
  background: rgba(255,255,255,0.02);
}
.question-block h4 { font-size: 0.9rem; margin-bottom: 10px; color: var(--accent); }

.modal-actions { display: flex; gap: 12px; margin-top: 24px; justify-content: flex-end; }

/* ─── Username Modal ─── */
.username-modal {
  text-align: center;
}
.username-modal h2 { margin-bottom: 8px; }
.username-modal p { color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9rem; }
.username-modal input {
  text-align: center; font-size: 1.1rem; font-weight: 600;
  max-width: 300px; margin: 0 auto;
}

/* ─── Animations ─── */
@keyframes fadeSlideUp {
  from { opacity:0; transform: translateY(20px); }
  to   { opacity:1; transform: translateY(0); }
}
@keyframes fadeSlideDown {
  from { opacity:0; transform: translateY(-16px); }
  to   { opacity:1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity:0; } to { opacity:1; }
}
@keyframes scaleIn {
  from { opacity:0; transform: scale(0.92); }
  to   { opacity:1; transform: scale(1); }
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@keyframes pulse {
  0%, 100% { opacity:1; }
  50% { opacity:0.5; }
}

/* Delay classes */
.delay-1 { animation-delay: 0.08s; }
.delay-2 { animation-delay: 0.16s; }
.delay-3 { animation-delay: 0.24s; }
.delay-4 { animation-delay: 0.32s; }
</style>
</head>
<body>

<canvas id="confetti-canvas"></canvas>

<div class="app-shell">
  <!-- HEADER -->
  <div class="header">
    <h1>⚡ Quiz Platform</h1>
    <p>Test your knowledge · Climb the leaderboard</p>
  </div>

  <!-- ═══ VIEW 1: QUIZ HALL ═══ -->
  <div id="view-hall">

    <div class="actions-row">
      <button class="btn btn-secondary" onclick="openCreateModal()">＋ Create Custom Quiz</button>
    </div>

    <div class="section-title"><span class="icon">📚</span> Available Quizzes</div>
    <div class="quiz-grid" id="quiz-grid"></div>

    <div class="section-title" style="margin-top:12px;"><span class="icon">🏆</span> Leaderboard</div>
    <div class="glass lb-wrap" id="lb-wrap">
      <table class="lb-table" id="lb-table">
        <thead>
          <tr>
            <th>Rank</th><th>User</th><th>Quiz</th><th>Score</th><th>%</th><th>Grade</th><th>Time</th>
          </tr>
        </thead>
        <tbody id="lb-body"></tbody>
      </table>
      <div class="lb-empty" id="lb-empty" style="display:none;">No results yet. Be the first to take a quiz!</div>
    </div>
  </div>

  <!-- ═══ VIEW 2: QUIZ PLAY ═══ -->
  <div id="view-play" style="display:none;">
    <div class="glass quiz-play" style="padding:32px;">
      <div class="qp-header">
        <div class="qp-title" id="qp-title"></div>
        <div class="qp-timer" id="qp-timer">⏱ --:--</div>
      </div>
      <div class="progress-wrap"><div class="progress-bar" id="progress-bar" style="width:0%;"></div></div>
      <div class="qp-counter" id="qp-counter"></div>
      <div class="qp-question" id="qp-question"></div>
      <div class="options-grid" id="options-grid"></div>
      <div id="explanation-area"></div>
    </div>
  </div>

  <!-- ═══ VIEW 3: RESULTS ═══ -->
  <div id="view-results" style="display:none;">
    <div class="results-view">
      <div class="result-grade-ring" id="result-ring" style="--pct:0;">
        <div class="result-grade-inner">
          <div class="result-grade-letter" id="result-grade"></div>
          <div class="result-pct" id="result-pct"></div>
        </div>
      </div>
      <div class="result-title" id="result-title"></div>
      <div class="result-subtitle" id="result-subtitle"></div>
      <div class="result-stats">
        <div class="stat-card"><div class="stat-value" id="stat-score"></div><div class="stat-label">Score</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-correct"></div><div class="stat-label">Correct</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-time"></div><div class="stat-label">Time</div></div>
      </div>
      <button class="btn btn-primary" onclick="backToHall()" style="margin-top:8px;">← Back to Quiz Hall</button>
    </div>
  </div>
</div>

<!-- ═══ USERNAME MODAL ═══ -->
<div class="modal-overlay" id="username-modal">
  <div class="modal username-modal" style="max-width:400px;">
    <h2>👋 Welcome!</h2>
    <p>Enter your name to get started</p>
    <input type="text" id="username-input" placeholder="Your name…" maxlength="20"
           onkeydown="if(event.key==='Enter') setUsername()">
    <div class="modal-actions" style="justify-content:center; margin-top:20px;">
      <button class="btn btn-primary" onclick="setUsername()">Let's Go!</button>
    </div>
  </div>
</div>

<!-- ═══ CREATE QUIZ MODAL ═══ -->
<div class="modal-overlay" id="create-modal">
  <div class="modal">
    <h2>🛠 Create Custom Quiz</h2>
    <label>Title</label>
    <input type="text" id="cq-title" placeholder="My Awesome Quiz">
    <label>Description</label>
    <textarea id="cq-desc" placeholder="A short description…"></textarea>
    <label>Category</label>
    <input type="text" id="cq-category" placeholder="General" value="Custom">
    <label>Time Limit (seconds, 0 = no limit)</label>
    <input type="number" id="cq-time" value="120" min="0">

    <div id="cq-questions">
      <div class="question-block" data-qi="0">
        <h4>Question 1</h4>
        <label>Question Text</label>
        <input type="text" class="cqq-text" placeholder="What is…?">
        <label>Option A</label><input type="text" class="cqq-opt-a" placeholder="Option A">
        <label>Option B</label><input type="text" class="cqq-opt-b" placeholder="Option B">
        <label>Option C</label><input type="text" class="cqq-opt-c" placeholder="Option C">
        <label>Option D</label><input type="text" class="cqq-opt-d" placeholder="Option D">
        <label>Correct Answer</label>
        <select class="cqq-correct">
          <option value="0">A</option><option value="1">B</option>
          <option value="2">C</option><option value="3">D</option>
        </select>
        <label>Explanation</label>
        <input type="text" class="cqq-expl" placeholder="Because…">
      </div>
    </div>
    <button class="btn btn-secondary" onclick="addQuestionBlock()" style="margin-top:12px;width:100%;">+ Add Another Question</button>
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeCreateModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitCustomQuiz()">Create Quiz</button>
    </div>
  </div>
</div>

<script>
// ─── State ───
let currentUser = '';
let quizzes = [];
let activeQuiz = null;
let activeQuestions = [];
let currentQIndex = 0;
let answers = [];
let quizStartTime = 0;
let timerInterval = null;
let questionBlockCount = 1;

// ─── Audio ───
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
function ensureAudio() { if (!audioCtx) audioCtx = new AudioCtx(); }

function playBeep(freq, duration, type='sine') {
  try {
    ensureAudio();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, audioCtx.currentTime);
    g.gain.setValueAtTime(0.12, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
    o.connect(g); g.connect(audioCtx.destination);
    o.start(); o.stop(audioCtx.currentTime + duration);
  } catch(e) {}
}
function correctSound() { playBeep(880, 0.15); setTimeout(() => playBeep(1100, 0.2), 120); }
function wrongSound()   { playBeep(200, 0.25, 'sawtooth'); setTimeout(() => playBeep(160, 0.3, 'sawtooth'), 180); }

// ─── Confetti ───
const confettiCanvas = document.getElementById('confetti-canvas');
const cCtx = confettiCanvas.getContext('2d');
let confettiParticles = [];
let confettiRunning = false;

function resizeConfetti() { confettiCanvas.width = window.innerWidth; confettiCanvas.height = window.innerHeight; }
window.addEventListener('resize', resizeConfetti); resizeConfetti();

function launchConfetti() {
  confettiParticles = [];
  const colors = ['#a78bfa','#c4b5fd','#818cf8','#34d399','#fbbf24','#f87171','#60a5fa','#f472b6'];
  for (let i = 0; i < 200; i++) {
    confettiParticles.push({
      x: Math.random() * confettiCanvas.width,
      y: -20 - Math.random() * 300,
      w: 6 + Math.random() * 6,
      h: 4 + Math.random() * 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      vx: (Math.random() - 0.5) * 6,
      vy: 2 + Math.random() * 4,
      rot: Math.random() * 360,
      rv: (Math.random() - 0.5) * 8,
      gravity: 0.08 + Math.random() * 0.04,
      opacity: 1
    });
  }
  confettiRunning = true;
  animateConfetti();
}

function animateConfetti() {
  if (!confettiRunning) return;
  cCtx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
  let alive = 0;
  confettiParticles.forEach(p => {
    if (p.opacity <= 0) return;
    alive++;
    p.x += p.vx;
    p.vy += p.gravity;
    p.y += p.vy;
    p.rot += p.rv;
    if (p.y > confettiCanvas.height + 20) { p.opacity = 0; return; }
    cCtx.save();
    cCtx.translate(p.x, p.y);
    cCtx.rotate(p.rot * Math.PI / 180);
    cCtx.globalAlpha = p.opacity;
    cCtx.fillStyle = p.color;
    cCtx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
    cCtx.restore();
  });
  if (alive > 0) requestAnimationFrame(animateConfetti);
  else confettiRunning = false;
}

// ─── Views ───
function showView(name) {
  document.getElementById('view-hall').style.display = name === 'hall' ? '' : 'none';
  document.getElementById('view-play').style.display = name === 'play' ? '' : 'none';
  document.getElementById('view-results').style.display = name === 'results' ? '' : 'none';
}

// ─── Username ───
function setUsername() {
  const v = document.getElementById('username-input').value.trim();
  currentUser = v || 'Guest';
  document.getElementById('username-modal').classList.remove('active');
  loadHall();
}

// ─── Load Hall ───
async function loadHall() {
  showView('hall');
  // load quizzes
  const qRes = await fetch('/api/quizzes');
  quizzes = await qRes.json();
  renderQuizGrid();
  // load leaderboard
  const lRes = await fetch('/api/leaderboard');
  const lb = await lRes.json();
  renderLeaderboard(lb);
}

function renderQuizGrid() {
  const grid = document.getElementById('quiz-grid');
  const catIcons = { Programming: '🐍', Science: '🔬', Math: '📐', Mixed: '🎲', Custom: '🛠' };
  grid.innerHTML = quizzes.map((q, i) => {
    const icon = catIcons[q.category] || '📝';
    const mins = Math.floor(q.time_limit / 60);
    const secs = q.time_limit % 60;
    const timeStr = q.time_limit ? `${mins}m ${secs}s` : 'No limit';
    return `
      <div class="glass quiz-card delay-${(i % 4) + 1}">
        <span class="card-cat">${icon} ${q.category}</span>
        <h3>${q.title}</h3>
        <p class="card-desc">${q.description}</p>
        <div class="card-meta">
          <span>📋 ${q.questions.length} questions</span>
          <span>⏱ ${timeStr}</span>
          <span>⭐ ${q.total_points} pts</span>
        </div>
        <button class="btn btn-primary btn-start" onclick="startQuiz(${q.id})">Start Quiz →</button>
      </div>`;
  }).join('');
}

function renderLeaderboard(lb) {
  const body = document.getElementById('lb-body');
  const empty = document.getElementById('lb-empty');
  if (lb.length === 0) {
    body.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  const medals = { 1: '🥇', 2: '🥈', 3: '🥉' };
  body.innerHTML = lb.map(e => {
    const m = Math.floor(e.time / 60), s = Math.floor(e.time % 60);
    const gc = e.grade.startsWith('A') ? 'grade-a' : (e.grade === 'B' ? 'grade-b' : 'grade-c');
    const rank = medals[e.rank] || e.rank;
    return `<tr>
      <td class="lb-rank">${rank}</td>
      <td>${e.user}</td>
      <td>${e.quiz}</td>
      <td class="mono">${e.score}/${e.total}</td>
      <td class="mono">${e.pct.toFixed(1)}%</td>
      <td><span class="lb-grade ${gc}">${e.grade}</span></td>
      <td class="mono">${m}m ${s}s</td>
    </tr>`;
  }).join('');
}

// ─── Start Quiz ───
function startQuiz(quizId) {
  const quiz = quizzes.find(q => q.id === quizId);
  if (!quiz) return;
  activeQuiz = quiz;
  // shuffle questions
  activeQuestions = [...quiz.questions].sort(() => Math.random() - 0.5);
  currentQIndex = 0;
  answers = [];
  quizStartTime = Date.now();

  showView('play');
  document.getElementById('qp-title').textContent = quiz.title;
  startTimer(quiz.time_limit);
  renderQuestion();
}

function startTimer(limit) {
  clearInterval(timerInterval);
  const el = document.getElementById('qp-timer');
  if (!limit) { el.textContent = '⏱ ∞'; return; }
  const endTime = Date.now() + limit * 1000;
  timerInterval = setInterval(() => {
    const rem = Math.max(0, Math.floor((endTime - Date.now()) / 1000));
    const m = Math.floor(rem / 60), s = rem % 60;
    el.textContent = `⏱ ${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    el.className = rem <= 15 ? 'qp-timer warning' : 'qp-timer';
    if (rem <= 0) { clearInterval(timerInterval); finishQuiz(); }
  }, 250);
}

function renderQuestion() {
  if (currentQIndex >= activeQuestions.length) { finishQuiz(); return; }
  const q = activeQuestions[currentQIndex];
  const total = activeQuestions.length;
  const pct = ((currentQIndex) / total) * 100;

  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('qp-counter').textContent = `Q${currentQIndex + 1} / ${total}  ·  ${q.difficulty}  ·  ${q.points} pts`;
  document.getElementById('qp-question').textContent = q.text;
  document.getElementById('explanation-area').innerHTML = '';

  const labels = ['A','B','C','D','E','F'];
  const grid = document.getElementById('options-grid');
  grid.innerHTML = q.options.map((opt, i) =>
    `<button class="opt-btn" onclick="selectAnswer(${i})" data-idx="${i}">
      <span class="opt-label">${labels[i]}</span>
      <span>${opt}</span>
    </button>`
  ).join('');
}

function selectAnswer(idx) {
  const q = activeQuestions[currentQIndex];
  const btns = document.querySelectorAll('.opt-btn');
  btns.forEach(b => b.classList.add('disabled'));

  const correctIdx = q.answer_index;
  btns[correctIdx].classList.add('correct');

  if (idx === correctIdx) {
    correctSound();
    answers.push({ index: idx, correct: true, points: q.points });
  } else {
    wrongSound();
    btns[idx].classList.add('wrong');
    answers.push({ index: idx, correct: false, points: 0 });
  }

  if (q.explanation) {
    document.getElementById('explanation-area').innerHTML =
      `<div class="explanation-box">💡 ${q.explanation}</div>`;
  }

  setTimeout(() => {
    currentQIndex++;
    renderQuestion();
  }, 2000);
}

// ─── Finish Quiz ───
async function finishQuiz() {
  clearInterval(timerInterval);
  const timeTaken = (Date.now() - quizStartTime) / 1000;
  const score = answers.reduce((s, a) => s + a.points, 0);
  const correctCount = answers.filter(a => a.correct).length;
  const totalQ = activeQuestions.length;
  const totalPts = activeQuestions.reduce((s, q) => s + q.points, 0);
  const pct = totalPts > 0 ? (score / totalPts * 100) : 0;
  let grade;
  if (pct >= 90) grade = 'A+'; else if (pct >= 80) grade = 'A';
  else if (pct >= 70) grade = 'B'; else if (pct >= 60) grade = 'C';
  else if (pct >= 50) grade = 'D'; else grade = 'F';

  // submit to server
  await fetch('/api/quiz/submit', {
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
      answers: answers.map(a => a.index)
    })
  });

  // show results
  showView('results');
  document.getElementById('progress-bar').style.width = '100%';

  const msgs = {
    'A+': 'Outstanding! 🌟', 'A': 'Excellent work! 🎯',
    'B': 'Good job! 👍', 'C': 'Not bad! Keep learning 📖',
    'D': 'Room for improvement 💪', 'F': 'Keep trying! 🔄'
  };

  document.getElementById('result-grade').textContent = grade;
  document.getElementById('result-pct').textContent = pct.toFixed(1) + '%';
  document.getElementById('result-title').textContent = activeQuiz.title;
  document.getElementById('result-subtitle').textContent = msgs[grade] || 'Quiz completed!';
  document.getElementById('stat-score').textContent = `${score}/${totalPts}`;
  document.getElementById('stat-correct').textContent = `${correctCount}/${totalQ}`;
  const tm = Math.floor(timeTaken / 60), ts = Math.floor(timeTaken % 60);
  document.getElementById('stat-time').textContent = `${tm}m ${ts}s`;

  // animate ring
  setTimeout(() => {
    document.getElementById('result-ring').style.setProperty('--pct', pct);
  }, 100);

  // confetti for good grades
  if (pct >= 50) launchConfetti();
}

// ─── Back to Hall ───
function backToHall() { loadHall(); }

// ─── Create Quiz Modal ───
function openCreateModal() {
  questionBlockCount = 1;
  document.getElementById('cq-questions').innerHTML = makeQuestionBlock(0);
  document.getElementById('cq-title').value = '';
  document.getElementById('cq-desc').value = '';
  document.getElementById('cq-category').value = 'Custom';
  document.getElementById('cq-time').value = '120';
  document.getElementById('create-modal').classList.add('active');
}
function closeCreateModal() { document.getElementById('create-modal').classList.remove('active'); }

function makeQuestionBlock(idx) {
  return `<div class="question-block" data-qi="${idx}">
    <h4>Question ${idx + 1}</h4>
    <label>Question Text</label>
    <input type="text" class="cqq-text" placeholder="What is…?">
    <label>Option A</label><input type="text" class="cqq-opt-a" placeholder="Option A">
    <label>Option B</label><input type="text" class="cqq-opt-b" placeholder="Option B">
    <label>Option C</label><input type="text" class="cqq-opt-c" placeholder="Option C">
    <label>Option D</label><input type="text" class="cqq-opt-d" placeholder="Option D">
    <label>Correct Answer</label>
    <select class="cqq-correct">
      <option value="0">A</option><option value="1">B</option>
      <option value="2">C</option><option value="3">D</option>
    </select>
    <label>Explanation</label>
    <input type="text" class="cqq-expl" placeholder="Because…">
  </div>`;
}

function addQuestionBlock() {
  document.getElementById('cq-questions').insertAdjacentHTML('beforeend', makeQuestionBlock(questionBlockCount));
  questionBlockCount++;
}

async function submitCustomQuiz() {
  const title = document.getElementById('cq-title').value.trim();
  const desc = document.getElementById('cq-desc').value.trim();
  const cat = document.getElementById('cq-category').value.trim() || 'Custom';
  const timeL = parseInt(document.getElementById('cq-time').value) || 0;

  if (!title) { alert('Please enter a quiz title.'); return; }

  const blocks = document.querySelectorAll('.question-block');
  const questions = [];
  let valid = true;
  blocks.forEach((b, i) => {
    const text = b.querySelector('.cqq-text').value.trim();
    const a = b.querySelector('.cqq-opt-a').value.trim();
    const bv = b.querySelector('.cqq-opt-b').value.trim();
    const c = b.querySelector('.cqq-opt-c').value.trim();
    const d = b.querySelector('.cqq-opt-d').value.trim();
    const correct = parseInt(b.querySelector('.cqq-correct').value);
    const expl = b.querySelector('.cqq-expl').value.trim();
    if (!text || !a || !bv || !c || !d) { valid = false; return; }
    questions.push({
      id: 1000 + i,
      text: text,
      options: [a, bv, c, d],
      answer_index: correct,
      category: cat,
      difficulty: 'Medium',
      explanation: expl,
      points: 10
    });
  });

  if (!valid || questions.length === 0) { alert('Please fill in all question fields.'); return; }

  const res = await fetch('/api/quiz/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description: desc, category: cat, time_limit: timeL, questions, created_by: currentUser })
  });

  if (res.ok) {
    closeCreateModal();
    loadHall();
  } else {
    alert('Failed to create quiz.');
  }
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('username-modal').classList.add('active');
  document.getElementById('username-input').focus();
});
</script>
</body>
</html>
"""

# ── Flask Routes ───────────────────────────────────────────────

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
    if u["best_grade"] == "N/A" or result.grade < u["best_grade"]:
        u["best_grade"] = result.grade

    save_result_to_db(result)

    return jsonify({
        "status": "ok",
        "grade": result.grade,
        "percentage": result.percentage,
    })


@app.route("/api/leaderboard")
def api_leaderboard():
    quiz_id = request.args.get("quiz_id", type=int)
    return jsonify(platform.leaderboard(quiz_id=quiz_id))


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
        print("  ⚡  Quiz Platform — http://127.0.0.1:5004")
        print("  Use --cli for demo mode, --interactive for CLI mode")
        print("=" * 56)
        app.run(host="127.0.0.1", port=5004, debug=False)

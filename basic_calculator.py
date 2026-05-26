#!/usr/bin/env python3
"""
============================================================
  PROJECT 1: Basic Calculator - PREMIUM WEB EDITION
  A highly polished web-enabled calculator with glassmorphism,
  neumorphic responsive controls, memory registers, and local
  history storage.
============================================================
"""

import os
import sys
import math
import webbrowser
import threading
from flask import Flask, jsonify, request, render_template_string

# ── Original Math Logic ───────────────────────────────────────

def add(a, b):        return a + b
def subtract(a, b):   return a - b
def multiply(a, b):   return a * b

def divide(a, b):
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero!")
    return a / b

def floor_divide(a, b):
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero!")
    return a // b

def modulus(a, b):
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero!")
    return a % b

def power(a, b):      return a ** b

def square_root(a):
    if a < 0:
        raise ValueError("Cannot take square root of a negative number!")
    return math.sqrt(a)

def format_result(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        return round(value, 10)
    return value

# ── Standalone Web Interface ──────────────────────────────────

app = Flask(__name__)
app.secret_key = "calculator-web-premium-secret-2026"
HISTORY_LOGS = []

INDEX_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🧮 Neumorphic Web Calculator</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0d1117;
      --card: rgba(22, 27, 34, 0.7);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #58a6ff;
      --text: #c9d1d9;
      --font-mono: 'JetBrains Mono', monospace;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Outfit', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background-image: radial-gradient(ellipse 60% 40% at 50% -10%, rgba(88, 166, 255, 0.15), transparent 70%);
      overflow: hidden;
    }
    .wrapper {
      display: flex;
      gap: 24px;
      max-width: 620px;
      width: 90vw;
    }
    @media (max-width: 600px) { .wrapper { flex-direction: column; } }
    .card {
      background: var(--card);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 12px 40px rgba(0,0,0,0.5);
      flex: 1;
    }
    .display {
      height: 64px;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      text-align: right;
      font-size: 1.85rem;
      font-family: var(--font-mono);
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      margin-bottom: 16px;
      box-shadow: inset 0 2px 8px rgba(0,0,0,0.5);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }
    .btn {
      height: 52px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
      color: var(--text);
      font-size: 1.15rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }
    .btn:hover { background: rgba(255,255,255,0.08); transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .btn.op { background: rgba(88, 166, 255, 0.12); color: var(--accent); border-color: rgba(88, 166, 255, 0.25); }
    .btn.eq { background: linear-gradient(135deg, #58a6ff, #1f6feb); color: #fff; border: none; font-weight: 800; box-shadow: 0 4px 14px rgba(88,166,255,0.3); }
    .btn.eq:hover { box-shadow: 0 6px 20px rgba(88,166,255,0.45); }
    .history-box {
      flex: 0.8;
      max-height: 350px;
      overflow-y: auto;
    }
    .history-item {
      padding: 8px 12px;
      border-bottom: 1px solid var(--border);
      font-size: 0.82rem;
      font-family: var(--font-mono);
      color: #8b949e;
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="card">
      <div class="display" id="calcDisplay">0</div>
      <div class="grid">
        <button class="btn op" onclick="press('C')">C</button>
        <button class="btn op" onclick="press('√')">√</button>
        <button class="btn op" onclick="press('%')">%</button>
        <button class="btn op" onclick="press('/')">/</button>

        <button class="btn" onclick="press('7')">7</button>
        <button class="btn" onclick="press('8')">8</button>
        <button class="btn" onclick="press('9')">9</button>
        <button class="btn op" onclick="press('*')">*</button>

        <button class="btn" onclick="press('4')">4</button>
        <button class="btn" onclick="press('5')">5</button>
        <button class="btn" onclick="press('6')">6</button>
        <button class="btn op" onclick="press('-')">-</button>

        <button class="btn" onclick="press('1')">1</button>
        <button class="btn" onclick="press('2')">2</button>
        <button class="btn" onclick="press('3')">3</button>
        <button class="btn op" onclick="press('+')">+</button>

        <button class="btn" onclick="press('0')">0</button>
        <button class="btn" onclick="press('.')">.</button>
        <button class="btn" onclick="press('**')">**</button>
        <button class="btn eq" onclick="press('=')">=</button>
      </div>
    </div>
    
    <div class="card history-box">
      <h3 style="font-size: 1rem; margin-bottom: 12px; color: var(--accent);">📋 History Logs</h3>
      <div id="historyList">
        <div style="font-size:0.8rem; color:#8b949e;">No calculations yet.</div>
      </div>
    </div>
  </div>

  <script>
    let expr = '';
    const disp = document.getElementById('calcDisplay');
    let audioCtx = null;

    function playBeep() {
      try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.1);
        osc.frequency.setValueAtTime(750, audioCtx.currentTime);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.1);
      } catch (e) {}
    }

    function press(key) {
      playBeep();
      if (key === 'C') {
        expr = '';
        disp.textContent = '0';
      } else if (key === '=') {
        if (!expr) return;
        fetch('/api/calculate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({expression: expr})
        })
        .then(r => r.json())
        .then(d => {
          if (d.success) {
            disp.textContent = d.result;
            expr = String(d.result);
            loadHistory();
          } else {
            disp.textContent = 'Error';
            expr = '';
          }
        });
      } else if (key === '√') {
        expr = 'math.sqrt(' + expr + ')';
        disp.textContent = '√(' + disp.textContent + ')';
      } else {
        expr += key;
        disp.textContent = expr;
      }
    }

    function loadHistory() {
      fetch('/api/history')
        .then(r => r.json())
        .then(history => {
          const list = document.getElementById('historyList');
          list.innerHTML = '';
          if (history.length === 0) {
            list.innerHTML = '<div style="font-size:0.8rem; color:#8b949e;">No calculations yet.</div>';
            return;
          }
          history.forEach(h => {
            const d = document.createElement('div');
            d.className = 'history-item';
            d.textContent = h;
            list.appendChild(d);
          });
        });
    }
    loadHistory();
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(HISTORY_LOGS)

@app.route("/api/calculate", methods=["POST"])
def calculate():
    data = request.json or {}
    expr = data.get("expression", "").strip()
    if not expr:
        return jsonify({"success": False, "error": "Empty expression"})
        
    cleaned = "".join([c for c in expr if c in "0123456789+-*/().% "])
    if "math.sqrt" in expr:
        cleaned = expr.replace("math.sqrt", "math_sqrt")
        cleaned = "".join([c for c in cleaned if c in "0123456789+-*/().% sqrt"])
        cleaned = cleaned.replace("math_sqrt", "math.sqrt")
        
    try:
        res = eval(cleaned, {"__builtins__": None}, {"math": math})
        formatted = format_result(res)
        HISTORY_LOGS.insert(0, f"{expr} = {formatted}")
        return jsonify({"success": True, "result": formatted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── Original CLI logic ────────────────────────────────────────

def run_calculator_cli():
    print("=" * 50)
    print("        🧮  BASIC CALCULATOR  🧮")
    print("=" * 50)
    print("  Terminal interface started. Use --web to launch the browser panel.")
    print("-" * 50)
    # Simple direct interactive logic as fallback
    while True:
        try:
            expr = input("Enter sum (e.g. 10 + 5) or 'exit': ").strip()
            if expr.lower() == 'exit':
                break
            # Safe evaluate
            cleaned = "".join([c for c in expr if c in "0123456789+-*/().% "])
            print("Result:", eval(cleaned))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Error:", e)

# ── Main Entry ────────────────────────────────────────────────

if __name__ == "__main__":
    # If --cli explicitly passed, start CLI
    if "--cli" in sys.argv:
        run_calculator_cli()
    else:
        port = 5002
        print("=" * 50)
        print("  🧮  Basic Calculator - PREMIUM WEB EDITION")
        print(f"  ✨  Server live at: http://localhost:{port}")
        print("  (Run with --cli to use the standard terminal interface)")
        print("=" * 50)
        
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
        app.run(debug=False, host="0.0.0.0", port=port)

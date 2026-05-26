"""
📝 Personal Blog Site
Flask-based blog with create/edit/delete posts, tags, and search.
Run: python3 blog_site.py
Visit: http://localhost:5000
"""

import os
import sqlite3
import datetime
import re
from flask import (
    Flask, render_template_string, request, redirect,
    url_for, flash, abort, g
)
from functools import wraps

# ─── App Config ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"
DB_FILE = "blog.db"

BLOG_TITLE  = "My Personal Blog"
BLOG_TAGLINE = "Thoughts, ideas & stories ✍️"
ADMIN_PASSWORD = "admin123"  # Change this!

# ─── Database ──────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            slug       TEXT UNIQUE NOT NULL,
            body       TEXT NOT NULL,
            summary    TEXT,
            tags       TEXT DEFAULT '',
            published  INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id    INTEGER NOT NULL,
            author     TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        );
    """)
    # Sample post if empty
    c.execute("SELECT COUNT(*) FROM posts")
    if c.fetchone()[0] == 0:
        now = datetime.datetime.now().isoformat()
        c.execute("""
            INSERT INTO posts (title, slug, body, summary, tags, published, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            "Welcome to My Blog! 🎉",
            "welcome-to-my-blog",
            """This is your first blog post. You can edit or delete it from the admin panel.

Start writing about your **thoughts**, *experiences*, and **ideas**.

## Getting Started
- Click **New Post** to write your first article
- Use the admin panel to manage all posts
- Add tags to organize your content

Happy blogging! 🚀""",
            "Welcome to the blog! This is your first post.",
            "welcome,blog",
            now, now
        ))
    conn.commit()
    conn.close()

# ─── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80]

def make_unique_slug(title: str, exclude_id: int = None) -> str:
    base = slugify(title)
    slug = base
    db = get_db()
    i = 1
    while True:
        q = "SELECT id FROM posts WHERE slug=?"
        params = [slug]
        if exclude_id:
            q += " AND id!=?"
            params.append(exclude_id)
        row = db.execute(q, params).fetchone()
        if not row:
            return slug
        slug = f"{base}-{i}"
        i += 1

def nl2p(text: str) -> str:
    """Very lightweight markdown-like converter for display."""
    import html as html_module
    lines = text.split("\n")
    out = []
    for line in lines:
        line_esc = html_module.escape(line)
        # Bold
        line_esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line_esc)
        # Italic
        line_esc = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line_esc)
        # H2
        if line_esc.startswith("## "):
            out.append(f"<h2>{line_esc[3:]}</h2>")
        elif line_esc.startswith("# "):
            out.append(f"<h1>{line_esc[2:]}</h1>")
        elif line_esc.startswith("- "):
            out.append(f"<li>{line_esc[2:]}</li>")
        elif line_esc.strip() == "":
            out.append("<br>")
        else:
            out.append(f"<p>{line_esc}</p>")
    return "\n".join(out)

# ─── Templates ─────────────────────────────────────────────────────────────────

BASE_STYLE = """
<style>
  :root {
    --bg: #07090e;
    --card: rgba(16, 22, 36, 0.65);
    --accent: #7c6af7;
    --accent2: #a78bfa;
    --green: #4ade80;
    --text: #e2e8f0;
    --muted: #64748b;
    --border: rgba(255,255,255,0.07);
    --red: #f87171;
    --yellow: #facc15;
    --glow: rgba(124, 106, 247, 0.25);
  }

  /* ── Reset & Base ── */
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body {
    background: var(--bg);
    background-image:
      radial-gradient(ellipse 80% 50% at 50% -20%, rgba(124,106,247,0.15), transparent),
      radial-gradient(ellipse 60% 40% at 80% 60%, rgba(167,139,250,0.06), transparent);
    background-attachment: fixed;
    color: var(--text);
    font-family: 'Outfit', system-ui, sans-serif;
    font-weight: 400;
    font-size: 16px;
    line-height: 1.7;
    min-height: 100vh;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: rgba(124,106,247,0.35); border-radius: 8px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--accent); }

  /* ── Links ── */
  a { color: var(--accent); text-decoration: none; transition: color 0.25s ease; }
  a:hover { color: var(--accent2); text-decoration: none; }

  /* ── Navbar (glassmorphic) ── */
  .nav {
    background: rgba(16, 22, 36, 0.6);
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    padding: 16px 0;
    position: sticky; top: 0; z-index: 99;
    transition: background 0.3s ease;
  }
  .nav .inner {
    max-width: 900px; margin: auto; padding: 0 24px;
    display: flex; align-items: center; gap: 20px;
  }
  .nav .brand {
    font-size: 1.35rem; font-weight: 800;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .nav .spacer { flex: 1; }
  .nav a {
    color: var(--muted); font-size: .93rem; font-weight: 500;
    padding: 6px 14px; border-radius: 10px;
    transition: all 0.25s ease;
  }
  .nav a:hover {
    color: var(--text); background: rgba(124,106,247,0.1);
    text-decoration: none;
  }

  /* ── Container ── */
  .container { max-width: 900px; margin: 40px auto; padding: 0 24px; }

  /* ── Cards (glassmorphic) ── */
  .card {
    background: var(--card);
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 32px;
    margin-bottom: 24px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.45);
    transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
  }
  .card:hover {
    transform: translateY(-2px);
    border-color: rgba(124,106,247,0.2);
    box-shadow: 0 16px 48px rgba(0,0,0,0.5), 0 0 30px rgba(124,106,247,0.08);
  }

  /* ── Post Title ── */
  .post-title { font-size: 1.55rem; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
  .post-title a { color: var(--text); transition: color 0.25s ease; }
  .post-title a:hover { color: var(--accent2); }

  /* ── Meta ── */
  .meta { color: var(--muted); font-size: .84rem; margin: 8px 0 14px; font-weight: 300; letter-spacing: 0.02em; }

  /* ── Tags (pill-shaped) ── */
  .tag {
    display: inline-block;
    background: rgba(124,106,247,0.08);
    border: 1px solid rgba(124,106,247,0.2);
    border-radius: 50px;
    padding: 3px 14px;
    font-size: .78rem; font-weight: 500;
    color: var(--accent2);
    margin-right: 6px;
    transition: all 0.25s ease;
  }
  .tag:hover {
    background: rgba(124,106,247,0.18);
    border-color: var(--accent);
    color: #fff;
    box-shadow: 0 0 14px rgba(124,106,247,0.25);
    text-decoration: none;
  }

  /* ── Summary ── */
  .summary { color: #94a3b8; margin-bottom: 14px; font-weight: 300; line-height: 1.65; }

  /* ── Buttons ── */
  .btn {
    display: inline-block; padding: 10px 22px;
    border-radius: 12px; font-weight: 600; font-size: .9rem;
    cursor: pointer; border: none;
    transition: all 0.3s ease; text-decoration: none;
  }
  .btn-primary {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: #fff;
    box-shadow: 0 4px 20px rgba(124,106,247,0.35);
  }
  .btn-primary:hover {
    box-shadow: 0 6px 28px rgba(124,106,247,0.5);
    transform: translateY(-1px);
  }
  .btn-success {
    background: linear-gradient(135deg, #22c55e, #4ade80);
    color: #000; box-shadow: 0 4px 16px rgba(34,197,94,0.3);
  }
  .btn-danger {
    background: linear-gradient(135deg, #ef4444, var(--red));
    color: #fff; box-shadow: 0 4px 16px rgba(248,113,113,0.3);
  }
  .btn-danger:hover { box-shadow: 0 6px 24px rgba(248,113,113,0.45); transform: translateY(-1px); }
  .btn-muted {
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--border);
    color: var(--text);
  }
  .btn-muted:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.15); }
  .btn:hover { text-decoration: none; }

  /* ── Form Inputs ── */
  input, textarea, select {
    width: 100%; padding: 12px 16px;
    background: rgba(7,9,14,0.8);
    border: 1px solid var(--border);
    border-radius: 12px;
    color: var(--text); font-size: 1rem;
    font-family: 'Outfit', system-ui, sans-serif;
    outline: none; transition: all 0.3s ease;
  }
  input:focus, textarea:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(124,106,247,0.15), 0 0 20px rgba(124,106,247,0.08);
  }
  input::placeholder, textarea::placeholder { color: #475569; }
  label { display: block; color: var(--muted); font-size: .9rem; font-weight: 500; margin: 16px 0 6px; }
  textarea { resize: vertical; min-height: 220px; }

  /* ── Flash Messages ── */
  .flash {
    padding: 14px 20px; border-radius: 14px; margin-bottom: 20px;
    font-weight: 600; backdrop-filter: blur(10px);
    border-left: 4px solid transparent;
    animation: flashIn 0.4s ease;
  }
  .flash.success {
    background: rgba(20,83,45,0.5); color: var(--green);
    border-left-color: var(--green);
    box-shadow: 0 4px 16px rgba(74,222,128,0.1);
  }
  .flash.error {
    background: rgba(69,10,10,0.5); color: var(--red);
    border-left-color: var(--red);
    box-shadow: 0 4px 16px rgba(248,113,113,0.1);
  }
  @keyframes flashIn {
    from { opacity: 0; transform: translateY(-10px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* ── Hero Section ── */
  .hero { text-align: center; padding: 60px 20px 36px; }
  .hero h1 {
    font-size: 2.8rem; font-weight: 800;
    background: linear-gradient(135deg, var(--text) 0%, var(--accent) 50%, var(--accent2) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    animation: heroGlow 3s ease-in-out infinite alternate;
  }
  .hero p { color: var(--muted); margin-top: 10px; font-size: 1.1rem; font-weight: 300; }
  @keyframes heroGlow {
    from { filter: brightness(1); }
    to   { filter: brightness(1.15); }
  }

  /* ── Post Body ── */
  .post-body { line-height: 1.9; font-weight: 300; }
  .post-body h1, .post-body h2 {
    margin: 24px 0 12px; font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .post-body p { margin-bottom: 12px; }
  .post-body li { margin-left: 24px; padding: 2px 0; }

  /* ── Comments ── */
  .comment-box { border-top: 1px solid var(--border); padding-top: 22px; margin-top: 22px; }
  .comment {
    background: rgba(7,9,14,0.5);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 12px;
    transition: border-color 0.25s ease;
  }
  .comment:hover { border-color: rgba(124,106,247,0.2); }
  .comment .author { font-weight: 700; color: var(--accent); }

  /* ── Sidebar (glassmorphic) ── */
  .sidebar {
    background: var(--card);
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
  }
  .sidebar h3 {
    font-size: 1rem; font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 14px;
  }

  /* ── Grid Layout ── */
  .grid { display: grid; grid-template-columns: 1fr 280px; gap: 24px; }
  @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }

  /* ── Search ── */
  .search-form input { max-width: 380px; }

  /* ── Draft Badge ── */
  .draft-badge {
    background: rgba(250,204,21,0.15); color: var(--yellow);
    border: 1px solid rgba(250,204,21,0.3);
    border-radius: 8px; padding: 2px 10px;
    font-size: .75rem; font-weight: 700;
    letter-spacing: 0.04em;
  }

  /* ── Admin Table ── */
  table { border-collapse: collapse; }
  table th { font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; font-size: .78rem; }
  table td, table th { padding: 12px 10px; }
  table tbody tr { border-bottom: 1px solid var(--border); transition: background 0.2s ease; }
  table tbody tr:hover { background: rgba(124,106,247,0.04); }
  table tbody tr:last-child { border-bottom: none; }

  /* ── Horizontal Rule ── */
  hr { border: none; border-top: 1px solid var(--border); margin: 28px 0; }

  /* ── Animations ── */
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .container { animation: fadeInUp 0.5s ease; }
</style>
"""

NAVBAR = """
<nav class="nav">
  <div class="inner">
    <a class="brand" href="/">✍️ {{title}}</a>
    <span class="spacer"></span>
    <a href="/">Home</a>
    <a href="/new">New Post</a>
    <a href="/search">Search</a>
    <a href="/admin">Admin</a>
  </div>
</nav>
""".replace("{{title}}", BLOG_TITLE)

def page(content: str, title: str = BLOG_TITLE) -> str:
    flashes = ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} | {BLOG_TITLE}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  {BASE_STYLE}
</head><body>
{NAVBAR}
{content}
</body></html>"""

# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    q = request.args.get("tag", "")
    if q:
        posts = db.execute(
            "SELECT * FROM posts WHERE published=1 AND tags LIKE ? ORDER BY created_at DESC",
            (f"%{q}%",)
        ).fetchall()
    else:
        posts = db.execute(
            "SELECT * FROM posts WHERE published=1 ORDER BY created_at DESC"
        ).fetchall()

    all_tags = set()
    for p in db.execute("SELECT tags FROM posts WHERE published=1").fetchall():
        for t in (p["tags"] or "").split(","):
            t = t.strip()
            if t:
                all_tags.add(t)

    posts_html = ""
    if not posts:
        posts_html = '<p style="color:var(--muted)">No posts yet. <a href="/new">Write the first one!</a></p>'
    for p in posts:
        tags_html = " ".join(f'<a class="tag" href="/?tag={t.strip()}">{t.strip()}</a>'
                              for t in (p["tags"] or "").split(",") if t.strip())
        posts_html += f"""
        <div class="card">
          <div class="post-title"><a href="/post/{p['slug']}">{p['title']}</a></div>
          <div class="meta">📅 {p['created_at'][:10]}</div>
          <div class="summary">{p['summary'] or ''}</div>
          {tags_html}
          <div style="margin-top:14px">
            <a class="btn btn-primary" href="/post/{p['slug']}">Read More →</a>
          </div>
        </div>"""

    sidebar_tags = " ".join(
        f'<a class="tag" style="margin:3px;display:inline-block" href="/?tag={t}">{t}</a>'
        for t in sorted(all_tags)
    ) or "<span style='color:var(--muted)'>No tags yet</span>"

    content = f"""
    <div class="hero">
      <h1>✍️ {BLOG_TITLE}</h1>
      <p>{BLOG_TAGLINE}</p>
    </div>
    <div class="container">
      <div class="grid">
        <div>{posts_html}</div>
        <div>
          <div class="sidebar">
            <h3>🏷️ Tags</h3>
            {sidebar_tags}
          </div>
          <div class="sidebar" style="margin-top:16px">
            <h3>📊 Stats</h3>
            <p style="color:var(--muted)">Posts: <strong style="color:var(--text)">{len(posts)}</strong></p>
          </div>
        </div>
      </div>
    </div>"""
    return page(content, "Home")


@app.route("/post/<slug>")
def post(slug):
    db = get_db()
    p = db.execute("SELECT * FROM posts WHERE slug=? AND published=1", (slug,)).fetchone()
    if not p:
        abort(404)
    comments = db.execute(
        "SELECT * FROM comments WHERE post_id=? ORDER BY created_at", (p["id"],)
    ).fetchall()

    tags_html = " ".join(
        f'<a class="tag" href="/?tag={t.strip()}">{t.strip()}</a>'
        for t in (p["tags"] or "").split(",") if t.strip()
    )
    body_html = nl2p(p["body"])

    comments_html = ""
    for c in comments:
        comments_html += f"""
        <div class="comment">
          <div class="author">👤 {c['author']} <span style="color:var(--muted);font-weight:400;font-size:.8rem">{c['created_at'][:16]}</span></div>
          <p style="margin-top:6px">{c['content']}</p>
        </div>"""

    flash_msg = ""
    for category, msg in get_flashed_messages():
        flash_msg += f'<div class="flash {category}">{msg}</div>'

    content = f"""
    <div class="container">
      {flash_msg}
      <div class="card">
        <h1 class="post-title">{p['title']}</h1>
        <div class="meta">📅 {p['created_at'][:10]}  |  ✏️ Updated {p['updated_at'][:10]}</div>
        <div style="margin-bottom:14px">{tags_html}</div>
        <hr>
        <div class="post-body">{body_html}</div>
        <hr>
        <div style="display:flex;gap:8px;margin-top:6px">
          <a class="btn btn-muted" href="/edit/{p['slug']}">✏️ Edit</a>
          <a class="btn btn-danger" href="/delete/{p['slug']}" onclick="return confirm('Delete this post?')">🗑 Delete</a>
          <a class="btn btn-muted" href="/">← Back</a>
        </div>
      </div>
      <div class="card comment-box">
        <h3 style="margin-bottom:14px">💬 Comments ({len(comments)})</h3>
        {comments_html or '<p style="color:var(--muted)">No comments yet. Be the first!</p>'}
        <hr>
        <h4 style="margin:14px 0 6px">Leave a Comment</h4>
        <form method="POST" action="/post/{slug}/comment">
          <input name="author" placeholder="Your name" required style="margin-bottom:8px">
          <textarea name="content" placeholder="Your comment..." rows="3" required style="min-height:80px;margin-bottom:8px"></textarea>
          <button class="btn btn-primary" type="submit">Post Comment</button>
        </form>
      </div>
    </div>"""
    return page(content, p["title"])


@app.route("/post/<slug>/comment", methods=["POST"])
def add_comment(slug):
    db = get_db()
    p = db.execute("SELECT id FROM posts WHERE slug=? AND published=1", (slug,)).fetchone()
    if not p:
        abort(404)
    author  = request.form.get("author", "").strip()[:60]
    content = request.form.get("content", "").strip()[:1000]
    if not author or not content:
        flash("Both name and comment are required.", "error")
    else:
        now = datetime.datetime.now().isoformat()
        db.execute(
            "INSERT INTO comments (post_id, author, content, created_at) VALUES (?,?,?,?)",
            (p["id"], author, content, now)
        )
        db.commit()
        flash("Comment added!", "success")
    return redirect(url_for("post", slug=slug))


def _post_form(title="", body="", summary="", tags="", published=True,
               action="/new", btn_label="Publish Post", form_title="New Post"):
    checked = "checked" if published else ""
    return f"""
    <div class="container">
      <div class="card">
        <h2 style="margin-bottom:20px">{form_title}</h2>
        <form method="POST" action="{action}">
          <label>Title *</label>
          <input name="title" value="{title}" placeholder="Post title..." required>
          <label>Summary (shown on listing)</label>
          <input name="summary" value="{summary}" placeholder="Short description...">
          <label>Body * (supports **bold**, *italic*, ## Heading, - list)</label>
          <textarea name="body" placeholder="Write your post here...">{body}</textarea>
          <label>Tags (comma-separated)</label>
          <input name="tags" value="{tags}" placeholder="python, tutorial, life">
          <label style="display:flex;align-items:center;gap:8px;margin-top:14px">
            <input type="checkbox" name="published" {checked} style="width:auto">
            Published (uncheck to save as draft)
          </label>
          <div style="margin-top:20px;display:flex;gap:8px">
            <button class="btn btn-primary" type="submit">{btn_label}</button>
            <a class="btn btn-muted" href="/">Cancel</a>
          </div>
        </form>
      </div>
    </div>"""


@app.route("/new", methods=["GET", "POST"])
def new_post():
    if request.method == "POST":
        title   = request.form.get("title", "").strip()
        body    = request.form.get("body",  "").strip()
        summary = request.form.get("summary", "").strip()
        tags    = request.form.get("tags", "").strip()
        pub     = 1 if request.form.get("published") else 0
        if not title or not body:
            return page('<div class="container"><div class="flash error">Title and body are required.</div>'
                        + _post_form(title, body, summary, tags, bool(pub)) + "</div>")
        slug = make_unique_slug(title)
        now  = datetime.datetime.now().isoformat()
        db = get_db()
        db.execute(
            "INSERT INTO posts (title, slug, body, summary, tags, published, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (title, slug, body, summary, tags, pub, now, now)
        )
        db.commit()
        flash("Post published!" if pub else "Draft saved.", "success")
        return redirect(url_for("post", slug=slug) if pub else url_for("index"))
    return page(_post_form(), "New Post")


@app.route("/edit/<slug>", methods=["GET", "POST"])
def edit_post(slug):
    db = get_db()
    p = db.execute("SELECT * FROM posts WHERE slug=?", (slug,)).fetchone()
    if not p:
        abort(404)
    if request.method == "POST":
        title   = request.form.get("title", "").strip()
        body    = request.form.get("body", "").strip()
        summary = request.form.get("summary", "").strip()
        tags    = request.form.get("tags", "").strip()
        pub     = 1 if request.form.get("published") else 0
        if not title or not body:
            return page('<div class="flash error">Title and body required.</div>' +
                        _post_form(title, body, summary, tags, bool(pub),
                                   f"/edit/{slug}", "Update Post", "Edit Post"))
        new_slug = make_unique_slug(title, exclude_id=p["id"])
        now = datetime.datetime.now().isoformat()
        db.execute(
            "UPDATE posts SET title=?, slug=?, body=?, summary=?, tags=?, published=?, updated_at=? WHERE id=?",
            (title, new_slug, body, summary, tags, pub, now, p["id"])
        )
        db.commit()
        flash("Post updated!", "success")
        return redirect(url_for("post", slug=new_slug))
    return page(_post_form(p["title"], p["body"], p["summary"] or "", p["tags"] or "",
                            bool(p["published"]), f"/edit/{slug}", "Update Post", "✏️ Edit Post"), "Edit Post")


@app.route("/delete/<slug>")
def delete_post(slug):
    db = get_db()
    p = db.execute("SELECT id FROM posts WHERE slug=?", (slug,)).fetchone()
    if p:
        db.execute("DELETE FROM posts WHERE id=?", (p["id"],))
        db.execute("DELETE FROM comments WHERE post_id=?", (p["id"],))
        db.commit()
    flash("Post deleted.", "success")
    return redirect(url_for("index"))


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    posts = []
    if q:
        db = get_db()
        posts = db.execute(
            "SELECT * FROM posts WHERE published=1 AND (title LIKE ? OR body LIKE ? OR tags LIKE ?) ORDER BY created_at DESC",
            (f"%{q}%", f"%{q}%", f"%{q}%")
        ).fetchall()

    results_html = ""
    for p in posts:
        results_html += f"""
        <div class="card">
          <div class="post-title"><a href="/post/{p['slug']}">{p['title']}</a></div>
          <div class="meta">📅 {p['created_at'][:10]}</div>
          <div class="summary">{p['summary'] or ''}</div>
        </div>"""

    content = f"""
    <div class="container">
      <h2 style="margin-bottom:18px">🔍 Search</h2>
      <form method="GET" action="/search" class="search-form" style="margin-bottom:20px;display:flex;gap:10px">
        <input name="q" value="{q}" placeholder="Search posts...">
        <button class="btn btn-primary" type="submit">Search</button>
      </form>
      {f'<p style="color:var(--muted)">Found {len(posts)} result(s) for "<strong>{q}</strong>"</p>' if q else ''}
      {results_html or ('<p style="color:var(--muted)">No results found.</p>' if q else '')}
    </div>"""
    return page(content, "Search")


@app.route("/admin")
def admin():
    db = get_db()
    all_posts = db.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    rows = ""
    for p in all_posts:
        draft = '<span class="draft-badge">DRAFT</span>' if not p["published"] else ""
        rows += f"""
        <tr>
          <td><a href="/post/{p['slug']}">{p['title']}</a> {draft}</td>
          <td style="color:var(--muted)">{p['created_at'][:10]}</td>
          <td>{p['tags'] or '—'}</td>
          <td>
            <a class="btn btn-muted" href="/edit/{p['slug']}" style="padding:4px 10px;font-size:.8rem">Edit</a>
            <a class="btn btn-danger" href="/delete/{p['slug']}" onclick="return confirm('Delete?')" style="padding:4px 10px;font-size:.8rem">Delete</a>
          </td>
        </tr>"""

    content = f"""
    <div class="container">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px">
        <h2>🛠 Admin Panel</h2>
        <a class="btn btn-primary" href="/new">➕ New Post</a>
      </div>
      <div class="card">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="color:var(--muted);font-size:.85rem;border-bottom:1px solid var(--border)">
              <th style="text-align:left;padding:8px">Title</th>
              <th style="text-align:left;padding:8px">Date</th>
              <th style="text-align:left;padding:8px">Tags</th>
              <th style="text-align:left;padding:8px">Actions</th>
            </tr>
          </thead>
          <tbody>{rows or '<tr><td colspan="4" style="color:var(--muted);padding:20px">No posts yet.</td></tr>'}</tbody>
        </table>
      </div>
    </div>"""
    return page(content, "Admin")


@app.errorhandler(404)
def not_found(e):
    return page('<div class="container"><div class="card"><h2>404 – Page Not Found</h2><p><a href="/">← Go home</a></p></div></div>', "404"), 404


def get_flashed_messages():
    from flask import session
    msgs = session.pop("_flashes", [])
    return msgs


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print(f"  📝 {BLOG_TITLE}")
    print("  Running at: http://localhost:5000")
    print("  Admin panel: http://localhost:5000/admin")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)

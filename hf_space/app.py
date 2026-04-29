"""
redex — HF Space Web Interface
Gradio version for HuggingFace Spaces deployment.
"""

import gradio as gr
import sqlite3
import os
from pathlib import Path

DB_PATH = Path.home() / ".redex" / "redex.db"


def search_archive(query, sub, limit):
    """Search posts in the local archive."""
    if not query:
        return ""

    if not DB_PATH.exists():
        return "⚠️ No archive found. Run `redex sync` locally first."

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
        SELECT p.*, posts_fts.rank
        FROM posts_fts
        JOIN posts p ON posts_fts.rowid = p.rowid
        WHERE posts_fts MATCH ?
    """
    params = [query]
    if sub:
        sql += " AND p.subreddit = ?"
        params.append(sub)
    sql += " ORDER BY posts_fts.rank LIMIT ?"
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "🔍 No results found."

    lines = []
    for r in rows:
        lines.append(f"## 📌 {r['title']}")
        lines.append(f"**r/{r['subreddit']}** · u/{r['author']} · {r['score']} pts")
        if r.get('selftext'):
            lines.append(r['selftext'][:300])
        lines.append(f"[Reddit link](https://reddit.com/r/{r['subreddit']}/comments/{r['id']})")
        lines.append("")

    return "\n".join(lines)


def get_recent():
    """Get recent posts from archive."""
    if not DB_PATH.exists():
        return "⚠️ No archive found."

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts ORDER BY created_utc DESC LIMIT 20")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "📭 No posts in archive yet."

    lines = []
    for r in rows:
        lines.append(f"## 📌 {r['title']}")
        lines.append(f"**r/{r['subreddit']}** · u/{r['author']} · {r['score']} pts")
        if r.get('selftext'):
            lines.append(r['selftext'][:200])
        lines.append("")

    return "\n".join(lines)


def get_stats():
    """Get archive stats."""
    if not DB_PATH.exists():
        return "⚠️ Archive not initialized"

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM posts")
    posts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM comments")
    comments = cur.fetchone()[0]
    conn.close()

    return f"📊 **Archive Stats**\n\n- Posts: **{posts}**\n- Comments: **{comments}**"


# Gradio UI
with gr.Blocks(title="redex — Reddit Index") as demo:
    gr.Markdown("# 🗄️ redex — Reddit Index\n*Your offline Reddit archive.*")
    gr.Markdown("---")

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 🔍 Search")
            query = gr.Textbox(placeholder="e.g. asyncio memory leak", label="Query")
            sub = gr.Textbox(placeholder="python (optional)", label="Subreddit")
            limit = gr.Slider(5, 100, value=20, label="Max results")
            btn = gr.Button("Search", variant="primary")
            output = gr.Markdown()

        with gr.Column(scale=1):
            gr.Markdown("### 📊 Status")
            stats = gr.Markdown()
            gr.Markdown("### 📜 Recent")
            recent = gr.Markdown()

    btn.click(search_archive, inputs=[query, sub, limit], outputs=output)
    demo.load(lambda: (get_stats(), get_recent()), outputs=[stats, recent])

    gr.Markdown("---")
    gr.Markdown("Built with ❤️ by [my-ai-stack](https://github.com/my-ai-stack/redex)")

demo.launch()

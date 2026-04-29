"""HF Space: redex Web Interface"""
import streamlit as st
import subprocess
import json
import os
from pathlib import Path

st.set_page_config(page_title="redex — Reddit Index", page_icon="🗄️")
st.title("🗄️ redex — Reddit Index")
st.markdown("*Your offline Reddit archive — searchable, permanent.*")

DB_PATH = Path.home() / ".redex" / "redex.db"

# ---- Sidebar: Status ----
st.sidebar.header("Archive Status")
if DB_PATH.exists():
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM posts")
    posts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM comments")
    comments = cur.fetchone()[0]
    conn.close()
    st.sidebar.metric("Posts", posts)
    st.sidebar.metric("Comments", comments)
else:
    st.sidebar.warning("No archive yet. Run `redex sync` first.")

# ---- Search ----
st.header("🔍 Search Archive")
query = st.text_input("Search query", placeholder="e.g. asyncio memory leak")
col1, col2 = st.columns(2)
with col1:
    sub = st.text_input("Sub (optional)", placeholder="e.g. python")
with col2:
    limit = st.slider("Max results", 5, 100, 20)

if st.button("Search", type="primary") and query:
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Simple FTS search
    cur.execute("""
        SELECT p.*, posts_fts.rank
        FROM posts_fts
        JOIN posts p ON posts_fts.rowid = p.rowid
        WHERE posts_fts MATCH ?
        LIMIT ?
    """, (query, limit))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        st.info("No results found.")
    else:
        for r in rows:
            with st.expander(f"📌 {r['title'][:80]}"):
                st.caption(f"r/{r['subreddit']} · u/{r['author']} · {r['score']} pts")
                st.markdown(r.get('selftext', '')[:500])
                st.markdown(f"[View on Reddit](https://reddit.com/r/{r['subreddit']}/comments/{r['id']})")

# ---- Recent Threads ----
st.header("📜 Recent Threads")
import sqlite3
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM posts ORDER BY created_utc DESC LIMIT 10")
recent = cur.fetchall()
conn.close()

if recent:
    for r in recent:
        with st.expander(f"📌 {r['title'][:80]}"):
            st.caption(f"r/{r['subreddit']} · u/{r['author']}")
            st.markdown(r.get('selftext', '')[:300])
else:
    st.info("No posts in archive yet.")

st.markdown("---")
st.caption("Built with ❤️ by my-ai-stack · [GitHub](https://github.com/my-ai-stack/redex)")

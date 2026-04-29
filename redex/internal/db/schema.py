"""SQLite database with FTS5 full-text search."""

import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional


SCHEMA = """
-- Main tables
CREATE TABLE IF NOT EXISTS posts (
    id          TEXT PRIMARY KEY,
    subreddit   TEXT NOT NULL,
    author      TEXT NOT NULL,
    title       TEXT NOT NULL,
    selftext    TEXT,
    score       INTEGER DEFAULT 0,
    created_utc INTEGER NOT NULL,
    url         TEXT,
    permalink   TEXT,
    fetched_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id          TEXT PRIMARY KEY,
    post_id     TEXT NOT NULL,
    parent_id   TEXT,
    author      TEXT NOT NULL,
    body        TEXT NOT NULL,
    score       INTEGER DEFAULT 0,
    created_utc INTEGER NOT NULL,
    depth       INTEGER DEFAULT 0,
    fetched_at  INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS sync_state (
    sub         TEXT PRIMARY KEY,
    last_fetch  INTEGER,
    last_post_id TEXT
);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    title,
    selftext,
    content='posts',
    content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
    body,
    content='comments',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, title, selftext) VALUES (new.rowid, new.title, new.selftext);
END;

CREATE TRIGGER IF NOT EXISTS comments_ai AFTER INSERT ON comments BEGIN
    INSERT INTO comments_fts(rowid, body) VALUES (new.rowid, new.body);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_posts_sub ON posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author);
"""


class Database:
    """SQLite + FTS5 database for redex archive."""

    def __init__(self, db_path: str = "~/.redex/redex.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        if self._conn is None:
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row
            await self._conn.executescript(SCHEMA)

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ---- Upsert ----

    async def upsert_post(self, post: dict):
        """Insert or update a post."""
        await self.connect()
        await self._conn.execute("""
            INSERT OR REPLACE INTO posts
            (id, subreddit, author, title, selftext, score, created_utc, url, permalink, fetched_at)
            VALUES (:id, :subreddit, :author, :title, :selftext, :score, :created_utc, :url, :permalink, :fetched_at)
        """, {
            "id": post["id"],
            "subreddit": post["subreddit"],
            "author": post["author"],
            "title": post["title"],
            "selftext": post.get("selftext", ""),
            "score": post.get("score", 0),
            "created_utc": post["created_utc"],
            "url": post.get("url"),
            "permalink": post.get("permalink"),
            "fetched_at": int(datetime.utcnow().timestamp()),
        })
        await self._conn.commit()

    async def upsert_comment(self, comment: dict):
        """Insert or update a comment."""
        await self.connect()
        await self._conn.execute("""
            INSERT OR REPLACE INTO comments
            (id, post_id, parent_id, author, body, score, created_utc, depth, fetched_at)
            VALUES (:id, :post_id, :parent_id, :author, :body, :score, :created_utc, :depth, :fetched_at)
        """, {
            "id": comment["id"],
            "post_id": comment["post_id"],
            "parent_id": comment.get("parent_id"),
            "author": comment["author"],
            "body": comment["body"],
            "score": comment.get("score", 0),
            "created_utc": comment["created_utc"],
            "depth": comment.get("depth", 0),
            "fetched_at": int(datetime.utcnow().timestamp()),
        })
        await self._conn.commit()

    # ---- Search ----

    async def search_posts(self, query: str, sub: str = None, author: str = None, limit: int = 50) -> list[dict]:
        """Full-text search on posts."""
        await self.connect()
        sql = """
            SELECT p.*, posts_fts.rank
            FROM posts_fts
            JOIN posts p ON posts_fts.rowid = p.rowid
            WHERE posts_fts MATCH :query
        """
        params = {"query": query}
        if sub:
            sql += " AND p.subreddit = :sub"
            params["sub"] = sub
        if author:
            sql += " AND p.author = :author"
            params["author"] = author
        sql += " ORDER BY posts_fts.rank LIMIT :limit"
        params["limit"] = limit

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def search_comments(self, query: str, sub: str = None, limit: int = 50) -> list[dict]:
        """Full-text search on comments."""
        await self.connect()
        sql = """
            SELECT c.*, p.subreddit, comments_fts.rank
            FROM comments_fts
            JOIN comments c ON comments_fts.rowid = c.rowid
            JOIN posts p ON c.post_id = p.id
            WHERE comments_fts MATCH :query
        """
        params = {"query": query}
        if sub:
            sql += " AND p.subreddit = :sub"
            params["sub"] = sub
        sql += " ORDER BY comments_fts.rank LIMIT :limit"
        params["limit"] = limit

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    # ---- Thread ----

    async def get_thread(self, post_id: str) -> Optional[dict]:
        """Get post + comments for a thread."""
        await self.connect()
        async with self._conn.execute(
            "SELECT * FROM posts WHERE id = :id", {"id": post_id}
        ) as cur:
            post_row = await cur.fetchone()

        if not post_row:
            return None

        async with self._conn.execute(
            "SELECT * FROM comments WHERE post_id = :id ORDER BY created_utc",
            {"id": post_id},
        ) as cur:
            comment_rows = await cur.fetchall()

        return {
            "post": dict(post_row),
            "comments": [dict(r) for r in comment_rows],
        }

    # ---- Export ----

    async def get_threads(self, sub: str = None, since: str = None, limit: int = 1000) -> list[dict]:
        """Get threads for export."""
        await self.connect()
        sql = "SELECT * FROM posts WHERE 1=1"
        params = {}
        if sub:
            sql += " AND subreddit = :sub"
            params["sub"] = sub
        if since:
            ts = int(datetime.fromisoformat(since).timestamp())
            sql += " AND created_utc >= :since"
            params["since"] = ts
        sql += " ORDER BY created_utc DESC LIMIT :limit"
        params["limit"] = limit

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    # ---- Stats ----

    async def get_stats(self) -> dict:
        """Get archive statistics."""
        await self.connect()
        stats = {}
        async with self._conn.execute("SELECT COUNT(*) as n FROM posts") as cur:
            stats["posts"] = (await cur.fetchone())["n"]
        async with self._conn.execute("SELECT COUNT(*) as n FROM comments") as cur:
            stats["comments"] = (await cur.fetchone())["n"]
        return stats

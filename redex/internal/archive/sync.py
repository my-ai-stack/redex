"""Incremental archive sync logic."""

import asyncio
from datetime import datetime
from typing import Optional


class Archiver:
    """Handles incremental sync of Reddit content to local DB."""

    def __init__(self, db, config: dict):
        self.db = db
        self.config = config
        self.comment_depth = config["archive"].get("comment_depth", 10)

    async def sync_subreddit(
        self, client, sub: str, depth: int = 100, comment_depth: int = 10
    ):
        """Sync a subreddit's posts and comments."""
        after = None

        for i in range(0, depth, 100):
            data = await client.get_subreddit_posts(sub, limit=100, after=after)
            posts = data.get("children", [])

            for post_data in posts:
                post = post_data["data"]
                post["subreddit"] = sub  # normalize

                await self.db.upsert_post(post)

                # Fetch comments for each post
                try:
                    await self._sync_comments(client, post["id"], comment_depth)
                except Exception as e:
                    # Don't fail the whole sync for one bad post
                    print(f"  [dim]Failed to sync comments for {post['id']}: {e}[/dim]")

            after = data.get("after")
            if not after:
                break

    async def _sync_comments(self, client, post_id: str, depth: int = 10):
        """Sync comments for a post."""
        try:
            comment_tree = await client.get_comments_by_post(post_id, limit=100)
        except Exception:
            return

        # comment_tree is a 2-element list: [post_data, comments_listing]
        if len(comment_tree) < 2:
            return

        comments_listing = comment_tree[1]
        await self._flatten_comments(comments_listing, post_id, depth=depth)

    async def _flatten_comments(self, listing, post_id: str, depth: int = 0):
        """Recursively flatten comment tree into flat dicts."""
        if depth > self.comment_depth:
            return

        children = listing.get("data", {}).get("children", [])
        for item in children:
            kind = item["kind"]
            if kind == "t1":  # comment
                c = item["data"]
                comment_record = {
                    "id": c["id"],
                    "post_id": post_id,
                    "parent_id": c.get("parent_id"),
                    "author": c["author"],
                    "body": c["body"],
                    "score": c.get("score", 0),
                    "created_utc": c["created_utc"],
                    "depth": depth,
                }
                await self.db.upsert_comment(comment_record)

                # Recurse into replies
                if c.get("replies"):
                    await self._flatten_comments(c["replies"], post_id, depth=depth + 1)
            elif kind == "t3":  # nested post (continue)
                pass

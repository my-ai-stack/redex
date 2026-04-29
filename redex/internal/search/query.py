"""Search engine with FTS + optional semantic search."""

import asyncio
from typing import Optional


class SearchEngine:
    """Search engine for redex archive — FTS + optional semantic."""

    def __init__(self, db, config: dict, semantic: bool = False):
        self.db = db
        self.config = config
        self.semantic = semantic and config["search"]["semantic"].get("enabled", False)
        self._embedding_model = None

    def _load_semantic(self):
        """Lazy-load sentence-transformers model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                model_name = self.config["search"]["semantic"]["model"]
                self._embedding_model = SentenceTransformer(model_name)
            except ImportError:
                raise ImportError(
                    "Semantic search requires sentence-transformers. "
                    "Install with: pip install redex[semantic]"
                )

    async def search(
        self,
        query: str,
        sub: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search posts via FTS5. Optionally re-rank with semantic search."""
        if self.semantic:
            return await self._semantic_search(query, sub=sub, author=author, limit=limit)
        else:
            return await self.db.search_posts(query, sub=sub, author=author, limit=limit)

    async def _semantic_search(
        self, query: str, sub: Optional[str] = None, author: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """FTS + semantic re-ranking."""
        self._load_semantic()

        # First pass: broad FTS retrieval
        fts_results = await self.db.search_posts(query, sub=sub, author=author, limit=200)
        if not fts_results:
            return []

        # Generate query embedding
        query_emb = self._embedding_model.encode(query)

        # Score each result by cosine similarity
        scored = []
        for post in fts_results:
            text = f"{post['title']} {post.get('selftext', '')}"
            emb = self._embedding_model.encode(text)
            score = float(query_emb @ emb.T)  # cosine similarity
            post["score"] = score
            scored.append(post)

        # Sort and return top K
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

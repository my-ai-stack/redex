#!/usr/bin/env python3
"""Quick test for redex module."""
import sys, asyncio
sys.path.insert(0, '.')
from redex.cli import _run
from redex.internal.db.schema import Database
from redex.internal.api.reddit import RedditClient
from redex.internal.archive.sync import Archiver
from redex.internal.search.query import SearchEngine
print("All imports OK")

async def test():
    db = Database("~/.redex/test.db")
    await db.connect()
    stats = await db.get_stats()
    await db.close()
    return stats

result = _run(test())
print(f"DB test OK: {result}")

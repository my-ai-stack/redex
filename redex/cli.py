#!/usr/bin/env python3
"""redex — Reddit Index CLI"""

import sys
import os

# Ensure local package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import click
from rich.console import Console
from rich.table import Table

console = Console()


def _run(coro):
    """Run an async coroutine from sync context."""
    return asyncio.run(coro)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """redex — Reddit Index: Your searchable, offline Reddit archive."""
    pass


@main.command()
def auth():
    """Authenticate with Reddit OAuth."""
    from .internal.api.reddit import RedditClient

    console.print("[bold blue]🔐 redex auth[/bold blue]")
    console.print("To get credentials: https://www.reddit.com/prefs/apps")
    console.print()
    console.print("[yellow]⚠️  Warning:[/yellow] redex stores your Reddit credentials locally.")
    console.print("[yellow]          Credentials are stored in config.yaml — treat it as a secret.[/yellow]")

    client_id = click.prompt("Client ID")
    client_secret = click.prompt("Client Secret", hide_input=True)
    username = click.prompt("Reddit Username")
    password = click.prompt("Reddit Password", hide_input=True)

    client = RedditClient(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
    )

    if _run(client.authenticate()):
        console.print("[green]✅ Authentication successful![/green]")
        console.print("[dim]Token stored in config.yaml[/dim]")
    else:
        console.print("[red]❌ Authentication failed. Check your credentials.[/red]")
        raise click.Abort()


@main.command()
@click.argument("sub", required=False)
@click.option("--depth", default=100, help="Number of posts to fetch")
@click.option("--comments", default=10, help="Max comment depth")
def sync(sub, depth, comments):
    """Sync subreddits, saved posts, or specific threads."""
    from .internal.api.reddit import RedditClient
    from .internal.archive.sync import Archiver
    from .internal.db.schema import Database

    console.print("[bold blue]📦 redex sync[/bold blue]")

    config = _load_config()
    db = Database(config["archive"]["db_path"])
    archiver = Archiver(db, config)
    client = RedditClient.from_config(config["reddit"])

    if not _run(client.authenticate()):
        console.print("[red]❌ Not authenticated. Run `redex auth` first.[/red]")
        raise click.Abort()

    console.print("[dim]Connected. Syncing...[/dim]")

    if sub:
        console.print(f"[dim]Syncing r/{sub} (depth={depth})...[/dim]")
        _run(archiver.sync_subreddit(client, sub, depth=depth, comment_depth=comments))
    else:
        subs = config["archive"]["default_subs"]
        console.print(f"[dim]Syncing {len(subs)} default subs: {', '.join(subs)}[/dim]")
        for s in subs:
            _run(archiver.sync_subreddit(client, s, depth=depth, comment_depth=comments))

    console.print("[green]✅ Sync complete![/green]")
    stats = _run(db.get_stats())
    console.print(f"[dim]DB now has {stats['posts']} posts, {stats['comments']} comments[/dim]")
    _run(client.close())


@main.command()
@click.argument("query")
@click.option("--sub", help="Filter by subreddit")
@click.option("--author", help="Filter by author")
@click.option("--semantic", is_flag=True, help="Use semantic search (requires sentence-transformers)")
@click.option("--limit", default=20, help="Max results")
def search(query, sub, author, semantic, limit):
    """Search your archive."""
    from .internal.search.query import SearchEngine
    from .internal.db.schema import Database

    config = _load_config()
    db = Database(config["archive"]["db_path"])
    engine = SearchEngine(db, config, semantic=semantic)

    console.print(f"[bold blue]🔍 Searching:[/bold blue] [yellow]{query}[/yellow]")
    if sub:
        console.print(f"[dim]sub: r/{sub}[/dim]")
    if author:
        console.print(f"[dim]author: u/{author}[/dim]")

    results = _run(engine.search(query, sub=sub, author=author, limit=limit))

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    table = Table(title=f"Found {len(results)} result(s)")
    table.add_column("Score", style="cyan", width=6)
    table.add_column("Sub", style="magenta", width=15)
    table.add_column("Title", style="white")
    table.add_column("Author", style="dim", width=15)

    for r in results:
        title = r["title"][:60] + ("..." if len(r["title"]) > 60 else "")
        table.add_row(
            f"{r.get('score', 0):.2f}",
            f"r/{r['subreddit']}",
            title,
            f"u/{r['author']}",
        )

    console.print(table)


@main.command()
@click.argument("thread_id")
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "text"]))
def thread(thread_id, fmt):
    """Render a full thread as Markdown."""
    from .internal.db.schema import Database

    config = _load_config()
    db = Database(config["archive"]["db_path"])

    data = _run(db.get_thread(thread_id))
    if not data:
        console.print(f"[red]Thread {thread_id} not found in archive.[/red]")
        raise click.Abort()

    post, comments = data["post"], data["comments"]

    output = f"""# {post['title']}

> **r/{post['subreddit']}** by u/{post['author']} | {post['score']} pts | {post['created_utc']}
>
> {post.get('selftext', '') or '(link post)'}

---

## Comments ({len(comments)})

"""

    for c in comments:
        depth = min(c.get("depth", 0), 10)
        indent = "  " * depth
        output += f"{indent}- **{c['author']}** ({c['score']} pts): {c['body']}\n"

    console.print(output)


@main.command()
@click.option("--sub", help="Subreddit to export")
@click.option("--since", help="ISO date filter (e.g. 2024-01-01)")
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "json"]))
@click.argument("outdir", type=click.Path())
def export(sub, since, fmt, outdir):
    """Export threads to Markdown files."""
    from .internal.db.schema import Database
    import os
    import json

    config = _load_config()
    db = Database(config["archive"]["db_path"])

    threads = _run(db.get_threads(sub=sub, since=since))
    console.print(f"[dim]Exporting {len(threads)} threads to {outdir}...[/dim]")

    os.makedirs(outdir, exist_ok=True)

    for t in threads:
        fname = f"{t['id']}.{fmt}"
        fpath = os.path.join(outdir, fname)

        if fmt == "markdown":
            content = f"""# {t['title']}

> r/{t['subreddit']} by u/{t['author']} | {t['score']} pts
{"> " + t.get("selftext", "") if t.get("selftext") else ""}

"""
        else:
            content = json.dumps(t, indent=2)

        with open(fpath, "w") as f:
            f.write(content)

    console.print(f"[green]✅ Exported {len(threads)} files to {outdir}[/green]")


# ---- Config loader ----

def _load_config():
    """Load config.yaml from redex package dir or cwd."""
    import yaml
    from pathlib import Path

    # Look in: ./config.yaml, ~/.redex/config.yaml, ./redex/config.yaml
    search = [
        Path("config.yaml"),
        Path("~/.redex/config.yaml").expanduser(),
        Path(__file__).parent.parent / "config.yaml",
    ]

    for p in search:
        if p.exists():
            with open(p) as f:
                return yaml.safe_load(f)

    console.print("[red]❌ No config.yaml found![/red]")
    console.print("[dim]Copy config.yaml.example to config.yaml and fill in your Reddit credentials.[/dim]")
    raise click.Abort()

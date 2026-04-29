---
title: redex
emoji: 🗄️
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "4.0.0"
python_version: "3.11"
app_file: app.py
pinned: false
---

# 🗄️ redex — Reddit Index

> "Google for your Reddit life."

A local-first CLI tool that makes Reddit yours — searchable, permanent, and offline.

## Features

- **Full-text search** — SQLite FTS5, milliseconds response
- **Incremental sync** — only fetches new content since last run
- **Rate-limit aware** — plays nice with Reddit's 100 QPM free tier
- **Offline reading** — export threads as clean Markdown

## How It Works

1. Run `redex sync` locally to build your archive
2. This Space searches your local `~/.redex/redex.db` database
3. Query by keyword, subreddit, or author

## Local Setup

```bash
pip install redex
redex auth  # enter your Reddit credentials
redex sync  # sync default subreddits
redex search "your query"
```

Get credentials at https://www.reddit.com/prefs/apps

## Learn More

- [GitHub](https://github.com/my-ai-stack/redex)

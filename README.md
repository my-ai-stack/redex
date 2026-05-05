# redex — Reddit Index

> "Google for your Reddit life."

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/redex)](https://pypi.org/project/redex/)
[![Downloads](https://img.shields.io/pypi/dm/redex)](https://pypi.org/project/redex/)
[![Stars](https://img.shields.io/github/stars/my-ai-stack/redex)](https://github.com/my-ai-stack/redex/stargazers)

**redex** is a local-first CLI tool that makes Reddit yours — searchable, permanent, and offline. Archive posts and comments, search them instantly with FTS5, and export to Markdown.

## ⚡ Features

| Feature | Description |
|---------|-------------|
| 🔄 **Incremental sync** | Subscribe to subreddits, auto-fetch new content |
| 📂 **Full-text search** | SQLite FTS5, finds posts in milliseconds |
| 🧠 **Semantic search** | Optional local embeddings via `sentence-transformers` |
| 🌐 **Offline reading** | Export threads as clean Markdown |
| 📊 **Rate-limit aware** | Plays nice with Reddit's 100 QPM free tier |
| 📁 **Human-readable** | No binary lock-in, export anytime |

## 🚀 Quick Start

### Install
```bash
pip install redex
```

### Authenticate
```bash
redex auth
# Follow the prompts — get credentials at https://www.reddit.com/prefs/apps
```

### Sync
```bash
# Sync your default subreddits
redex sync

# Sync a specific subreddit
redex sync r/python --depth 100

# Set depth of comment nesting
redex sync r/LocalLLaMA --depth 100 --comments 20
```

### Search
```bash
# Full-text search
redex search "asyncio memory leak"

# Filter by subreddit
redex search "docker compose issue" --sub docker

# Filter by author
redex search "Qwen fine-tuning" --author some_username

# Semantic search (requires sentence-transformers)
redex search "async context managers python" --semantic
```

### Read Threads
```bash
# Get a thread as Markdown
redex thread t3_abc123

# Export a subreddit to Markdown files
redex export --sub python --since 2024-01-01 ./my-archive/
```

## 📦 Architecture

```
Reddit API ──▶ redex sync ──▶ SQLite + FTS5 ──▶ redex search
                                  │
                              Optional:
                          LanceDB semantic
```

## 🔧 Config

Copy `config.yaml.example` to `config.yaml` in the project root or `~/.redex/`:

```yaml
reddit:
  client_id: "..."
  client_secret: "..."
  username: "your_user"
  password: "your_pass"

archive:
  default_subs:
    - "python"
    - "LocalLLaMA"
  post_depth: 100
  db_path: "~/.redex/redex.db"
```

## 📦 Optional Dependencies

```bash
# Semantic search (local embeddings)
pip install redex[semantic]
```

## 🔗 Links

- **GitHub:** [https://github.com/my-ai-stack/redex](https://github.com/my-ai-stack/redex)

## Why redex?

Reddit's search is garbage. Content gets deleted daily. The official API is rate-limited and your data isn't yours.

redex fixes that — a local, permanent, searchable index of the Reddit content you care about.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## ⭐ Support

Star the repo if you find it useful!

---

**Built with ❤️ by [my-ai-stack](https://github.com/my-ai-stack)**

# redex — HF Space

This is a [HuggingFace Space](https://huggingface.co/spaces) for the redex web interface.

## Files
- `app.py` — Streamlit app (run with `streamlit run app.py`)
- `README.md` — This file

## Setup
```bash
pip install streamlit aiosqlite click httpx pyyaml python-dateutil tenacity rich
streamlit run app.py
```

## Note
The Space uses your local `~/.redex/redex.db` archive file.

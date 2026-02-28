# 🎬 Faceless Video Pipeline

Fully automated pipeline that turns a text script into a ready-to-upload
YouTube Shorts / TikTok video — with AI narration, stock footage, and
one-click publishing.

## How It Works

```
Script Text ──▶ edge-tts (audio) ──▶ Pexels API (background video)
                                         │
                                   moviepy (merge & render)
                                         │
                              Streamlit UI (preview & approve)
                                         │
                              Playwright (auto-upload to YT / TikTok)
```

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install the Playwright browser

```bash
playwright install chromium
```

### 3. Set your Pexels API key

```bash
cp .env.example .env
# Open .env and paste your free API key from https://www.pexels.com/api/
```

### 4. Run the app

```bash
streamlit run app.py
```

### 5. (One-time) Log into YouTube / TikTok

Click the **🔑 Login YouTube** or **🔑 Login TikTok** buttons in the
sidebar. A browser window opens — log in manually, then close it. Your
session cookies are saved locally and reused for all future uploads.

Alternatively, from the terminal:

```bash
python uploader.py --login youtube
python uploader.py --login tiktok
```

## Project Structure

| File | Purpose |
|------|---------|
| `config.py` | API keys, paths, video resolution, TTS voice |
| `tts_engine.py` | Text → MP3 via edge-tts |
| `video_fetcher.py` | Keyword → portrait stock video via Pexels |
| `video_engine.py` | Merge audio + video, loop/trim, render MP4 |
| `uploader.py` | Playwright auto-upload (YouTube / TikTok) |
| `app.py` | Streamlit UI — generate, preview, approve, upload |

## Requirements

- Python 3.10+
- A free [Pexels API key](https://www.pexels.com/api/)
- Internet connection (TTS + video download)
- Chromium (installed via Playwright)

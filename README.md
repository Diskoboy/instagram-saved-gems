# Instagram Saved Gems

Two independent tools for processing Instagram content.

📖 [Документация на русском](README.ru.md)

---

## Module 1 — Instagram Archive

Archives your saved Instagram posts from the official data export:
downloads all media, generates previews, categorizes content via AI,
and gives you three output formats to work with.

**What you get:**
- `html/index.html` — searchable web gallery with AI categories, Tools digest, and Workflow tab
- `tmp/media/` — flat export: all photos and videos in one folder, named `{postId}_filename.jpg/mp4`
- `obsidian/` — Markdown notes per post, ready to drop into your Obsidian vault

**Pipeline:**

```
saved_posts.html  →  parser.py   →  data/links.json
links.json        →  fetch.py    →  content/{id}/        (media download)
content/{id}/     →  thumbnailer →  thumbnails
content/{id}/     →  transcriber →  transcription.json   (audio → text)
content/{id}/     →  ocr.py      →  ocr.json             (screen text)
data/posts/{id}/  →  enricher.py →  enriched.json        (AI categories)
data/posts/{id}/  →  builder.py  →  html/index.html      (web gallery)
data/posts/{id}/  →  obsidian    →  obsidian/*.md
content/{id}/     →  export_flat →  tmp/media/           (flat copy)
```

---

## Module 2 — Video Analysis

Analyzes videos from any source (not just Instagram):
transcribes audio with faster-whisper, extracts on-screen text via LLM vision,
and builds an HTML report grouped by tools and content value.

```
urls.txt / .mp4  →  fetcher.py   →  content_analysis/{id}/video.mp4
video.mp4        →  transcriber  →  transcription
video.mp4        →  ocr.py       →  screen text
analysis.json    →  reporter.py  →  html/analysis.html
```

---

## Installation

```bash
git clone https://github.com/Diskoboy/instagram-saved-gems.git
cd instagram-saved-gems
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit .env with your settings
```

For Video Analysis (Module 2):
```bash
pip install -r requirements_analysis.txt
```

---

## Configuration

Copy `.env.example` to `.env` and adjust the values.

### LLM Provider

| Provider | Setting | Notes |
|----------|---------|-------|
| Ollama (local) | `LLM_PROVIDER=ollama` | Default. [ollama.com](https://ollama.com/download) → `ollama pull gemma3:4b` |
| OpenRouter | `LLM_PROVIDER=openrouter` | Set `OPENROUTER_API_KEY` |
| Anthropic Claude | `LLM_PROVIDER=claude` | Set `ANTHROPIC_API_KEY` |

OCR requires a vision-capable model: `gemma3:4b`, `llava:7b`, `moondream`.

### Browser Authentication

yt-dlp reads Instagram cookies directly from your browser (you must be logged in):

```env
BROWSER=firefox
FIREFOX_PROFILE=~/snap/firefox/common/.mozilla/firefox
```

Find your profile path:
```bash
ls ~/snap/firefox/common/.mozilla/firefox/   # Snap Firefox
ls ~/.mozilla/firefox/                        # Regular install
```

### Instagram Rate Limiting

All delays are configurable in `.env` to avoid bans:

```env
FETCH_SLEEP_MIN=3          # min delay between requests (seconds)
FETCH_SLEEP_MAX=10         # max random delay (seconds)
FETCH_SOCKET_TIMEOUT=60    # socket timeout
FETCH_RETRIES=5            # retries on failure
FETCH_EXTRACTOR_RETRIES=3  # extractor-level retries
FETCH_PROCESS_TIMEOUT=120  # hard subprocess timeout
FETCH_API_TIMEOUT=20       # Instagram API fallback timeout
```

---

## Module 1 — Usage

### 1. Get your Instagram export

Go to Instagram → Settings → Your activity → Download your information.
Choose **HTML** format. Unzip and put `saved_posts.html` (and optionally `saved_collections.html`) in the project root.

Or create a plain text file with one URL per line:
```
https://www.instagram.com/p/ABC123/
https://www.instagram.com/reel/XYZ456/
```

### 2. Run the pipeline

```bash
# Full pipeline
python run.py

# Individual steps
python run.py --only extract     # parse HTML → links.json
python run.py --only fetch       # download media from Instagram
python run.py --only thumbnails  # extract/assign thumbnails
python run.py --only transcribe  # transcribe audio (faster-whisper)
python run.py --only ocr         # extract on-screen text (ollama vision)
python run.py --only enrich      # AI categorization
python run.py --only build       # build web gallery
python run.py --only obsidian    # export to Obsidian
python run.py --only export      # flat copy to tmp/media/
```

All steps are **incremental** — already processed posts are skipped automatically.

### 3. View results

```bash
open html/index.html       # macOS
xdg-open html/index.html   # Linux
# Windows: double-click html/index.html
```

### Flat export

All media in one folder, useful for sorting or importing into photo apps:
```bash
python scripts/export_flat.py
# → tmp/media/{postId}_media_001.jpg
# → tmp/media/{postId}_media_001.mp4
```

### Obsidian export

```bash
python run.py --only obsidian
# → obsidian/{postId}.md
```

---

## Module 2 — Usage

```bash
# From URLs file
python scripts/analysis/fetcher.py --urls-file urls.txt

# From local video files
python scripts/analysis/fetcher.py --local-dir /path/to/videos

# Transcribe + OCR
python scripts/analysis/transcriber.py
python scripts/analysis/ocr.py

# Build HTML report
python scripts/analysis/reporter.py
open html/analysis.html
```

---

## Troubleshooting

**yt-dlp fails / Instagram blocks:**
- Make sure you are logged into Instagram in Firefox/Chrome
- Increase delays: `FETCH_SLEEP_MIN=5`, `FETCH_SLEEP_MAX=20`

**LLM timeout:**
Set `LLM_TIMEOUT=240` in `.env`.

**ffmpeg not found (Windows):**
Download from [github.com/BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases),
copy `ffmpeg.exe` and `ffprobe.exe` into the `bin/` folder of the project.

**OCR returns JSON blobs:**
Already handled — `clean_ocr_text()` extracts plain text automatically.

---

## run.py vs run_analysis.py

| | `run.py` | `run_analysis.py` |
|---|---|---|
| **Module** | 1 — Instagram Archive | 2 — Video Analysis |
| **Source** | `saved_posts.html` / URL list | any video: URLs, local files, mp4 |
| **Steps** | extract → fetch → thumbnails → transcribe → ocr → enrich → build → obsidian → export | fetch → transcribe → ocr → report |
| **Output** | `html/index.html` (post gallery) | `html/analysis.html` (video report) |
| **Extra flags** | `--only <step>` | `--only`, `--skip`, `--from-posts`, `--urls-file`, `--local-dir`, `--no-llm` |

Use `run.py` for your Instagram saved posts archive.
Use `run_analysis.py` for analyzing arbitrary videos from any source.

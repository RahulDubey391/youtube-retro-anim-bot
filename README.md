# YouTube Content Agent (Gemini + Google Drive + YouTube API)

Automated Python pipeline that uses **Google Gemini** (`google-genai`) to brainstorm viral topics, write high-retention scripts, generate SEO titles/descriptions/hashtags, create **Veo** video clips (with automatic fallback to **Imagen** + Ken Burns motion), render animated captions & custom thumbnails, back everything up to **Google Drive**, and upload directly to **YouTube** (both **Shorts 9:16** and **Long-Form 16:9**).

## Default Niche
- **Mind-Blowing Facts, Psychology & History** (easily customizable via `.env` or `--niche`).

---

## 1. Setup

### Install dependencies
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure `.env`
Copy `.env.example` to `.env` and add your Gemini API key:
```powershell
Copy-Item .env.example .env
```
Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) and set `GEMINI_API_KEY=...` in `.env`.

### Set up Google Cloud OAuth (YouTube + Google Drive)
1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable **YouTube Data API v3** and **Google Drive API**.
3. Configure the **OAuth consent screen** (External, add your Google account under Test Users).
4. Go to **Credentials -> Create Credentials -> OAuth client ID -> Desktop app**.
5. Download the JSON file and save it as `client_secrets.json` in this project root.

*(On your first upload run, a browser window will open to sign into your YouTube/Google account and save `token.json` for future automated runs.)*

---

## 2. Usage

### Generate locally without uploading (`--dry-run`)
```powershell
.venv\Scripts\python.exe main.py --format shorts --dry-run
```

### Generate & upload a YouTube Short (to Drive + YouTube as `private`)
```powershell
.venv\Scripts\python.exe main.py --format shorts --privacy private
```

### Generate & upload a Long-Form 16:9 video (`public`)
```powershell
.venv\Scripts\python.exe main.py --format long --privacy public
```

### Custom niche or topic
```powershell
.venv\Scripts\python.exe main.py --format shorts --niche "Space & Cosmic Mysteries" --topic "Why Time Moves Slower Near Black Holes"
```

### Force Imagen + Ken Burns motion (skip Veo)
```powershell
.venv\Scripts\python.exe main.py --format shorts --no-veo
```


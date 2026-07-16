# Meeting Pipeline

Automated backend service that processes meeting transcripts from Read.ai, extracts structured action items using LLMs (Gemini/Groq), and synchronizes them to Google Sheets and optionally Notion. It also handles initial email notifications and recurring daily reminders for open action items.

## Setup

1. Clone the repository and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and configure your credentials.

3. Start the FastAPI server locally:
   ```bash
   uvicorn app.main:app --reload
   ```

## Google Sheets Integration

1. Create a Service Account in Google Cloud Console.
2. Download the JSON key file and save it (e.g. `service_account.json`).
3. Set `GOOGLE_SERVICE_ACCOUNT_FILE` to this path in `.env`.
4. Share your target Google Sheet with the Service Account email (give Editor access).
5. Set the `SHEET_ID` in `.env` (the long string in the sheet's URL).

## Testing Locally

### Extraction Only (Standalone)
Run the extraction script against the sample transcript to verify LLM output:
```bash
python -m app.extract
```

### Full Pipeline via Manual Upload
Start the server and test using `curl`:
```bash
curl -X POST http://localhost:8000/manual-upload -F "transcript=$(cat sample_transcript.txt)"
```

### Daily Scheduler Dry Run
Run the daily reminder job manually:
```bash
python -m app.scheduler
```

## Deployment

Deployable as a standard FastAPI application on Render or Railway free/hobby tiers.
- For Webhooks: Point Read.ai's webhook configuration to `https://your-domain.com/webhook/readai`
- For Scheduler: Set up a Cron Job on Render or use GitHub Actions to run `python -m app.scheduler` daily.

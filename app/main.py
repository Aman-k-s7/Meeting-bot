import os
import hmac
import hashlib
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from app.extract import extract_action_items
from app.sheets_sync import append_action_items_to_sheet
from app.notion_sync import append_action_items_to_notion
from app.notify import send_immediate_emails

load_dotenv()
app = FastAPI(title="Meeting Pipeline")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    import os
    file_path = os.path.join(os.path.dirname(__file__), "frontend.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

# Simple in-memory cache for deduplication: { "hash": "YYYY-MM-DD" }
processed_hashes = {}

def is_duplicate(transcript_text: str) -> bool:
    text_hash = hashlib.sha256(transcript_text.encode('utf-8')).hexdigest()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    if processed_hashes.get(text_hash) == today_str:
        return True
        
    # Prune old hashes (simple cleanup)
    keys_to_delete = [k for k, v in processed_hashes.items() if v != today_str]
    for k in keys_to_delete:
        del processed_hashes[k]
        
    processed_hashes[text_hash] = today_str
    return False

def run_pipeline(transcript_text: str, user_name: str) -> dict:
    if is_duplicate(transcript_text):
        return {"status": "skipped", "message": "Exact duplicate transcript submitted today."}
        
    # 1. Extract
    meeting_data = extract_action_items(transcript_text)
    
    # 2. Sheets Sync
    appended_items = append_action_items_to_sheet(meeting_data, user_name)
    project_code = meeting_data.get("_project_code", "MTG-???")
    
    # 3. Notion Sync (Optional)
    append_action_items_to_notion(meeting_data, project_code)
    
    # 4. Immediate Emails
    if appended_items:
        send_immediate_emails(appended_items)
        
    return {
        "status": "success",
        "project_code": project_code,
        "items_processed": len(appended_items)
    }

@app.post("/webhook/readai/{user_name}")
async def readai_webhook(request: Request, user_name: str):
    signing_key = os.getenv("READAI_SIGNING_KEY")
    raw_body = await request.body()
    
    if signing_key:
        signature = request.headers.get("X-Read-Signature")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing X-Read-Signature header")
            
        expected_sig = hmac.new(
            signing_key.encode('utf-8'),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_sig, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        print("WARNING: READAI_SIGNING_KEY not set, skipping signature verification (dev mode).")
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    transcript = payload.get("transcript")
    if not transcript:
        raise HTTPException(status_code=400, detail="Missing transcript in payload")
        
    result = run_pipeline(transcript, user_name)
    return result

@app.post("/manual-upload")
async def manual_upload(
    transcript: str = Form(None),
    file: UploadFile = File(None),
    user_name: str = Form(...)
):
    transcript_text = ""
    if file and file.filename:
        content = await file.read()
        transcript_text = content.decode("utf-8")
    elif transcript:
        transcript_text = transcript
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'transcript' or 'file'")
        
    if not transcript_text.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")
        
    result = run_pipeline(transcript_text, user_name)
    return result

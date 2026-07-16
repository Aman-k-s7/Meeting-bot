import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from app.notify import send_reminder_emails_batch, send_digest_email

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def run_daily_scheduler():
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    sheet_id = os.getenv("SHEET_ID")
    worksheet_name = os.getenv("WORKSHEET_NAME", "Sheet1")
    
    if not creds_file or not os.path.exists(creds_file):
        print("Scheduler skipped: Creds file not found.")
        return
    if not sheet_id:
        print("Scheduler skipped: SHEET_ID not set.")
        return

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        print("Worksheet not found.")
        return
        
    records = worksheet.get_all_records()
    now_utc = datetime.utcnow()
    current_timestamp = now_utc.strftime("%Y-%m-%d %H:%M")
    
    reminders = []
    all_open = []
    
    # We need to update specific cells: J (Aging) and K (Email Push)
    # gspread uses 1-based indexing, header is row 1, data starts at row 2
    cells_to_update = []
    
    for idx, row in enumerate(records):
        row_num = idx + 2
        status = str(row.get("Status", "Open"))
        if status.lower() == "done":
            continue
            
        meeting_date_str = str(row.get("Meeting Date", ""))
        try:
            meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d")
            aging_days = (now_utc - meeting_date).days
        except Exception:
            aging_days = 0
            
        cells_to_update.append(gspread.Cell(row=row_num, col=10, value=aging_days)) # J is 10
        cells_to_update.append(gspread.Cell(row=row_num, col=11, value=current_timestamp)) # K is 11
        
        item_data = {
            "project_code": row.get("Project Code", ""),
            "action_item": row.get("Action Item", ""),
            "owner": row.get("Owner", ""),
            "email": row.get("Email", ""),
            "aging": aging_days
        }
        reminders.append(item_data)
        all_open.append(item_data)
        
    if cells_to_update:
        worksheet.update_cells(cells_to_update)
        print(f"Updated {len(cells_to_update) // 2} rows in Sheets.")
        
    if reminders:
        send_reminder_emails_batch(reminders)
        
    if all_open:
        send_digest_email(all_open)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_daily_scheduler()

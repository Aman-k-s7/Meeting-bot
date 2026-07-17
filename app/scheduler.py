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
    
    if not creds_file or not os.path.exists(creds_file):
        print("Scheduler skipped: Creds file not found.")
        return
    if not sheet_id:
        print("Scheduler skipped: SHEET_ID not set.")
        return

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open_by_key(sheet_id)
    worksheets = spreadsheet.worksheets()
    
    now_utc = datetime.utcnow()
    current_timestamp = now_utc.strftime("%Y-%m-%d %H:%M")
    
    all_reminders = []
    all_open_for_digest = []
    
    for worksheet in worksheets:
        # Skip internal or empty sheets
        if worksheet.title in ["Metadata", "Sheet1"]:
            continue
            
        try:
            records = worksheet.get_all_records()
        except Exception as e:
            print(f"Skipping worksheet {worksheet.title}: {e}")
            continue
            
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
            
            # Since scheduler runs daily, we don't want to overwrite the "Sent" flag 
            # if they already got their immediate email push. We can leave K alone, 
            # or update another column for "Last Reminder Sent".
            # For now, we only update Aging (J).
            
            item_data = {
                "project_code": row.get("Project Code", ""),
                "action_item": row.get("Action Item", ""),
                "owner": row.get("Owner", ""),
                "email": row.get("Email", ""),
                "aging": aging_days,
                "manager": worksheet.title
            }
            all_reminders.append(item_data)
            all_open_for_digest.append(item_data)
            
        if cells_to_update:
            worksheet.update_cells(cells_to_update)
            print(f"Updated {len(cells_to_update)} aging rows in '{worksheet.title}'.")
            
    if all_reminders:
        send_reminder_emails_batch(all_reminders)
        
    if all_open_for_digest:
        send_digest_email(all_open_for_digest)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_daily_scheduler()

import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

OWNER_EMAIL_MAP = {
    "alice": "alice@example.com",
    "bob": "bob@example.com",
    "charlie": "charlie@example.com",
    "dave": "dave@example.com",
    "eve": "eve@example.com"
}

def get_next_project_code(client: gspread.Client, sheet_id: str) -> str:
    """
    Fetches and increments the Project Code counter from a 'Metadata' worksheet.
    Returns something like MTG-001.
    """
    spreadsheet = client.open_by_key(sheet_id)
    
    try:
        metadata_sheet = spreadsheet.worksheet("Metadata")
    except gspread.exceptions.WorksheetNotFound:
        metadata_sheet = spreadsheet.add_worksheet(title="Metadata", rows=10, cols=10)
        metadata_sheet.update_acell("A1", "0") # Initialize counter
        
    current_val = metadata_sheet.acell("A1").value
    if not current_val:
        current_val = 0
    else:
        current_val = int(current_val)
        
    next_val = current_val + 1
    metadata_sheet.update_acell("A1", str(next_val))
    
    return f"MTG-{next_val:03d}"

def append_action_items_to_sheet(meeting_data: dict) -> list:
    """
    Appends action items to the Google Sheet exactly matching the schema.
    Returns the list of rows that were appended (for email notifications).
    """
    if str(os.getenv("PUSH_TO_SHEETS", "true")).lower() != "true":
        return []
        
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    sheet_id = os.getenv("SHEET_ID")
    worksheet_name = os.getenv("WORKSHEET_NAME", "Sheet1")
    
    if not creds_file or not os.path.exists(creds_file):
        print(f"Sheets sync skipped: Creds file {creds_file} not found.")
        return []
    if not sheet_id:
        print("Sheets sync skipped: SHEET_ID not set.")
        return []

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    project_code = get_next_project_code(client, sheet_id)
    spreadsheet = client.open_by_key(sheet_id)
    
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=100, cols=12)
        # Add headers as per schema
        worksheet.append_row([
            "Project Code", "Project Name", "Meeting Date", "Meeting Type",
            "Participants", "Action Item", "Owner", "Email", "Timeline",
            "Aging", "Email Push", "Status"
        ])
    
    project_name = meeting_data.get("project_name", "")
    meeting_date = meeting_data.get("meeting_date", "")
    if not meeting_date:
        meeting_date = datetime.utcnow().strftime("%Y-%m-%d")
        
    meeting_type = meeting_data.get("meeting_type", "")
    participants = "\n".join([f"- {p}" for p in meeting_data.get("participants", [])])
    
    rows_to_append = []
    appended_data = [] # Structured data for returning
    
    for item in meeting_data.get("action_items", []):
        owner_name = item.get("owner", "")
        owner_email = OWNER_EMAIL_MAP.get(owner_name.lower(), "")
        
        row = [
            project_code,                   # A: Project Code
            project_name,                   # B: Project Name
            meeting_date,                   # C: Meeting Date
            meeting_type,                   # D: Meeting Type
            participants,                   # E: Participants
            item.get("action_item", ""),    # F: Action Item
            owner_name,                     # G: Owner
            owner_email,                    # H: Email
            item.get("timeline", ""),       # I: Timeline
            "",                             # J: Aging
            "",                             # K: Email Push
            item.get("status", "Open")      # L: Status
        ]
        rows_to_append.append(row)
        
        appended_data.append({
            "project_code": project_code,
            "project_name": project_name,
            "meeting_date": meeting_date,
            "action_item": item.get("action_item", ""),
            "owner": owner_name,
            "email": owner_email,
            "timeline": item.get("timeline", "")
        })
        
    if rows_to_append:
        worksheet.append_rows(rows_to_append)
        
    meeting_data["_project_code"] = project_code
    return appended_data

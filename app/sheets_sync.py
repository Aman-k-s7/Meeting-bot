import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

import json

# Try to load real employee emails from emails.json, fallback to empty dict
OWNER_EMAIL_MAP = {}
email_json_path = os.path.join(os.path.dirname(__file__), "emails.json")
if os.path.exists(email_json_path):
    with open(email_json_path, "r", encoding="utf-8") as f:
        try:
            OWNER_EMAIL_MAP = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load emails.json: {e}")

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

def append_action_items_to_sheet(meeting_data: dict, worksheet_name: str) -> list:
    """
    Appends action items to the Google Sheet exactly matching the schema.
    Creates a new worksheet for the given worksheet_name if it doesn't exist.
    Returns the list of rows that were appended (for email notifications).
    """
    if str(os.getenv("PUSH_TO_SHEETS", "true")).lower() != "true":
        return []
        
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    sheet_id = os.getenv("SHEET_ID")
    
    if not worksheet_name:
        worksheet_name = "Meeting-Bot"
        
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
        worksheet.append_rows(rows_to_append, table_range="A1")
        
    meeting_data["_project_code"] = project_code
    return appended_data

def update_email_push_status(worksheet_name: str, successful_items: list):
    """
    Updates the 'Email Push' column to 'Sent' for items that were successfully emailed.
    """
    if not successful_items:
        return
        
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    sheet_id = os.getenv("SHEET_ID")
    if not creds_file or not os.path.exists(creds_file) or not sheet_id:
        return
    
    if not worksheet_name:
        worksheet_name = "Meeting-Bot"
        
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return

    records = worksheet.get_all_values()
    cells_to_update = []
    
    for item in successful_items:
        pc = item.get("project_code")
        ai = item.get("action_item")
        
        for i, row in enumerate(records):
            # Column A is row[0] (Project Code), Column F is row[5] (Action Item)
            if len(row) > 5 and row[0] == pc and row[5] == ai:
                # Column K is 11 (1-based index)
                cells_to_update.append(gspread.Cell(row=i+1, col=11, value="Sent"))
                
    if cells_to_update:
        worksheet.update_cells(cells_to_update)

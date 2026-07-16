import os
from notion_client import Client
from datetime import datetime
from app.sheets_sync import OWNER_EMAIL_MAP

def append_action_items_to_notion(meeting_data: dict, project_code: str):
    if str(os.getenv("PUSH_TO_NOTION", "false")).lower() != "true":
        return

    notion_api_key = os.getenv("NOTION_API_KEY")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not notion_api_key or not database_id:
        print("Notion sync skipped: NOTION_API_KEY or NOTION_DATABASE_ID not set.")
        return

    notion = Client(auth=notion_api_key)

    project_name = meeting_data.get("project_name", "")
    meeting_date = meeting_data.get("meeting_date", "")
    if not meeting_date:
        meeting_date = datetime.utcnow().strftime("%Y-%m-%d")
        
    meeting_type = meeting_data.get("meeting_type", "")
    participants = ", ".join(meeting_data.get("participants", []))

    for item in meeting_data.get("action_items", []):
        owner_name = item.get("owner", "")
        owner_email = OWNER_EMAIL_MAP.get(owner_name.lower(), "")

        # Try to parse date for Notion format
        try:
            # If it's already YYYY-MM-DD it's fine, otherwise try to extract it or fallback
            # Notion requires ISO8601 (e.g. YYYY-MM-DD)
            date_str = meeting_date
        except Exception:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        properties = {
            "Action Item": {"title": [{"text": {"content": item.get("action_item", "")}}]},
            "Project": {"rich_text": [{"text": {"content": f"{project_code} - {project_name}"}}]},
            "Meeting Date": {"date": {"start": date_str}},
            "Meeting Type": {"rich_text": [{"text": {"content": meeting_type}}]},
            "Participants": {"rich_text": [{"text": {"content": participants}}]},
            "Owner": {"rich_text": [{"text": {"content": owner_name}}]},
            "Timeline": {"rich_text": [{"text": {"content": item.get("timeline", "")}}]},
            "Status": {"select": {"name": "Open"}}
        }
        
        if owner_email:
            properties["Email"] = {"email": owner_email}
            
        try:
            notion.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
        except Exception as e:
            print(f"Error syncing to Notion: {e}")

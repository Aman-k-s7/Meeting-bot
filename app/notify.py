import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_smtp_connection():
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    
    if not host or not user or not password:
        return None
        
    server = smtplib.SMTP(host, port)
    server.starttls()
    server.login(user, password)
    return server

def send_email(to_email: str, subject: str, body: str):
    from_name = os.getenv("FROM_NAME", "Meeting Bot")
    from_email = os.getenv("SMTP_USER")
    
    msg = MIMEMultipart()
    msg['From'] = f"{from_name} <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'html'))
    
    server = get_smtp_connection()
    if server:
        try:
            server.send_message(msg)
            print(f"Email sent to {to_email}")
        finally:
            server.quit()
    else:
        print(f"[Dry Run - SMTP Not Configured] Email to {to_email} | Subject: {subject} | Body: {body}")

def send_immediate_emails(appended_items: list):
    """
    Called upon creation to email the owner of the action item.
    appended_items is a list of dicts.
    """
    if str(os.getenv("SEND_IMMEDIATE_EMAILS", "true")).lower() != "true":
        return

    for item in appended_items:
        email = item.get("email")
        if email:
            subject = f"New Action Item: {item.get('project_code')} - {item.get('project_name')}"
            body = f"""
            <p>Hi {item.get('owner')},</p>
            <p>You have been assigned a new action item from the meeting <b>{item.get('project_name')}</b> on {item.get('meeting_date')}.</p>
            <p><b>Action Item:</b> {item.get('action_item')}</p>
            <p><b>Timeline:</b> {item.get('timeline')}</p>
            <p>Please update the Google Sheet when this is completed.</p>
            """
            send_email(email, subject, body)

def send_reminder_emails_batch(reminders: list):
    """
    reminders is a list of dicts: {'email': ..., 'action_item': ..., 'aging': ...}
    Groups action items by email address and sends one digest email per owner.
    """
    grouped = {}
    for r in reminders:
        email = r.get("email")
        if not email:
            continue
        if email not in grouped:
            grouped[email] = []
        grouped[email].append(r)
        
    for email, items in grouped.items():
        subject = "Action Item Reminder(s)"
        body = "<p>You have the following open action items:</p><ul>"
        for item in items:
            body += f"<li><b>{item['project_code']}</b>: {item['action_item']} (Aging: {item['aging']} days)</li>"
        body += "</ul><p>Please mark them as 'Done' in the Google Sheet when completed.</p>"
        
        send_email(email, subject, body)
        
def send_digest_email(open_items: list):
    recipients = os.getenv("TEAM_DIGEST_RECIPIENTS")
    if not recipients or not open_items:
        return
        
    subject = "Daily Action Items Digest"
    body = "<p>Here are all currently open action items:</p><ul>"
    
    for item in open_items:
        body += f"<li><b>{item.get('project_code')}</b> ({item.get('owner')}): {item.get('action_item')} (Aging: {item.get('aging')} days)</li>"
        
    body += "</ul>"
    
    for recipient in recipients.split(","):
        email = recipient.strip()
        if email:
            send_email(email, subject, body)

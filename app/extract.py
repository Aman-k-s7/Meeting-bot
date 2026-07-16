import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
import google.generativeai as genai
from groq import Groq

class ActionItem(BaseModel):
    action_item: str = Field(description="The action item task, under ~20 words.")
    owner: str = Field(description="The person responsible for the action item.")
    timeline: str = Field(description="The deadline formatted as an exact date (YYYY-MM-DD), converting relative terms (like 'Today') using the meeting date. Empty if none mentioned.")
    status: str = Field(default="Open", description="Always set to 'Open'")

class MeetingExtraction(BaseModel):
    project_name: str = Field(description="The meeting name/title inferred from the transcript.")
    meeting_date: str = Field(description="The date of the meeting if mentioned, else empty string.")
    meeting_type: str = Field(description="The inferred category or type of the meeting.")
    participants: List[str] = Field(description="List of participant names mentioned or speaking in the transcript.")
    action_items: List[ActionItem] = Field(description="List of extracted action items.")

from datetime import datetime

def extract_action_items(transcript: str) -> dict:
    """
    Extracts structured action items from a transcript using the configured LLM.
    Does not raise errors at import time for missing keys, only at call time.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Extract structured data from the following meeting transcript.
    Only extract real commitments, not chit-chat. Each action item should be under 20 words.
    For timelines, convert relative terms (like 'Today' or 'Next Monday') into exact dates (YYYY-MM-DD). 
    Assume the meeting took place today ({today_str}) unless explicitly stated otherwise in the transcript.
    Return ONLY valid JSON matching the exact schema required.
    
    Transcript:
    {transcript}
    """
    
    if provider == "gemini":
        return _extract_gemini(prompt)
    elif provider == "groq":
        return _extract_groq(prompt)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

def _extract_gemini(prompt: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=MeetingExtraction
        )
    )
    
    response = model.generate_content(prompt)
    return json.loads(response.text)

def _extract_groq(prompt: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")
    client = Groq(api_key=api_key)
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    system_prompt = (
        "You are an assistant that extracts meeting details and action items. "
        "Convert relative timelines (like 'Today') to exact dates (YYYY-MM-DD) taking reference from the meeting date. "
        "You must respond in JSON format matching the following schema:\n"
        "{\n"
        '  "project_name": "string",\n'
        '  "meeting_date": "string",\n'
        '  "meeting_type": "string",\n'
        '  "participants": ["string", "string"],\n'
        '  "action_items": [\n'
        '    {\n'
        '      "action_item": "string",\n'
        '      "owner": "string",\n'
        '      "timeline": "string",\n'
        '      "status": "Open"\n'
        '    }\n'
        '  ]\n'
        "}"
    )
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    
    return json.loads(response.choices[0].message.content)

if __name__ == "__main__":
    from dotenv import load_dotenv
    import sys
    load_dotenv()
    
    # Read sample transcript for standalone testing
    try:
        with open("sample_transcript.txt", "r") as f:
            transcript = f.read()
    except FileNotFoundError:
        print("sample_transcript.txt not found.")
        sys.exit(1)
        
    try:
        result = extract_action_items(transcript)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Extraction failed: {e}")

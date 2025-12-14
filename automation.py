import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from groq import Groq
import os
# --- CONFIG ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "None")
GCHAT_WEBHOOK = os.getenv("GCHAT_WEBHOOK")
SHEET_NAME = os.getenv("SHEET_NAME")          # The main Google Sheet file name

TEAM = [
    'Jeffry', 'Pritika', 'Fariha', 'Krithiga', 'Maha', 'Lavanya', 
    'thakshana', 'Santy', 'Rishi', 'Veda', 'Mythreye', 'Ashween'
]

def run_daily_summary():
    print("Starting daily summary generation...")
    
    # Connect
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    today_str = datetime.now().strftime("%d-%b-%Y")

    all_updates_text = ""
    has_updates = False

    # --- AGGREGATE DATA FROM ALL SHEETS ---
    for member in TEAM:
        try:
            worksheet = sh.worksheet(member)
            records = worksheet.get_all_records()
            
            # Filter for today
            member_updates = [
                r for r in records
                if str(r['Date']) == today_str
            ]



            if member_updates:
                has_updates = True
                for u in member_updates:
                    # u['AI_Project_Class'] is the auto-classified tag from app.py
                    all_updates_text += f"- {member}: {u['Task']} - {u['Notes']}\n"

        except gspread.WorksheetNotFound:
            continue # Skip if user hasn't created a sheet yet
        except Exception as e:
            print(f"Error reading {member}: {e}")

    if not has_updates:
        print("No updates found today.")
        return

    # --- GENERATE SUMMARY ---
    client_ai = Groq(api_key=GROQ_API_KEY)
    
    prompt = f"""
    You are a Senior Technical Program Manager. 
    Summarize the following daily updates into a cohesive report.
    
    Rules:
    1. Group updates by the PROJECT NAME (e.g., Wolters, Palantir) that appears in the brackets.
    2. Format cleanly with bold headers for projects.
    3. If multiple people worked on the same project, combine their updates.

    
    Raw Data:
    {all_updates_text}
    """

    chat_completion = client_ai.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-120b",
    )
    
    final_report = chat_completion.choices[0].message.content

    # --- SEND TO CHAT ---
    message_payload = {
        "text": f"*Daily Team Dispatch - {today_str}*\n\n{final_report}"
    }
    
    requests.post(GCHAT_WEBHOOK, json=message_payload)
    print("Summary sent successfully.")

if __name__ == "__main__":
    run_daily_summary()
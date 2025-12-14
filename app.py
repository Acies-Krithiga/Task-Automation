from flask import Flask, render_template, request, redirect, url_for, flash
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from groq import Groq
from schedule import start_scheduler
from dotenv import load_dotenv
import os

load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("secret_key")  # Needed for flash messages

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "None")
GCHAT_WEBHOOK = os.getenv("GCHAT_WEBHOOK")
SHEET_NAME = os.getenv("SHEET_NAME")          # The main Google Sheet file name

# Team List (Exact names matching your request)
TEAM = [
    'Jeffry', 'Pritika', 'Fariha', 'Krithi', 'Mahalakshmi', 'Lavanya', 
    'Thakshana', 'Santhosh', 'Rishikesh', 'Vedavalli', 'Mythreye', 'Ashween'
]

# --- GOOGLE SHEETS CONNECTION ---
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

# --- THE CLASSIFIER AGENT ---
def classify_task(task_text, notes_text, days_since_last_update, date_text):
    """
    Uses Groq to intelligently tag the project name.
    Token-optimized: no people list, no history passed.
    """
    try:
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""
You are a Project Manager AI that assigns a SINGLE Project Name.

====================
RULES
====================

1. SAME INITIATIVE GROUPING
Different names referring to the same initiative must be grouped.

Examples:
- "Palantir Research"
- "Databricks Research"
→ "Palantir–Databricks"

2. CONTEXTUAL SPLITTING
Research and Partnership should be grouped UNLESS the notes clearly
indicate different goals or outcomes.

3. TIME AWARENESS
If work resumes after a long gap (>7 days), it may be a new project.

====================
SIGNALS
====================
Days since last related update: {days_since_last_update}

====================
INPUT
====================
Task: {task_text}
Notes: {notes_text}
Date: {date_text}

====================
OUTPUT
====================
Project Name (max 3 words, no explanation):
"""

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"AI Error: {e}")
        return "Unclassified"

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', team=TEAM)

@app.route('/submit', methods=['POST'])
def submit():
    try:
        name = request.form['name']
        task = request.form['task']
        notes = request.form['notes']
        docs = request.form['docs']
        day = request.form['day']
        date_str = request.form['date']  # DD-MMM-YYYY

        client = get_client()
        sh = client.open(SHEET_NAME)

        try:
            worksheet = sh.worksheet(name)

            rows = worksheet.get_all_records(
                expected_headers=[
                    "Day",
                    "Date",
                    "Task",
                    "Notes",
                    "Referring Docs"
                ]
            )

            if rows:
                last_date_str = str(rows[-1]["Date"]).strip()
                last_date = datetime.strptime(last_date_str, "%d-%b-%Y")
                days_since_last_update = (datetime.now() - last_date).days
            else:
                days_since_last_update = 0

        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=name, rows=100, cols=10)
            worksheet.append_row([
                "Day",
                "Date",
                "Task",
                "Notes",
                "Referring Docs"
            ])
            days_since_last_update = 0

        # 🔹 LLM classification (USED ONLY INTERNALLY)
        project_class = classify_task(
            task_text=task,
            notes_text=notes,
            days_since_last_update=days_since_last_update,
            date_text=date_str
        )

        # 🔹 Store ONLY human data
        worksheet.append_row([
            day,
            date_str,
            task,
            notes,
            docs
        ])

        flash(
            f"Update logged for {name}! (Auto-tagged as: {project_class})",
            "success"
        )
        return redirect(url_for('index'))

    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for('index'))
     


if __name__ == "__main__":
    start_scheduler()
    app.run(port=5000)
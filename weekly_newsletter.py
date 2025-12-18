import gspread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from groq import Groq
from jinja2 import Environment, FileSystemLoader
import os
from dotenv import load_dotenv
import requests
load_dotenv()

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SHEET_NAME = "Daily-Task-Tracker"
GCHAT_WEBHOOK = os.getenv("GCHAT_WEBHOOK")

TEAM = [
    'Jeffry', 'Pritika', 'Fariha', 'Krithiga', 'Mahalakshmi', 'Lavanya', 
    'Thakshana', 'Santhosh', 'Rishikesh', 'Vedavalli', 'Mythreye S', 
    'Ashween', 'Ashish', 'Jeffrey','Chandramohan', 'Roopa'
]

# EMAIL SETTINGS
import os

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAILS = os.getenv("RECIPIENT_EMAILS", "").split(",")


# ---------------------------------------------------
# 1. READ LAST 7 DAYS DATA (NO PROJECT COLUMN)
# ---------------------------------------------------
def get_weekly_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)

    seven_days_ago = datetime.now() - timedelta(days=8)

    # We collect RAW updates only
    updates = []

    print("Fetching data from team sheets...")

    for member in TEAM:
        try:
            worksheet = sh.worksheet(member)

            records = worksheet.get_all_records(
                expected_headers=[
                    "Day",
                    "Date",
                    "Task",
                    "Notes",
                    "Referring Docs"
                ]
            )

            for r in records:
                try:
                    row_date = datetime.strptime(
                        str(r["Date"]).strip(),
                        "%d-%b-%Y"
                    )
                except ValueError:
                    continue  # Skip bad date rows safely

                if row_date >= seven_days_ago:
                    updates.append(
                        f"{member}: {r['Task']} ({r['Notes']})"
                    )

        except gspread.WorksheetNotFound:
            continue
        except Exception as e:
            print(f"Error reading sheet for {member}: {e}")
            continue

    return updates

# ---------------------------------------------------
# 2. GENERATE WEEKLY AI CONTENT
# ---------------------------------------------------
def run_weekly_chat_summary():
        print("📊 Starting weekly chat summary...")

        # 1. Get weekly data (reuse newsletter logic)
        project_data = get_weekly_data()
        if not project_data:
            print("No weekly data found.")
            return

        # 2. Generate Chat-friendly summary via AI
        client_ai = Groq(api_key=GROQ_API_KEY)

        prompt = f"""
        You are a Senior Engineering Leader.
        Create a concise WEEKLY TEAM UPDATE for Google Chat.

        Rules:
        1. Group updates by PROJECT NAME
        2. Use short bullet points
        3. Be concise and executive-friendly
        4. No HTML, only markdown-style bullets
        5. End with a positive closing line
        6. read the notes carefully before summarising as 2 tasks can be in same notes so classify that properly
        7. Do NOT mention specific team members

        Weekly Data:
        {project_data}
        """

        completion = client_ai.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        weekly_summary = completion.choices[0].message.content.strip()

        # 3. Send to Google Chat
        date_range = f"{(datetime.now() - timedelta(days=8)).strftime('%b %d')} – {datetime.now().strftime('%b %d')}"
        message_payload = {
            "text": f"📊 Weekly Engineering Summary ({date_range})\n\n{weekly_summary}"
        }

        requests.post(GCHAT_WEBHOOK, json=message_payload)
        print("✅ Weekly chat summary sent.")

def generate_newsletter_content(updates):
    client = Groq(api_key=GROQ_API_KEY)

    # ---------------------------------------------------
    # 1. EXECUTIVE SUMMARY
    # ---------------------------------------------------
    intro_prompt = f"""
You are a Senior Engineering Manager.

Write a concise executive summary (maximum 3 sentences, ~75 words or less)
based on the weekly updates below.

Guidelines:
- Focus only on the major areas of progress or focus for the week
- Keep it high-level and leadership-oriented
- Do NOT mention specific team members
- Do NOT describe individual tasks in depth
- Donot add Development word to the titles also read the notes carefully before summarising as 2 tasks can be in same notes so classify that properly
- Donot put team memebers name in the updates instead just focus on the tasks and projects
- Give it in a positive tone and not so chatgptish
- Even if a person has put update for one day include their name in the updates & team contributions
- Donot add extra words like collabrated if it is connected leave it as connected
- Donot include the team members name if there are others names it's ok to have it
Weekly Updates:
{updates}
"""

    intro_res = client.chat.completions.create(
        messages=[{"role": "user", "content": intro_prompt}],
        model="openai/gpt-oss-120b"
    )

    executive_summary = intro_res.choices[0].message.content.strip()

    # ---------------------------------------------------
    # 2. PROJECT GROUPING + REPHRASED CONTENT
    # ---------------------------------------------------
    project_prompt = f"""
Group the following updates by logical project or initiative.
Infer appropriate project names.

Guidelines:
- Rephrase the content clearly and professionally
- Preserve the original meaning exactly (do NOT change substance)
- Carefully read both tasks and notes before summarizing
- Tag ALL team members explicitly mentioned in the updates for each project
- Do NOT invent work or add assumptions
- Do NOT include markdown or explanations
- Don't over segmentations like for the same set of people if they are doing 4 tasks donot put each point as seperate task instead try and club:example-if it is all related to  Research & Outreach Initiative then put it to gether
- Donot add Development word to the titles also read the notes carefully before summarising as 2 tasks can be in same notes so classify that properly
- Donot put same content in multiple projects instead classify it properly
- When summarizing work within a project, avoid repeating the same activity across multiple points.
-If an update exists even for ONE day → include it
- If it doesn’t logically connect to other work → keep it as a separate stream
- If an update involves presentations, demos, pitch decks, CLTV discussions,
stakeholder coordination, or enablement activities, it MUST NOT be grouped
with product build, implementation, or engineering work — even if the
technology or domain is the same.


If an activity (such as debugging, testing, or review) appears in multiple updates, mention it once in a consolidated manner rather than restating it.
Combine related efforts into a single, coherent statement wherever possible.

Return ONLY valid JSON in the format below:

{{
  "Project Name": {{
      "tasks": [
          "Accurately rephrased point 1",
          "Accurately rephrased point 2"
      ],
      "team_members": [
          "Jane",
          "Bob",
          "Alice"
      ]
  }}
}}

Weekly Updates:
{updates}
"""

    proj_res = client.chat.completions.create(
        messages=[{"role": "user", "content": project_prompt}],
        model="openai/gpt-oss-120b"
    )

    # ---------------------------------------------------
    # 3. SAFE JSON PARSING (NO eval)
    # ---------------------------------------------------
    import json, re

    raw = proj_res.choices[0].message.content
    cleaned = re.sub(r"```json|```", "", raw).strip()
    project_summaries = json.loads(cleaned)

    return executive_summary, project_summaries


# ---------------------------------------------------
# 3. SEND EMAIL
# ---------------------------------------------------
def send_email(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Weekly Team Digest - {datetime.now().strftime('%d-%b-%Y')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENT_EMAILS)

    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
        server.quit()
        print("✅ Weekly Newsletter Sent Successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# ---------------------------------------------------
# 4. MAIN WEEKLY JOB
# ---------------------------------------------------
def run_email_weekly():
    updates = get_weekly_data()

    if not updates:
        print("No data found for the last 7 days.")
        return

    print("Generating AI weekly summaries...")
    exec_summary, project_summaries = generate_newsletter_content(updates)

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("email_template.html")

    date_range_str = (
        f"{(datetime.now() - timedelta(days=8)).strftime('%d-%b-%Y')} "
        f"- {datetime.now().strftime('%d-%b-%Y')}"
    )

    final_html = template.render(
        date_range=date_range_str,
        executive_summary=exec_summary,
        project_summaries=project_summaries
    )
    
    send_email(final_html)
    run_weekly_chat_summary()

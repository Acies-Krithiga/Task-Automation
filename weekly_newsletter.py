import gspread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from groq import Groq
from jinja2 import Environment, FileSystemLoader
import os

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "None")
SHEET_NAME = "Daily Tracker"

TEAM = [
    'Jeff', 'Pritika', 'Fariha', 'Krithi', 'Maha', 'Lavanya',
    'thakshana', 'Santy', 'Rishi', 'Veda', 'Mythreye', 'Ashween'
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

    seven_days_ago = datetime.now() - timedelta(days=7)

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
def generate_newsletter_content(updates):
    client = Groq(api_key=GROQ_API_KEY)

    # --- Executive Summary ---
    intro_prompt = f"""
You are a Senior Engineering Manager.
Write a concise 3-sentence executive summary
based on these weekly updates.

Updates:
{updates}
"""

    intro_res = client.chat.completions.create(
        messages=[{"role": "user", "content": intro_prompt}],
        model="openai/gpt-oss-120b"
    )

    executive_summary = intro_res.choices[0].message.content

    # --- Project Grouping + Bullet Points ---
    project_prompt = f"""
Group the following updates by logical project or initiative.
Infer project names yourself.
For each project, generate bullet points.

Return JSON in this format:
{{
  "Project Name": {{
      "tasks": ["point 1", "point 2"],
      "team_members": "Names"
  }}
}}

Updates:
{updates}
"""

    proj_res = client.chat.completions.create(
        messages=[{"role": "user", "content": project_prompt}],
        model="openai/gpt-oss-120b"
    )

    project_summaries = eval(proj_res.choices[0].message.content)

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
        f"{(datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')} "
        f"- {datetime.now().strftime('%d-%b-%Y')}"
    )

    final_html = template.render(
        date_range=date_range_str,
        executive_summary=exec_summary,
        project_summaries=project_summaries
    )

    send_email(final_html)

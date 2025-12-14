from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time

from automation import run_daily_summary
from weekly_newsletter import run_email_weekly  # adjust if needed

def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # -------------------------
    # DAILY UPDATE – 9:30 PM
    # -------------------------
    scheduler.add_job(
        func=run_daily_summary,
        trigger="cron",
        hour=14,
        minute=35,
        id="daily_gchat_update",
        replace_existing=True
    )

    # -------------------------
    # WEEKLY UPDATE – MON 10 AM
    # -------------------------
    scheduler.add_job(
        func=weekly_email_job,
        trigger="cron",
        day_of_week="sun",
        hour=17,
        minute=25,
        id="weekly_email_update",
        replace_existing=True
    )

    scheduler.start()
    print("✅ Scheduler started")

    return scheduler


def weekly_email_job():
    print("📧 Starting weekly email job...", datetime.now())

    try:
        run_email_weekly()
        print("✅ Weekly email sent successfully")

    except Exception as e:
        print("❌ Weekly email failed:", str(e))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from . import models
from .scrapers import get_scraper
from .email import send_daily_report
from datetime import datetime
import requests

scheduler = BackgroundScheduler()

def run_all_scrapes():
    """Cron job: scrape all active sources"""
    db = models.SessionLocal()
    try:
        sources = db.query(models.Source).filter(models.Source.active == True).all()
        total_new = 0
        
        for source in sources:
            try:
                scraper = get_scraper(source)
                results = scraper.scrape()
                
                for r in results:
                    existing = db.query(models.Lead).filter(
                        models.Lead.user_id == source.user_id,
                        models.Lead.title == r["title"]
                    ).first()
                    
                    if not existing:
                        lead = models.Lead(
                            user_id=source.user_id,
                            source_id=source.id,
                            title=r["title"],
                            description=r.get("description", ""),
                            url=r.get("url", ""),
                            company=r.get("company", ""),
                            location=r.get("location", "")
                        )
                        db.add(lead)
                        total_new += 1
                
                source.last_scraped = datetime.utcnow()
            except Exception as e:
                print(f"Scheduler error for source {source.id}: {e}")
        
        db.commit()
        print(f"[Scheduler] Scraped {len(sources)} sources, {total_new} new leads")
    finally:
        db.close()

def send_daily_reports():
    """Cron job: send daily email reports"""
    db = models.SessionLocal()
    try:
        users = db.query(models.User).filter(models.User.active == True).all()
        
        for user in users:
            if not user.email or user.email == "demo@leadradar.dk":
                continue
            
            leads = db.query(models.Lead).filter(
                models.Lead.user_id == user.id,
                models.Lead.notified == False
            ).all()
            
            if not leads:
                continue
            
            lead_data = []
            for lead in leads:
                badge = "new"
                if lead.source:
                    if "job" in lead.source.source_type:
                        badge = "job"
                    elif "news" in lead.source.source_type:
                        badge = "news"
                
                lead_data.append({
                    "title": lead.title,
                    "company": lead.company,
                    "description": lead.description[:200],
                    "url": lead.url,
                    "location": lead.location or "Danmark",
                    "badge": badge
                })
                lead.notified = True
            
            db.commit()
            
            # Call API to send email (avoids SMTP threading issues)
            try:
                send_daily_report(user.email, lead_data)
                print(f"[Scheduler] Sent report to {user.email} ({len(lead_data)} leads)")
            except Exception as e:
                print(f"[Scheduler] Email error for {user.email}: {e}")
    finally:
        db.close()

def init_scheduler():
    scheduler.add_job(
        run_all_scrapes,
        trigger=CronTrigger(hour=6, minute=0),  # Daily at 6 AM
        id="daily_scrape",
        replace_existing=True
    )
    scheduler.add_job(
        send_daily_reports,
        trigger=CronTrigger(hour=7, minute=0),  # Daily at 7 AM
        id="daily_email",
        replace_existing=True
    )
    scheduler.start()
    print("[Scheduler] Started. Jobs: daily_scrape @ 06:00, daily_email @ 07:00")

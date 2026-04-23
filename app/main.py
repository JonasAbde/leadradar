from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import os
import json

from . import models
from .scrapers import get_scraper
from .email import send_daily_report

app = FastAPI(title="LeadRadar", description="Autonomous lead monitoring for SMBs")

# Mount static and templates
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass
templates = Jinja2Templates(directory="templates")

# Init DB on startup
@app.on_event("startup")
def startup():
    models.init_db()

# Dependencies
def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============== PUBLIC PAGES ==============

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard - simplified MVP"""
    # For MVP, show demo data or first user
    user = db.query(models.User).first()
    if not user:
        return templates.TemplateResponse("onboard.html", {"request": request})
    
    leads = db.query(models.Lead).filter(
        models.Lead.user_id == user.id
    ).order_by(models.Lead.created_at.desc()).limit(50).all()
    
    sources = db.query(models.Source).filter(
        models.Source.user_id == user.id
    ).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "leads": leads,
        "sources": sources,
        "lead_count": len(leads),
        "new_today": len([l for l in leads if l.created_at.date() == datetime.utcnow().date()])
    })

# ============== API ENDPOINTS ==============

@app.post("/api/sources")
def create_source(
    name: str = Form(...),
    source_type: str = Form(...),
    url: str = Form(""),
    keywords: str = Form(""),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).first()
    if not user:
        user = models.User(email="demo@leadradar.dk")
        db.add(user)
        db.commit()
        db.refresh(user)
    
    config = json.dumps({"keywords": [k.strip() for k in keywords.split(",") if k.strip()]})
    
    source = models.Source(
        user_id=user.id,
        name=name,
        source_type=source_type,
        url=url,
        config=config
    )
    db.add(source)
    db.commit()
    
    return {"status": "ok", "source_id": source.id}

@app.get("/api/sources")
def list_sources(db: Session = Depends(get_db)):
    user = db.query(models.User).first()
    if not user:
        return {"sources": []}
    return {"sources": [
        {"id": s.id, "name": s.name, "type": s.source_type, "active": s.active}
        for s in user.sources
    ]}

@app.post("/api/scrape/{source_id}")
def trigger_scrape(source_id: int, db: Session = Depends(get_db)):
    source = db.query(models.Source).filter(models.Source.id == source_id).first()
    if not source:
        raise HTTPException(404, "Source not found")
    
    scraper = get_scraper(source)
    results = scraper.scrape()
    
    leads_created = 0
    for r in results:
        # Check if lead already exists (simple dedup)
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
            leads_created += 1
    
    source.last_scraped = datetime.utcnow()
    db.commit()
    
    return {"scraped": len(results), "new_leads": leads_created}

@app.post("/api/scrape-all")
def scrape_all(db: Session = Depends(get_db)):
    """Trigger scraping for all active sources"""
    sources = db.query(models.Source).filter(models.Source.active == True).all()
    total_new = 0
    
    for source in sources:
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
    
    db.commit()
    return {"sources_scraped": len(sources), "new_leads": total_new}

@app.post("/api/send-report")
def send_report(db: Session = Depends(get_db)):
    """Send daily report to user"""
    user = db.query(models.User).first()
    if not user:
        return {"status": "no user"}
    
    today = datetime.utcnow().date()
    leads = db.query(models.Lead).filter(
        models.Lead.user_id == user.id,
        models.Lead.notified == False
    ).all()
    
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
    
    if user.email and user.email != "demo@leadradar.dk":
        send_daily_report(user.email, lead_data)
    
    return {"status": "sent", "leads": len(lead_data)}

@app.post("/api/onboard")
def onboard(email: str = Form(...), db: Session = Depends(get_db)):
    user = models.User(email=email)
    db.add(user)
    db.commit()
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

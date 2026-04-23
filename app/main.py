from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import json
import csv
import io

from . import models
from .auth import (
    get_current_user, get_current_user_optional,
    hash_password, verify_password, create_access_token
)
from .scrapers import get_scraper
from .email import send_daily_report
from .stripe_config import get_checkout_session_url, handle_webhook, SUBSCRIPTION_LIMITS

app = FastAPI(title="LeadRadar", description="Autonomous lead monitoring for SMBs")

# Templates
templates = Jinja2Templates(directory="templates")

# Init DB on startup
@app.on_event("startup")
def startup():
    models.init_db()

# ============== PUBLIC PAGES ==============

@app.get("/", response_class=HTMLResponse)
def landing(request: Request, user: models.User = Depends(get_current_user_optional)):
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "user": user
    })

@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request, user: models.User = Depends(get_current_user_optional)):
    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "user": user
    })

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# ============== AUTH API ==============

@app.post("/api/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(models.get_db)
):
    # Check if user exists
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        raise HTTPException(400, "Email already registered")
    
    user = models.User(
        email=email,
        password_hash=hash_password(password),
        subscription_tier="free"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create token and redirect
    token = create_access_token(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*30)
    return response

@app.post("/api/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(models.get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    
    token = create_access_token(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*30)
    return response

@app.get("/api/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("access_token")
    return response

# ============== DASHBOARD ==============

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    leads = db.query(models.Lead).filter(
        models.Lead.user_id == user.id
    ).order_by(models.Lead.created_at.desc()).limit(100).all()
    
    sources = db.query(models.Source).filter(
        models.Source.user_id == user.id
    ).all()
    
    limits = SUBSCRIPTION_LIMITS.get(user.subscription_tier, SUBSCRIPTION_LIMITS["free"])
    
    today = datetime.utcnow().date()
    new_today = len([l for l in leads if l.created_at.date() == today])
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "leads": leads,
        "sources": sources,
        "lead_count": len(leads),
        "new_today": new_today,
        "limits": limits,
        "source_limit": limits["sources"],
        "can_add_source": len(sources) < limits["sources"]
    })

# ============== API ENDPOINTS ==============

@app.post("/api/sources")
def create_source(
    name: str = Form(...),
    source_type: str = Form(...),
    url: str = Form(""),
    keywords: str = Form(""),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    # Check source limit
    limits = SUBSCRIPTION_LIMITS.get(user.subscription_tier, SUBSCRIPTION_LIMITS["free"])
    current_count = db.query(models.Source).filter(models.Source.user_id == user.id).count()
    if current_count >= limits["sources"]:
        raise HTTPException(403, "Source limit reached. Upgrade to add more.")
    
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
    db.refresh(source)
    
    return {"status": "ok", "source_id": source.id}

@app.delete("/api/sources/{source_id}")
def delete_source(
    source_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    source = db.query(models.Source).filter(
        models.Source.id == source_id,
        models.Source.user_id == user.id
    ).first()
    if not source:
        raise HTTPException(404, "Source not found")
    
    db.delete(source)
    db.commit()
    return {"status": "deleted"}

@app.get("/api/sources")
def list_sources(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    sources = db.query(models.Source).filter(models.Source.user_id == user.id).all()
    return {"sources": [
        {"id": s.id, "name": s.name, "type": s.source_type, "active": s.active, "last_scraped": s.last_scraped.isoformat() if s.last_scraped else None}
        for s in sources
    ]}

@app.post("/api/scrape/{source_id}")
def trigger_scrape(
    source_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    source = db.query(models.Source).filter(
        models.Source.id == source_id,
        models.Source.user_id == user.id
    ).first()
    if not source:
        raise HTTPException(404, "Source not found")
    
    scraper = get_scraper(source)
    results = scraper.scrape()
    
    leads_created = 0
    for r in results:
        existing = db.query(models.Lead).filter(
            models.Lead.user_id == user.id,
            models.Lead.title == r["title"]
        ).first()
        
        if not existing:
            lead = models.Lead(
                user_id=user.id,
                source_id=source.id,
                title=r["title"],
                description=r.get("description", ""),
                url=r.get("url", ""),
                company=r.get("company", ""),
                location=r.get("location", ""),
                score=r.get("score", 0)
            )
            db.add(lead)
            leads_created += 1
    
    source.last_scraped = datetime.utcnow()
    db.commit()
    
    return {"scraped": len(results), "new_leads": leads_created}

@app.post("/api/scrape-all")
def scrape_all(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    sources = db.query(models.Source).filter(
        models.Source.user_id == user.id,
        models.Source.active == True
    ).all()
    total_new = 0
    
    for source in sources:
        scraper = get_scraper(source)
        results = scraper.scrape()
        
        for r in results:
            existing = db.query(models.Lead).filter(
                models.Lead.user_id == user.id,
                models.Lead.title == r["title"]
            ).first()
            
            if not existing:
                lead = models.Lead(
                    user_id=user.id,
                    source_id=source.id,
                    title=r["title"],
                    description=r.get("description", ""),
                    url=r.get("url", ""),
                    company=r.get("company", ""),
                    location=r.get("location", ""),
                    score=r.get("score", 0)
                )
                db.add(lead)
                total_new += 1
        
        source.last_scraped = datetime.utcnow()
    
    db.commit()
    return {"sources_scraped": len(sources), "new_leads": total_new}

@app.post("/api/leads/{lead_id}/status")
def update_lead_status(
    lead_id: int,
    status: str = Form(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id,
        models.Lead.user_id == user.id
    ).first()
    if not lead:
        raise HTTPException(404, "Lead not found")
    
    lead.status = status
    db.commit()
    return {"status": "ok"}

@app.get("/api/leads/export")
def export_leads(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Export leads as CSV"""
    leads = db.query(models.Lead).filter(
        models.Lead.user_id == user.id
    ).order_by(models.Lead.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Company", "Description", "Location", "URL", "Status", "Score", "Created"])
    
    for lead in leads:
        writer.writerow([
            lead.title,
            lead.company,
            lead.description,
            lead.location,
            lead.url,
            lead.status,
            lead.score,
            lead.created_at.strftime("%Y-%m-%d %H:%M")
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leadradar_export.csv"}
    )

@app.post("/api/send-report")
def send_report(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    leads = db.query(models.Lead).filter(
        models.Lead.user_id == user.id,
        models.Lead.notified == False
    ).all()
    
    if not leads:
        return {"status": "no new leads"}
    
    lead_data = []
    for lead in leads:
        badge = lead.source.source_type if lead.source else "new"
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
    
    if user.email:
        success = send_daily_report(user.email, lead_data, f"http://57.128.215.250:8000/dashboard")
        return {"status": "sent" if success else "failed", "leads": len(lead_data)}
    
    return {"status": "no email configured"}

# ============== STRIPE ==============

@app.get("/api/create-checkout-session")
def create_checkout(
    tier: str,
    user: models.User = Depends(get_current_user)
):
    if tier not in ["pro", "agency"]:
        raise HTTPException(400, "Invalid tier")
    
    try:
        url = get_checkout_session_url(user.email, tier)
        return {"url": url}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/stripe-webhook")
def stripe_webhook(request: Request):
    payload = request.body()
    sig_header = request.headers.get("stripe-signature")
    
    event = handle_webhook(payload, sig_header)
    if not event:
        raise HTTPException(400, "Invalid webhook")
    
    # Handle subscription events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Update user subscription in DB
        pass
    
    return {"status": "ok"}

# ============== HEALTH ==============

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

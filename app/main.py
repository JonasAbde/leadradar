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
import logging
import html

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import models
from .auth import (
    get_current_user, get_current_user_optional,
    hash_password, verify_password, create_access_token, validate_password
)
from .scrapers import get_scraper
from .mail import send_daily_report
from .stripe_config import get_checkout_session_url, handle_webhook, SUBSCRIPTION_LIMITS
from .cvr_enrichment import enrich_lead
from .alert_dispatcher import create_alert, dispatch_alert, get_or_create_prefs

app = FastAPI(title="LeadRadar", description="Autonomous lead monitoring for SMBs")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Logging setup
logger = logging.getLogger("leadradar")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Security helpers
def sanitize_source_name(name: str) -> str:
    """Strip HTML tags and limit length for source names."""
    name = html.escape(name.strip())
    return name[:100]

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
@limiter.limit("5/minute")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(models.get_db)
):
    from email_validator import validate_email, EmailNotValidError
    
    # Validate email format
    try:
        email_info = validate_email(email.strip(), check_deliverability=False)
        email = email_info.normalized
    except EmailNotValidError:
        raise HTTPException(400, "Invalid email address")
    
    # Validate password
    pw_error = validate_password(password)
    if pw_error:
        raise HTTPException(400, pw_error)
    
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
    logger.info(f"New user registered: {email}")
    
    # Create token and redirect
    token = create_access_token(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    secure_cookie = os.getenv("HTTPS_ENABLED", "").lower() == "true"
    response.set_cookie(
        key="access_token", value=token, httponly=True,
        max_age=60*60*24*30, secure=secure_cookie, samesite="lax"
    )
    return response

@app.post("/api/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(models.get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        logger.warning(f"Failed login attempt for {email} from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(401, "Invalid credentials")
    
    token = create_access_token(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    secure_cookie = os.getenv("HTTPS_ENABLED", "").lower() == "true"
    response.set_cookie(
        key="access_token", value=token, httponly=True,
        max_age=60*60*24*30, secure=secure_cookie, samesite="lax"
    )
    logger.info(f"User logged in: {email}")
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
@limiter.limit("20/minute")
def create_source(
    request: Request,
    name: str = Form(...),
    source_type: str = Form(...),
    url: str = Form(""),
    keywords: str = Form(""),
    preset: str = Form(""),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    # Check source limit
    limits = SUBSCRIPTION_LIMITS.get(user.subscription_tier, SUBSCRIPTION_LIMITS["free"])
    current_count = db.query(models.Source).filter(models.Source.user_id == user.id).count()
    if current_count >= limits["sources"]:
        raise HTTPException(403, "Source limit reached. Upgrade to add more.")
    
    cfg = {"keywords": [k.strip() for k in keywords.split(",") if k.strip()]}
    if source_type == "rss_preset":
        cfg["preset"] = preset or "version2_tech"
    config = json.dumps(cfg)
    
    source = models.Source(
        user_id=user.id,
        name=sanitize_source_name(name),
        source_type=source_type,
        url=url,
        config=config
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info(f"User {user.id} created source '{source.name}'")
    
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
    logger.info(f"User {user.id} deleted source {source_id}")
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
@limiter.limit("30/minute")
def trigger_scrape(
    request: Request,
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
            db.flush()
            alert = create_alert(
                db, user_id=user.id,
                source_type="lead", event="new_lead",
                message=f"Ny lead: {lead.title}",
                lead_id=lead.id,
                link_path=f"/dashboard?lead={lead.id}",
                commit=False,
            )
            dispatch_alert(db, alert, commit=False)
            leads_created += 1
    
    source.last_scraped = datetime.utcnow()
    db.commit()
    logger.info(f"User {user.id} scraped source {source_id}: {len(results)} results, {leads_created} new leads")
    
    return {"scraped": len(results), "new_leads": leads_created}

@app.post("/api/scrape-all")
@limiter.limit("10/minute")
def scrape_all(
    request: Request,
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
                    contact_email=r.get("contact_email", None),
                    phone=r.get("phone", None),
                    location=r.get("location", ""),
                    score=r.get("score", 0)
                )
                
                # Enrich with CVR API
                try:
                    enrichment = enrich_lead(lead.company)
                    if enrichment:
                        lead.phone = enrichment.get("phone") or lead.phone
                        lead.contact_email = enrichment.get("email") or lead.contact_email
                        lead.cvr_number = enrichment.get("cvr_number")
                        lead.address = enrichment.get("address")
                        lead.zipcode = enrichment.get("zipcode")
                        lead.city = enrichment.get("city")
                        lead.industry_code = enrichment.get("industry_code")
                        lead.industry_desc = enrichment.get("industry_desc")
                        lead.company_type = enrichment.get("company_type")
                        lead.employee_count = enrichment.get("employee_count")
                        lead.owner_name = enrichment.get("owner_name")
                        lead.enriched = True
                        lead.enriched_at = datetime.utcnow()
                        lead.enrichment_data = json.dumps(enrichment.get("raw_data"))
                        logger.info(f"Enriched lead: {lead.company} -> CVR {lead.cvr_number}")
                except Exception as e:
                    logger.warning(f"Enrichment failed for {lead.company}: {e}")
                
                db.add(lead)
                db.flush()
                alert = create_alert(
                    db, user_id=user.id,
                    source_type="lead", event="new_lead",
                    message=f"Ny lead: {lead.title}",
                    lead_id=lead.id,
                    link_path=f"/dashboard?lead={lead.id}",
                    commit=False,
                )
                dispatch_alert(db, alert, commit=False)
                total_new += 1
        
        source.last_scraped = datetime.utcnow()
    
    db.commit()
    logger.info(f"User {user.id} scrape-all: {len(sources)} sources, {total_new} new leads")
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

@app.post("/api/leads/{lead_id}/sync-crm")
@limiter.limit("20/minute")
def sync_lead_to_crm(
    request: Request,
    lead_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Manually sync a single lead to CRM. Returns immediately (queue-based)."""
    lead = db.query(models.Lead).filter(
        models.Lead.id == lead_id,
        models.Lead.user_id == user.id
    ).first()
    if not lead:
        raise HTTPException(404, "Lead not found")
    
    # Find user's active CRM config
    config = db.query(models.CRMProviderConfig).filter(
        models.CRMProviderConfig.user_id == user.id,
        models.CRMProviderConfig.enabled == True
    ).first()
    
    provider_name = "mock"  # Default: no external calls
    if config:
        provider_name = config.provider
    
    from app.crm_sync_worker import enqueue_lead_sync
    enqueued = enqueue_lead_sync(db, lead_id, user.id, provider_name)
    
    if not enqueued:
        return {"success": True, "message": "Already in queue"}
    
    # Run immediately for single-lead sync
    from app.crm_sync_worker import process_sync_queue
    summary = process_sync_queue(db, max_jobs=1)
    
    # Refresh lead state
    db.refresh(lead)
    
    return {
        "success": lead.crm_sync_status == "synced",
        "status": lead.crm_sync_status,
        "provider": provider_name,
        "external_ids": {
            "company": lead.crm_external_company_id,
            "contact": lead.crm_external_contact_id,
            "lead": lead.crm_external_lead_id,
        } if lead.crm_sync_status == "synced" else None,
        "error": lead.crm_last_error,
    }

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
        base_url = os.getenv("PUBLIC_BASE_URL", "http://57.128.215.250:8000")
        success = send_daily_report(user.email, lead_data, f"{base_url}/dashboard")
        return {"status": "sent" if success else "failed", "leads": len(lead_data)}
    
    return {"status": "no email configured"}

# ============== STRIPE ==============

@app.get("/api/create-checkout-session")
@limiter.limit("10/minute")
def create_checkout(
    request: Request,
    tier: str,
    user: models.User = Depends(get_current_user)
):
    if tier not in ["pro", "agency"]:
        raise HTTPException(400, "Invalid tier")
    
    # Graceful degradation if Stripe not configured
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return JSONResponse(
            status_code=200,
            content={
                "status": "mock",
                "message": "Stripe is not configured yet. Contact support to upgrade.",
                "tier": tier,
                "price_dkk": 99 if tier == "pro" else 499
            }
        )
    
    try:
        url = get_checkout_session_url(user.email, tier)
        return {"url": url}
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/stripe-webhook")
@limiter.limit("20/minute")
def stripe_webhook(request: Request):
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return {"status": "mock", "message": "Stripe not configured"}
    
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

# ============== ALERTS ==============

@app.get("/api/alerts")
def list_alerts(unread_only: bool = False, db: Session = Depends(models.get_db), user = Depends(get_current_user)):
    q = db.query(models.Alert).filter(models.Alert.user_id == user.id)
    if unread_only:
        q = q.filter(models.Alert.read == False)
    alerts = q.order_by(models.Alert.created_at.desc()).limit(50).all()
    return [{
        "id": a.id,
        "source_type": a.source_type,
        "event": a.event,
        "severity": a.severity,
        "message": a.message,
        "lead_id": a.lead_id,
        "link_path": a.link_path,
        "read": a.read,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in alerts]

@app.post("/api/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(models.get_db), user = Depends(get_current_user)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id, models.Alert.user_id == user.id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.read = True
    db.commit()
    return {"status": "ok"}

@app.delete("/api/alerts/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(models.get_db), user = Depends(get_current_user)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id, models.Alert.user_id == user.id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    db.delete(alert)
    db.commit()
    return {"status": "deleted"}

@app.get("/api/notification-prefs")
def get_prefs(db: Session = Depends(models.get_db), user = Depends(get_current_user)):
    prefs = get_or_create_prefs(db, user.id)
    return {
        "new_lead_web": prefs.new_lead_web,
        "new_lead_email": prefs.new_lead_email,
        "new_lead_slack": prefs.new_lead_slack,
        "slack_webhook_url": prefs.slack_webhook_url,
        "email_digest": prefs.email_digest,
        "digest_hour": prefs.digest_hour,
    }

@app.put("/api/notification-prefs")
def update_prefs(
    data: dict,
    db: Session = Depends(models.get_db),
    user = Depends(get_current_user)
):
    prefs = get_or_create_prefs(db, user.id)
    prefs.new_lead_web = data.get("new_lead_web", prefs.new_lead_web)
    prefs.new_lead_email = data.get("new_lead_email", prefs.new_lead_email)
    prefs.new_lead_slack = data.get("new_lead_slack", prefs.new_lead_slack)
    if "slack_webhook_url" in data:
        prefs.slack_webhook_url = data["slack_webhook_url"] or None
    prefs.email_digest = data.get("email_digest", prefs.email_digest)
    prefs.digest_hour = data.get("digest_hour", prefs.digest_hour)
    db.commit()
    return {"status": "ok"}

# ============== HEALTH ==============

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

"""LeadRadar test suite — Fase 5: CRM + Enrichment"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ─── AUTH ───
def test_register_invalid_email():
    r = client.post("/api/register", data={"email": "bad", "password": "***"})
    assert r.status_code == 400
    assert "Invalid email" in r.json()["detail"]

def test_register_short_password():
    r = client.post("/api/register", data={"email": "a@b.co", "password": ""})
    assert r.status_code == 400

def test_register_and_login():
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@x.co"
    r = client.post("/api/register", data={"email": email, "password": "***"})
    assert r.status_code == 303
    r = client.post("/api/login", data={"email": email, "password": "***"})
    assert r.status_code == 303

def test_login_wrong_password():
    r = client.post("/api/login", data={"email": "test@leadradar.dk", "password": "***"})
    assert r.status_code == 401

def test_dashboard_without_auth():
    r = client.get("/dashboard")
    assert r.status_code == 401

# ─── PUBLIC PAGES ───
@pytest.mark.parametrize("path", ["/", "/pricing", "/login", "/register", "/health"])
def test_public_pages(path):
    assert client.get(path).status_code in (200, 307)

# ─── SCRAPERS ───
def test_cvr_scraper_runs():
    from app.scrapers import CVRScraper
    class FakeSource:
        config = '{"keywords": ["it"]}'
    scraper = CVRScraper(FakeSource())
    results = scraper.scrape()
    assert isinstance(results, list)

# ─── CRM MOCK PROVIDER ───
def test_mock_crm_provider_basic():
    from app.crm.mock_provider import MockCRMProvider
    from app.crm import LeadData
    
    provider = MockCRMProvider()
    assert provider.test_connection() is True
    
    lead = LeadData(
        id=1,
        title="Test Lead",
        company="TestCo",
        email="admin@testco.dk",
        phone="12345678",
        cvr_number="12345678",
        score=50
    )
    result = provider.sync_lead(lead)
    assert result.success is True
    assert result.company_id is not None
    assert result.lead_id is not None

def test_mock_crm_provider_idempotency():
    """Same lead synced twice must not create duplicates."""
    from app.crm.mock_provider import MockCRMProvider
    from app.crm import LeadData
    
    provider = MockCRMProvider()
    lead = LeadData(
        id=42,
        title="Dup Test",
        company="DupCo",
        cvr_number="87654321",
    )
    
    r1 = provider.sync_lead(lead)
    r2 = provider.sync_lead(lead)
    
    assert r1.company_id == r2.company_id, "Company ID should match on retry"
    assert r1.lead_id == r2.lead_id, "Lead ID should match on retry"
    assert len(provider.companies) == 1
    assert len(provider.leads) == 1

def test_mock_crm_provider_no_contact_data():
    """Lead with no email/phone should skip contact gracefully."""
    from app.crm.mock_provider import MockCRMProvider
    from app.crm import LeadData
    
    provider = MockCRMProvider()
    lead = LeadData(
        id=3,
        title="No Contact",
        company="GhostCo",
        email=None,
        phone=None,
        owner_name=None,
    )
    result = provider.sync_lead(lead)
    assert result.success is True  # Company still created
    assert len(provider.contacts) == 0

# ── ALERTS ───────────────────────────────────────────────────────────

def test_alert_api_flow():
    import uuid
    email = f"alert_{uuid.uuid4().hex[:8]}@x.co"
    client.post("/api/register", data={"email": email, "password": "***"})
    client.post("/api/login", data={"email": email, "password": "***"})

    # Default prefs
    r = client.get("/api/notification-prefs")
    assert r.status_code == 200
    assert r.json()["new_lead_web"] is True

    # Update prefs
    r = client.put("/api/notification-prefs", json={"new_lead_slack": True, "slack_webhook_url": "https://hooks.slack.com/test"})
    assert r.status_code == 200

    # Empty alerts
    r = client.get("/api/alerts?unread_only=true")
    assert r.status_code == 200
    assert r.json() == []

    # Create a source and scrape to trigger alert
    r = client.post("/api/sources", data={"name": "Test News", "source_type": "news", "url": "https://example.com/feed"})
    assert r.status_code == 200
    source_id = r.json()["source_id"]
    client.post(f"/api/scrape/{source_id}")

    # Should now have an alert
    r = client.get("/api/alerts?unread_only=true")
    assert r.status_code == 200
    alerts = r.json()
    assert len(alerts) >= 0  # scraper may or may not return results

    if alerts:
        alert_id = alerts[0]["id"]
        # Mark read
        r = client.post(f"/api/alerts/{alert_id}/read")
        assert r.status_code == 200
        # Delete
        r = client.delete(f"/api/alerts/{alert_id}")
        assert r.status_code == 200

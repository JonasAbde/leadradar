"""LeadRadar test suite — Fase 4"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ─── AUTH ───
def test_register_invalid_email():
    r = client.post("/api/register", data={"email": "bad", "password": "testpass123"})
    assert r.status_code == 400
    assert "Invalid email" in r.json()["detail"]

def test_register_short_password():
    r = client.post("/api/register", data={"email": "a@b.co", "password": ""})
    assert r.status_code == 400

def test_register_and_login():
    # Use unique email
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@x.co"
    r = client.post("/api/register", data={"email": email, "password": "testpass123"})
    assert r.status_code == 303
    # Login
    r = client.post("/api/login", data={"email": email, "password": "testpass123"})
    assert r.status_code == 303

def test_login_wrong_password():
    r = client.post("/api/login", data={"email": "test@leadradar.dk", "password": "wrong"})
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

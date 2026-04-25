import sys, os, random, json
sys.path.insert(0, '.')
os.environ.setdefault('SECRET_KEY', 'dev_key_test_123')

from app.models import engine, Base, User, SessionLocal, Lead, Source
from app.auth import hash_password
from datetime import datetime

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Create test user
existing = db.query(User).filter(User.email == 'test@leadradar.dk').first()
if existing:
    uid = existing.id
    print(f"User exists: id={uid}")
else:
    user = User(
        email='test@leadradar.dk',
        password_hash=hash_password('test1234'),
        subscription_tier='pro',
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    uid = user.id
    print(f"Created user: id={uid}")

# Clear old data
db.query(Lead).filter(Lead.user_id == uid).delete()
db.query(Source).filter(Source.user_id == uid).delete()
db.commit()

# Create test source
source = Source(
    user_id=uid,
    name='TED EU Tenders',
    source_type='ted_eu',
    url='https://ted.europa.eu',
    config=json.dumps({'cpv_codes': ['71314320', '79960000'], 'country': 'DNK'}),
    active=True,
    created_at=datetime.utcnow()
)
db.add(source)
db.commit()
print(f"Created source: id={source.id}")

# Test leads
leads = [
    ('Renovering af kontorlokaler i København', 'Region Hovedstaden', 89, '2025-03-15', 'København'),
    ('IT-support og drift til region Sjælland', 'Sundhed IT', 78, '2025-04-01', 'Sjælland'),
    ('Facility management, Aarhus kommune', 'Aarhus kommune', 92, '2025-02-28', 'Aarhus'),
    ('Rengøringskontrakt, 5000 kvm', 'Boligforeningen Sjælland', 45, '2025-03-10', 'Roskilde'),
    ('IT-drift og overvågning, Region Midt', 'Region Midtjylland', 81, '2025-05-01', 'Aarhus'),
    ('Vinduespudsning og hovedrengøring', 'CleanService A/S', 55, '2025-04-15', 'Vejle'),
    ('Drift af IT-infrastruktur, Region Syd', 'IT-Partners A/S', 73, '2025-06-01', 'Esbjerg'),
    ('Bygning af nyt skole i Odense', 'Odense kommune', 67, '2025-07-01', 'Odense'),
    ('Rådgivning om bæredygtig energi', 'Energirådgiveren ApS', 62, '2025-03-20', 'Fredericia'),
    ('Rengøring til hospital i Odense', 'OUH', 41, '2025-02-20', 'Odense'),
]

for title, company, score, deadline, location in leads:
    lead = Lead(
        user_id=uid,
        source_id=source.id,
        title=title,
        company=company,
        description=f'Dette er en test lead med relevant CPV kode.',
        score=score,
        cpv_values=json.dumps(['71314320']),
        deadline_date=deadline,
        source_url='https://ted.europa.eu',
        location=location,
        status='new',
        created_at=datetime.utcnow()
    )
    db.add(lead)
    print(f"Added: {title}")

db.commit()
print(f"Done - {len(leads)} leads created")
db.close()

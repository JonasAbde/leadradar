import uvicorn
from app.main import app
from app.scheduler import init_scheduler
from app.models import init_db

if __name__ == "__main__":
    init_db()
    init_scheduler()
    uvicorn.run(app, host="0.0.0.0", port=8000)

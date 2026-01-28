# application.py
from app.main import app  # esta é a app real

@app.get("/")
def health():
    return {"status": "ok", "app": "barcelona"}

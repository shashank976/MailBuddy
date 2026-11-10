from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gmail_service import get_recent_emails


app = FastAPI(title="MailBuddy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "MailBuddy backend is running!"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/emails")
def read_emails():
    emails = get_recent_emails()

    return {
        "count": len(emails),
        "emails": emails
    }
import os
import json
import uuid
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

app = FastAPI()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
DATABASE_URL = os.getenv("DATABASE_URL")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ==========================
# DATABASE CONNECTION
# ==========================

def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_token(token_json):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM oauth_tokens;")
    cur.execute("INSERT INTO oauth_tokens (token) VALUES (%s);", (token_json,))

    conn.commit()
    cur.close()
    conn.close()


def load_token():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT token FROM oauth_tokens LIMIT 1;")
    result = cur.fetchone()

    cur.close()
    conn.close()

    return result[0] if result else None


# Initialize DB on startup
@app.on_event("startup")
def startup_event():
    init_db()


# ==========================
# AUTHORIZE
# ==========================

@app.get("/authorize")
def authorize():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    flow.redirect_uri = REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    return RedirectResponse(auth_url)


# ==========================
# CALLBACK
# ==========================

@app.get("/oauth2callback")
def oauth2callback(code: str):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)

    creds = flow.credentials

    save_token(creds.to_json())

    return {"message": "Authorization successful and token stored in DB ✅"}


# ==========================
# CREATE MEETING
# ==========================

@app.post("/create-meeting")
def create_meeting(
    start_time: str,
    end_time: str,
    candidate_email: str,
    interviewer_email: str
):

    token_json = load_token()

    if not token_json:
        raise HTTPException(status_code=401, detail="Authorize first")

    creds_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    # Auto refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_token(creds.to_json())

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": "Interview Meeting",
        "description": "Interview scheduled via API",
        "start": {
            "dateTime": start_time,
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end_time,
            "timeZone": "Asia/Kolkata"
        },
        "attendees": [
            {"email": candidate_email},
            {"email": interviewer_email}
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet"
                }
            }
        }
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all"
    ).execute()

    return {
        "meet_link": created_event.get("hangoutLink")
    }
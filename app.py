import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

app = FastAPI()

# ==============================
# CONFIG
# ==============================

SCOPES = ["https://www.googleapis.com/auth/calendar"]

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

TOKEN_FILE = "token.json"


# ==============================
# AUTHORIZATION ROUTE
# ==============================

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
        redirect_uri=REDIRECT_URI,
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    return RedirectResponse(auth_url)


# ==============================
# CALLBACK ROUTE
# ==============================

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
        redirect_uri=REDIRECT_URI,
    )

    flow.fetch_token(code=code)

    creds = flow.credentials

    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

    return {"message": "Authorization successful ✅ You can close this window."}


# ==============================
# LOAD & REFRESH TOKEN
# ==============================

def get_google_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise HTTPException(status_code=401, detail="Please authorize first via /authorize")

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


# ==============================
# CREATE MEETING (QUERY PARAMS)
# ==============================

@app.post("/create-meeting")
def create_meeting(
    start_time: str,
    end_time: str,
    candidate_email: str,
    interviewer_email: str,
    summary: str = "Interview Meeting"
):
    """
    Example:
    POST /create-meeting?start_time=2026-02-20T10:00:00+05:30
                         &end_time=2026-02-20T10:30:00+05:30
                         &candidate_email=test@gmail.com
                         &interviewer_email=hr@gmail.com
    """

    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": summary,
        "start": {
            "dateTime": start_time,
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time,
            "timeZone": "Asia/Kolkata",
        },
        "attendees": [
            {"email": candidate_email},
            {"email": interviewer_email},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    event = (
        service.events()
        .insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
        )
        .execute()
    )

    return {
        "status": "success",
        "meeting_link": event.get("hangoutLink"),
        "event_id": event.get("id"),
    }
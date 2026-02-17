import os
import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

app = FastAPI()

# ==============================
# ENV VARIABLES (FROM RENDER)
# ==============================

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# ==============================
# AUTHORIZE ROUTE
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
    )

    flow.redirect_uri = REDIRECT_URI

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    return RedirectResponse(authorization_url)


# ==============================
# OAUTH CALLBACK
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
    )

    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)

    creds = flow.credentials

    with open("token.json", "w") as token:
        token.write(creds.to_json())

    return {"message": "Authorization successful ✅"}


# ==============================
# CREATE MEETING
# ==============================

@app.post("/create-meeting")
def create_meeting(
    start_time: str,
    end_time: str,
    candidate_email: str,
    interviewer_email: str
):

    if not os.path.exists("token.json"):
        raise HTTPException(status_code=401, detail="Authorize first")

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # 🔥 Auto refresh token if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as token:
            token.write(creds.to_json())

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
        conferenceDataVersion=1
    ).execute()

    return {
        "meet_link": created_event.get("hangoutLink")
    }


# ==============================
# ROOT ROUTE
# ==============================

@app.get("/")
def home():
    return {"message": "Google Meet Scheduler API Running 🚀"}
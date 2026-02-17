import os
from flask import Flask, request, jsonify, redirect
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

app = Flask(__name__)

# ==========================
# CONFIGURATION
# ==========================
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = "token.json"
CREDS_FILE = "credentials.json"

# 🔥 IMPORTANT: Must match EXACTLY what is in Google Cloud Console
REDIRECT_URI = "https://meeting-service-tgf2.onrender.com/oauth2callback"

creds = None

# Load existing token if available
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)


# ==========================
# HOME ROUTE
# ==========================
@app.route("/")
def home():
    return "Meeting Service Running ✅"


# ==========================
# AUTHORIZE ROUTE
# ==========================
@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        CREDS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    return redirect(auth_url)


# ==========================
# OAUTH CALLBACK
# ==========================
@app.route("/oauth2callback")
def oauth2callback():
    global creds

    flow = Flow.from_client_secrets_file(
        CREDS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials

    # Save token permanently
    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

    return "Authorization successful ✅ You can close this window."


# ==========================
# CREATE MEETING ENDPOINT
# ==========================
@app.route("/create-meeting", methods=["POST"])
def create_meeting():
    global creds

    if not creds:
        return jsonify({"error": "Please authorize first via /authorize"}), 401

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            return jsonify({"error": "Authorization expired. Please re-authorize."}), 401

    service = build("calendar", "v3", credentials=creds)

    data = request.get_json()

    try:
        event = {
            "summary": "Interview Meeting",
            "start": {
                "dateTime": data["start_time"],
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": data["end_time"],
                "timeZone": "Asia/Kolkata",
            },
            "attendees": [
                {"email": data["candidate_email"]},
                {"email": data["interviewer_email"]},
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": "interview-" + data["start_time"]
                }
            },
        }

        event = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1
        ).execute()

        meet_link = event.get("hangoutLink")

        return jsonify({
            "status": "success",
            "meeting_link": meet_link
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==========================
# DEBUG ROUTE
# ==========================
@app.route("/routes")
def routes():
    return str(app.url_map)


# ==========================
# RUN APP
# ==========================
if __name__ == "__main__":
    app.run(debug=True)

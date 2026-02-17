import os
import datetime
import json
import pickle
from flask import Flask, request, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

creds = None

# Load token if exists
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

@app.route("/")
def home():
    return "Meeting Service Running"

@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri="http://localhost:8080/oauth2callback"
    )

    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

@app.route("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri="http://localhost:8080/oauth2callback"
    )

    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials

    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    return "Authorization successful. You can close this."

@app.route("/create-meeting", methods=["POST"])
def create_meeting():
    global creds

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            return jsonify({"error": "Not authorized"}), 401

    service = build('calendar', 'v3', credentials=creds)

    data = request.json

    event = {
        'summary': 'Interview Meeting',
        'start': {
            'dateTime': data['start_time'],
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': data['end_time'],
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': [
            {'email': data['candidate_email']},
            {'email': data['interviewer_email']},
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': 'meet123'
            }
        },
    }

    event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1
    ).execute()

    meet_link = event.get('hangoutLink')

    return jsonify({"meeting_link": meet_link})

if __name__ == "__main__":
    app.run(port=8080)

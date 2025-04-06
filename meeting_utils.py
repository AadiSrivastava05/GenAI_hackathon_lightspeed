import os
import json
import uuid
import re
import datetime
import dateparser
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import logging
from models import Meeting, User, db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']

class MeetingScheduler:
    def __init__(self, api_key=None):
        # Use provided API key or get from environment
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', None)
        
        if not self.api_key:
            logger.warning("No API key provided for MeetingScheduler.")
            self.model = None
            return
        
        # Initialize Gemini client
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def parse_meeting_details(self, query):
        """Parse natural language to meeting details using Gemini"""
        if not self.model:
            return None
        
        prompt = f"""
        Parse the following meeting request and extract the following information:
        1. Attendees (email addresses or names of people)
        2. Meeting date and time
        3. Duration (in minutes)
        4. Meeting title/subject
        5. Any additional notes
        
        Request: {query}
        
        Format your response as a JSON object with the following keys:
        {{
            "attendees": [list of attendees],
            "datetime": "YYYY-MM-DD HH:MM",
            "duration": duration in minutes (integer),
            "title": "meeting title",
            "notes": "any additional notes"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx+1]
                meeting_details = json.loads(json_str)
                return meeting_details
            else:
                return None
        except Exception as e:
            logger.error(f"Error parsing meeting details: {e}")
            return None
    
    def map_attendees_to_users(self, attendees):
        """Map attendee names/emails to User objects"""
        users = []
        unmapped_attendees = []
        
        for attendee in attendees:
            # Check if it's an email
            if re.match(r'^[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}$', attendee):
                user = User.query.filter_by(email=attendee).first()
                if user:
                    users.append(user)
                else:
                    unmapped_attendees.append(attendee)
            else:
                # Try to find user by username (case insensitive)
                user = User.query.filter(User.username.ilike(attendee)).first()
                if user:
                    users.append(user)
                else:
                    unmapped_attendees.append(attendee)
        
        return users, unmapped_attendees

def get_calendar_credentials():
    """Get Google Calendar credentials"""
    creds = None
    
    # Check if the token file exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_info(json.load(open(TOKEN_FILE)))
    
    # If credentials don't exist or are invalid
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def create_calendar_event(meeting_details, creator_id):
    """Create Google Calendar event with Google Meet link"""
    try:
        # Get credentials
        creds = get_calendar_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        # Parse datetime
        start_time = dateparser.parse(meeting_details['datetime'])
        duration = int(meeting_details['duration'])
        end_time = start_time + datetime.timedelta(minutes=duration)
        
        # Format attendees - ensure all values are strings
        attendees = [{'email': str(attendee)} for attendee in meeting_details['attendees']]
        
        # Create event with conference data
        event = {
            'summary': str(meeting_details['title']),
            'description': str(meeting_details.get('notes', '')),
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'attendees': attendees,
            'conferenceData': {
                'createRequest': {
                    'requestId': str(uuid.uuid4()),
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }
        
        # Insert the event with conferenceDataVersion=1
        event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()
        
        # Create a Meeting object
        creator = User.query.get(creator_id)
        meeting = Meeting(
            title=meeting_details['title'],
            date_time=start_time,
            duration=duration,
            notes=meeting_details['notes'],
            meet_link=event.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri', None),
            creator_id=creator_id
        )
        
        # Add attendees
        scheduler = MeetingScheduler()
        users, _ = scheduler.map_attendees_to_users(meeting_details['attendees'])
        meeting.attendees.extend(users)
        
        # Save to database
        db.session.add(meeting)
        db.session.commit()
        
        return {
            'event_id': event['id'],
            'meet_link': event.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri', 'No meet link available'),
            'meeting_id': meeting.id
        }
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return None 
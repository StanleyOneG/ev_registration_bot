import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Define the access scope for the Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar"]


# Function to get Google Calendar API credentials
def get_credentials():
    creds = None  # Initialize credentials as None
    # Check if the file 'CREDENTIALS\token json' exists
    if os.path.exists("token.json"):
        # Load credentials from the file if it exists
        creds = Credentials.from_authorized_user_file("token.json")

    # Check if credentials do not exist or are invalid
    if not creds or not creds.valid:
        # Check if credentials exist, are expired, and can be refreshed
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired credentials
            creds.refresh(Request())
        else:
            # Create a flow for handling Auth 2.0 authentication
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            # Run the Auth 2.0 authentication flow locally
            creds = flow.run_local_server(port=0)
        # Save the refreshed or newly obtained credentials to 'CREDENTIALS\ token. json'
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # Return the credentials
    return creds


# Function to create a new Google Calendar event
def create_event(service, summary, start_time, end_time):
    try:
        # Create a new event object
        event = {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "timeZone": "Europe/Moscow",
        }
        # Call the Calendar API to create the event
        event = service.events().insert(calendarId="primary", body=event).execute()
        # Print the event ID
        print("Event created with ID: %s" % (event.get("id")))

    except HttpError as error:
        print(f"An error occurred: {error}")


# Main function
def main():
    # Get Google Calendar API credentials
    creds = get_credentials()
    # Build the Google Calendar API service object
    service = build("calendar", "v3", credentials=creds)
    # Create a new event
    create_event(
        service,
        "Python Class",
        "2024-05-11T10:00:00+03:00",
        "2024-05-11T12:00:00+03:00",
    )


if __name__ == "__main__":
    main()

import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import argparse
from enum import Enum

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CommuneType(Enum):
    """Enum containing the different communes."""

    GERMAN = "german"
    AMERICAN = "american"


parser = argparse.ArgumentParser(
    description="Recreate a token file for the Google Calendar API"
)
parser.add_argument(
    "--commune",
    "-c",
    help="The commune for which to recreate the token file",
    type=str,
)


def main(commune: CommuneType):
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(f"{commune.value}_calendar_configs/token.json"):
        creds = Credentials.from_authorized_user_file(
            f"{commune.value}_calendar_configs/token.json", SCOPES
        )
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                f"{commune.value}_calendar_configs/credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(f"{commune.value}_calendar_configs/token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        # now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        now = datetime.datetime.now(datetime.UTC).isoformat()
        print("Getting the upcoming 10 events")
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return

        # Prints the start and name of the next 10 events
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(start, event["summary"])

    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    args = parser.parse_args()
    if args.commune == CommuneType.AMERICAN.value:
        main(CommuneType.AMERICAN)
        exit(0)
    elif args.commune == CommuneType.GERMAN.value:
        main(CommuneType.GERMAN)
        exit(0)
    else:
        print("Invalid commune. Please choose 'german' or 'american'.")
        exit(1)

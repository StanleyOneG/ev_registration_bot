import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from google_calendar_helper.google_calendar_get import Commune


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_credentials(commune: Commune):
    creds = None
    if os.path.exists(f"{commune.value}/token.json"):
        creds = Credentials.from_authorized_user_file(f"{commune.value}/token.json")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise ValueError("Invalid credentials")

        #     flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        #     creds = flow.run_local_server(port=0)
        # with open("token.json", "w") as token:
        #     token.write(creds.to_json())

    return creds


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    children_amount: int,
    phone: str,
    commune: Commune,
) -> bool:
    creds = get_credentials(commune)
    service = build("calendar", "v3", credentials=creds)

    try:
        event = {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "timeZone": "Europe/Moscow",
            "description": f"Кол-во детей: {children_amount}\nТел.: {phone}\nTelegram-bot",
        }
        event = service.events().insert(calendarId="primary", body=event).execute()
        logger.info("Event created with ID: %s" % (event.get("id")))
        return True

    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        return False

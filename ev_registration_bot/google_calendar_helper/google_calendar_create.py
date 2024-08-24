import logging
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from ev_registration_bot.google_calendar_helper.utils import (
    Commune,
    VisitType,
    get_visit_type_color,
)
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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


def make_description_in_calendar(
    children_amount: int,
    phone: str,
    visit_type: VisitType,
    total_guests: int | None = None,
):
    text = (
        f"Тип посещения: {'Терапия' if visit_type.name == VisitType.THERAPY.name else 'Лекция'}\n\n"
        f"Кол-во детей: {children_amount}\n\n"
        f"Тел.: {phone}\n\n"
        f"Telegram-bot"
    )
    if total_guests and visit_type.name == VisitType.LECTURE.name:
        text += f"\n\n(не редактировать) Общее кол-во гостей: {total_guests}"

    return text


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    children_amount: int,
    phone: str,
    commune: Commune,
    visit_type: VisitType,
    total_guests: int | None = None,
) -> bool:
    creds = get_credentials(commune)
    service = build("calendar", "v3", credentials=creds)

    try:
        event = {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "timeZone": "Europe/Moscow",
            "description": make_description_in_calendar(
                children_amount,
                phone,
                visit_type,
                total_guests,
            ),
            "colorId": str(get_visit_type_color(visit_type, commune)),
        }
        event = service.events().insert(calendarId="primary", body=event).execute()
        logger.info("Event created with ID: %s" % (event.get("id")))
        return True

    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        return False

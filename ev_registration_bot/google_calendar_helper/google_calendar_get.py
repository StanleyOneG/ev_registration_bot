import datetime
import enum
import logging
import os.path
from pprint import pprint

import pytz
from google.auth.external_account_authorized_user import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

moscow_tz = pytz.timezone("Europe/Moscow")


class Commune(enum.Enum):
    AMERICAN = "american_calendar_configs"
    GERMAN = "german_calendar_configs"


class OutOfTimeException(Exception):
    pass


class Slot(BaseModel):
    start: str
    end: str
    name: str = Field(..., max_length=100)
    description: str = Field(None, max_length=500)

    def __eq__(self, other):
        if isinstance(other, Slot):
            return self.start == other.start
        return NotImplemented


now = datetime.datetime.now(moscow_tz)


def get_creds(commune: Commune) -> Credentials:
    creds = None
    logger.info(f"Getting credentials for {commune.value}")
    logger.info(f"Path to token: {commune.value}/token.json")
    if os.path.exists(f"{commune.value}/token.json"):
        creds = Credentials.from_authorized_user_file(
            f"{commune.value}/token.json", SCOPES
        )
    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise ValueError("Invalid credentials")

        #     flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        #     creds = flow.run_local_server(port=0)
        # with open(f"{commune.value}/token.json", "w") as token:
        #     token.write(creds.to_json())

    return creds


def get_regs_for_today(commune: Commune):
    now = datetime.datetime.now(moscow_tz)
    if now.hour >= 21:
        raise OutOfTimeException("Out of time for today")

    end_of_today = now.replace(hour=21, minute=0, second=0, microsecond=0)
    end_of_today_iso = end_of_today.isoformat()
    creds = get_creds(commune)

    try:
        service = build("calendar", "v3", credentials=creds)

        events_result: dict = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end_of_today_iso,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events: list = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return []

        detailed_events = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            detailed_events.append(Slot(start=start, end=end, name=event["summary"]))
        # logger.info(detailed_events)
        return detailed_events

    except HttpError as error:
        logger.error(f"An error occurred while fetching events: {error}")


def get_next_regs(day: datetime.datetime, commune: Commune) -> list | list[Slot] | None:
    now = datetime.datetime.now(moscow_tz)
    if day == now.date():
        return get_regs_for_today(commune)

    start_of_day = moscow_tz.localize(
        datetime.datetime(
            day.year,
            day.month,
            day.day,
            11,
            0,
            0,
            0,
        )
    )
    end_of_day = moscow_tz.localize(
        datetime.datetime(
            day.year,
            day.month,
            day.day,
            21,
            0,
            0,
            0,
        )
    )

    creds = get_creds(commune)

    try:
        service = build("calendar", "v3", credentials=creds)

        events_result: dict = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events: list = events_result.get("items", [])

        if not events:
            return []

        detailed_events = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            detailed_events.append(Slot(start=start, end=end, name=event["summary"]))
        # logger.info(detailed_events)
        return detailed_events
    except HttpError as error:
        logger.error(f"An error occurred while fetching events: {error}")


def get_free_slots_for_a_day(
    day: datetime.datetime,
    commune: Commune,
) -> list | list[Slot]:
    hours = [
        moscow_tz.localize(
            datetime.datetime(
                day.year,
                day.month,
                day.day,
                i,
                0,
                0,
                0,
            )
        )
        for i in range(11, 21)
    ]

    free_hour_slots = [
        Slot(
            start=hour.isoformat(),
            end=(hour + datetime.timedelta(hours=1)).isoformat(),
            name="Free",
        )
        for hour in hours
        if hour.hour != 15 and hour.hour != 16
    ]

    occupied = get_next_regs(day, commune)

    if occupied is None:
        return []
    free_slots = []
    for free_slot in free_hour_slots:
        if free_slot not in occupied:
            free_slots.append(free_slot)
    now = datetime.datetime.now(moscow_tz)

    if day == now.date():
        free_slots: list[Slot] = [
            slot for slot in free_slots if slot.start >= now.isoformat()
        ]
    else:
        free_slots: list[Slot] = [
            slot for slot in free_slots if slot.start >= "11:00:00"
        ]

    # logger.info(free_slots)
    return free_slots

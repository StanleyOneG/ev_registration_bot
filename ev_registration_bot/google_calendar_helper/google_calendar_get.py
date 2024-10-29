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

from ev_registration_bot.google_calendar_helper.utils import Commune, VisitType

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

moscow_tz = pytz.timezone("Europe/Moscow")


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


class LectureSlot(BaseModel):
    start: str
    end: str
    name: str = Field(..., max_length=100)
    description: str = Field(None, max_length=500)
    total_guests: int = Field(0, ge=0, le=10)

    def __eq__(self, other):
        if isinstance(other, LectureSlot):
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

    return creds


def extract_total_guests(description: str) -> int:
    """Extract total guests from event description."""
    try:
        if "(не редактировать) Общее кол-во гостей:" in description:
            guests_str = description.split("(не редактировать) Общее кол-во гостей:")[
                -1
            ].strip()
            return int(guests_str)
        return 0
    except (ValueError, IndexError):
        logger.error(f"Failed to extract total guests from description: {description}")
        return 0


def get_events_for_day(
    day: datetime.datetime,
    commune: Commune,
) -> tuple[list[Slot], list[LectureSlot]]:
    """Get all events for a specific day, separated by type."""
    now = datetime.datetime.now(moscow_tz)

    if day == now.date():
        if now.hour >= 21:
            raise OutOfTimeException("Out of time for today")
        start_time = now
    else:
        start_time = moscow_tz.localize(
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

    end_time = moscow_tz.localize(
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
    service = build("calendar", "v3", credentials=creds)

    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        therapy_visits = []
        lecture_visits = []

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            description = event.get("description", "")

            if "Тип посещения: Терапия" in description:
                therapy_visits.append(Slot(start=start, end=end, name=event["summary"]))
            elif "Тип посещения: Лекция" in description:
                total_guests = extract_total_guests(description)
                lecture_visits.append(
                    LectureSlot(
                        start=start,
                        end=end,
                        name=event["summary"],
                        total_guests=total_guests,
                    )
                )

        return therapy_visits, lecture_visits
    except HttpError as error:
        logger.error(f"An error occurred while fetching events: {error}")
        return [], []


def get_free_slots_for_a_day(
    day: datetime.datetime,
    commune: Commune,
) -> list[Slot]:
    """Get free slots for therapy visits."""
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

    therapy_visits, lecture_visits = get_events_for_day(day, commune)

    free_slots = []
    for free_slot in free_hour_slots:
        # Check for therapy visit conflicts
        has_therapy = any(
            (
                free_slot.start <= therapy.start < free_slot.end
                or free_slot.start < therapy.end <= free_slot.end
                or (therapy.start <= free_slot.start and therapy.end >= free_slot.end)
            )
            for therapy in therapy_visits
        )

        # Check for lecture visit conflicts
        has_lecture = any(
            (
                free_slot.start <= lecture.start < free_slot.end
                or free_slot.start < lecture.end <= free_slot.end
                or (lecture.start <= free_slot.start and lecture.end >= free_slot.end)
            )
            for lecture in lecture_visits
        )

        # Only add the slot if there are no conflicts with either therapy or lecture visits
        if not has_therapy and not has_lecture:
            free_slots.append(free_slot)

    now = datetime.datetime.now(moscow_tz)
    if day == now.date():
        free_slots = [slot for slot in free_slots if slot.start >= now.isoformat()]
    else:
        free_slots = [slot for slot in free_slots if slot.start >= "11:00:00"]

    return free_slots


def get_lecture_free_slots_for_a_day(
    day: datetime.datetime,
    commune: Commune,
) -> list[LectureSlot]:
    """Get free 1-hour slots for lectures."""
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
        LectureSlot(
            start=hour.isoformat(),
            end=(hour + datetime.timedelta(hours=1)).isoformat(),
            name="Free lecture",
            total_guests=0,
        )
        for hour in hours
        if hour.hour != 15 and hour.hour != 16
    ]

    therapy_visits, lecture_visits = get_events_for_day(day, commune)

    available_slots = []
    for free_slot in free_hour_slots:
        # Check for therapy visit conflicts
        has_therapy = any(
            (
                free_slot.start <= therapy.start < free_slot.end
                or free_slot.start < therapy.end <= free_slot.end
                or (therapy.start <= free_slot.start and therapy.end >= free_slot.end)
            )
            for therapy in therapy_visits
        )

        if has_therapy:
            continue

        # Find all overlapping lecture slots
        overlapping_lectures = [
            lecture
            for lecture in lecture_visits
            if (
                free_slot.start <= lecture.start < free_slot.end
                or free_slot.start < lecture.end <= free_slot.end
                or (lecture.start <= free_slot.start and lecture.end >= free_slot.end)
            )
        ]

        # Calculate total guests from all overlapping slots
        if overlapping_lectures:
            # Group overlapping lectures by their time slots
            time_slots = {}
            for lecture in overlapping_lectures:
                slot_key = (lecture.start, lecture.end)
                if slot_key in time_slots:
                    time_slots[slot_key] += lecture.total_guests
                else:
                    time_slots[slot_key] = lecture.total_guests

            # For each half hour within the hour slot, sum up all overlapping guests
            total_guests = 0
            slot_start = datetime.datetime.fromisoformat(free_slot.start)
            slot_end = datetime.datetime.fromisoformat(free_slot.end)

            # Check first half hour
            first_half_guests = sum(
                guests
                for (start, end), guests in time_slots.items()
                if (
                    datetime.datetime.fromisoformat(start)
                    <= slot_start
                    < datetime.datetime.fromisoformat(end)
                    or slot_start
                    < datetime.datetime.fromisoformat(end)
                    <= slot_start + datetime.timedelta(minutes=30)
                    or (
                        datetime.datetime.fromisoformat(start) <= slot_start
                        and datetime.datetime.fromisoformat(end)
                        >= slot_start + datetime.timedelta(minutes=30)
                    )
                )
            )

            # Check second half hour
            second_half_guests = sum(
                guests
                for (start, end), guests in time_slots.items()
                if (
                    datetime.datetime.fromisoformat(start)
                    <= slot_start + datetime.timedelta(minutes=30)
                    < datetime.datetime.fromisoformat(end)
                    or slot_start + datetime.timedelta(minutes=30)
                    < datetime.datetime.fromisoformat(end)
                    <= slot_end
                    or (
                        datetime.datetime.fromisoformat(start)
                        <= slot_start + datetime.timedelta(minutes=30)
                        and datetime.datetime.fromisoformat(end) >= slot_end
                    )
                )
            )

            # Take the maximum number of guests from either half hour
            total_guests = max(first_half_guests, second_half_guests)
            free_slot.total_guests = total_guests

        available_slots.append(free_slot)

    now = datetime.datetime.now(moscow_tz)
    if day == now.date():
        available_slots = [
            slot for slot in available_slots if slot.start >= now.isoformat()
        ]
    else:
        available_slots = [slot for slot in available_slots if slot.start >= "11:00:00"]

    return available_slots


def get_lecture_free_half_an_hour_slots_for_a_day(
    day: datetime.datetime,
    commune: Commune,
) -> list[LectureSlot]:
    """Get free 30-minute slots for lectures."""
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

    # Create slots for both XX:00 and XX:30
    free_slots = []
    for hour in hours:
        if hour.hour != 15 and hour.hour != 16:
            # Add slot for the first half hour (XX:00-XX:30)
            free_slots.append(
                LectureSlot(
                    start=hour.isoformat(),
                    end=(hour + datetime.timedelta(minutes=30)).isoformat(),
                    name="Free lecture",
                    total_guests=0,
                )
            )
            # Add slot for the second half hour (XX:30-XX+1:00)
            half_hour = hour + datetime.timedelta(minutes=30)
            free_slots.append(
                LectureSlot(
                    start=half_hour.isoformat(),
                    end=(half_hour + datetime.timedelta(minutes=30)).isoformat(),
                    name="Free lecture",
                    total_guests=0,
                )
            )

    therapy_visits, lecture_visits = get_events_for_day(day, commune)

    available_slots = []
    for free_slot in free_slots:
        # Check for therapy visit conflicts
        has_therapy = any(
            (
                free_slot.start <= therapy.start < free_slot.end
                or free_slot.start < therapy.end <= free_slot.end
                or (therapy.start <= free_slot.start and therapy.end >= free_slot.end)
            )
            for therapy in therapy_visits
        )

        if has_therapy:
            continue

        # Find all overlapping lecture slots
        overlapping_lectures = [
            lecture
            for lecture in lecture_visits
            if (
                free_slot.start <= lecture.start < free_slot.end
                or free_slot.start < lecture.end <= free_slot.end
                or (lecture.start <= free_slot.start and lecture.end >= free_slot.end)
            )
        ]

        # Calculate total guests from all overlapping slots
        total_guests = 0
        for lecture in overlapping_lectures:
            total_guests += lecture.total_guests

        free_slot.total_guests = total_guests
        available_slots.append(free_slot)

    now = datetime.datetime.now(moscow_tz)
    if day == now.date():
        available_slots = [
            slot for slot in available_slots if slot.start >= now.isoformat()
        ]
    else:
        available_slots = [slot for slot in available_slots if slot.start >= "11:00:00"]

    return available_slots

import caldav
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from langchain_core.tools import tool


# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = "https://sync.infomaniak.com/calendars"
USERNAME = os.getenv("CALENDAR_USERNAME")
PASSWORD = os.getenv("CALENDAR_PASSWORD")


#Helpers for calendar interactions
def get_calendar(target_name=None):
    """
    Connects to Infomaniak and returns a specific calendar by name.
    If target_name is None, returns the primary calendar.
    """
    client = caldav.DAVClient(url=URL, username=USERNAME, password=PASSWORD)
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        return None
    if target_name:
        for cal in calendars:
            if target_name.lower() in cal.get_display_name().lower():
                return cal
    return calendars[0]
@tool
def check_calendar_availability(date: str, time: str) -> str:
    """Check available time slots of 30 minutes in the Infomaniak calendar.

    Args:
        date (str): Desired date in format YYYY-MM-DD.
        time (str): Preferred start time in format HH:MM (24h).

    Returns:
        str: One of:
            - A list of up to 5 available time slots within the next 3 days,
            formatted as "DD/MM/YYYY at HH:MM"
            - "No available slots found in the next 3 days."
            - "Calendar not found."
            - An error message if an exception occurs
    """
    duration_minutes = 30
    try:
        start_from = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        duration_hours = duration_minutes / 60


        calendar = get_calendar("Clinique")
        if not calendar:
            return "Calendar not found."


        end_scan = start_from + timedelta(days=3)
        events = calendar.search(start=start_from, end=end_scan, event=True)


        busy_times = []
        for event in events:
            comp = event.icalendar_instance.subcomponents[0]
            dt_start = comp.get("dtstart").dt
            dt_end = comp.get("dtend").dt
            if not isinstance(dt_start, datetime):
                dt_start = datetime.combine(dt_start, datetime.min.time())
            if not isinstance(dt_end, datetime):
                dt_end = datetime.combine(dt_end, datetime.min.time())
            busy_times.append((dt_start.replace(tzinfo=None), dt_end.replace(tzinfo=None)))


        free_slots = []
        current = start_from.replace(minute=0, second=0, microsecond=0)
        slot_delta = timedelta(hours=duration_hours)


        while current + slot_delta <= end_scan and len(free_slots) < 5:
            if 8 <= current.hour < 18:
                overlap = any(current < b_end and current + slot_delta > b_start for b_start, b_end in busy_times)
                if not overlap:
                    free_slots.append(current)
            current += timedelta(minutes=30)
            if current.hour >= 18:
                current = (current + timedelta(days=1)).replace(hour=8, minute=0)


        if not free_slots:
            return "No available slots found in the next 3 days."


        slots_str = "\n".join([f"- {s.strftime('%d/%m/%Y at %H:%M')} ({duration_minutes} min)" for s in free_slots])
        return f"Available slots:\n{slots_str}"


    except Exception as e:
        return f"Calendar error: {e}"



@tool
def create_calendar_event(title: str, date: str, time: str, description: str) -> str:
    """Create a calendar event of 30 minutes in the Infomaniak calendar.

    Args:
        title (str): Event title.
        date (str): Event date in format YYYY-MM-DD.
        time (str): Event start time in format HH:MM (24h).
        description (str): Event description.

    Returns:
        str: Confirmation message if the event is created, or an error message
        if the calendar is unavailable, a conflict is detected, or an exception occurs.
    """
    duration_minutes = 30
    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_minutes)


        calendar = get_calendar("Clinique")
        if not calendar:
            return "Calendar not found."


        conflicts = calendar.search(start=start_dt, end=end_dt, event=True)
        if conflicts:
            return f"Conflict detected: {len(conflicts)} existing event(s) at this time. Please choose another slot."


        calendar.save_event(
            dtstart=start_dt,
            dtend=end_dt,
            summary=title,
            description=description
        )
        return f"Event '{title}' created on {date} at {time} ({duration_minutes} min)."


    except Exception as e:
        return f"Calendar error: {e}"

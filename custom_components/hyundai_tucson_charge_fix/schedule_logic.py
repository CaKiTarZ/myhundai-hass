"""Schedule calculation logic for Hyundai Tucson Charge Fix."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def parse_hhmm(value: str) -> dt.time:
    """Parse an HH:MM or HH:MM:SS string into a datetime.time."""
    parts = value.strip().split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(f"Invalid time format: {value!r}")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    return dt.time(hour=hour, minute=minute, second=second)


def _time_in_window(current: dt.time, start: dt.time, end: dt.time) -> bool:
    """Return True if current is within [start, end), supporting overnight windows."""
    if start == end:
        return True
    if start < end:
        return start <= current < end
    # Overnight window (e.g., 23:00 to 07:00)
    return current >= start or current < end


def is_charging_allowed(
    now_utc: dt.datetime,
    tz_name: str,
    weekday_start: str,
    weekday_end: str,
    weekend_all_day: bool,
) -> bool:
    """Return True if charging is allowed at now_utc in the given timezone."""
    tz = ZoneInfo(tz_name)
    local_now = now_utc.astimezone(tz)
    weekday = local_now.weekday()  # 0=Mon .. 6=Sun

    if weekend_all_day and weekday >= 5:
        return True

    start = parse_hhmm(weekday_start)
    end = parse_hhmm(weekday_end)
    return _time_in_window(local_now.time(), start, end)


def next_window_transition(
    now_utc: dt.datetime,
    tz_name: str,
    weekday_start: str,
    weekday_end: str,
    weekend_all_day: bool,
) -> dt.datetime | None:
    """Compute the next UTC datetime when charging_allowed flips state."""
    tz = ZoneInfo(tz_name)
    local_now = now_utc.astimezone(tz)
    current_allowed = is_charging_allowed(
        now_utc, tz_name, weekday_start, weekday_end, weekend_all_day
    )
    start = parse_hhmm(weekday_start)
    end = parse_hhmm(weekday_end)

    candidates: list[dt.datetime] = []
    base_date = local_now.date()
    for day_offset in range(0, 9):
        day = base_date + dt.timedelta(days=day_offset)
        for boundary_time in (dt.time(0, 0), start, end):
            candidate_local = dt.datetime.combine(day, boundary_time, tzinfo=tz)
            if candidate_local <= local_now:
                continue
            candidates.append(candidate_local.astimezone(dt.timezone.utc))

    for candidate_utc in sorted(set(candidates)):
        # Check 1 second after boundary to confirm state actually flips
        probe = candidate_utc + dt.timedelta(seconds=1)
        if (
            is_charging_allowed(
                probe, tz_name, weekday_start, weekday_end, weekend_all_day
            )
            != current_allowed
        ):
            return candidate_utc

    return None

"""Unit tests for Spain charging schedule logic."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "hyundai_tucson_charge_fix"
    / "schedule_logic.py"
)
_SPEC = importlib.util.spec_from_file_location("schedule_logic", _MODULE_PATH)
assert _SPEC and _SPEC.loader
schedule_logic = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(schedule_logic)

MADRID = ZoneInfo("Europe/Madrid")


class TestSpainScheduleLogic(unittest.TestCase):
    """Verify weekday 00:00-08:00 and weekend all-day rules in Europe/Madrid."""

    def _utc(self, year: int, month: int, day: int, hour: int, minute: int) -> dt.datetime:
        return dt.datetime(year, month, day, hour, minute, tzinfo=MADRID).astimezone(
            dt.timezone.utc
        )

    def test_weekday_inside_window(self) -> None:
        # Wednesday 2026-11-25 at 00:00 and 07:59 Madrid time
        for hour, minute in ((0, 0), (3, 30), (7, 59)):
            self.assertTrue(
                schedule_logic.is_charging_allowed(
                    self._utc(2026, 11, 25, hour, minute),
                    "Europe/Madrid",
                    "00:00",
                    "08:00",
                    True,
                )
            )

    def test_weekday_outside_window(self) -> None:
        # Wednesday 2026-11-25 at 08:00, 14:00, 23:59 Madrid time
        for hour, minute in ((8, 0), (14, 0), (23, 59)):
            self.assertFalse(
                schedule_logic.is_charging_allowed(
                    self._utc(2026, 11, 25, hour, minute),
                    "Europe/Madrid",
                    "00:00",
                    "08:00",
                    True,
                )
            )

    def test_weekend_all_day(self) -> None:
        # Saturday 2026-11-28 and Sunday 2026-11-29 at 00:00, 12:00, 23:59
        for day in (28, 29):
            for hour, minute in ((0, 0), (12, 0), (23, 59)):
                self.assertTrue(
                    schedule_logic.is_charging_allowed(
                        self._utc(2026, 11, day, hour, minute),
                        "Europe/Madrid",
                        "00:00",
                        "08:00",
                        True,
                    )
                )

    def test_next_transition_weekday_and_weekend(self) -> None:
        # Wednesday 14:00 -> next transition is Thursday 00:00 Madrid
        wed_14 = self._utc(2026, 11, 25, 14, 0)
        self.assertEqual(
            schedule_logic.next_window_transition(
                wed_14, "Europe/Madrid", "00:00", "08:00", True
            ),
            self._utc(2026, 11, 26, 0, 0),
        )

        # Saturday 10:00 -> next transition is Monday 08:00 Madrid (since Sat/Sun + Mon 00:00-08:00 are all allowed!)
        sat_10 = self._utc(2026, 11, 28, 10, 0)
        self.assertEqual(
            schedule_logic.next_window_transition(
                sat_10, "Europe/Madrid", "00:00", "08:00", True
            ),
            self._utc(2026, 11, 30, 8, 0),
        )

    def test_overnight_custom_window(self) -> None:
        # Custom 23:00 to 07:00
        self.assertTrue(
            schedule_logic.is_charging_allowed(
                self._utc(2026, 11, 25, 23, 30),
                "Europe/Madrid",
                "23:00",
                "07:00",
                True,
            )
        )
        self.assertFalse(
            schedule_logic.is_charging_allowed(
                self._utc(2026, 11, 25, 12, 0),
                "Europe/Madrid",
                "23:00",
                "07:00",
                True,
            )
        )


if __name__ == "__main__":
    unittest.main()

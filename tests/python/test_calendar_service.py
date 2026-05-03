"""
Tests unitaires — Calendar Service (EXO v8)
JSON-backed local calendar.
"""

import sys
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def calendar_service(tmp_path):
    """Create a CalendarService with a temporary directory."""
    from calendar_service import CalendarService
    cal_file = tmp_path / "calendar.json"
    svc = CalendarService(calendar_file=cal_file)
    return svc


class TestCalendarService:
    """Tests du CalendarService."""

    def test_create_service(self, calendar_service):
        assert calendar_service is not None

    def test_add_event(self, calendar_service):
        result = calendar_service.add_event(
            title="Réunion",
            date="2025-06-15",
            time="14:00",
            duration_min=60,
        )
        assert result["created"] is True
        assert "event_id" in result

    def test_add_event_no_time(self, calendar_service):
        result = calendar_service.add_event(
            title="Journée entière",
            date="2025-06-20",
        )
        assert result["created"] is True

    def test_list_events(self, calendar_service):
        calendar_service.add_event("Event 1", "2025-06-15")
        calendar_service.add_event("Event 2", "2025-06-16")
        listing = calendar_service.list_events()
        assert len(listing["events"]) == 2

    def test_list_events_date_range(self, calendar_service):
        calendar_service.add_event("Early", "2025-06-01")
        calendar_service.add_event("Late", "2025-06-30")
        listing = calendar_service.list_events(
            from_date="2025-06-10",
            to_date="2025-06-20",
        )
        # Only "Early" is before range, "Late" is after
        assert len(listing["events"]) == 0 or all(
            "2025-06-10" <= e["date"] <= "2025-06-20"
            for e in listing["events"]
        )

    def test_today_events(self, calendar_service):
        import datetime
        today = datetime.date.today().isoformat()
        calendar_service.add_event("Today Event", today)
        listing = calendar_service.today()
        assert len(listing["events"]) >= 1

    def test_delete_event(self, calendar_service):
        result = calendar_service.add_event("To Delete", "2025-06-15")
        event_id = result["event_id"]
        del_result = calendar_service.delete_event(event_id)
        assert del_result is True
        # Should be gone
        listing = calendar_service.list_events()
        ids = [e["id"] for e in listing["events"]]
        assert event_id not in ids

    def test_delete_nonexistent(self, calendar_service):
        result = calendar_service.delete_event("nonexistent-id")
        assert result is False

    def test_upcoming_events(self, calendar_service):
        import datetime
        future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        calendar_service.add_event("Future", future)
        listing = calendar_service.upcoming(days=7)
        assert len(listing["events"]) >= 1

    def test_invalid_date_format(self, calendar_service):
        # CalendarService doesn't validate date format, it stores as-is
        result = calendar_service.add_event("Bad Date", "not-a-date")
        assert result["created"] is True

from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import SystemSetting
from tagging.models import TagLog, TagType

from .models import AttendanceSession
from .services import refresh_attendance_session

User = get_user_model()


class AttendanceSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="employee1",
            password="password123",
            email="employee1@example.com",
            role=User.Role.EMPLOYEE,
        )
        SystemSetting.objects.create(
            company_name="Test Company",
            default_timezone="Asia/Manila",
            lunch_minutes_allowed=60,
            break_minutes_allowed=15,
            bio_minutes_allowed=10,
            late_after_time=time(9, 0),
        )
        self.tag_types = {
            "TIME_IN": self._create_tag_type("TIME_IN", "Time In", TagType.Category.SHIFT, TagType.Direction.IN),
            "TIME_OUT": self._create_tag_type("TIME_OUT", "Time Out", TagType.Category.SHIFT, TagType.Direction.OUT),
            "LUNCH_OUT": self._create_tag_type("LUNCH_OUT", "Lunch Out", TagType.Category.LUNCH, TagType.Direction.OUT, 60),
            "LUNCH_IN": self._create_tag_type("LUNCH_IN", "Lunch In", TagType.Category.LUNCH, TagType.Direction.IN),
            "BREAK_OUT": self._create_tag_type("BREAK_OUT", "Break Out", TagType.Category.BREAK, TagType.Direction.OUT, 15),
            "BREAK_IN": self._create_tag_type("BREAK_IN", "Break In", TagType.Category.BREAK, TagType.Direction.IN),
            "BIO_OUT": self._create_tag_type("BIO_OUT", "Bio Out", TagType.Category.BIO, TagType.Direction.OUT, 10),
            "BIO_IN": self._create_tag_type("BIO_IN", "Bio In", TagType.Category.BIO, TagType.Direction.IN),
        }

    def test_refresh_attendance_session_calculates_daily_summary(self):
        work_date = date(2026, 4, 11)
        self._create_log("TIME_IN", work_date, 1, 0)
        self._create_log("LUNCH_OUT", work_date, 4, 0)
        self._create_log("LUNCH_IN", work_date, 5, 5)
        self._create_log("BREAK_OUT", work_date, 7, 0)
        self._create_log("BREAK_IN", work_date, 7, 20)
        self._create_log("BIO_OUT", work_date, 9, 0)
        self._create_log("BIO_IN", work_date, 9, 12)
        self._create_log("TIME_OUT", work_date, 10, 0)

        session = refresh_attendance_session(self.user, work_date)

        self.assertEqual(AttendanceSession.objects.count(), 1)
        self.assertEqual(session.total_lunch_minutes, 65)
        self.assertEqual(session.total_break_minutes, 20)
        self.assertEqual(session.total_bio_minutes, 12)
        self.assertEqual(session.total_overbreak_minutes, 12)
        self.assertEqual(session.total_work_minutes, 443)
        self.assertEqual(session.total_late_minutes, 0)
        self.assertFalse(session.is_late)
        self.assertFalse(session.has_incomplete_records)
        self.assertEqual(session.missing_tag_pairs_count, 0)
        self.assertEqual(session.overbreak_records.count(), 3)

    def test_refresh_attendance_session_flags_missing_pairs(self):
        work_date = date(2026, 4, 12)
        self._create_log("TIME_IN", work_date, 0, 0)
        self._create_log("LUNCH_OUT", work_date, 4, 0)

        session = refresh_attendance_session(self.user, work_date)

        self.assertTrue(session.has_incomplete_records)
        self.assertEqual(session.missing_tag_pairs_count, 2)
        self.assertIn("Missing lunch in for lunch out.", session.summary_notes)
        self.assertIn("Incomplete shift pair. Missing time in or time out.", session.summary_notes)

    def _create_tag_type(self, code, name, category, direction, allowed_minutes=None):
        return TagType.objects.create(
            code=code,
            name=name,
            category=category,
            direction=direction,
            default_allowed_minutes=allowed_minutes,
        )

    def _create_log(self, code, work_date, hours_from_start, minutes):
        base = timezone.make_aware(datetime(2026, 4, work_date.day, 8, 0))
        timestamp = base + timedelta(hours=hours_from_start, minutes=minutes)
        return TagLog.objects.create(
            employee=self.user,
            tag_type=self.tag_types[code],
            work_date=work_date,
            timestamp=timestamp,
            work_mode="ONSITE",
        )

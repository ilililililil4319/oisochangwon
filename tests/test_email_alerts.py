import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json
import sqlite3
import unittest
from datetime import date, datetime, timedelta
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import email_alerts
from email_alerts import AlertError, send_due_alerts, smtp_config, subscribe, unsubscribe

NOW = datetime(2026, 10, 3, 10, tzinfo=ZoneInfo("Asia/Seoul"))
CONFIG = {"SMTP_HOST": "h", "SMTP_PORT": 587, "SMTP_USER": "u", "SMTP_PASSWORD": "p", "SMTP_FROM": "f@example.com"}
EVENTS = [
    {"date": date(2026, 9, 1), "title": "지난 일정", "description": ""},
    {"date": date(2026, 10, 5), "title": "다가오는 일정", "description": "설명"},
    {"date": date(2026, 12, 1), "title": "나중 일정", "description": ""},
]


class FakeSMTP:
    sent = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def send_message(self, message):
        FakeSMTP.sent.append(message)


class EmailAlertTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db = Path(self.temp.name) / "alerts.sqlite3"
        FakeSMTP.sent = []

    def tearDown(self):
        self.temp.cleanup()

    def test_no_consent_no_storage(self):
        for privacy, receive in ((False, True), (True, False), (False, False)):
            with self.assertRaises(AlertError):
                subscribe("a@example.com", EVENTS, privacy, receive, db_path=self.db, now=NOW)
        self.assertEqual(email_alerts.count_subscriptions(self.db), 0)

    def test_invalid_email_rejected(self):
        with self.assertRaises(AlertError):
            subscribe("not-an-email", EVENTS, True, True, db_path=self.db, now=NOW)

    def test_subscribe_stores_only_future_alerts_and_unsubscribe_deletes(self):
        result = subscribe(" A@Example.com ", EVENTS, True, True, db_path=self.db, now=NOW)
        self.assertEqual(result["email"], "a@example.com")
        self.assertEqual([a["title"] for a in result["alerts"]], ["다가오는 일정", "나중 일정"])
        self.assertEqual(result["alerts"][0]["send_on"], "2026-10-04")
        connection = sqlite3.connect(self.db)
        columns = [row[1] for row in connection.execute("PRAGMA table_info(email_alerts)")]
        connection.close()
        self.assertNotIn("nickname", columns)
        again = subscribe("a@example.com", EVENTS[2:], True, True, db_path=self.db, now=NOW)
        self.assertEqual(again["token"], result["token"])
        self.assertEqual(email_alerts.count_subscriptions(self.db), 1)
        self.assertEqual(unsubscribe(token=result["token"], db_path=self.db), 1)
        self.assertEqual(email_alerts.count_subscriptions(self.db), 0)

    def test_due_alerts_sent_once_and_deleted_after_last(self):
        subscribe("a@example.com", EVENTS, True, True, db_path=self.db, now=NOW)
        self.assertEqual(send_due_alerts(CONFIG, db_path=self.db, today=date(2026, 10, 3), smtp_factory=FakeSMTP), 0)
        self.assertEqual(send_due_alerts(CONFIG, db_path=self.db, today=date(2026, 10, 4), smtp_factory=FakeSMTP), 1)
        self.assertEqual(send_due_alerts(CONFIG, db_path=self.db, today=date(2026, 10, 4), smtp_factory=FakeSMTP), 0)
        self.assertIn("다가오는 일정", FakeSMTP.sent[0]["Subject"])
        send_due_alerts(CONFIG, db_path=self.db, today=date(2026, 11, 30), smtp_factory=FakeSMTP)
        self.assertEqual(len(FakeSMTP.sent), 2)
        self.assertEqual(email_alerts.count_subscriptions(self.db), 0)

    def test_smtp_config_requires_all_values(self):
        values = {"SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587", "SMTP_USER": "u", "SMTP_PASSWORD": "p", "SMTP_FROM": "f"}
        self.assertEqual(smtp_config(values.get)["SMTP_PORT"], 587)
        self.assertIsNone(smtp_config({**values, "SMTP_PASSWORD": ""}.get))
        self.assertIsNone(smtp_config(lambda name: None))

    def test_welcome_mail_has_ics_and_unsubscribe_link(self):
        result = subscribe("a@example.com", EVENTS, True, True, db_path=self.db, now=NOW)
        message = email_alerts.build_welcome_message(
            CONFIG, result["email"], result["alerts"], result["token"], b"BEGIN:VCALENDAR", "https://app/"
        )
        body = message.get_body(("plain",)).get_content()
        self.assertIn(f"https://app/?unsubscribe={result['token']}", body)
        self.assertEqual([part.get_filename() for part in message.iter_attachments()], ["oisochangwon_schedule.ics"])


if __name__ == "__main__":
    unittest.main()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
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

    def test_smtp_config_needs_user_and_password_and_defaults_to_gmail(self):
        values = {"SMTP_USER": "team@gmail.com", "SMTP_PASSWORD": "abcd efgh ijkl mnop"}
        config = smtp_config(values.get)
        self.assertEqual(config["SMTP_HOST"], "smtp.gmail.com")
        self.assertEqual(config["SMTP_PORT"], 587)
        self.assertEqual(config["SMTP_FROM"], "team@gmail.com")
        self.assertEqual(config["SMTP_PASSWORD"], "abcdefghijklmnop")
        custom = smtp_config({**values, "SMTP_HOST": "smtp.naver.com", "SMTP_PORT": "465", "SMTP_FROM": "f@x.com"}.get)
        self.assertEqual((custom["SMTP_HOST"], custom["SMTP_PORT"], custom["SMTP_FROM"]), ("smtp.naver.com", 465, "f@x.com"))
        self.assertIsNone(smtp_config({**values, "SMTP_PASSWORD": ""}.get))
        self.assertIsNone(smtp_config({"SMTP_PASSWORD": "p"}.get))
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


class SendFallbackTests(unittest.TestCase):
    """10/3 배포 앱 발송 실패 대응: 한 포트가 막히면 다른 방식(587 STARTTLS ↔ 465 SSL)으로 한 번 더"""

    CONFIG = {"SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": 587, "SMTP_USER": "u@gmail.com",
              "SMTP_PASSWORD": "p", "SMTP_FROM": "u@gmail.com"}

    def test_connection_error_retries_with_other_port(self):
        from unittest.mock import patch
        calls = []

        def broken(config, message, port, stage):
            calls.append(("starttls", port))
            stage["name"] = "암호화(STARTTLS)"
            raise TimeoutError("timed out")

        with patch.object(email_alerts, "_send_starttls", broken), \
                patch.object(email_alerts, "_send_ssl", lambda c, m, port, stage: calls.append(("ssl", port))):
            email_alerts.send_message(self.CONFIG, object())
        self.assertEqual(calls, [("starttls", 587), ("ssl", 465)])

    def test_both_failures_report_port_and_stage(self):
        import smtplib
        from unittest.mock import patch

        def drop(config, message, port, stage):
            stage["name"] = "연결"
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

        with patch.object(email_alerts, "_send_starttls", drop), patch.object(email_alerts, "_send_ssl", drop):
            with self.assertRaises(email_alerts.SendFailure) as caught:
                email_alerts.send_message(self.CONFIG, object())
        self.assertEqual(str(caught.exception), "587 연결 SMTPServerDisconnected / 465 연결 SMTPServerDisconnected")

    def test_login_failure_is_not_retried(self):
        import smtplib
        from unittest.mock import patch
        calls = []

        def denied(config, message, port, stage):
            raise smtplib.SMTPAuthenticationError(535, b"bad")

        with patch.object(email_alerts, "_send_starttls", denied), \
                patch.object(email_alerts, "_send_ssl", lambda c, m, port, stage: calls.append(port)):
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                email_alerts.send_message(self.CONFIG, object())
        self.assertEqual(calls, [])

"""이메일 일정 알림(선택) — 사용자가 직접 신청하고 두 가지 동의를 한 경우에만 이메일을 저장한다.

- 수집 항목: 이메일 주소, 알림 일정(날짜·제목). 실명·전화번호·닉네임은 받지 않는다.
- 보유 기간: 마지막 알림 발송 후 즉시 또는 수신 해지 시 즉시 삭제.
- 발송: Streamlit Secrets에 SMTP_USER·SMTP_PASSWORD(앱 비밀번호)가 있을 때만. 서버는 기본 Gmail.
  설정이 없으면 이메일을 아예 받지 않는다(저장해 놓고 못 보내는 일이 없도록).
- 앱에 상시 스케줄러가 없으므로, 신청 즉시 전체 일정(.ics, 하루 전 알림 포함)을 메일로 보내고,
  날짜가 다가온 알림은 앱이 실행될 때 확인해 보낸다.
"""

import json
from contextlib import contextmanager
import re
import secrets
import smtplib
import sqlite3
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
DB_PATH = Path(__file__).resolve().parents[1] / "storage" / "alerts.sqlite3"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
CONSENT_VERSION = "2026-10-03"
SMTP_KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")
MAX_ALERTS = 40

PRIVACY_NOTICE = (
    "**개인정보 수집·이용 안내 (이메일 알림 신청자만)**\n\n"
    "- 수집 항목: 이메일 주소, 알림 받을 일정(날짜·제목)\n"
    "- 이용 목적: 창원 정착 일정·혜택 확인일 알림 메일 발송\n"
    "- 보유 기간: 마지막 알림을 보낸 뒤 또는 수신 해지 즉시 삭제\n"
    "- 동의하지 않아도 모든 기능을 그대로 쓸 수 있어요. 이메일 없이 ‘캘린더 파일’로도 알림을 받을 수 있어요."
)


class AlertError(ValueError):
    pass


SMTP_DEFAULTS = {"SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587"}


def smtp_config(get_setting):
    """get_setting(name) → 값 또는 None.

    꼭 필요한 값은 SMTP_USER(보내는 메일 주소)와 SMTP_PASSWORD(앱 비밀번호) 두 개뿐이다.
    SMTP_HOST·SMTP_PORT를 비우면 Gmail(smtp.gmail.com:587), SMTP_FROM을 비우면 SMTP_USER로 보낸다.
    """
    values = {key: (get_setting(key) or "").strip() for key in SMTP_KEYS}
    if not values["SMTP_USER"] or not values["SMTP_PASSWORD"]:
        return None
    for key, default in SMTP_DEFAULTS.items():
        values[key] = values[key] or default
    values["SMTP_FROM"] = values["SMTP_FROM"] or values["SMTP_USER"]
    # Gmail 앱 비밀번호는 4글자씩 띄어 보여 주므로 공백을 지운다
    values["SMTP_PASSWORD"] = values["SMTP_PASSWORD"].replace(" ", "")
    try:
        values["SMTP_PORT"] = int(values["SMTP_PORT"])
    except ValueError:
        return None
    return values


def _connect(db_path=None):
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS email_alerts (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            alerts TEXT NOT NULL,
            consent_privacy_at TEXT NOT NULL,
            consent_receive_at TEXT NOT NULL,
            consent_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return connection


@contextmanager
def _db(db_path=None):
    """트랜잭션 커밋 후 연결을 닫는다."""
    connection = _connect(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _now():
    return datetime.now(KOREA_TIMEZONE)


def normalize_email(value):
    email = (value or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise AlertError("이메일 주소 형식을 확인해 주세요.")
    return email


def alerts_from_events(events, today, remind_days_before=1):
    """앞으로 남은 일정만 알림으로. 각 알림: {send_on, event_date, title, description, sent}."""
    alerts = []
    for event in events:
        event_date = event["date"] if isinstance(event["date"], date) else date.fromisoformat(event["date"])
        if event_date < today:
            continue
        send_on = max(today, event_date - timedelta(days=remind_days_before))
        alerts.append({
            "send_on": send_on.isoformat(),
            "event_date": event_date.isoformat(),
            "title": event["title"],
            "description": event.get("description", ""),
            "sent": False,
        })
    return alerts[:MAX_ALERTS]


def subscribe(email, events, consent_privacy, consent_receive, db_path=None, now=None):
    """두 동의가 모두 있어야 저장. 같은 이메일이면 일정만 새로 바꾼다. 해지용 토큰을 돌려준다."""
    if consent_privacy is not True or consent_receive is not True:
        raise AlertError("개인정보 수집·이용과 알림 수신에 모두 동의해야 신청할 수 있어요.")
    email = normalize_email(email)
    now = now or _now()
    alerts = alerts_from_events(events, now.date())
    if not alerts:
        raise AlertError("앞으로 남은 일정이 없어 알림을 신청할 수 없어요.")
    stamp = now.isoformat(timespec="seconds")
    with _db(db_path) as connection:
        row = connection.execute("SELECT token FROM email_alerts WHERE email = ?", (email,)).fetchone()
        token = row[0] if row else secrets.token_urlsafe(16)
        connection.execute(
            """
            INSERT INTO email_alerts (token, email, alerts, consent_privacy_at, consent_receive_at,
                                      consent_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET alerts = excluded.alerts,
                consent_privacy_at = excluded.consent_privacy_at,
                consent_receive_at = excluded.consent_receive_at,
                consent_version = excluded.consent_version
            """,
            (token, email, json.dumps(alerts, ensure_ascii=False), stamp, stamp, CONSENT_VERSION, stamp),
        )
    return {"token": token, "email": email, "alerts": alerts}


def unsubscribe(email=None, token=None, db_path=None):
    """이메일 또는 해지 토큰으로 즉시 삭제. 삭제한 건수를 돌려준다."""
    with _db(db_path) as connection:
        if token:
            cursor = connection.execute("DELETE FROM email_alerts WHERE token = ?", (token,))
        elif email:
            cursor = connection.execute("DELETE FROM email_alerts WHERE email = ?", (normalize_email(email),))
        else:
            return 0
        return cursor.rowcount


def count_subscriptions(db_path=None):
    with _db(db_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM email_alerts").fetchone()[0]


def _unsubscribe_line(app_url, token):
    return f"알림 그만 받기(이메일 즉시 삭제): {app_url}?unsubscribe={token}" if app_url else ""


def build_welcome_message(config, email, alerts, token, ics_bytes, app_url=None):
    message = EmailMessage()
    message["Subject"] = "[오이소창원] 창원 정착 일정 알림 신청 완료"
    message["From"] = config["SMTP_FROM"]
    message["To"] = email
    lines = [
        "창원 정착 일정 알림을 신청해 주셔서 고마워요.",
        "",
        "다가오는 일정",
        *[f"- {alert['event_date']} {alert['title']}" for alert in alerts[:10]],
        "",
        "첨부한 캘린더 파일(.ics)을 열면 휴대폰·PC 캘린더에 일정이 들어가고, 하루 전 오전 9시에 알림이 떠요.",
        "이메일 알림은 일정 하루 전에 보내드려요(앱 서버 상황에 따라 늦어질 수 있어요).",
        "",
        "혜택 일정은 확인일 기준 공식 자료를 바탕으로 했어요. 최종 대상·일정은 담당 기관 공고에서 확인하세요.",
        _unsubscribe_line(app_url, token),
    ]
    message.set_content("\n".join(line for line in lines if line is not None))
    if ics_bytes:
        message.add_attachment(
            ics_bytes, maintype="text", subtype="calendar", filename="oisochangwon_schedule.ics"
        )
    return message


def build_reminder_message(config, email, due_alerts, token, app_url=None):
    message = EmailMessage()
    first = due_alerts[0]
    message["Subject"] = f"[오이소창원] {first['event_date']} {first['title']}"
    message["From"] = config["SMTP_FROM"]
    message["To"] = email
    lines = ["다가오는 창원 정착 일정이에요.", ""]
    for alert in due_alerts:
        lines += [f"■ {alert['event_date']} {alert['title']}", alert["description"], ""]
    lines += [
        "혜택 일정은 확인일 기준이에요. 최종 대상·일정은 담당 기관 공고에서 확인하세요.",
        _unsubscribe_line(app_url, token),
    ]
    message.set_content("\n".join(lines))
    return message


def send_message(config, message, smtp_factory=None):
    if smtp_factory is not None:
        with smtp_factory() as server:
            server.send_message(message)
        return
    if config["SMTP_PORT"] == 465:
        with smtplib.SMTP_SSL(config["SMTP_HOST"], 465, timeout=15) as server:
            server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.send_message(message)
    else:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=15) as server:
            server.starttls()
            server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.send_message(message)


def send_due_alerts(config, db_path=None, today=None, app_url=None, smtp_factory=None):
    """보낼 날이 된 알림을 보낸다. 다 보낸 신청은 바로 삭제(보유 기간 종료). 보낸 메일 수를 돌려준다."""
    today = today or _now().date()
    sent_count = 0
    with _db(db_path) as connection:
        rows = connection.execute("SELECT token, email, alerts FROM email_alerts").fetchall()
    for token, email, alerts_json in rows:
        alerts = json.loads(alerts_json)
        due = [alert for alert in alerts if not alert["sent"] and alert["send_on"] <= today.isoformat()]
        # 이미 지난 일정은 보내지 않고 정리
        due_to_send = [alert for alert in due if alert["event_date"] >= today.isoformat()]
        if due_to_send:
            send_message(config, build_reminder_message(config, email, due_to_send, token, app_url), smtp_factory)
            sent_count += 1
        for alert in due:
            alert["sent"] = True
        with _db(db_path) as connection:
            if all(alert["sent"] for alert in alerts):
                connection.execute("DELETE FROM email_alerts WHERE token = ?", (token,))
            elif due:
                connection.execute(
                    "UPDATE email_alerts SET alerts = ? WHERE token = ?",
                    (json.dumps(alerts, ensure_ascii=False), token),
                )
    return sent_count

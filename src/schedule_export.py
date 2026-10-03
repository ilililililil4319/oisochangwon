"""정착 일정 내보내기 — 캘린더 파일(.ics)과 정착 리포트(HTML).

- 모두 사용자가 입력한 전입일·하는 일, 앱이 계산한 일정, 저장된 체크만 사용한다(값을 지어내지 않음).
- 실명·연락처·닉네임은 넣지 않는다. 파일은 사용자 기기에만 저장된다.
"""

import hashlib
import html
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
CALENDAR_LEVELS = ("해당 가능", "조건부 해당 가능")
APP_NAME = "오이소창원"


def _as_date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def build_schedule_events(move_in_date, milestone_labels, mission_groups, matches):
    """캘린더·알림에 넣을 일정 목록. 각 항목: {date, title, description, kind}.

    1) 정착 일정(전입일 기준 0·7·30·90·180일)
    2) 월별 할 일 시작일(전입 후 N개월)
    3) 해당 가능·조건부 해당 가능 혜택 중 날짜가 정해진 일정
    """
    from dateutil.relativedelta import relativedelta

    events = []
    for day, label in milestone_labels.items():
        events.append({
            "date": move_in_date + timedelta(days=day),
            "title": f"[창원 정착] {label}" if day else "[창원 정착] 전입한 날",
            "description": f"전입 후 {day}일째 정착 일정이에요." if day else "창원 전입일이에요.",
            "kind": "milestone",
        })
    for group in mission_groups:
        start = move_in_date + relativedelta(months=group["month"] - 1)
        todo = "\n".join(f"- {mission['미션']}" for mission in group["missions"])
        events.append({
            "date": start,
            "title": f"[창원 정착] {group['month']}개월 차 할 일 · {group['theme']}",
            "description": f"이번 달 할 일\n{todo}",
            "kind": "missions",
        })
    for match in matches:
        if match["level"] not in CALENDAR_LEVELS:
            continue
        for day, label in match.get("events", []):
            events.append({
                "date": _as_date(day),
                "title": f"[혜택 확인] {match['name']}",
                "description": (
                    f"{label}\n안내 확인일 {match.get('checked') or '-'} 기준이에요. "
                    "실제 일정·대상은 공고와 담당 기관에서 꼭 확인하세요."
                    + (f"\n{match['link']}" if match.get("link") else "")
                ),
                "kind": "policy",
                "url": match.get("link"),
            })
    events.sort(key=lambda event: (event["date"], event["kind"] != "milestone", event["title"]))
    return events


def _ics_text(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def _fold(line):
    """RFC 5545: 한 줄 75바이트 이하로 접기(UTF-8 글자를 자르지 않음)."""
    out, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        limit = 75 if not out else 74
        if len(current) + len(encoded) > limit:
            out.append(current)
            current = b""
        current += encoded
    out.append(current)
    return "\r\n ".join(part.decode("utf-8") for part in out)


def build_ics(events, now=None, remind_days_before=1):
    """종일 일정 .ics(바이트). 하루 전 오전 9시 알림(VALARM) 포함."""
    now = now or datetime.now(KOREA_TIMEZONE)
    stamp = now.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{APP_NAME}//Changwon Settlement//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{APP_NAME} 창원 정착 일정",
        "X-WR-TIMEZONE:Asia/Seoul",
    ]
    for event in events:
        day = _as_date(event["date"])
        uid_source = f"{day.isoformat()}|{event['title']}".encode("utf-8")
        uid = hashlib.sha1(uid_source).hexdigest()[:20]
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@oisochangwon",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_text(event['title'])}",
            f"DESCRIPTION:{_ics_text(event['description'])}",
        ]
        if event.get("url"):
            lines.append(f"URL:{event['url']}")
        if remind_days_before is not None:
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_ics_text(event['title'])}",
                # 종일 일정 시작(0시) 기준 15시간 전 = 전날 오전 9시
                f"TRIGGER:-PT{remind_days_before * 24 - 9}H",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


def _e(value):
    return html.escape(str(value or ""))


def build_report_html(profile, settlement_day, progress_summary, mission_groups, states, notes,
                      matches, events, generated_at=None):
    """내 기기에 저장하는 정착 리포트(HTML, 인쇄하면 PDF로 저장 가능). 개인 식별 정보 없음."""
    generated_at = generated_at or datetime.now(KOREA_TIMEZONE)
    today = generated_at.date()
    rows = []
    rows.append("<h1>창원 정착 리포트</h1>")
    rows.append(
        f"<p class='meta'>{_e(APP_NAME)} · 만든 날 {generated_at:%Y-%m-%d %H:%M} (한국시간) · "
        "실명·연락처는 들어 있지 않아요.</p>"
    )
    day_text = f"정착 {settlement_day + 1}일째" if settlement_day is not None and settlement_day >= 0 else "전입 예정"
    rows.append("<h2>1. 나의 조건</h2><table>")
    for label, value in (
        ("창원 전입일", profile.get("move_in_date")),
        ("지금", day_text),
        ("하는 일", profile.get("job_type") or "미입력"),
        ("나이", f"{profile['age']}세" if profile.get("age") else "미입력"),
        ("차량", profile.get("vehicle") or "미입력"),
    ):
        rows.append(f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>")
    rows.append("</table>")

    rows.append("<h2>2. 정착 할 일 진행</h2>")
    if progress_summary:
        rows.append(
            f"<p>전체 {progress_summary['overall_completed']} / {progress_summary['overall_total']} 완료 · "
            f"이번 단계 {progress_summary['stage_completed']} / {progress_summary['stage_total']} 완료</p>"
        )
    for group in mission_groups:
        rows.append(f"<h3>{group['month']}개월 차 · {_e(group['theme'])}</h3><ul class='todo'>")
        for mission in group["missions"]:
            done = states.get(mission["ID"]) is True
            note = notes.get(mission["ID"])
            rows.append(
                f"<li class='{'done' if done else ''}'>{'☑' if done else '☐'} {_e(mission['미션'])}"
                + (f"<br><span class='note'>내 기록: {_e(note)}</span>" if note else "")
                + "</li>"
            )
        rows.append("</ul>")

    rows.append("<h2>3. 다가오는 일정</h2><table><tr><th>날짜</th><th>일정</th></tr>")
    upcoming = [event for event in events if _as_date(event["date"]) >= today][:15]
    for event in upcoming:
        rows.append(f"<tr><td>{_as_date(event['date']).isoformat()}</td><td>{_e(event['title'])}</td></tr>")
    if not upcoming:
        rows.append("<tr><td colspan='2'>남은 일정이 없어요.</td></tr>")
    rows.append("</table>")

    rows.append("<h2>4. 나에게 맞는 혜택</h2>")
    for level in ("해당 가능", "조건부 해당 가능", "직접 확인"):
        group = [match for match in matches if match["level"] == level]
        if not group:
            continue
        rows.append(f"<h3>{_e(level)} · {len(group)}개</h3><ul>")
        for match in group:
            link = (
                f" · <a href='{_e(match['link'])}'>공식 안내</a>" if (match.get("link") or "").startswith("https://") else ""
            )
            reason = match["reasons"][0] if match.get("reasons") else ""
            rows.append(
                f"<li><b>{_e(match['name'])}</b>{link}<br><span class='note'>{_e(reason)}"
                f"{' · 확인일 ' + _e(match['checked']) if match.get('checked') else ''}</span></li>"
            )
        rows.append("</ul>")
    rows.append(
        "<p class='meta'>안내는 확인일 기준 공식 자료를 바탕으로 한 것이고, 최종 대상 여부와 일정은 "
        "담당 기관 공고에서 확인해 주세요.</p>"
    )
    style = (
        "body{font-family:'Noto Sans KR','Malgun Gothic',sans-serif;max-width:780px;margin:24px auto;padding:0 16px;"
        "color:#1d2733;line-height:1.55}h1{color:#063465;border-bottom:3px solid #FE6A01;padding-bottom:6px}"
        "h2{color:#063465;margin-top:28px}h3{color:#2E9E6B;margin-bottom:4px}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #D5DDE7;padding:6px 10px;text-align:left;vertical-align:top}th{background:#EEF4FB;width:30%}td:first-child{white-space:nowrap}"
        "ul{padding-left:20px}.todo{list-style:none;padding-left:4px}.done{color:#2E9E6B}.note{color:#5b6775;font-size:.92em}"
        ".meta{color:#5b6775;font-size:.9em}a{color:#063465}@media print{body{margin:0}}"
    )
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>창원 정착 리포트</title><style>{style}</style></head><body>"
        + "".join(rows)
        + "</body></html>"
    ).encode("utf-8")

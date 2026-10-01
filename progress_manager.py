from datetime import date, datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
MAX_SETTLEMENT_MONTH = 6


def current_settlement_month(move_in_date, current_date=None):
    if not isinstance(move_in_date, date) or isinstance(move_in_date, datetime):
        raise TypeError("move_in_date must be a datetime.date value")
    if current_date is None:
        current_date = datetime.now(KOREA_TIMEZONE).date()
    if not isinstance(current_date, date) or isinstance(current_date, datetime):
        raise TypeError("current_date must be a datetime.date value")

    elapsed = relativedelta(current_date, move_in_date)
    elapsed_months = elapsed.years * 12 + elapsed.months
    return min(MAX_SETTLEMENT_MONTH, max(1, elapsed_months + 1))


def calculate_mission_progress(missions, completed_states, current_month):
    if not isinstance(current_month, int) or not 1 <= current_month <= MAX_SETTLEMENT_MONTH:
        raise ValueError("current_month must be between 1 and 6")

    current_missions = [
        mission for mission in missions if mission["개월"] == current_month
    ]
    completed_count = sum(
        completed_states.get(mission["ID"], False) is True
        for mission in missions
    )
    current_completed_count = sum(
        completed_states.get(mission["ID"], False) is True
        for mission in current_missions
    )

    return {
        "overall_completed": completed_count,
        "overall_total": len(missions),
        "stage_completed": current_completed_count,
        "stage_total": len(current_missions),
    }


def encouragement_message(completed_count, total_count):
    if not isinstance(completed_count, int) or not isinstance(total_count, int):
        raise TypeError("mission counts must be integers")
    if total_count < 0 or completed_count < 0 or completed_count > total_count:
        raise ValueError("mission counts are out of range")
    if total_count == 0:
        return "이번 단계에 준비된 할 일이 없어요."
    if completed_count == 0:
        return "가장 간단한 것부터 하나 시작해볼까요?"
    if completed_count == total_count:
        return f"{total_count}개나 완료하셨어요! 이번 단계도 잘 마쳤네요."
    if completed_count == 1:
        return "좋아요. 첫걸음을 시작했어요!"
    if completed_count == total_count - 1:
        return f"{completed_count}개 완료! 하나만 더 하면 이번 단계 끝이에요."
    if completed_count * 2 == total_count:
        return f"{completed_count}개 완료했어요. 절반을 마쳤네요!"
    if completed_count * 2 > total_count:
        return f"{completed_count}개 완료했어요. 절반을 넘겼네요!"
    return f"벌써 {completed_count}개 완료했어요. 하나씩 잘 해가고 있어요."

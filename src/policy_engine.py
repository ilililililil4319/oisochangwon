from datetime import date
from dateutil.relativedelta import relativedelta


def evaluate_p01(profile):
    """
    P01 기업노동자 전입지원금 판정
    """

    required_fields = [
        "move_in_date",
        "previous_residence_years",
        "employed_in_changwon",
    ]

    missing_fields = [
        field for field in required_fields
        if profile.get(field) is None
    ]

    if missing_fields:
        return {
            "policy_id": "P01",
            "policy_name": "기업노동자 전입지원금",
            "status": "needs_info",
            "reason": "정책 판정에 필요한 정보가 부족합니다.",
            "missing_fields": missing_fields,
            "eligible_date": None,
        }

    move_in_date = profile["move_in_date"]
    previous_residence_years = profile["previous_residence_years"]
    employed_in_changwon = profile["employed_in_changwon"]

    # 이전 지역에서 1년 이상 거주했는지
    if previous_residence_years < 1:
        return {
            "policy_id": "P01",
            "policy_name": "기업노동자 전입지원금",
            "status": "not_eligible",
            "reason": "창원 전입 전 타지역 1년 이상 거주 조건을 충족하지 않습니다.",
            "missing_fields": [],
            "eligible_date": None,
        }

    # 지원 대상은 '창원 소재 영리기업·소상공인 사업장에 근무하는 노동자'(창원시 인구정책 누리집) → 사업주(자영업)는 제외
    if profile.get("job_type") == "자영업":
        return {
            "policy_id": "P01",
            "policy_name": "기업노동자 전입지원금",
            "status": "not_eligible",
            "reason": "창원 소재 사업장에 근무하는 노동자가 대상이라 자영업(사업주)은 해당하지 않습니다.",
            "missing_fields": [],
            "eligible_date": None,
        }

    # 창원 소재 기업에 재직 중인지
    if not employed_in_changwon:
        return {
            "policy_id": "P01",
            "policy_name": "기업노동자 전입지원금",
            "status": "not_eligible",
            "reason": "창원 소재 사업장 재직 조건을 충족하지 않습니다.",
            "missing_fields": [],
            "eligible_date": None,
        }

    # 6개월은 180일이 아니라 달력 기준 6개월로 계산
    eligible_date = move_in_date + relativedelta(months=6)

    if date.today() < eligible_date:
        return {
            "policy_id": "P01",
            "policy_name": "기업노동자 전입지원금",
            "status": "eligible_later",
            "reason": "전입 후 6개월 계속 거주 조건이 아직 충족되지 않았습니다.",
            "missing_fields": [],
            "eligible_date": eligible_date.isoformat(),
        }

    return {
        "policy_id": "P01",
        "policy_name": "기업노동자 전입지원금",
        "status": "eligible_now",
        "reason": "현재 확인된 핵심 조건을 충족합니다.",
        "missing_fields": [],
        "eligible_date": eligible_date.isoformat(),
    }


if __name__ == "__main__":
    demo_profile = {
        "move_in_date": date(2026, 9, 20),
        "previous_residence_years": 2,
        "employed_in_changwon": True,
    }

    result = evaluate_p01(demo_profile)
    print(result)
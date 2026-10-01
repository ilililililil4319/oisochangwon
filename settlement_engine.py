from datetime import date, datetime, timedelta


MILESTONE_DAYS = (0, 7, 30, 90, 180)


def build_settlement_plan(move_in_date):
    """Build elapsed-day milestones and their settlement missions."""
    if not isinstance(move_in_date, date) or isinstance(move_in_date, datetime):
        raise TypeError("move_in_date must be a datetime.date value")

    milestones = []
    for elapsed_days in MILESTONE_DAYS:
        milestone_date = move_in_date + timedelta(days=elapsed_days)
        milestones.append(
            {
                "day": elapsed_days,
                "date": milestone_date.isoformat(),
            }
        )

    return {
        "move_in_date": move_in_date.isoformat(),
        "milestones": milestones,
    }

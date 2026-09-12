from __future__ import annotations

from datetime import date, timedelta
import calendar


def parse_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def add_months(d: date, months: int = 1) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


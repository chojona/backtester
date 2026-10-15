"""Evidence-backed ordinary NQ trade-date rule before the 2012 hours change.

This maps timestamps only. It does not certify historical holiday exceptions or
the completeness of a session's bars.
"""
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CHANGE = date(2012, 11, 19)


def ordinary_nq_trade_date(stamp):
    """Return an ordinary trade date, or None outside regular Globex hours.

    CME's November 2012 change notice establishes that, before the change,
    Monday-Thursday 16:30-17:30 ET belonged to the next trade date.
    Dated holiday and emergency exceptions must be applied separately.
    """
    if stamp.tzinfo is None:
        raise ValueError("Aware timestamp required")
    local = stamp.astimezone(NY)
    day, clock, weekday = local.date(), local.time(), local.weekday()
    if day >= CHANGE:
        raise ValueError("Pre-2012 mapping only")
    if weekday == 5 or (weekday == 6 and clock < time(18)):
        return None
    if weekday == 4 and clock >= time(16, 15):
        return None
    if weekday < 4 and time(16, 15) <= clock < time(16, 30):
        return None
    if weekday < 4 and time(17, 30) <= clock < time(18):
        return None
    if weekday <= 3 and clock >= time(16, 30):
        return day + timedelta(days=1)
    if weekday == 6 and clock >= time(18):
        return day + timedelta(days=1)
    return day

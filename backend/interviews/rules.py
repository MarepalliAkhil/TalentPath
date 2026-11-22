"""Every scheduling number in one place (documented in docs/HIRA.md)."""

from datetime import timedelta

MIN_LEAD = timedelta(hours=24)  # slots start at least 24 hours ahead
HORIZON_DAYS = 14  # look this far ahead for slots
GRID_MINUTES = 30  # slots start on the hour or half hour (IST)
MAX_SLOTS = 5  # HIRA offers 3 to 5 slots
MIN_SLOTS = 3
MAX_SLOTS_PER_DAY = 2  # spread the choice across days
MIN_GAP_SAME_DAY = timedelta(hours=2)
HOLD_MINUTES = 30  # a picked slot is held while the candidate confirms
LINK_TTL = timedelta(hours=72)  # email link lifetime (single use)
RESCHEDULE_LIMIT = 2
RESCHEDULE_CUTOFF = timedelta(hours=12)  # no candidate reschedules within 12 hours
REMINDERS = (("24h", timedelta(hours=24)), ("1h", timedelta(hours=1)))
DAY_REMINDER_LATEST = timedelta(hours=12)  # no "24 hours before" reminder once within 12 hours
SCORECARD_DUE = timedelta(hours=24)  # after the interview ends
OVERDUE_NEEDS_YOU = timedelta(hours=48)  # after the interview ends
CHASE_EVERY = timedelta(hours=24)

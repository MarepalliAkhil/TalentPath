"""Minimal RFC 5545 calendar invites (.ics) for simulated emails and downloads."""

from datetime import UTC, datetime

from core.brand import get_brand


def _stamp(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line with a leading space."""
    out, chunk = [], line
    while len(chunk.encode("utf-8")) > 75:
        cut = 75
        while len(chunk[:cut].encode("utf-8")) > 75:
            cut -= 1
        out.append(chunk[:cut])
        chunk = " " + chunk[cut:]
    out.append(chunk)
    return "\r\n".join(out)


def build_ics(interview, *, summary: str, description: str, location: str, sequence: int = 0) -> str:
    brand = get_brand()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{brand['name']}//HIRA//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:interview-{interview.id}@talentpath.example",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{_stamp(datetime.now(UTC))}",
        f"DTSTART:{_stamp(interview.starts_at)}",
        f"DTEND:{_stamp(interview.ends_at)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"LOCATION:{_escape(location)}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"

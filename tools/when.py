#!/usr/bin/env python3
"""Dates and time zones: weekdays, date arithmetic, conversions and shared working hours.

Donna runs this instead of working out weekdays, date gaps or time-zone conversions from memory.
Shrey's zone defaults to Asia/Kolkata; pass --tz for another. A zone can be an IANA name
("America/New_York"), a city ("new york", "london", "bengaluru") or a common abbreviation
("IST", "ET", "PT"; ET and PT mean the region's local time, daylight saving included).

  python3 tools/when.py now --also london "new york"
  python3 tools/when.py day 2026-10-14
  python3 tools/when.py calendar --days 14
  python3 tools/when.py add 2026-10-04 --workdays 5
  python3 tools/when.py convert "2026-10-14 9:00am" --from "new york" --to IST london
  python3 tools/when.py overlap 2026-10-14 --zones IST "new york" --hours 9-19
  python3 tools/when.py overlap 2026-10-14 --zones IST=8-22 sydney "san francisco"
"""

from __future__ import annotations

import argparse
import calendar
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

DEFAULT_TZ = "Asia/Kolkata"
ALIASES = {
    **dict.fromkeys(["ist", "india", "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "hyderabad",
                     "chennai", "pune", "kolkata", "ahmedabad", "gurgaon", "gurugram", "noida"], "Asia/Kolkata"),
    **dict.fromkeys(["et", "est", "edt", "eastern", "boston", "washington"], "America/New_York"),
    **dict.fromkeys(["ct", "cst", "cdt", "central"], "America/Chicago"),
    **dict.fromkeys(["mt", "mst", "mdt", "mountain"], "America/Denver"),
    **dict.fromkeys(["pt", "pst", "pdt", "pacific", "san francisco", "sf", "bay area", "seattle"],
                    "America/Los_Angeles"),
    **dict.fromkeys(["uk", "gmt", "bst"], "Europe/London"),
    **dict.fromkeys(["aest", "aedt"], "Australia/Sydney"),
    "sgt": "Asia/Singapore",
    "gst": "Asia/Dubai",
    "utc": "UTC",
}


def zone(name: str) -> ZoneInfo:
    """Resolve an IANA name, alias or city to a ZoneInfo."""
    key = name.strip()
    if key.lower() in ALIASES:
        return ZoneInfo(ALIASES[key.lower()])
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError):
        pass
    wanted = key.lower().replace(" ", "_")
    zones = available_timezones()
    matches = [z for z in zones if z.lower().rsplit("/", 1)[-1] == wanted]
    if matches:  # several matches are links to the same zone, e.g. Asia/Istanbul and Europe/Istanbul
        return ZoneInfo(min(matches, key=len))
    hint = sorted(z for z in zones if wanted in z.lower())[:8]
    raise ValueError(f"unknown time zone {name!r}" + (f"; did you mean {', '.join(hint)}?" if hint else ""))


def parse_date(text: str, today: date) -> date:
    t = text.strip().lower()
    offsets = {"today": 0, "tomorrow": 1, "yesterday": -1}
    if t in offsets:
        return today + timedelta(days=offsets[t])
    try:
        return date.fromisoformat(t)
    except ValueError:
        raise ValueError(f"can't read the date {text!r}; use YYYY-MM-DD, today or tomorrow") from None


def parse_time(text: str) -> time:
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)?", text.strip().lower())
    if not m:
        raise ValueError(f"can't read the time {text!r}; use 15:30 or 3:30pm")
    hour, minute, half = int(m[1]), int(m[2] or 0), m[3]
    if half:
        if not 1 <= hour <= 12:
            raise ValueError(f"can't read the time {text!r}")
        hour = hour % 12 + (12 if half == "pm" else 0)
    return time(hour, minute)


def parse_moment(text: str, tz: ZoneInfo, today: date) -> datetime:
    """'2026-10-14 15:30', '2026-10-14T15:30', 'tomorrow 3pm' or '9:00 am' (today) as a time in tz."""
    words = re.sub(r"(\d)T(\d)", r"\1 \2", text).split()
    if len(words) >= 2 and words[-1].lower() in ("am", "pm"):
        words[-2:] = [words[-2] + words[-1]]
    if not words:
        raise ValueError("no time given")
    day = parse_date(" ".join(words[:-1]), today) if len(words) > 1 else today
    return datetime.combine(day, parse_time(words[-1]), tzinfo=tz)


def clock_change(dt: datetime) -> str | None:
    """Say if a local time is skipped or repeated by a daylight-saving change."""
    actual = dt.astimezone(timezone.utc).astimezone(dt.tzinfo)
    if actual.replace(tzinfo=None) != dt.replace(tzinfo=None):
        return (f"{dt:%H:%M} doesn't exist on {dt:%d %b %Y} in {dt.tzinfo.key} (clocks go forward); "
                f"read as {actual:%H:%M}")
    if dt.replace(fold=0).utcoffset() != dt.replace(fold=1).utcoffset():
        return f"{dt:%H:%M} happens twice on {dt:%d %b %Y} in {dt.tzinfo.key} (clocks go back); read as the first"
    return None


def convert(moment: datetime, targets: list[ZoneInfo]) -> list[datetime]:
    return [moment.astimezone(tz) for tz in targets]


def add_months(d: date, months: int) -> date:
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


def shift(d: date, days: int = 0, weeks: int = 0, months: int = 0, workdays: int = 0) -> date:
    """Months first, then days and weeks, then working days (Mon-Fri; public holidays not excluded)."""
    d = add_months(d, months) + timedelta(days=days, weeks=weeks)
    step = 1 if workdays > 0 else -1
    for _ in range(abs(workdays)):
        d += timedelta(days=step)
        while d.weekday() >= 5:
            d += timedelta(days=step)
    return d


def relative(d: date, today: date) -> str:
    gap = (d - today).days
    named = {0: "today", 1: "tomorrow", -1: "yesterday"}
    if gap in named:
        return named[gap]
    return f"in {gap} days" if gap > 0 else f"{-gap} days ago"


def working_window(day: date, tz: ZoneInfo, start: time, end: time) -> tuple[datetime, datetime]:
    """One zone's working hours on a local date, in UTC. An end at or before the start runs past midnight."""
    begin = datetime.combine(day, start, tzinfo=tz)
    finish = datetime.combine(day + timedelta(days=1 if end <= start else 0), end, tzinfo=tz)
    return begin.astimezone(timezone.utc), finish.astimezone(timezone.utc)


def shared_hours(day: date, zones: list[tuple[ZoneInfo, time, time]]) -> list[tuple[datetime, datetime]]:
    """UTC spans that are working time in every zone. The first zone's local date anchors the day;
    the others may be on the previous or next local date (Sydney's Thursday morning is California's
    Wednesday afternoon)."""
    first, start, end = zones[0]
    spans = [working_window(day, first, start, end)]
    for tz, start, end in zones[1:]:
        options = [working_window(day + timedelta(days=k), tz, start, end) for k in (-1, 0, 1)]
        spans = [(max(a, c), min(b, d)) for a, b in spans for c, d in options if max(a, c) < min(b, d)]
    return sorted(spans)


def fmt(dt: datetime) -> str:
    return f"{dt:%a %d %b %Y, %H:%M} {dt.tzname()} ({dt.tzinfo.key})"


def _hours(text: str) -> tuple[time, time]:
    start, _, end = text.partition("-")
    if not end:
        raise ValueError(f"can't read the hours {text!r}; use 9-18 or 9:30-18:30")
    return parse_time(start), parse_time(end)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"Shrey's time zone (default {DEFAULT_TZ})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("now", help="current date and time")
    p.add_argument("--also", nargs="+", default=[], help="other zones to show")

    p = sub.add_parser("day", help="weekday and distance from today")
    p.add_argument("date", nargs="+")

    p = sub.add_parser("calendar", help="list dates with weekdays")
    p.add_argument("start", nargs="?", default="today")
    p.add_argument("--days", type=int, default=14)

    p = sub.add_parser("add", help="date arithmetic")
    p.add_argument("date")
    for unit in ("days", "weeks", "months", "workdays"):
        p.add_argument(f"--{unit}", type=int, default=0)

    p = sub.add_parser("convert", help="a time in one zone, in others")
    p.add_argument("moment", help="'2026-10-14 15:30', 'tomorrow 3pm' or '9:30am'")
    p.add_argument("--from", dest="src", help="zone the time is in (default --tz)")
    p.add_argument("--to", nargs="+", default=[], help="zones to convert to (default --tz)")

    p = sub.add_parser("overlap", help="working hours shared by several zones")
    p.add_argument("date")
    p.add_argument("--zones", nargs="+", required=True, help="zones, each optionally with hours: IST=8-22")
    p.add_argument("--hours", default="9-18", help="working hours where a zone gives none (default 9-18)")

    a = ap.parse_args(argv)
    try:
        home = zone(a.tz)
        now = datetime.now(home)
        today = now.date()
        if a.cmd == "now":
            for tz in [home, *map(zone, a.also)]:
                print(fmt(now.astimezone(tz)))
        elif a.cmd == "day":
            for text in a.date:
                d = parse_date(text, today)
                print(f"{d:%A %d %b %Y} · {relative(d, today)} · ISO week {d.isocalendar()[1]}")
        elif a.cmd == "calendar":
            start = parse_date(a.start, today)
            for i in range(a.days):
                d = start + timedelta(days=i)
                notes = [n for n, hit in (("today", d == today), ("weekend", d.weekday() >= 5)) if hit]
                print(f"{d:%a %d %b %Y}" + (f"  ({', '.join(notes)})" if notes else ""))
        elif a.cmd == "add":
            start = parse_date(a.date, today)
            end = shift(start, a.days, a.weeks, a.months, a.workdays)
            print(f"{end:%A %d %b %Y} · {relative(end, today)}")
            if a.workdays:
                print("Working days are Mon-Fri; public holidays are not excluded.")
        elif a.cmd == "convert":
            src = zone(a.src) if a.src else home
            moment = parse_moment(a.moment, src, datetime.now(src).date())
            warning = clock_change(moment)
            if warning:
                print(f"Note: {warning}")
            moment = moment.astimezone(timezone.utc).astimezone(src)
            print(fmt(moment))
            for dt in convert(moment, [zone(t) for t in a.to] or [home]):
                print(f"= {fmt(dt)}")
        else:
            default = _hours(a.hours)
            zones = []
            for spec in a.zones:
                name, _, hours = spec.partition("=")
                zones.append((zone(name), *(_hours(hours) if hours else default)))
            day = parse_date(a.date, today)
            spans = shared_hours(day, zones)
            if not spans:
                print(f"No shared working hours on {day:%a %d %b %Y}. Widen --hours, or give a zone "
                      "its own hours, e.g. IST=8-22.")
            for i, (begin, end) in enumerate(spans, 1):
                print(f"Option {i}: {int((end - begin).total_seconds() // 60)} min")
                for tz, _, _ in zones:
                    b, e = begin.astimezone(tz), end.astimezone(tz)
                    weekend = "  (weekend)" if b.weekday() >= 5 else ""
                    print(f"  {tz.key:<22}{b:%a %d %b} {b:%H:%M}-{e:%H:%M} {e.tzname()}{weekend}")
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

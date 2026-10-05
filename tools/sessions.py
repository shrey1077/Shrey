#!/usr/bin/env python3
"""ADHD-friendly day planner: turns anchors, fixed events and tasks into short, timed sessions.

Donna runs this instead of laying out a day by hand. Input is a JSON file; print a starting point
with --example:

  python3 tools/sessions.py --example > secretary/private/plan-input.json
  python3 tools/sessions.py secretary/private/plan-input.json
  python3 tools/sessions.py secretary/private/plan-input.json --widget > secretary/private/today.json

What it does:
- Places anchors (wake-up, breakfast, meals, wind-down) and fixed events (meetings) first.
- Adds a "get ready" buffer before each meeting and a short reset after it, so nothing starts cold.
- Keeps focus sessions inside `focus_hours` (a task can carry its own `window`, e.g. chess after
  18:00), so work never starts before breakfast.
- Cuts tasks into focus sessions of at most `session_minutes`, each followed by a break; every
  `long_break_every` sessions the break is a long one.
- Puts high-energy tasks in peak hours and low-energy ones outside them, without letting a minor
  task jump far ahead of an important one.
- Caps total focus time at `max_focus_minutes`. What doesn't fit is reported, never crammed in.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULTS = {
    "session_minutes": 45,
    "min_session_minutes": 20,
    "break_minutes": 10,
    "long_break_minutes": 20,
    "long_break_every": 3,
    "buffer_before_meeting": 10,
    "reset_after_meeting": 5,
    "focus_hours": ["09:30-19:00"],
    "peak_hours": ["10:00-13:00"],
    "max_focus_minutes": 300,
}
BREAKS = ["Break: water and a stretch", "Break: walk around the room", "Break: step outside, eyes off screens"]
LONG_BREAK = "Long break: snack, move, no phone"
ICONS = {"anchor": "⚓", "meal": "🍽", "meeting": "📅", "event": "📌", "buffer": "⏳", "reset": "↺",
         "focus": "🎯", "break": "☕"}

EXAMPLE = {
    "date": "2026-10-05",
    "timezone": "Asia/Kolkata",
    "day_start": "07:00",
    "day_end": "22:30",
    "anchors": [
        {"title": "Wake up: water, curtains open, feet on the floor", "start": "07:00", "minutes": 15, "kind": "anchor"},
        {"title": "Breakfast", "start": "07:45", "minutes": 30, "kind": "meal"},
        {"title": "Lunch", "start": "13:15", "minutes": 45, "kind": "meal"},
        {"title": "Dinner", "start": "20:00", "minutes": 45, "kind": "meal"},
        {"title": "Wind down: lay out tomorrow's clothes, screens off", "start": "22:00", "minutes": 30,
         "kind": "anchor"},
    ],
    "fixed": [{"title": "Call with Priya", "start": "11:00", "end": "11:30", "kind": "meeting"}],
    "tasks": [
        {"id": "t1", "title": "Draft the Q3 deck", "minutes": 120, "priority": 1, "energy": "high",
         "first_step": "Open the deck and write three slide titles"},
        {"id": "t2", "title": "Reply to the three emails Donna drafted", "minutes": 20, "priority": 2,
         "energy": "low", "first_step": "Open Gmail drafts"},
        {"id": "t3", "title": "Chess puzzles", "minutes": 30, "priority": 4, "energy": "medium",
         "window": "18:00-21:30"},
    ],
    "settings": DEFAULTS,
}


def minutes(text: str) -> int:
    hours, _, mins = text.strip().partition(":")
    value = int(hours) * 60 + int(mins or 0)
    if not 0 <= value <= 24 * 60 or not 0 <= int(mins or 0) < 60:
        raise ValueError(f"bad time {text!r}; use HH:MM")
    return value


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _window(text: str) -> tuple[int, int]:
    start, _, end = text.partition("-")
    return minutes(start), minutes(end)


def plan(spec: dict) -> dict:
    """Lay out the day. Returns blocks (sorted), unscheduled tasks, clashes and the focus total."""
    s = {**DEFAULTS, **spec.get("settings", {})}
    day_start, day_end = minutes(spec.get("day_start", "07:00")), minutes(spec.get("day_end", "22:30"))
    peaks = [_window(w) for w in s["peak_hours"]]
    focus_hours = [_window(w) for w in s["focus_hours"]]
    blocks, clashes = [], []

    for a in spec.get("anchors", []):
        start = minutes(a["start"])
        blocks.append({"start": start, "end": start + int(a.get("minutes", 15)), "kind": a.get("kind", "anchor"),
                       "title": a["title"]})
    for f in spec.get("fixed", []):
        start, end = minutes(f["start"]), minutes(f["end"])
        kind = f.get("kind", "meeting")
        blocks.append({"start": start, "end": end, "kind": kind, "title": f["title"]})
        if kind == "meeting":
            blocks.append({"start": start - s["buffer_before_meeting"], "end": start, "kind": "buffer",
                           "title": f"Get ready: {f['title']}"})
            blocks.append({"start": end, "end": end + s["reset_after_meeting"], "kind": "reset",
                           "title": "Reset: note the next step, water"})

    # Buffers and resets give way to anything real they overlap; real clashes are reported.
    fixed = sorted((b for b in blocks if b["kind"] not in ("buffer", "reset")), key=lambda b: b["start"])
    for prev, nxt in zip(fixed, fixed[1:]):
        if nxt["start"] < prev["end"]:
            clashes.append(f"{prev['title']} ({clock(prev['start'])}-{clock(prev['end'])}) overlaps "
                           f"{nxt['title']} ({clock(nxt['start'])}-{clock(nxt['end'])})")
    soft = []
    for b in (b for b in blocks if b["kind"] in ("buffer", "reset")):
        for f in fixed:
            if f["start"] < b["end"] and b["start"] < f["end"]:
                if b["kind"] == "buffer":
                    b["start"] = max(b["start"], f["end"]) if f["end"] <= b["end"] else b["end"]
                else:
                    b["end"] = min(b["end"], f["start"]) if f["start"] >= b["start"] else b["start"]
        if b["end"] > b["start"]:
            soft.append(b)
    busy = sorted(fixed + soft, key=lambda b: b["start"])

    gaps, cursor = [], day_start
    for b in busy:
        if b["start"] > cursor:
            gaps.append((cursor, min(b["start"], day_end)))
        cursor = max(cursor, b["end"])
    if cursor < day_end:
        gaps.append((cursor, day_end))

    tasks = [{**t, "left": int(t["minutes"]), "order": i, "parts": [],
              "windows": [_window(t["window"])] if t.get("window") else focus_hours}
             for i, t in enumerate(spec.get("tasks", []))]
    focus_total, sessions_done, out = 0, 0, list(busy)
    min_len, cap = s["min_session_minutes"], s["max_focus_minutes"]

    def mismatch(task: dict, at: int) -> int:
        in_peak = any(p0 <= at < p1 for p0, p1 in peaks)
        energy = task.get("energy", "medium")
        return int((energy == "high" and not in_peak) or (energy == "low" and in_peak))

    def room(task: dict, at: int, gap_end: int) -> int:
        """Minutes this task could use from `at`, inside its window, the gap and the daily cap."""
        for w0, w1 in task["windows"]:
            if w0 <= at < w1:
                return min(gap_end, w1, at + cap - focus_total) - at
        return 0

    for g0, g1 in gaps:
        cursor = g0
        while focus_total < cap and cursor < g1:
            fits = [t for t in tasks if t["left"] > 0 and min(t["left"], min_len) <= room(t, cursor, g1)]
            if not fits:
                # Nothing can start now: jump to the next time a waiting task's window opens.
                opens = [w0 for t in tasks if t["left"] > 0 for w0, _ in t["windows"] if cursor < w0 < g1]
                if not opens:
                    break
                cursor = min(opens)
                continue
            task = min(fits, key=lambda t: (4 * t.get("priority", 3) + 5 * mismatch(t, cursor), t["order"]))
            want = min(s["session_minutes"], task["left"])
            if 0 < task["left"] - want < min_len:
                want = task["left"]  # finish it rather than leave a scrap
            length = min(want, room(task, cursor, g1))
            if 0 < task["left"] - length < min_len and task["left"] - min_len >= min_len:
                length = task["left"] - min_len  # leave a session-sized remainder, not a scrap
            if length <= 0:
                break
            task["left"] -= length
            focus_total += length
            sessions_done += 1
            block = {"start": cursor, "end": cursor + length, "kind": "focus", "title": task["title"],
                     "task_id": task.get("id")}
            task["parts"].append(block)
            out.append(block)
            cursor += length
            long = sessions_done % s["long_break_every"] == 0
            rest = s["long_break_minutes"] if long else s["break_minutes"]
            after = cursor + rest
            if any(t["left"] > 0 and room(t, after, g1) >= min(t["left"], min_len) for t in tasks):
                out.append({"start": cursor, "end": after, "kind": "break",
                            "title": LONG_BREAK if long else BREAKS[(sessions_done - 1) % len(BREAKS)]})
                cursor = after

    for t in tasks:
        n = len(t["parts"])
        for i, b in enumerate(t["parts"], 1):
            if n > 1 or t["left"] > 0:
                b["title"] = f"{t['title']} ({i}/{n}{'+' if t['left'] > 0 else ''})"
            b["first_step"] = t.get("first_step") if i == 1 else "Pick up where you left off"
    out.sort(key=lambda b: (b["start"], b["end"]))
    for i, b in enumerate(out, 1):
        b["id"] = f"b{i}"
    unscheduled = [{"id": t.get("id"), "title": t["title"], "minutes": t["left"]} for t in tasks if t["left"] > 0]
    return {"blocks": out, "unscheduled": unscheduled, "clashes": clashes, "focus_minutes": focus_total,
            "sessions": sessions_done}


def widget_feed(spec: dict, result: dict) -> dict:
    """The today.json skeleton the desktop widget reads. Donna adds message, mood, outfit and the rest."""
    blocks = []
    for b in result["blocks"]:
        item = {"id": b["id"], "start": clock(b["start"]), "end": clock(b["end"]), "kind": b["kind"],
                "title": b["title"]}
        for key in ("first_step", "task_id"):
            if b.get(key):
                item[key] = b[key]
        blocks.append(item)
    return {"version": 1, "date": spec.get("date", date.today().isoformat()),
            "timezone": spec.get("timezone", "Asia/Kolkata"),
            "generated_at": datetime.now(ZoneInfo(spec.get("timezone", "Asia/Kolkata"))).isoformat(timespec="minutes"),
            "mood": "neutral", "message": "", "blocks": blocks, "unscheduled": result["unscheduled"]}


def _hm(total: int) -> str:
    return f"{total // 60}h {total % 60:02d}m" if total >= 60 else f"{total}m"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="plan input JSON")
    ap.add_argument("--example", action="store_true", help="print an example input")
    ap.add_argument("--widget", action="store_true", help="print today.json for the desktop widget")
    ap.add_argument("--json", action="store_true", help="print the raw result")
    a = ap.parse_args(argv)
    if a.example:
        print(json.dumps(EXAMPLE, indent=2, ensure_ascii=False))
        return 0
    if not a.input:
        ap.error("give an input file, or --example")
    try:
        with open(a.input, encoding="utf-8") as fh:
            spec = json.load(fh)
        result = plan(spec)
    except (OSError, ValueError, KeyError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if a.widget:
        print(json.dumps(widget_feed(spec, result), indent=2, ensure_ascii=False))
        return 0
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    when = date.fromisoformat(spec["date"]).strftime("%a %d %b %Y") if spec.get("date") else "Today"
    print(f"{when}: {_hm(result['focus_minutes'])} of focus in {result['sessions']} sessions")
    for b in result["blocks"]:
        step = f"  → {b['first_step']}" if b.get("first_step") and b["first_step"] != "Pick up where you left off" else ""
        print(f"{clock(b['start'])}-{clock(b['end'])}  {ICONS.get(b['kind'], '•')} {b['title']}{step}")
    for c in result["clashes"]:
        print(f"⚠️ Clash: {c}")
    if result["unscheduled"]:
        print("Didn't fit (tomorrow, or drop it): "
              + "; ".join(f"{t['title']} ({t['minutes']} min)" for t in result["unscheduled"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

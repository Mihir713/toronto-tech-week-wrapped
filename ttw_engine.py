"""TTW Wrapped — Event data and stats engine"""
import json, os
from datetime import datetime
from collections import Counter

EVENTS_DB_PATH = os.path.join(os.path.dirname(__file__), "events.json")

def load_events(path=None):
    path = path or EVENTS_DB_PATH
    with open(path) as f:
        return json.load(f)

def wrapped_stats(attended_ids, events_db=None):
    """
    Core stat generator for TTW Wrapped.
    
    attended_ids: list of event id strings (from events.json — format: ttw-{id})
    events_db: full events JSON as dict (with 'events' key), 
               or None to load automatically from events.json
    
    Returns: dict of wrapped stats
    """
    if events_db is None:
        events_db = load_events()
    
    events = events_db["events"]
    emap = {e["id"]: e for e in events}
    attended = [emap[eid] for eid in attended_ids if eid in emap]

    if not attended:
        return {"error": "no matching events found", "hint": "check event IDs against events.json"}

    # ── connections ──────────────────────────────────────────────────────────
    conn = 0
    for e in attended:
        base = e.get("connections_estimate", 10)
        if e.get("category") == "intimate":
            base = int(base * 1.5)
        if e.get("category") == "summit" and e.get("attendee_count", 0) > 200:
            base = int(base * 0.8)
        conn += base

    # ── steps ────────────────────────────────────────────────────────────────
    steps = sum(e.get("steps_estimate", 1000) for e in attended)

    # ── time spent ─────────────────────────────────────────────────────────
    total_hours = 0.0
    transit_buffer = 0.5  # 30 min avg transit between events
    for e in attended:
        try:
            start = datetime.strptime(e["time_start"], "%H:%M")
            end   = datetime.strptime(e["time_end"],   "%H:%M")
            dur_h = (end - start).seconds / 3600
        except Exception:
            dur_h = e.get("duration_h", 2.0)
        total_hours += dur_h + transit_buffer

    # ── neighborhoods explored ────────────────────────────────────────────
    hoods = list({e.get("neighborhood", "Toronto") for e in attended})

    # ── category breakdown ──────────────────────────────────────────────────
    cats = Counter(e.get("category", "other") for e in attended)
    top_cat = cats.most_common(1)[0][0] if cats else "networking"

    # ── speaker exposure ───────────────────────────────────────────────────
    speakers = []
    for e in attended:
        speakers.extend(e.get("speakers", []))
    unique_speakers = len(set(speakers))

    # ── attendee reach ──────────────────────────────────────────────────
    total_attendees = sum(e.get("attendee_count", 0) for e in attended)

    # ── vibe label ────────────────────────────────────────────────────────
    score = (
        cats.get("summit", 0) * 3 + cats.get("featured", 0) * 3 +
        cats.get("wellness", 0) * 2 + cats.get("outdoor", 0) * 2 +
        cats.get("intimate", 0) * 2 +
        len(cats)
    )
    if score >= 15:
        vibe, emoji = "The Connector", "🔗"
    elif score >= 8:
        vibe, emoji = "The Balanced Builder", "⚖️"
    else:
        vibe, emoji = "The Deep Diver", "🎯"

    # ── time-of-day spread ──────────────────────────────────────────────
    morning   = sum(1 for e in attended if e.get("time_start","12:00") < "12:00")
    afternoon = sum(1 for e in attended if "12:00" <= e.get("time_start","12:00") < "17:00")
    evening   = sum(1 for e in attended if e.get("time_start","12:00") >= "17:00")

    # ── top themes ──────────────────────────────────────────────────────────
    themes = Counter()
    for e in attended:
        themes.update(e.get("theme", []))
        themes.update(e.get("tags", []))
    top_themes = [t for t, _ in themes.most_common(5)]

    return {
        "connections_made":        conn,
        "steps_walked":            steps,
        "hours_at_ttw":             round(total_hours, 1),
        "neighborhoods_explored":  len(hoods),
        "neighborhoods":          hoods,
        "events_attended":         len(attended),
        "unique_speakers_seen":    unique_speakers,
        "top_category":             top_cat,
        "top_themes":              top_themes,
        "vibe_label":              vibe,
        "vibe_emoji":              emoji,
        "morning_events":          morning,
        "afternoon_events":        afternoon,
        "evening_events":          evening,
        "total_attendees_reached": total_attendees,
    }


def get_event_by_id(event_id, events_db=None):
    """Get a single event by its id."""
    if events_db is None:
        events_db = load_events()
    emap = {e["id"]: e for e in events_db["events"]}
    return emap.get(event_id)

def list_events(events_db=None, category=None, date=None):
    """List events, optionally filtered."""
    if events_db is None:
        events_db = load_events()
    events = events_db["events"]
    if category:
        events = [e for e in events if e.get("category") == category]
    if date:
        events = [e for e in events if e.get("date") == date]
    return events

if __name__ == "__main__":
    import sys
    db = load_events()

    ids = sys.argv[1:] if len(sys.argv) > 1 else [
        "ttw-10123",     # Founder Showcase
        "ttw-ttwhomecoming",  # TTW Homecoming
        "ttw-scy9dutq",  # Endeavor CEO Roundtable
    ]
    stats = wrapped_stats(ids, db)
    print(json.dumps(stats, indent=2))

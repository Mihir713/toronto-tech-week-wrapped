#!/usr/bin/env python3
"""Convert events.json → events.js for file:// loading without CORS issues."""

import json
import re
import sys
from pathlib import Path

def clean_event(e):
    """Strip down to what the visualizer needs, fix garbled data."""
    title = (e.get('title') or '').strip()
    # Remove repeated title patterns from PDF scraping artifacts
    if title.count(title[:20]) > 1:
        title = title[:title.find(title[10:], 20)] if title.find(title[10:], 20) > 0 else title
    
    neighborhood = (e.get('neighborhood') or e.get('venue') or '').strip()
    # Filter out scraped timestamps that leaked into neighborhood
    if re.match(r'\d{4}-\d{2}-\d{2}', neighborhood):
        neighborhood = 'OTHER'
    
    return {
        'i': e.get('id', ''),
        'n': title,
        'c': (e.get('category') or 'networking').strip(),
        'h': neighborhood,
        'o': e.get('connections_estimate', 15) or 15,
        's': e.get('steps_estimate', 1000) or 1000,
        'd': (e.get('date') or '').strip(),
        't': ((e.get('time_start') or '12:00').replace('AM','').replace('PM','').strip()),
        'e': ((e.get('time_end') or '13:00').replace('AM','').replace('PM','').strip()),
        'desc': (e.get('description') or '').strip()[:200],
        'lu': (e.get('luma_url') or '').strip(),
        'img': (e.get('image_url') or '').strip(),
    }

def main():
    events_path = Path(__file__).parent / 'events.json'
    output_path = Path(__file__).parent / 'events.js'
    
    print(f"Loading {events_path}...")
    with open(events_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    raw = data.get('events', [])
    cleaned = [clean_event(e) for e in raw]
    
    # Remove obvious duplicates (same title, same date)
    seen = set()
    deduped = []
    for e in cleaned:
        key = (e['n'][:40], e['d'])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    
    # Stats
    cats = {}
    hoods = set()
    total_conn = 0
    with_img = 0
    with_luma = 0
    for e in deduped:
        cats[e['c']] = cats.get(e['c'], 0) + 1
        if e['h']: hoods.add(e['h'])
        total_conn += e['o']
        if e['img']: with_img += 1
        if e['lu']: with_luma += 1
    
    print(f"  Raw events: {len(raw)}")
    print(f"  After dedup: {len(deduped)}")
    print(f"  Categories: {dict(sorted(cats.items()))}")
    print(f"  Neighborhoods: {len(hoods)}")
    print(f"  Avg connections/event: {total_conn/len(deduped):.0f}")
    print(f"  With images: {with_img}")
    print(f"  With Luma URLs: {with_luma}")
    
    # Write as JS
    js = f"// Auto-generated from events.json — {len(deduped)} events\n"
    js += f"// Categories: {sorted(cats.keys())}\n"
    js += f"// Neighborhoods: {len(hoods)}\n"
    js += f"window.TTW_EVENTS = {json.dumps(deduped, ensure_ascii=False)};\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js)
    
    size_kb = output_path.stat().st_size / 1024
    print(f"\nWrote {output_path} ({size_kb:.0f} KB)")
    print("Done!")

if __name__ == '__main__':
    main()

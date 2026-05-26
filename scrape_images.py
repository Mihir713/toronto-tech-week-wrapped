#!/usr/bin/env python3
"""
Image scraper for Toronto Tech Week events.
Tries multiple sources to find images for events without them.

Strategy (in order):
1. Unsplash API — fast, free (50 req/hr on free tier)
2. Google Custom Search — finds Luma event pages
3. Direct Luma URL guess from event title

Usage:
  python3 scrape_images.py                    # Process ALL events, 1 req/sec
  python3 scrape_images.py --limit 20          # Process first 20
  python3 scrape_images.py --unsplash-key KEY  # Use Unsplash API
  python3 scrape_images.py --google-key KEY --google-cx CX  # Use Google CSE
  python3 scrape_images.py --dry-run           # Just show what would be scraped

Output: events_with_images.json (same format, with image_url populated)
"""

import json
import time
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional
import os

# ═══════════ CONFIG ═══════════
UNSPLASH_KEY = os.environ.get('UNSPLASH_KEY', '')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
GOOGLE_CX = os.environ.get('GOOGLE_CX', '')
RATE_LIMIT_SEC = 1.5  # seconds between requests
BATCH_SIZE = 50       # save progress every N events
MAX_RESULTS = 500     # max events to process in one run if no --limit

# ═══════════ IMAGE SOURCES ═══════════

def unsplash_search(query: str) -> Optional[str]:
    """Search Unsplash for a relevant image."""
    if not UNSPLASH_KEY:
        return None
    try:
        params = urllib.parse.urlencode({
            'query': query,
            'per_page': 1,
            'orientation': 'landscape',
            'client_id': UNSPLASH_KEY
        })
        url = f'https://api.unsplash.com/search/photos?{params}'
        req = urllib.request.Request(url, headers={'Accept-Version': 'v1'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        results = data.get('results', [])
        if results:
            return results[0]['urls'].get('small', results[0]['urls'].get('regular', ''))
    except Exception as e:
        print(f"  Unsplash error: {e}")
    return None


def google_image_search(query: str) -> Optional[str]:
    """Use Google Custom Search to find event images."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return None
    try:
        params = urllib.parse.urlencode({
            'q': query,
            'cx': GOOGLE_CX,
            'key': GOOGLE_API_KEY,
            'searchType': 'image',
            'num': 1,
            'imgSize': 'medium',
        })
        url = f'https://www.googleapis.com/customsearch/v1?{params}'
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        items = data.get('items', [])
        if items:
            return items[0].get('link', '')
    except Exception as e:
        print(f"  Google error: {e}")
    return None


def guess_luma_url(title: str) -> Optional[str]:
    """Try to guess a Luma event URL from the title."""
    # Luma URLs follow patterns like:
    # https://lu.ma/event-slug
    # We can't easily guess slugs, but we can search Luma
    return None  # Would need Luma API access


# ═══════════ QUERY BUILDING ═══════════
EVENT_CATEGORY_KEYWORDS = {
    'networking': 'tech networking event conference',
    'workshop': 'tech workshop hands-on session',
    'pitch': 'startup pitch competition demo day',
    'social': 'networking mixer social event',
    'outdoor': 'outdoor walk park toronto',
    'hackathon': 'hackathon coding competition',
    'featured': 'tech conference keynote stage',
    'wellness': 'yoga meditation wellness session',
}

def build_query(event: dict) -> str:
    """Build a search query for an event."""
    title = event.get('title', '') or event.get('n', '')
    # Extract key company/org names
    companies = re.findall(r'\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,}){0,2})\b', title)
    company_str = ' '.join(companies[:2]) if companies else ''
    
    # Use category-specific keywords
    cat = (event.get('category') or event.get('c') or 'networking').lower()
    cat_kw = EVENT_CATEGORY_KEYWORDS.get(cat, 'tech event')
    
    query = f"{title[:80]} {company_str} {cat_kw} Toronto"
    return query[:200]


# ═══════════ MAIN ═══════════

def load_events(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('events', [])


def save_events(events: list, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'event_week': 'May 25-30, 2026',
            'sources': ['torontotechweek.com PDF', 'Unsplash API', 'Google CSE'],
            'scraped_at': time.strftime('%Y-%m-%d'),
            'total_events': len(events),
            'events': events
        }, f, indent=2, ensure_ascii=False)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Scrape event images')
    parser.add_argument('--limit', type=int, default=0, help='Max events to process')
    parser.add_argument('--unsplash-key', type=str, default='', help='Unsplash API key')
    parser.add_argument('--google-key', type=str, default='', help='Google API key')
    parser.add_argument('--google-cx', type=str, default='', help='Google CX ID')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be scraped')
    parser.add_argument('--input', type=str, default='events.json', help='Input file')
    parser.add_argument('--output', type=str, default='events_with_images.json', help='Output file')
    parser.add_argument('--force', action='store_true', help='Re-scrape events that already have images')
    args = parser.parse_args()
    
    global UNSPLASH_KEY, GOOGLE_API_KEY, GOOGLE_CX
    UNSPLASH_KEY = args.unsplash_key or UNSPLASH_KEY
    GOOGLE_API_KEY = args.google_key or GOOGLE_API_KEY
    GOOGLE_CX = args.google_cx or GOOGLE_CX
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    print(f"Loading {input_path}...")
    events = load_events(input_path)
    
    # Filter: events without images (or all if --force)
    if args.force:
        targets = events
        print(f"  Forcing re-scrape of all {len(targets)} events")
    else:
        targets = [e for e in events if not (e.get('image_url') or e.get('img'))]
        print(f"  {len(targets)}/{len(events)} events need images")
    
    if args.limit:
        targets = targets[:args.limit]
        print(f"  Limited to {len(targets)} events")
    
    if args.dry_run:
        print(f"\nWould scrape {len(targets)} events:")
        for e in targets[:10]:
            q = build_query(e)
            print(f"  • {e.get('title','?')[:60]}")
            print(f"    Query: {q[:100]}")
        return
    
    if not UNSPLASH_KEY and not GOOGLE_API_KEY:
        print("\n⚠️  No API keys provided!")
        print("   Set UNSPLASH_KEY env var or pass --unsplash-key")
        print("   Free Unsplash key: https://unsplash.com/developers")
        print("   Running in dry-run mode to show queries...\n")
        for e in targets[:5]:
            print(f"  Query: {build_query(e)[:120]}")
        return
    
    print(f"\nScraping {len(targets)} events (rate: {RATE_LIMIT_SEC}s between requests)...")
    print(f"  Sources: {'Unsplash ' if UNSPLASH_KEY else ''}{'Google CSE' if GOOGLE_API_KEY else ''}")
    print()
    
    found = 0
    for i, event in enumerate(targets):
        title = (event.get('title') or event.get('n') or '')[:60]
        query = build_query(event)
        
        image_url = None
        source = ''
        
        # Try Unsplash first (free, reliable)
        if UNSPLASH_KEY:
            image_url = unsplash_search(query)
            if image_url:
                source = 'unsplash'
        
        # Try Google if Unsplash failed
        if not image_url and GOOGLE_API_KEY:
            image_url = google_image_search(query[:150])
            if image_url:
                source = 'google'
        
        # Update event
        if image_url:
            event['image_url'] = image_url
            event['image_source'] = source
            found += 1
        
        status = '✓' if image_url else '✗'
        print(f"  [{i+1}/{len(targets)}] {status} {title}")
        
        # Save progress periodically
        if (i + 1) % BATCH_SIZE == 0:
            save_events(events, output_path)
            print(f"  💾 Saved {len(events)} events to {output_path}")
        
        time.sleep(RATE_LIMIT_SEC)
    
    # Final save
    save_events(events, output_path)
    print(f"\n✅ Done! {found}/{len(targets)} events got images")
    print(f"   Output: {output_path}")
    
    # Print stats
    with_img = sum(1 for e in events if e.get('image_url'))
    print(f"   Total events with images: {with_img}/{len(events)}")


if __name__ == '__main__':
    main()

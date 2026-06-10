"""Apply venue neighborhood data from data/venue_neighborhoods.json on startup."""

import json
import os
from typing import Dict, Optional

from database import SessionLocal, Venue, basedir

DATA_PATH = os.path.join(basedir, 'data', 'venue_neighborhoods.json')


def load_neighborhood_data(path: str = DATA_PATH) -> Optional[Dict]:
    if not os.path.isfile(path):
        print(f'Venue neighborhood data not found at {path}; skipping migration.')
        return None

    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)

    venues = payload.get('venues')
    if not isinstance(venues, dict):
        print('Invalid venue neighborhood data: missing "venues" object.')
        return None

    return venues


def apply_neighborhood_mappings(session, venues: Dict, only_empty: bool = True) -> Dict[str, int]:
    stats = {
        'updated': 0,
        'skipped_set': 0,
        'skipped_missing': 0,
    }

    db_venues = session.query(Venue).all()
    by_name = {venue.name: venue for venue in db_venues}

    for name, entry in venues.items():
        venue = by_name.get(name)
        if not venue:
            stats['skipped_missing'] += 1
            continue

        neighborhood = entry.get('neighborhood')
        venue_type = entry.get('venue_type')

        changed = False
        if neighborhood and (not only_empty or not venue.neighborhood):
            if not venue.neighborhood:
                venue.neighborhood = neighborhood
                changed = True
        if venue_type and (not only_empty or not venue.venue_type):
            if not venue.venue_type:
                venue.venue_type = venue_type
                changed = True

        if changed:
            stats['updated'] += 1
        else:
            stats['skipped_set'] += 1

    return stats


def migrate_venue_neighborhoods() -> None:
    venues = load_neighborhood_data()
    if not venues:
        return

    session = SessionLocal()
    try:
        empty_count = session.query(Venue).filter(
            (Venue.neighborhood == None) | (Venue.neighborhood == '')  # noqa: E711
        ).count()
        if empty_count == 0:
            print('All venues already have neighborhoods; skipping neighborhood migration.')
            return

        stats = apply_neighborhood_mappings(session, venues, only_empty=True)
        session.commit()
        print(
            'Venue neighborhood migration: '
            f"{stats['updated']} updated, "
            f"{stats['skipped_set']} already set, "
            f"{stats['skipped_missing']} names not in database."
        )
    except Exception as exc:
        session.rollback()
        print(f'Venue neighborhood migration failed: {exc}')
    finally:
        session.close()


if __name__ == '__main__':
    migrate_venue_neighborhoods()

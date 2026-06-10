"""Extract venue neighborhood mappings from a WordPress SQL dump."""

import csv
import io
import re
from collections import defaultdict
from typing import Dict, Iterator, List, Optional, Set

NEIGHBORHOOD_PAGE_IDS = {
    '24514': 'Eastern Market',
    '24650': 'Midtown',
    '24656': 'Northend',
    '24658': 'Downtown',
    '24660': 'Corktown',
    '24662': 'Southwest',
    '24664': 'Ferndale',
    '24666': 'Hamtramck',
    '33809': 'University District',
    '33821': 'The Villages',
    '37340': 'Grandmont/Rosedale',
}

CANONICAL_NEIGHBORHOODS = frozenset(NEIGHBORHOOD_PAGE_IDS.values())

SECTION_RE = re.compile(
    r'(Coffee|Eat/Drink|Shop|Art/Museums|Parks|Records|Music|Gallery|Theatre|Bar|Restaurant)'
    r'[^\[]*\[list_venues[^\]]*include="([^"]+)"',
    re.IGNORECASE,
)
LIST_VENUES_RE = re.compile(r'\[list_venues[^\]]*include="([^"]+)"')


def parse_sql_values_line(line: str) -> Optional[List[str]]:
    stripped = line.strip()
    if not stripped.startswith('('):
        return None
    if stripped.endswith(','):
        stripped = stripped[:-1]
    if stripped.endswith(');'):
        stripped = stripped[:-2] + ')'
    if not stripped.endswith(')'):
        return None
    inner = stripped[1:-1]
    reader = csv.reader(io.StringIO(inner), delimiter=',', quotechar="'", escapechar='\\')
    try:
        return next(reader)
    except (StopIteration, csv.Error):
        return None


def iter_dump_rows(dump_path: str, table_name: str) -> Iterator[List[str]]:
    insert_marker = f'INSERT INTO `{table_name}` VALUES'
    in_section = False
    with open(dump_path, encoding='utf-8', errors='replace') as handle:
        for line in handle:
            if insert_marker in line:
                in_section = True
                continue
            if not in_section:
                continue
            if line.startswith('UNLOCK TABLES') or 'ENABLE KEYS' in line:
                break
            row = parse_sql_values_line(line)
            if row:
                yield row


def _load_wp_venue_names(dump_path: str, prefix: str) -> Dict[str, str]:
    posts_table = f'{prefix}posts'
    names: Dict[str, str] = {}
    for row in iter_dump_rows(dump_path, posts_table):
        if len(row) <= 20:
            continue
        if row[20] == 'tribe_venue' and row[7] == 'publish':
            names[row[0]] = row[5]
    return names


def _load_venue_cities(dump_path: str, prefix: str, venue_ids: Set[str]) -> Dict[str, str]:
    meta_table = f'{prefix}postmeta'
    cities: Dict[str, str] = {}
    for row in iter_dump_rows(dump_path, meta_table):
        if len(row) < 4:
            continue
        post_id, meta_key, meta_value = row[1], row[2], row[3]
        if post_id in venue_ids and meta_key == '_VenueCity':
            cities[post_id] = (meta_value or '').strip()
    return cities


def _assign_from_guides(
    dump_path: str,
    prefix: str,
    wp_names: Dict[str, str],
    mappings: Dict[str, Dict[str, Optional[str]]],
) -> int:
    posts_table = f'{prefix}posts'
    assigned = 0

    for row in iter_dump_rows(dump_path, posts_table):
        if row[0] not in NEIGHBORHOOD_PAGE_IDS:
            continue
        neighborhood = NEIGHBORHOOD_PAGE_IDS[row[0]]
        content = row[4] or ''
        sections = list(SECTION_RE.finditer(content))

        if sections:
            for match in sections:
                venue_type = match.group(1)
                for wp_id in match.group(2).split(','):
                    wp_id = wp_id.strip()
                    if not wp_id:
                        continue
                    name = wp_names.get(wp_id)
                    if not name or name in mappings:
                        continue
                    mappings[name] = {
                        'neighborhood': neighborhood,
                        'venue_type': venue_type,
                    }
                    assigned += 1
        else:
            for match in LIST_VENUES_RE.finditer(content):
                for wp_id in match.group(1).split(','):
                    wp_id = wp_id.strip()
                    if not wp_id:
                        continue
                    name = wp_names.get(wp_id)
                    if not name or name in mappings:
                        continue
                    mappings[name] = {
                        'neighborhood': neighborhood,
                        'venue_type': None,
                    }
                    assigned += 1

    return assigned


def _assign_from_cities(
    wp_names: Dict[str, str],
    wp_cities: Dict[str, str],
    mappings: Dict[str, Dict[str, Optional[str]]],
) -> int:
    assigned = 0
    name_to_wp_id = {name: wp_id for wp_id, name in wp_names.items()}

    for name, wp_id in name_to_wp_id.items():
        if name in mappings:
            continue
        city = wp_cities.get(wp_id, '')
        if city in CANONICAL_NEIGHBORHOODS:
            mappings[name] = {
                'neighborhood': city,
                'venue_type': None,
            }
            assigned += 1

    return assigned


def extract_neighborhood_mappings(
    dump_path: str,
    prefix: str = 'tdil_',
) -> Dict[str, Dict[str, Optional[str]]]:
    """Return {venue_name: {neighborhood, venue_type}} from a WordPress dump."""
    wp_names = _load_wp_venue_names(dump_path, prefix)
    mappings: Dict[str, Dict[str, Optional[str]]] = {}

    _assign_from_guides(dump_path, prefix, wp_names, mappings)
    wp_cities = _load_venue_cities(dump_path, prefix, set(wp_names.keys()))
    _assign_from_cities(wp_names, wp_cities, mappings)

    return mappings


def summarize_by_neighborhood(
    mappings: Dict[str, Dict[str, Optional[str]]],
) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for entry in mappings.values():
        counts[entry['neighborhood']] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

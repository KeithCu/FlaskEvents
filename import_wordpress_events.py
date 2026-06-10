#!/usr/bin/env python3
"""Import venues and events from a WordPress / The Events Calendar database dump."""

import argparse
import csv
import io
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import unescape
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

import phpserialize
import pytz
from sqlalchemy import text

from database import Base, Event, Venue, engine, get_next_event_ids, migrate_database, SessionLocal
from fts import setup_fts_triggers

DEFAULT_TIMEZONE = 'America/Detroit'
DEFAULT_COLOR = '#3788d8'
SITE_URL = 'https://thedetroitilove.com'
UNKNOWN_VENUE = 'Unknown Venue'
VIRTUAL_VENUE_NAMES = {'virtual detroit'}

VENUE_META_KEYS = {
    '_VenueAddress', '_VenueCity', '_VenueState', '_VenueZip', '_VenueCountry',
    '_VenuePhone', '_VenueURL', '_thumbnail_id', '_yoast_wpseo_opengraph-image',
}
EVENT_META_KEYS = {
    '_EventStartDate', '_EventEndDate', '_EventVenueID', '_EventURL',
    '_EventRecurrence', '_EventTimezone', '_EventAllDay',
}
TEC_WEEKDAYS = {1: 'MO', 2: 'TU', 3: 'WE', 4: 'TH', 5: 'FR', 6: 'SA', 7: 'SU'}


@dataclass
class WPPost:
    post_id: str
    post_title: str
    post_content: str
    post_excerpt: str
    post_status: str
    post_parent: str
    guid: str
    post_type: str
    post_mime_type: str


@dataclass
class ImportStats:
    venues_imported: int = 0
    venues_with_image: int = 0
    venues_without_image: int = 0
    events_imported: int = 0
    events_recurring: int = 0
    events_one_time: int = 0
    events_skipped: int = 0
    titles_truncated: int = 0
    recurrence_warnings: int = 0
    skip_reasons: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


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


def post_from_row(row: List[str]) -> WPPost:
    return WPPost(
        post_id=row[0],
        post_title=row[5],
        post_content=row[4],
        post_excerpt=row[6],
        post_status=row[7],
        post_parent=row[17],
        guid=row[18],
        post_type=row[20],
        post_mime_type=row[21] if len(row) > 21 else '',
    )


def strip_html(value: str) -> str:
    if not value:
        return ''
    text_value = re.sub(r'<[^>]+>', ' ', value)
    text_value = unescape(text_value)
    text_value = re.sub(r'\s+', ' ', text_value).strip()
    return text_value


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def normalize_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith('//'):
        value = 'https:' + value
    elif not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', value):
        value = 'https://' + value
    if value.startswith('http://'):
        value = 'https://' + value[7:]
    return truncate(value, 500)


def build_address(meta: Dict[str, str]) -> Optional[str]:
    street = meta.get('_VenueAddress', '').strip()
    city = meta.get('_VenueCity', '').strip()
    state = meta.get('_VenueState', '').strip() or meta.get('_VenueStateProvince', '').strip()
    zip_code = meta.get('_VenueZip', '').strip()
    country = meta.get('_VenueCountry', '').strip()

    parts = []
    if street:
        parts.append(street)
    city_line = ', '.join(p for p in (city, state) if p)
    if zip_code:
        city_line = f'{city_line} {zip_code}'.strip() if city_line else zip_code
    if city_line:
        parts.append(city_line)
    if country and country.lower() not in ('united states', 'usa', 'us'):
        parts.append(country)
    return '\n'.join(parts) if parts else None


def resolve_venue_image(
    venue_id: str,
    meta: Dict[str, str],
    attachments_by_id: Dict[str, WPPost],
    child_attachments: Dict[str, WPPost],
) -> Optional[str]:
    thumb_id = meta.get('_thumbnail_id', '').strip()
    if thumb_id and thumb_id in attachments_by_id:
        url = normalize_url(attachments_by_id[thumb_id].guid)
        if url:
            return url

    child = child_attachments.get(venue_id)
    if child:
        url = normalize_url(child.guid)
        if url:
            return url

    og_image = meta.get('_yoast_wpseo_opengraph-image', '').strip()
    return normalize_url(og_image)


def parse_php_recurrence(raw: str) -> Optional[dict]:
    if not raw:
        return None
    try:
        data = phpserialize.loads(raw.encode('utf-8'), decode_strings=True)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def tec_days_to_byday(rule: dict) -> List[str]:
    custom = rule.get('custom') or {}
    week = custom.get('week') or {}
    days = week.get('day') or []
    if isinstance(days, (str, int)):
        days = [days]
    byday = []
    for day in days:
        try:
            token = TEC_WEEKDAYS.get(int(day))
        except (TypeError, ValueError):
            token = None
        if token:
            byday.append(token)
    return byday


def parse_end_date(rule: dict) -> Optional[date]:
    end_type = rule.get('end-type') or rule.get('end_type')
    end_value = rule.get('end')
    if end_type in ('On', 'After') and end_value:
        if isinstance(end_value, date):
            return end_value
        try:
            return datetime.strptime(str(end_value)[:10], '%Y-%m-%d').date()
        except ValueError:
            return None
    return None


def recurrence_to_rrule(recurrence_raw: str, stats: ImportStats) -> Tuple[Optional[str], Optional[date], bool]:
    """Return (rrule, recurring_until, is_recurring)."""
    data = parse_php_recurrence(recurrence_raw)
    if not data:
        return None, None, False

    rules = data.get('rules') or []
    if isinstance(rules, dict):
        rules = list(rules.values())
    exclusions = data.get('exclusions') or []
    if isinstance(exclusions, dict):
        exclusions = list(exclusions.values())

    if not rules:
        if exclusions:
            stats.recurrence_warnings += 1
        return None, None, False

    if len(rules) > 1 or any(
        isinstance(rule, dict) and (rule.get('custom') or {}).get('type') == 'Date'
        for rule in rules
    ):
        stats.recurrence_warnings += 1
        return None, None, False

    rule = rules[0]
    if not isinstance(rule, dict):
        stats.recurrence_warnings += 1
        return None, None, False
    custom = rule.get('custom') or {}
    rule_type = custom.get('type') or rule.get('type')
    interval = custom.get('interval') or rule.get('interval') or 1
    try:
        interval = max(1, int(interval))
    except (TypeError, ValueError):
        interval = 1

    parts = []
    recurring_until = parse_end_date(rule)

    if rule_type == 'Weekly':
        parts.append('FREQ=WEEKLY')
        parts.append(f'INTERVAL={interval}')
        byday = tec_days_to_byday(rule)
        if byday:
            parts.append('BYDAY=' + ','.join(byday))
    elif rule_type == 'Daily':
        parts.append('FREQ=DAILY')
        parts.append(f'INTERVAL={interval}')
    elif rule_type == 'Monthly':
        parts.append('FREQ=MONTHLY')
        parts.append(f'INTERVAL={interval}')
        month = custom.get('month') or {}
        day = month.get('day')
        if day:
            try:
                parts.append(f'BYMONTHDAY={int(day)}')
            except (TypeError, ValueError):
                pass
    elif rule_type == 'Yearly':
        parts.append('FREQ=YEARLY')
        parts.append(f'INTERVAL={interval}')
    else:
        stats.recurrence_warnings += 1
        return None, None, False

    return ';'.join(parts), recurring_until, True


def parse_event_datetime(value: str, tz_name: str) -> Optional[datetime]:
    if not value or value.startswith('0000'):
        return None
    tz = pytz.timezone(tz_name or DEFAULT_TIMEZONE)
    for fmt in ('%Y-%m-%d %H:%M:%S',):
        try:
            naive = datetime.strptime(value, fmt)
            return tz.localize(naive)
        except ValueError:
            continue
    return None


@dataclass
class ExtractedData:
    venues: Dict[str, WPPost]
    events: Dict[str, WPPost]
    postmeta: Dict[str, Dict[str, str]]
    event_categories: Dict[str, List[str]]
    attachments_by_id: Dict[str, WPPost]
    child_attachments: Dict[str, WPPost]


def extract_from_dump(dump_path: str, prefix: str) -> ExtractedData:
    posts_table = f'{prefix}posts'
    meta_table = f'{prefix}postmeta'
    terms_table = f'{prefix}terms'
    taxonomy_table = f'{prefix}term_taxonomy'
    relationships_table = f'{prefix}term_relationships'

    venues: Dict[str, WPPost] = {}
    events: Dict[str, WPPost] = {}
    all_posts_by_id: Dict[str, WPPost] = {}

    for row in iter_dump_rows(dump_path, posts_table):
        post = post_from_row(row)
        all_posts_by_id[post.post_id] = post
        if post.post_type == 'tribe_venue' and post.post_status == 'publish':
            venues[post.post_id] = post
        elif (
            post.post_type == 'tribe_events'
            and post.post_status == 'publish'
            and post.post_parent == '0'
        ):
            events[post.post_id] = post

    relevant_ids: Set[str] = set(venues.keys()) | set(events.keys())
    postmeta: Dict[str, Dict[str, str]] = defaultdict(dict)

    for row in iter_dump_rows(dump_path, meta_table):
        if len(row) < 4:
            continue
        post_id, meta_key, meta_value = row[1], row[2], row[3]
        if post_id not in relevant_ids:
            continue
        if post_id in venues and meta_key in VENUE_META_KEYS:
            postmeta[post_id][meta_key] = meta_value
        elif post_id in events and meta_key in EVENT_META_KEYS:
            postmeta[post_id][meta_key] = meta_value
        if post_id in venues and meta_key == '_thumbnail_id' and meta_value:
            relevant_ids.add(meta_value)

    attachments_by_id: Dict[str, WPPost] = {}
    child_attachments: Dict[str, WPPost] = {}
    for post_id, post in all_posts_by_id.items():
        if post.post_type != 'attachment':
            continue
        if post_id in relevant_ids:
            attachments_by_id[post_id] = post
        if (
            post.post_parent in venues
            and post.post_mime_type.startswith('image/')
            and post.post_parent not in child_attachments
        ):
            child_attachments[post.post_parent] = post

    term_names: Dict[str, str] = {}
    for row in iter_dump_rows(dump_path, terms_table):
        if len(row) >= 2:
            term_names[row[0]] = row[1]

    event_cat_taxonomy_ids: Set[str] = set()
    term_id_by_taxonomy_id: Dict[str, str] = {}
    for row in iter_dump_rows(dump_path, taxonomy_table):
        if len(row) >= 3 and row[2] == 'tribe_events_cat':
            event_cat_taxonomy_ids.add(row[0])
            term_id_by_taxonomy_id[row[0]] = row[1]

    event_categories: Dict[str, List[str]] = defaultdict(list)
    for row in iter_dump_rows(dump_path, relationships_table):
        if len(row) < 2:
            continue
        object_id, term_taxonomy_id = row[0], row[1]
        if object_id not in events or term_taxonomy_id not in event_cat_taxonomy_ids:
            continue
        term_id = term_id_by_taxonomy_id.get(term_taxonomy_id)
        if term_id and term_id in term_names:
            event_categories[object_id].append(term_names[term_id])

    return ExtractedData(
        venues=venues,
        events=events,
        postmeta=dict(postmeta),
        event_categories=dict(event_categories),
        attachments_by_id=attachments_by_id,
        child_attachments=child_attachments,
    )


def extract_from_mariadb(
    host: str,
    user: str,
    password: str,
    database: str,
    prefix: str,
    port: int = 3306,
) -> ExtractedData:
    import pymysql

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
    posts_table = f'{prefix}posts'
    meta_table = f'{prefix}postmeta'

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT ID, post_title, post_content, post_excerpt, post_status,
                       post_parent, guid, post_type, post_mime_type
                FROM `{posts_table}`
                WHERE post_type IN ('tribe_venue', 'tribe_events', 'attachment')
                  AND post_status = 'publish'
                """
            )
            rows = cursor.fetchall()

        venues: Dict[str, WPPost] = {}
        events: Dict[str, WPPost] = {}
        all_posts_by_id: Dict[str, WPPost] = {}
        for row in rows:
            post = WPPost(
                post_id=str(row['ID']),
                post_title=row['post_title'] or '',
                post_content=row['post_content'] or '',
                post_excerpt=row['post_excerpt'] or '',
                post_status=row['post_status'] or '',
                post_parent=str(row['post_parent'] or '0'),
                guid=row['guid'] or '',
                post_type=row['post_type'] or '',
                post_mime_type=row['post_mime_type'] or '',
            )
            all_posts_by_id[post.post_id] = post
            if post.post_type == 'tribe_venue':
                venues[post.post_id] = post
            elif post.post_type == 'tribe_events' and post.post_parent == '0':
                events[post.post_id] = post

        relevant_ids = set(venues.keys()) | set(events.keys())
        if not relevant_ids:
            return ExtractedData({}, {}, {}, {}, {}, {})

        placeholders = ','.join(['%s'] * len(relevant_ids))
        venue_keys = tuple(VENUE_META_KEYS)
        event_keys = tuple(EVENT_META_KEYS)
        all_keys = venue_keys + event_keys

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT post_id, meta_key, meta_value
                FROM `{meta_table}`
                WHERE post_id IN ({placeholders})
                  AND meta_key IN ({','.join(['%s'] * len(all_keys))})
                """,
                tuple(relevant_ids) + all_keys,
            )
            meta_rows = cursor.fetchall()

        postmeta: Dict[str, Dict[str, str]] = defaultdict(dict)
        for row in meta_rows:
            post_id = str(row['post_id'])
            meta_key = row['meta_key']
            meta_value = row['meta_value'] or ''
            if post_id in venues and meta_key in VENUE_META_KEYS:
                postmeta[post_id][meta_key] = meta_value
            elif post_id in events and meta_key in EVENT_META_KEYS:
                postmeta[post_id][meta_key] = meta_value
            if post_id in venues and meta_key == '_thumbnail_id' and meta_value:
                relevant_ids.add(str(meta_value))

        attachment_ids = [pid for pid in relevant_ids if pid not in venues and pid not in events]
        if attachment_ids:
            with connection.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(attachment_ids))
                cursor.execute(
                    f"""
                    SELECT ID, post_title, post_content, post_excerpt, post_status,
                           post_parent, guid, post_type, post_mime_type
                    FROM `{posts_table}`
                    WHERE ID IN ({placeholders}) AND post_type = 'attachment'
                    """,
                    tuple(attachment_ids),
                )
                for row in cursor.fetchall():
                    post = WPPost(
                        post_id=str(row['ID']),
                        post_title=row['post_title'] or '',
                        post_content=row['post_content'] or '',
                        post_excerpt=row['post_excerpt'] or '',
                        post_status=row['post_status'] or '',
                        post_parent=str(row['post_parent'] or '0'),
                        guid=row['guid'] or '',
                        post_type=row['post_type'] or '',
                        post_mime_type=row['post_mime_type'] or '',
                    )
                    all_posts_by_id[post.post_id] = post

        attachments_by_id = {
            pid: post for pid, post in all_posts_by_id.items() if post.post_type == 'attachment'
        }
        child_attachments = {
            post.post_parent: post
            for post in attachments_by_id.values()
            if post.post_parent in venues and post.post_mime_type.startswith('image/')
        }

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT tr.object_id, t.name
                FROM `{prefix}term_relationships` tr
                JOIN `{prefix}term_taxonomy` tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
                JOIN `{prefix}terms` t ON t.term_id = tt.term_id
                WHERE tt.taxonomy = 'tribe_events_cat'
                """
            )
            category_rows = cursor.fetchall()

        event_categories: Dict[str, List[str]] = defaultdict(list)
        for row in category_rows:
            object_id = str(row['object_id'])
            if object_id in events:
                event_categories[object_id].append(row['name'])

        return ExtractedData(
            venues=venues,
            events=events,
            postmeta=dict(postmeta),
            event_categories=dict(event_categories),
            attachments_by_id=attachments_by_id,
            child_attachments=child_attachments,
        )
    finally:
        connection.close()


def build_venue_records(data: ExtractedData, stats: ImportStats) -> Tuple[List[dict], Dict[str, str]]:
    records = []
    wp_to_name: Dict[str, str] = {}

    for post_id, post in data.venues.items():
        meta = data.postmeta.get(post_id, {})
        name = post.post_title.strip() or f'Venue {post_id}'
        if len(name) > 100:
            stats.titles_truncated += 1
            name = truncate(name, 100)

        image_url = resolve_venue_image(
            post_id, meta, data.attachments_by_id, data.child_attachments
        )
        if image_url:
            stats.venues_with_image += 1
        else:
            stats.venues_without_image += 1

        records.append({
            'wp_id': post_id,
            'name': name,
            'address': build_address(meta),
            'description': strip_html(post.post_content) or None,
            'phone': truncate(meta.get('_VenuePhone', '').strip(), 50) or None,
            'website': normalize_url(meta.get('_VenueURL')),
            'image_url': image_url,
        })
        wp_to_name[post_id] = name

    return records, wp_to_name


def build_event_records(
    data: ExtractedData,
    wp_to_name: Dict[str, str],
    stats: ImportStats,
) -> List[dict]:
    records = []

    for post_id, post in data.events.items():
        meta = data.postmeta.get(post_id, {})
        start_raw = meta.get('_EventStartDate', '').strip()
        end_raw = meta.get('_EventEndDate', '').strip()
        tz_name = meta.get('_EventTimezone', DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE

        start = parse_event_datetime(start_raw, tz_name)
        end = parse_event_datetime(end_raw, tz_name)
        if not start or not end:
            stats.events_skipped += 1
            stats.skip_reasons['missing_dates'] += 1
            continue
        if end <= start:
            end = start + timedelta(hours=1)

        title = post.post_title.strip() or f'Event {post_id}'
        if len(title) > 100:
            stats.titles_truncated += 1
            title = truncate(title, 100)

        description = strip_html(post.post_content) or strip_html(post.post_excerpt) or None
        venue_wp_id = meta.get('_EventVenueID', '').strip()
        venue_name = wp_to_name.get(venue_wp_id, UNKNOWN_VENUE)

        rrule, recurring_until, is_recurring = recurrence_to_rrule(
            meta.get('_EventRecurrence', ''), stats
        )
        if is_recurring and not recurring_until:
            recurring_until = start.date() + timedelta(days=730)

        categories = data.event_categories.get(post_id, [])
        is_virtual = venue_name.strip().lower() in VIRTUAL_VENUE_NAMES

        records.append({
            'title': title,
            'description': description,
            'start': start,
            'end': end,
            'venue_name': venue_name,
            'url': normalize_url(meta.get('_EventURL')),
            'categories': ','.join(categories),
            'rrule': rrule,
            'is_recurring': is_recurring,
            'recurring_until': recurring_until,
            'is_virtual': is_virtual,
            'is_hybrid': False,
            'color': DEFAULT_COLOR,
            'bg': DEFAULT_COLOR,
        })

        if is_recurring:
            stats.events_recurring += 1
        else:
            stats.events_one_time += 1

    return records


def print_summary(stats: ImportStats, dry_run: bool) -> None:
    mode = 'DRY RUN' if dry_run else 'IMPORT'
    print(f'\n=== {mode} SUMMARY ===')
    print(f'Venues: {stats.venues_imported} ({stats.venues_with_image} with image, '
          f'{stats.venues_without_image} without)')
    print(f'Events: {stats.events_imported} imported '
          f'({stats.events_recurring} recurring, {stats.events_one_time} one-time)')
    print(f'Events skipped: {stats.events_skipped}')
    if stats.skip_reasons:
        for reason, count in sorted(stats.skip_reasons.items()):
            print(f'  - {reason}: {count}')
    if stats.titles_truncated:
        print(f'Titles/names truncated: {stats.titles_truncated}')
    if stats.recurrence_warnings:
        print(f'Recurrence conversion warnings: {stats.recurrence_warnings}')


def import_data(data: ExtractedData, dry_run: bool = False) -> ImportStats:
    stats = ImportStats()
    venue_records, wp_to_name = build_venue_records(data, stats)
    event_records = build_event_records(data, wp_to_name, stats)

    stats.venues_imported = len(venue_records)
    stats.events_imported = len(event_records)

    if dry_run:
        return stats

    Base.metadata.create_all(engine)
    migrate_database()

    session = SessionLocal()
    try:
        session.execute(text('DELETE FROM event'))
        session.execute(text('DELETE FROM venue'))
        session.commit()

        venue_id_by_name: Dict[str, int] = {}
        for record in venue_records:
            venue = Venue(
                name=record['name'],
                address=record['address'],
                description=record['description'],
                phone=record['phone'],
                website=record['website'],
                image_url=record['image_url'],
            )
            session.add(venue)
            session.flush()
            venue_id_by_name[record['name']] = venue.id

        if UNKNOWN_VENUE not in venue_id_by_name:
            unknown = Venue(name=UNKNOWN_VENUE)
            session.add(unknown)
            session.flush()
            venue_id_by_name[UNKNOWN_VENUE] = unknown.id
            stats.venues_imported += 1
            stats.venues_without_image += 1

        session.commit()

        batch: List[Event] = []
        batch_size = 1000
        for record in event_records:
            venue_id = venue_id_by_name.get(record['venue_name'], venue_id_by_name[UNKNOWN_VENUE])
            event = Event(
                title=record['title'],
                description=record['description'],
                start=record['start'],
                end=record['end'],
                venue_id=venue_id,
                url=record['url'],
                categories=record['categories'],
                rrule=record['rrule'],
                is_recurring=record['is_recurring'],
                recurring_until=record['recurring_until'],
                is_virtual=record['is_virtual'],
                is_hybrid=record['is_hybrid'],
                color=record['color'],
                bg=record['bg'],
            )
            batch.append(event)

            if len(batch) >= batch_size:
                get_next_event_ids(session, batch)
                session.bulk_save_objects(batch)
                session.commit()
                batch = []

        if batch:
            get_next_event_ids(session, batch)
            session.bulk_save_objects(batch)
            session.commit()

        setup_fts_triggers()
        return stats
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Import WordPress / The Events Calendar venues and events into Flask Events.'
    )
    parser.add_argument(
        '--dump',
        default='db-6-08-26.log',
        help='Path to MariaDB SQL dump (default: db-6-08-26.log)',
    )
    parser.add_argument('--prefix', default='tdil_', help='WordPress table prefix (default: tdil_)')
    parser.add_argument('--dry-run', action='store_true', help='Parse and report counts without writing')

    mariadb = parser.add_argument_group('MariaDB source (optional alternative to --dump)')
    mariadb.add_argument('--mariadb-host', help='MariaDB host')
    mariadb.add_argument('--mariadb-port', type=int, default=3306, help='MariaDB port')
    mariadb.add_argument('--mariadb-user', help='MariaDB user')
    mariadb.add_argument('--mariadb-password', default='', help='MariaDB password')
    mariadb.add_argument('--mariadb-database', help='MariaDB database name')
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mariadb_host:
        if not args.mariadb_user or not args.mariadb_database:
            parser.error('--mariadb-user and --mariadb-database are required with --mariadb-host')
        print(f'Extracting from MariaDB {args.mariadb_database}...')
        data = extract_from_mariadb(
            host=args.mariadb_host,
            user=args.mariadb_user,
            password=args.mariadb_password,
            database=args.mariadb_database,
            prefix=args.prefix,
            port=args.mariadb_port,
        )
    else:
        print(f'Extracting from dump {args.dump}...')
        data = extract_from_dump(args.dump, args.prefix)

    print(f'Found {len(data.venues)} venues and {len(data.events)} parent events in source.')
    stats = import_data(data, dry_run=args.dry_run)
    print_summary(stats, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Generate data/venue_neighborhoods.json from a WordPress SQL dump (dev-only)."""

import argparse
import json
import os
import sys

from venue_neighborhood_extract import extract_neighborhood_mappings, summarize_by_neighborhood

DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'venue_neighborhoods.json')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Extract venue neighborhoods from a WordPress dump into JSON.',
    )
    parser.add_argument('dump_path', help='Path to WordPress MariaDB dump (.log/.sql)')
    parser.add_argument(
        '--output', '-o',
        default=DEFAULT_OUTPUT,
        help=f'Output JSON path (default: {DEFAULT_OUTPUT})',
    )
    parser.add_argument(
        '--prefix',
        default='tdil_',
        help='WordPress table prefix (default: tdil_)',
    )
    args = parser.parse_args()

    if not os.path.isfile(args.dump_path):
        print(f'Error: dump not found: {args.dump_path}', file=sys.stderr)
        return 1

    print(f'Extracting from {args.dump_path}...')
    mappings = extract_neighborhood_mappings(args.dump_path, prefix=args.prefix)

    payload = {
        'generated_from': os.path.basename(args.dump_path),
        'venue_count': len(mappings),
        'venues': mappings,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write('\n')

    print(f'Wrote {len(mappings)} venues to {args.output}')
    print('By neighborhood:')
    for neighborhood, count in summarize_by_neighborhood(mappings).items():
        print(f'  {neighborhood}: {count}')

    return 0


if __name__ == '__main__':
    sys.exit(main())

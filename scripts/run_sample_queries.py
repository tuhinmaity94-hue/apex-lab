"""Run the course SQL examples on a local SQLite database opened read-only."""
import argparse
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'instance' / 'apex.db')
    parser.add_argument('--username', default='demo')
    parser.add_argument('--from', dest='date_from', type=date.fromisoformat, default=date.min)
    parser.add_argument('--to', dest='date_to', type=date.fromisoformat, default=date.max)
    parser.add_argument('--min-matches', type=int, default=2)
    args = parser.parse_args()
    if args.date_from > args.date_to or args.min_matches < 1:
        parser.error('Provide an ordered date range and a positive minimum match count.')
    params = {
        'username': args.username,
        'date_from': args.date_from.isoformat(),
        'date_to': args.date_to.isoformat(),
        'min_matches': args.min_matches,
    }

    source = (ROOT / 'database' / 'sample_queries.sql').read_text(encoding='utf-8')
    with closing(sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        statement = ''
        for line in source.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                print(statement.strip().splitlines()[0].removeprefix('-- '))
                rows = conn.execute(statement, params)
                print(json.dumps([dict(row) for row in rows], indent=2, ensure_ascii=False))
                statement = ''


if __name__ == '__main__':
    main()

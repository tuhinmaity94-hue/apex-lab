"""Compare the match journal query before and after adding its SQLite index."""
import argparse
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import random
import sqlite3
from statistics import median
from time import perf_counter_ns


SCHEMA = Path(__file__).resolve().parents[1] / 'database' / 'schema.sqlite.sql'
INDEX = 'ix_match_user_date'
QUERY = '''
SELECT id, played_at, map_name, rp
FROM "match"
WHERE user_id = ? AND played_at BETWEEN ? AND ?
ORDER BY played_at DESC, id DESC
LIMIT 50
'''
START = date(2025, 1, 1)
PARAMS = (1, (START + timedelta(days=150)).isoformat(), (START + timedelta(days=180)).isoformat())


def seed(conn, count):
    rng = random.Random(42)
    users = range(1, 101)
    dates = [(START + timedelta(days=offset)).isoformat() for offset in range(365)]
    conn.executemany(
        'INSERT INTO "user" (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
        ((i, f'bench-{i}', 'unused', 'user', START.isoformat()) for i in users),
    )
    conn.executemany('''
        INSERT INTO "match" (user_id, played_at, map_name, legend, placement, kills, damage, rp, note, is_sample)
        VALUES (?, ?, 'Benchmark map', 'Benchmark legend', 10, 1, 300, ?, '', 1)
    ''', ((rng.choice(users), rng.choice(dates), rng.randint(-50, 150)) for _ in range(count)))
    conn.commit()


def measure(conn, repeats):
    conn.execute('ANALYZE')
    plan = [row[3] for row in conn.execute('EXPLAIN QUERY PLAN ' + QUERY, PARAMS)]
    result = conn.execute(QUERY, PARAMS).fetchall()
    durations = []
    for _ in range(repeats):
        start = perf_counter_ns()
        conn.execute(QUERY, PARAMS).fetchall()
        durations.append((perf_counter_ns() - start) / 1_000_000)
    return plan, result, median(durations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=100_000)
    parser.add_argument('--repeats', type=int, default=25)
    args = parser.parse_args()
    if args.rows < 1 or args.repeats < 1:
        parser.error('Rows and repeats must be positive.')

    with closing(sqlite3.connect(':memory:')) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.executescript(SCHEMA.read_text(encoding='utf-8'))
        seed(conn, args.rows)
        index_sql = conn.execute('SELECT sql FROM sqlite_master WHERE name = ?', (INDEX,)).fetchone()[0]
        conn.execute(f'DROP INDEX {INDEX}')
        without = measure(conn, args.repeats)
        conn.execute(index_sql)
        with_index = measure(conn, args.repeats)

    if without[1] != with_index[1]:
        raise RuntimeError('The query returned different results after creating the index.')
    print(f'SQLite {sqlite3.sqlite_version} | {args.rows:,} synthetic matches | 100 users | {args.repeats} timed runs')
    print(f'Query: user {PARAMS[0]}, {PARAMS[1]} to {PARAMS[2]}, up to 50 rows; {len(without[1])} identical results')
    for label, (plan, _, elapsed) in [('Without index', without), ('With index', with_index)]:
        print(f'{label} | median {elapsed:.3f} ms')
        for step in plan:
            print(f'  {step}')


if __name__ == '__main__':
    main()

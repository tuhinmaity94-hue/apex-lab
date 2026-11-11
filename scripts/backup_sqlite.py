"""Consistent live SQLite backup. Does not modify or reset the source database."""
from datetime import datetime
from pathlib import Path
import os
import sqlite3
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
if os.getenv('DATABASE_URL'):
    raise SystemExit('This helper only backs up the default SQLite database. Use mysqldump for MySQL.')
source=ROOT/'instance'/'apex.db'
if not source.exists():raise SystemExit('Database does not exist. Start the app first.')
folder=ROOT/'backups';folder.mkdir(exist_ok=True)
target=folder/('apex-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
    result=dst.execute('PRAGMA integrity_check').fetchone()[0]
    if result!='ok':raise SystemExit('Backup integrity check failed: '+result)
print('Backup verified:',target)

"""Export baseline DDL from the same SQLAlchemy models used by the app."""
from pathlib import Path
import sys
from sqlalchemy import create_mock_engine
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.models import db

def export(dialect):
    chunks=['-- Apex Lab schema baseline v1. Generated from backend/models.py.']
    if dialect=='sqlite':chunks.append('PRAGMA foreign_keys=ON;')
    else:chunks.append('-- Run inside a dedicated utf8mb4 database on MySQL 8+.')
    def dump(sql,*args,**kwargs):
        chunks.append(str(sql.compile(dialect=engine.dialect)).strip()+';')
    engine=create_mock_engine(dialect+'://',dump)
    db.metadata.create_all(engine,checkfirst=False)
    out=ROOT/'database'
    out.mkdir(exist_ok=True)
    (out/f'schema.{dialect}.sql').write_text('\n\n'.join(chunks)+'\n',encoding='utf-8')
    print('Exported',dialect)

if __name__=='__main__':
    export('sqlite');export('mysql')

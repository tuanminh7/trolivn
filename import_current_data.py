import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, text

from app import app, db


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / 'seed_current_data.json'


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return value


def normalize_row(table, row):
    normalized = {}
    for column in table.columns:
        value = row.get(column.name)
        if isinstance(column.type, DateTime):
            value = parse_datetime(value)
        elif isinstance(column.type, Boolean) and value is not None:
            value = bool(value)
        normalized[column.name] = value
    return normalized


def table_rows(tables_payload, table_name):
    rows = tables_payload.get(table_name, [])
    if isinstance(rows, dict) and 'value' in rows:
        rows = rows['value']
    if rows is None:
        return []
    if isinstance(rows, dict):
        return [rows]
    return rows


def reset_postgres_sequences():
    if db.engine.dialect.name != 'postgresql':
        return
    for table in db.metadata.sorted_tables:
        if 'id' not in table.columns:
            continue
        db.session.execute(text(
            f"SELECT setval(pg_get_serial_sequence('\"{table.name}\"', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM \"{table.name}\"), 1), true)"
        ))


def import_data():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f'Không tìm thấy file dữ liệu: {INPUT_PATH}')
    payload = json.loads(INPUT_PATH.read_text(encoding='utf-8'))
    tables_payload = payload.get('tables', {})
    with app.app_context():
        db.create_all()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.flush()
        for table in db.metadata.sorted_tables:
            rows = table_rows(tables_payload, table.name)
            if not rows:
                continue
            db.session.execute(table.insert(), [normalize_row(table, row) for row in rows])
        reset_postgres_sequences()
        db.session.commit()
    print('Imported seed_current_data.json successfully.')


if __name__ == '__main__':
    import_data()

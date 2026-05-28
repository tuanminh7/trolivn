import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'app.db'
OUTPUT_PATH = BASE_DIR / 'seed_current_data.json'


TABLES = [
    'user',
    'message',
    'psychology_topic',
    'psychology_question',
    'psychology_submission',
    'chat_conversation',
    'chat_message',
    'emotion_entry',
    'student_profile',
    'teacher_profile',
    'career_test',
    'career_question',
    'career_submission',
    'career_job',
    'career_inquiry',
    'career_learning_path',
    'career_path_stage',
    'career_path_task',
    'career_path_skill',
    'forum_post',
    'forum_reaction',
    'forum_comment',
    'forum_report',
    'life_skill_lesson',
    'life_skill_progress',
]


def export_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(f'Không tìm thấy database: {DB_PATH}')
    payload = {'tables': {}}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        for table in TABLES:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                payload['tables'][table] = []
                continue
            rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
            payload['tables'][table] = [dict(row) for row in rows]
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Exported current data to {OUTPUT_PATH}')


if __name__ == '__main__':
    export_data()

from app import db, app
from sqlalchemy import text

def migrate():
    with app.app_context():
        conn = db.engine.connect()
        res = conn.execute(text("PRAGMA table_info('user')")).fetchall()
        cols = [r[1] for r in res]
        changed = False
        if 'is_active' not in cols:
            print('Adding column is_active to user...')
            conn.execute(text("ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            changed = True
        if 'account_id' not in cols:
            print('Adding column account_id to user...')
            conn.execute(text("ALTER TABLE user ADD COLUMN account_id INTEGER"))
            changed = True
        # ensure message table exists
        conn.execute(text('''CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER,
            content TEXT NOT NULL,
            created_at DATETIME,
            reply_to INTEGER
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS psychology_topic (
            id INTEGER PRIMARY KEY,
            title VARCHAR(160) NOT NULL,
            description TEXT,
            teacher_id INTEGER NOT NULL,
            is_published BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS psychology_question (
            id INTEGER PRIMARY KEY,
            topic_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a VARCHAR(255) NOT NULL,
            option_b VARCHAR(255) NOT NULL,
            option_c VARCHAR(255) NOT NULL,
            option_d VARCHAR(255) NOT NULL,
            position INTEGER DEFAULT 0
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS psychology_submission (
            id INTEGER PRIMARY KEY,
            topic_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            percent INTEGER NOT NULL,
            level INTEGER NOT NULL,
            answers_json TEXT NOT NULL,
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS chat_conversation (
            id INTEGER PRIMARY KEY,
            room_type VARCHAR(20) NOT NULL,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER,
            created_at DATETIME,
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS chat_message (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER,
            sender_role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS emotion_entry (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            mood VARCHAR(40) NOT NULL,
            intensity INTEGER NOT NULL,
            triggers_json TEXT NOT NULL,
            note TEXT,
            prompt VARCHAR(255),
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS student_profile (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL UNIQUE,
            full_name VARCHAR(160),
            class_name VARCHAR(80),
            address VARCHAR(255),
            phone VARCHAR(40),
            guardian_name VARCHAR(160),
            guardian_phone VARCHAR(40),
            emergency_contact VARCHAR(160),
            avatar_filename VARCHAR(255),
            updated_at DATETIME
        )'''))
        profile_cols = [r[1] for r in conn.execute(text("PRAGMA table_info('student_profile')")).fetchall()]
        if 'avatar_filename' not in profile_cols:
            conn.execute(text("ALTER TABLE student_profile ADD COLUMN avatar_filename VARCHAR(255)"))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS teacher_profile (
            id INTEGER PRIMARY KEY,
            teacher_id INTEGER NOT NULL UNIQUE,
            full_name VARCHAR(160),
            department VARCHAR(120),
            subject VARCHAR(120),
            phone VARCHAR(40),
            email_contact VARCHAR(120),
            office_location VARCHAR(160),
            consultation_time VARCHAR(160),
            bio TEXT,
            avatar_filename VARCHAR(255),
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_test (
            id INTEGER PRIMARY KEY,
            title VARCHAR(160) NOT NULL,
            description TEXT,
            teacher_id INTEGER NOT NULL,
            is_published BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_question (
            id INTEGER PRIMARY KEY,
            test_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            image_url VARCHAR(500),
            option_a VARCHAR(255) NOT NULL,
            option_b VARCHAR(255) NOT NULL,
            option_c VARCHAR(255) NOT NULL,
            option_d VARCHAR(255) NOT NULL,
            position INTEGER DEFAULT 0
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_submission (
            id INTEGER PRIMARY KEY,
            test_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            percent INTEGER NOT NULL,
            answers_json TEXT NOT NULL,
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_job (
            id INTEGER PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            name VARCHAR(160) NOT NULL,
            field VARCHAR(100) NOT NULL,
            icon VARCHAR(40),
            summary VARCHAR(255) NOT NULL,
            skills_json TEXT NOT NULL,
            work TEXT NOT NULL,
            study VARCHAR(80) NOT NULL,
            salary VARCHAR(80) NOT NULL,
            demand VARCHAR(80) NOT NULL,
            personality TEXT NOT NULL,
            color VARCHAR(40),
            is_featured BOOLEAN DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_inquiry (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            reply TEXT,
            created_at DATETIME,
            replied_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_learning_path (
            id INTEGER PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            title VARCHAR(160) NOT NULL,
            summary VARCHAR(255) NOT NULL,
            icon VARCHAR(40),
            color VARCHAR(40),
            goal_label VARCHAR(160),
            completion_percent INTEGER DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_path_stage (
            id INTEGER PRIMARY KEY,
            path_id INTEGER NOT NULL,
            year_label VARCHAR(80) NOT NULL,
            subtitle VARCHAR(120),
            title VARCHAR(160) NOT NULL,
            status VARCHAR(40) NOT NULL,
            is_open BOOLEAN DEFAULT 1,
            position INTEGER DEFAULT 0
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_path_task (
            id INTEGER PRIMARY KEY,
            stage_id INTEGER NOT NULL,
            title VARCHAR(180) NOT NULL,
            subtitle VARCHAR(180),
            task_type VARCHAR(40) NOT NULL,
            is_done BOOLEAN DEFAULT 0,
            position INTEGER DEFAULT 0
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS career_path_skill (
            id INTEGER PRIMARY KEY,
            path_id INTEGER NOT NULL,
            name VARCHAR(120) NOT NULL,
            level_label VARCHAR(80) NOT NULL,
            percent INTEGER DEFAULT 0,
            color VARCHAR(40)
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS forum_post (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            category VARCHAR(40) NOT NULL,
            title VARCHAR(180) NOT NULL,
            content TEXT NOT NULL,
            is_anonymous BOOLEAN DEFAULT 0,
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS forum_reaction (
            id INTEGER PRIMARY KEY,
            post_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            reaction_type VARCHAR(20) NOT NULL,
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS forum_comment (
            id INTEGER PRIMARY KEY,
            post_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_anonymous BOOLEAN DEFAULT 0,
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS forum_report (
            id INTEGER PRIMARY KEY,
            post_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            reason VARCHAR(255),
            created_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS life_skill_lesson (
            id INTEGER PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            title VARCHAR(180) NOT NULL,
            skill_category VARCHAR(80) NOT NULL,
            video_url VARCHAR(500) NOT NULL,
            thumbnail_url VARCHAR(500),
            duration VARCHAR(40),
            description TEXT NOT NULL,
            practice_steps TEXT,
            reflection_question VARCHAR(255),
            is_featured BOOLEAN DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS life_skill_progress (
            id INTEGER PRIMARY KEY,
            lesson_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            is_completed BOOLEAN DEFAULT 0,
            feedback VARCHAR(80),
            reflection TEXT,
            updated_at DATETIME
        )'''))
        if changed:
            print('Migration applied.')
        else:
            print('No migration needed.')
        conn.commit()

if __name__ == '__main__':
    migrate()

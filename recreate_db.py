import os
from app import app, db, User, Message
from datetime import datetime

DB_PATHS = [
    os.path.join(os.path.dirname(__file__), 'app.db'),
    os.path.join(os.path.dirname(__file__), 'instance', 'app.db')
]

def recreate_db():
    with app.app_context():
        # export users
        users = User.query.order_by(User.id).all()
        users_data = []
        for u in users:
            users_data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'password_hash': u.password_hash,
                'role': u.role,
                'account_id': u.account_id,
                'is_active': u.is_active,
            })

        # export messages if table exists
        messages_data = []
        try:
            msgs = Message.query.order_by(Message.id).all()
            for m in msgs:
                messages_data.append({
                    'id': m.id,
                    'sender_id': m.sender_id,
                    'recipient_id': m.recipient_id,
                    'content': m.content,
                    'created_at': m.created_at,
                    'reply_to': m.reply_to,
                })
        except Exception:
            messages_data = []

    # remove DB file(s) — attempt to close connections first
    with app.app_context():
        try:
            db.session.remove()
        except Exception:
            pass
        try:
            db.engine.dispose()
        except Exception:
            pass
    for DB_PATH in DB_PATHS:
        if os.path.exists(DB_PATH):
            print('Removing existing DB file:', DB_PATH)
            os.remove(DB_PATH)

    # recreate schema
    with app.app_context():
        db.create_all()
        # reinsert users WITHOUT setting primary key id to avoid UNIQUE conflicts
        old_to_new = {}
        for ud in users_data:
            u = User(username=ud['username'], email=ud['email'], role=ud['role'])
            u.password_hash = ud['password_hash']
            u.account_id = ud['account_id']
            u.is_active = ud.get('is_active', True)
            db.session.add(u)
        db.session.commit()
        # build mapping old id -> new id using email
        for ud in users_data:
            new_u = User.query.filter_by(email=ud['email']).first()
            if new_u:
                old_to_new[ud['id']] = new_u.id

        # reinsert messages, remapping sender/recipient ids
        for md in messages_data:
            sender_new = old_to_new.get(md['sender_id']) if md['sender_id'] else None
            recip_new = old_to_new.get(md['recipient_id']) if md['recipient_id'] else None
            m = Message(sender_id=sender_new, recipient_id=recip_new, content=md['content'], created_at=md['created_at'], reply_to=None)
            db.session.add(m)
        db.session.commit()

        print('Recreated DB. Users:', User.query.count(), 'Messages:', Message.query.count())

if __name__ == '__main__':
    recreate_db()

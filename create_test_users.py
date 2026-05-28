from app import db, User, app


def create_users():
    with app.app_context():
        db.create_all()
        users = [
            ('adminuser', 'admin@example.com', 'adminpass', 'admin'),
            ('teacher1', 'teacher@example.com', 'teacherpass', 'teacher'),
            ('student1', 'student@example.com', 'studentpass', 'student'),
            ('parent1', 'parent@example.com', 'parentpass', 'parent'),
        ]
        created = []
        for username, email, password, role in users:
            if User.query.filter_by(email=email).first():
                print(f'{email} already exists — skipping')
                continue
            u = User(username=username, email=email, role=role)
            u.account_id = User.next_account_id()
            u.set_password(password)
            db.session.add(u)
            created.append((username, email, password, role, u.account_id))
        db.session.commit()
        print('Created users:')
        for c in created:
            print(c)


if __name__ == '__main__':
    create_users()
    with app.app_context():
        print('\nAll users in DB:')
        for u in User.query.order_by(User.id).all():
            print(u.id, u.username, u.email, u.role, u.account_id)

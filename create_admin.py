import sys
from app import app, db, User

def create_admin(username='admin', email='admin@example.com', password='adminpass'):
    with app.app_context():
        _create_admin(username, email, password)

def _create_admin(username, email, password):
    db.create_all()
    if User.query.filter_by(role='admin').first():
        print('Admin đã tồn tại. Hủy bỏ tạo mới.')
        return
    u = User(username=username, email=email, role='admin')
    u.account_id = User.next_account_id()
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    print(f'Admin tạo thành công: {username} / {email}')

if __name__ == '__main__':
    if len(sys.argv) >= 4:
        create_admin(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print('Sử dụng: python create_admin.py <username> <email> <password>')
        print('Nếu không cung cấp tham số, tạo admin mặc định: admin/admin@example.com/adminpass')
        create_admin()

# Flask School App

Ứng dụng mẫu bằng Flask với chức năng đăng ký/đăng nhập và phân quyền cơ bản.

Hỗ trợ các vai trò: `admin`, `teacher`, `student`, `parent`.

Hướng dẫn nhanh:

1. Tạo virtualenv và cài dependencies:

```bash
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

2. Tạo admin (ví dụ):

```bash
python create_admin.py admin admin@example.com adminpass
```

3. Chạy ứng dụng:

```bash
python app.py
```

4. Truy cập http://127.0.0.1:5000/ (Đăng nhập bằng email và mật khẩu)

Ghi chú:
- Người dùng có thể đăng ký với vai trò `Học sinh` hoặc `Phụ huynh` tại trang đăng ký.
- Tài khoản `Giáo viên` phải do `Admin` tạo trong trang `Dashboard` -> `Tạo tài khoản giáo viên`.
 - Mỗi tài khoản khi đăng ký/được tạo sẽ kèm theo `Mã số` (6 chữ số) tự sinh, bắt đầu từ `250000`.

Tóm tắt các tính năng hiện có
- Đăng ký: người dùng đăng ký bằng `username`, `email`, `mật khẩu` và chọn vai trò (`Học sinh` hoặc `Phụ huynh`).
- Đăng nhập: chỉ dùng `email` + `mật khẩu` (người dùng phải chọn trước loại tài khoản khi đăng nhập: Phụ huynh / Giáo viên / Học sinh / Quản lí).
- Mỗi tài khoản có `Mã số` (`account_id`) tự sinh 6 chữ số, bắt đầu từ `250000`.
- Admin (vai trò `admin`) có trang quản lý:
	- Danh sách người dùng: xem thông tin, trạng thái, tới trang quản lý từng người.
	- Quản lý tài khoản: cấp/phục hồi (activate), thu hồi (deactivate), đổi mật khẩu cho bất kỳ tài khoản nào (giúp khôi phục khi quên mật khẩu).
	- Thống kê số lượng người dùng theo vai trò.
	- Chat quản trị: xem tin nhắn gửi từ giáo viên và học sinh, và trả lời họ.
- Tin nhắn (Message): giáo viên/học sinh có thể gửi tin nhắn tới admin qua trang liên hệ; admin trả lời trực tiếp (hiện theo lượt, chưa realtime).

Hướng dẫn cài đặt và chạy (Windows)

1. Tạo virtualenv và cài dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Khởi tạo cơ sở dữ liệu và tạo admin mẫu (hoặc tự tạo sau khi chạy app):

```bash
# Tạo admin mặc định (username, email, password)
python create_admin.py admin admin@example.com adminpass

# Hoặc tạo 4 tài khoản test (admin, teacher, student, parent)
python create_test_users.py
```

3. Chạy ứng dụng:

```bash
python app.py
```

4. Truy cập ứng dụng:

- Trang đăng nhập: http://127.0.0.1:5000/ — chọn vai trò (bắt buộc), sau đó nhập `email` và `mật khẩu`.
- Trang đăng ký: http://127.0.0.1:5000/register — chỉ cho phép chọn `Học sinh` hoặc `Phụ huynh`.

Test accounts đã được tạo (nếu chạy `create_test_users.py`):
- Admin: `admin@example.com` / `adminpass` (mã 250000)
- Teacher: `teacher@example.com` / `teacherpass` (mã 250001)
- Student: `student@example.com` / `studentpass` (mã 250002)
- Parent: `parent@example.com` / `parentpass` (mã 250003)

Trang admin chính (chỉ admin truy cập):
- `GET /admin/users` — danh sách người dùng và link quản lý.
- `GET /admin/user/<id>` — trang quản lý cụ thể: activate/deactivate, đổi mật khẩu.
- `GET /admin/stats` — thống kê số lượng user theo vai trò.
- `GET /admin/chat` — xem tin nhắn từ giáo viên/học sinh và trả lời (POST `/admin/reply/<message_id>`).

Người dùng (teacher/student) có thể gửi tin nhắn tới admin tại:
- `GET/POST /contact-admin` (form gửi nội dung tới admin).

Ghi chú về schema / database
- File DB mặc định: `app.db` (SQLite). Nếu cập nhật model (thêm cột `account_id`, `is_active`, `message`...), bạn có thể xóa `app.db` và khởi tạo lại để tránh lỗi migration đơn giản:

```bash
del app.db            # Windows (PowerShell: Remove-Item app.db)
python create_test_users.py
```

Giới hạn hiện tại và hướng phát triển gợi ý
- Chat hiện chưa realtime (nếu cần realtime, có thể dùng WebSocket / Flask-SocketIO).
- Reset mật khẩu qua email/chứng thực chưa triển khai (cần cấu hình SMTP và token).
- Giao diện admin hiện cơ bản — có thể mở rộng: lọc/sắp xếp, export CSV, audit log.

Nếu bạn muốn tôi tiếp tục, tôi có thể:
- Thêm link điều hướng admin trong `Dashboard`.
- Thêm chức năng reset mật khẩu qua email (OTP hoặc link) cho học sinh/phụ huynh.
- Nâng cấp chat lên realtime bằng `Flask-SocketIO`.
- Thêm trang danh sách/CSV export cho admin.

## Deploy lên Render

Dự án đã có sẵn `render.yaml` và `Procfile` để deploy Flask + Socket.IO trên Render.

### Cách deploy bằng Blueprint

1. Đẩy source code lên GitHub.
2. Vào Render, chọn `New` -> `Blueprint`.
3. Chọn repository của dự án.
4. Render sẽ đọc `render.yaml`, tự tạo Web Service và PostgreSQL database.
5. Sau khi deploy xong, mở web URL Render cấp.

### Cách deploy thủ công

Nếu tạo Web Service thủ công, dùng cấu hình:

```bash
Build Command: pip install -r requirements.txt
Start Command: gunicorn --worker-class eventlet -w 1 app:app
```

Biến môi trường cần có:

```bash
SECRET_KEY=<chuỗi bí mật>
DATABASE_URL=<PostgreSQL connection string>
SOCKETIO_ASYNC_MODE=eventlet
ENABLE_SOCKETIO=1
GEMINI_API_KEY=<nếu dùng Kbot Gemini>
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-1.5-flash
```

### Khởi tạo dữ liệu mẫu

Sau lần deploy đầu tiên, bảng dữ liệu sẽ tự được tạo khi app khởi động. Nếu muốn nạp tài khoản và dữ liệu demo, mở Render Shell rồi chạy:

```bash
python seed_demo_data.py
```

Nếu muốn đưa đúng dữ liệu local hiện tại lên Render, dự án có sẵn `seed_current_data.json`. Sau khi deploy, mở Render Shell rồi chạy:

```bash
python import_current_data.py
```

Nếu dùng Render free không có Shell, bật biến môi trường này rồi redeploy:

```bash
IMPORT_CURRENT_DATA=1
```

App sẽ tự import `seed_current_data.json` khi database còn trống. Sau khi đăng nhập được, đổi lại:

```bash
IMPORT_CURRENT_DATA=0
```

Nếu muốn ghi đè database đang có dữ liệu:

```bash
IMPORT_CURRENT_DATA=force
```

Nếu sau này muốn xuất lại dữ liệu local mới nhất:

```bash
python export_current_data.py
```

Tài khoản demo sau khi seed:

```bash
admin@example.com / adminpass
teacher@example.com / teacherpass
student@example.com / studentpass
parent@example.com / parentpass
```

Lưu ý: ảnh upload trong `static/uploads` có thể mất khi Render rebuild nếu không gắn Persistent Disk hoặc chuyển sang dịch vụ lưu trữ ngoài.

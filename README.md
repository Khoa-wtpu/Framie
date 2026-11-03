# FRAMIE

Nền tảng web trung gian kết nối Khách hàng với Nhiếp ảnh gia tự do: đặt lịch, đặt cọc, bàn giao ảnh và đánh giá.
Dự án nhóm môn Lập trình Web, xây bằng Django.

## Công nghệ

- Python 3.14 (cả nhóm dùng chung một bản)
- Django 6.1.2, Pillow (xử lý ảnh)
- Cơ sở dữ liệu SQLite

## Chạy project trên máy

1. Tải kho về: `git clone` hoặc dùng GitHub Desktop (File > Clone repository).
2. Mở thư mục `Framie` bằng PyCharm hoặc VS Code.
3. Tạo môi trường ảo:
   - PyCharm: File > Settings > Project > Python Interpreter > Add Interpreter > Virtualenv, chọn Python 3.14.
   - Hoặc gõ trong Terminal: `python -m venv .venv`
4. Bật môi trường ảo (dòng lệnh phải bắt đầu bằng `(.venv)`):
```
   .venv\Scripts\activate
```
5. Cài thư viện:
```
   pip install -r requirements.txt
```
6. Tạo bảng dữ liệu (file migration đã có sẵn trong kho):
```
   python manage.py migrate
```
7. Tạo tài khoản quản trị để thử (lệnh sẽ hỏi cả email và số điện thoại 10 chữ số bắt đầu bằng 0):
Mật khẩu phải đủ 8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt.
```
   python manage.py createsuperuser
```
8. Chạy web rồi mở http://127.0.0.1:8000/admin/ :
```
   python manage.py runserver
```
## Gửi email thật bằng Gmail (không bắt buộc)

Mặc định, khi chưa cấu hình, email (đăng ký thành công, mã quên mật khẩu) **in ra Terminal** thay vì gửi thật. Web vẫn chạy bình thường. Muốn gửi email thật thì làm như sau.

1. **Tạo mật khẩu ứng dụng Gmail** (không dùng mật khẩu đăng nhập Gmail):
   - Vào tài khoản Google, bật **Xác minh 2 bước** (bắt buộc, không bật thì không tạo được mật khẩu ứng dụng).
   - Vào https://myaccount.google.com/apppasswords, đặt tên ứng dụng (ví dụ `FRAMIE`), bấm Tạo.
   - Google hiện mật khẩu 16 ký tự. Copy rồi **viết liền, bỏ khoảng trắng**.
2. **Tạo file `.env`** ở thư mục gốc project (cùng cấp `manage.py`), tên đúng là `.env`:
```
FRAMIE_EMAIL_USER=gmail-cua-ban@gmail.com
FRAMIE_EMAIL_PASSWORD=matkhauungdung16kytu
```
   - Không dùng dấu nháy, không có dấu cách quanh dấu `=`.
   - **Không đưa `.env` lên GitHub.** Trước khi commit, kiểm tra GitHub Desktop không liệt kê file `.env` (`.env` phải có trong `.gitignore`).
   - Gmail dùng chung của nhóm: xin leader gửi riêng, đừng đăng lên nhóm chat công khai.
3. Chạy lại `python manage.py runserver`. Thư viện `python-dotenv` (đã có trong `requirements.txt`) sẽ đọc file `.env` khi khởi động.
4. Gmail vẫn lỗi trên mạng của bạn thì chạy `thu_smtp.py` từ thư mục gốc để xem lý do (và đừng commit file này).

## Lưu ý khi tạo tài khoản quản trị

Lệnh `python manage.py createsuperuser` giờ áp dụng luật mật khẩu của FRAMIE: **từ 8 ký tự, đủ 4 loại: chữ hoa, chữ thường, số và ký tự đặc biệt** (chữ có dấu như `ẩ` không tính là ký tự đặc biệt). Ví dụ hợp lệ: `Xk9#mQ2vLp`. Mật khẩu quá đơn giản sẽ bị từ chối ngay trong lệnh.

## Cấu trúc project

| Thư mục | Vai trò | Người phụ trách |
|---|---|---|
| `config/` | Cấu hình chung của project (`settings.py`, `urls.py`) | Khoa |
| `core/` | Khung giao diện chung, trang chủ, trang lỗi, hằng số trạng thái (`constants.py`) | Tuyền |
| `accounts/` | Tài khoản, đăng ký, đăng nhập, quên mật khẩu, phân quyền | Phanh |
| `chat/` | Trao đổi trực tuyến | Phanh |
| `notifications/` | Thông báo | Phanh |
| `profiles/` | Hồ sơ, Portfolio, Gói dịch vụ, Duyệt hồ sơ | Khoa |
| `search/` | Tìm kiếm, lọc, xem hồ sơ Nhiếp ảnh gia | Khoa |
| `schedule/` | Lịch khả dụng | Khoa |
| `bookings/` | Quản lý Booking | Tuyền |
| `payments/` | Thanh toán | Nguyên |
| `delivery/` | Bàn giao ảnh | Nguyên |
| `reviews/` | Đánh giá | Nguyên |
| `templates/` | Giao diện HTML dùng chung (khung, trang lỗi) | Tuyền |
| `static/` | CSS, JS, logo, font do nhóm viết | cả nhóm |
| `media/` | File người dùng tải lên khi chạy thử (không đưa lên GitHub) | |

## Quy tắc làm việc nhóm

- Mỗi người làm trên nhánh riêng: `khoa`, `tuyen`, `nguyen`, `phanh`. Không làm trực tiếp trên `main`.
- Làm xong thì tạo Pull Request vào `main`, Khoa kiểm tra và gộp. Trước khi bắt đầu việc mới, cập nhật nhánh từ `main`.
- Chỉ sửa file trong app của mình. Cần sửa app của người khác thì nhắn người đó.
- Tên trạng thái lấy từ `core/constants.py` (ví dụ `TrangThaiBooking.DA_HUY`), không tự gõ chữ tiếng Việt.
- Model User dùng của Django (đã mở rộng trong `accounts/models.py`), không tạo bảng tài khoản riêng.
- Sau khi sửa `models.py`: chạy `python manage.py makemigrations`, rồi đưa file migration mới lên cùng commit.
- Không đưa lên GitHub: `.venv`, `.idea`, `db.sqlite3`, `media/`, mật khẩu hoặc file `.env`.


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

## Xử lý quá hạn tự động

FRAMIE tự xử lý 5 việc quá hạn: **giữ chỗ 5 phút** (slot về "Lịch trống"), **đặt cọc 1 ngày**, **Nhiếp ảnh gia chưa xác nhận khi quá giờ chụp** (tự hủy), **thanh toán 60% sau 2 ngày**, **xóa ảnh sau 3 ngày mở quyền tải**. Có 3 lớp cùng làm việc này, chạy song song vẫn an toàn:

| Lớp | Khi nào chạy | Đúng giờ khi không ai mở web? |
|---|---|---|
| Luồng nền (`bookings/nen_qua_han.py`) | Tự mở khi web server chạy (`runserver`, gunicorn, uvicorn...), lặp mỗi **60 giây** | Có, trong lúc web server còn chạy. Slot được nhả chậm nhất khoảng 1 phút sau khi hết 5 phút giữ chỗ |
| Middleware (`bookings/middleware.py`) | Khi có người mở trang Booking, Thanh toán, Bàn giao, Tổng quan, Tìm kiếm; quét tối đa 45 giây một lần | Không (chỉ khi có người mở web) |
| Lệnh `xu_ly_qua_han` | Chạy tay hoặc lên lịch | Có, kể cả khi web server tắt, nếu đã lên lịch |

**Khi chạy thử trên máy:** chỉ cần `python manage.py runserver`, luồng nền tự chạy, không cần làm gì thêm. Muốn xem kết quả: nhìn log, hoặc chạy tay `python manage.py xu_ly_qua_han` (in số mục đã xử lý).

**Khi triển khai thật:** nên lên lịch lệnh mỗi 1 phút để chắc chắn đúng giờ cả khi web server khởi động lại hay tắt:

- Windows (Task Scheduler): tạo Basic Task, Trigger "Daily", bật "Repeat task every 1 minute for a duration of Indefinitely", Action "Start a program":
  - Program: `C:\đường\dẫn\Framie\.venv\Scripts\python.exe`
  - Arguments: `manage.py xu_ly_qua_han`
  - Start in: `C:\đường\dẫn\Framie`
- Linux (cron): thêm dòng `* * * * * cd /đường/dẫn/Framie && .venv/bin/python manage.py xu_ly_qua_han >> /var/log/framie_qua_han.log 2>&1`
- Hoặc chạy một tiến trình riêng, lặp liên tục: `python manage.py xu_ly_qua_han --lap 60`

**Tùy chỉnh** (`config/settings.py`): `XU_LY_QUA_HAN_NEN_GIAY` (mặc định 60, đặt `0` để tắt luồng nền, ví dụ khi chạy nhiều worker và đã dùng cron), `XU_LY_QUA_HAN_KHOANG_CACH_GIAY` (khoảng cách tối thiểu giữa 2 lần quét của middleware, mặc định 45).

**Lưu ý:** luồng nền thuộc từng tiến trình web, nên chạy nhiều worker sẽ có nhiều luồng (vẫn đúng, chỉ lặp việc). Web server tắt hẳn thì luồng nền tắt theo; chỉ lệnh lên lịch mới chạy tiếp.

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


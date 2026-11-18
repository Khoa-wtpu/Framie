# Dữ liệu demo FRAMIE

## Tài khoản dùng cho buổi báo cáo

| Vai trò | Username | Đăng nhập bằng email | Mật khẩu |
|---|---|---|---|
| Khách hàng | `kh01` (Nguyễn Thảo My) | `kh01@example.com` (hoặc email thật, xem bên dưới) | `Framie@2026` |
| Nhiếp ảnh gia (NAG chính, Đà Nẵng) | `nag05` (Đặng Quốc Anh) | `nag05@example.com` (hoặc email thật, xem bên dưới) | `Framie@2026` |

Đăng nhập bằng **email**, không phải username.

Luồng demo với hai tài khoản này:

| Booking | Trạng thái | Dùng để demo |
|---|---|---|
| BK18 | Chốt Booking, chụp sau 3 ngày, Đà Nẵng - Bãi Xép | Thẻ dự báo thời tiết |
| BK09 | Chờ Khách hàng kiểm tra, 7 ảnh Chân dung | Slider trước (màu) / sau (đen trắng) |
| BK19 | Chờ xác nhận, chụp sau 9 ngày, Đà Nẵng - Phố cổ Hội An | nag05 chấp nhận yêu cầu mới |

Trang chủ có 3 nhiếp ảnh gia nổi bật: nag02 (Trần Bảo Ngọc), nag05 (Đặng Quốc Anh), nag06 (Hoàng Mỹ Linh); cả ba đều có ảnh bìa thật.
Các tài khoản mẫu khác: `nag01` ... `nag04`, `nag06`, `nag07` (đã duyệt), `nag08`, `nag09` (chờ duyệt), `nag10` (đã từ chối), `kh02` ... `kh08`, `admin_mau`; cùng mật khẩu, email dạng `<username>@example.com`.

## Nạp lại dữ liệu (làm sát ngày báo cáo để lịch trống còn hạn 45 ngày)

```
python manage.py nap_khu_vuc
python manage.py nap_du_lieu_mau
```

## Nhận email thật cho tài khoản demo

Email `@example.com` là địa chỉ giả nên không nhận được thư. Muốn `kh01` và `nag05` nhận email thật (mã OTP, thông báo Booking...), cần CẢ HAI việc:

1. **Hệ thống phải có tài khoản gửi email** (một lần): file `.env` ở gốc dự án có `FRAMIE_EMAIL_USER` và `FRAMIE_EMAIL_PASSWORD` (mật khẩu ứng dụng của Gmail). Không có hai biến này thì thư chỉ in ra Terminal, không gửi đi.
2. **Đặt email thật cho hai tài khoản demo**, thêm vào `.env`:
   ```
   DEMO_EMAIL_NAG05=tenban+nag05@gmail.com
   DEMO_EMAIL_KH01=tenban+kh01@gmail.com
   ```
   Rồi nạp lại: `python manage.py nap_du_lieu_mau`.

Lưu ý:
- Hai email phải KHÁC nhau (email là duy nhất). Gmail cho dùng dạng `tenban+nag05@gmail.com` và `tenban+kh01@gmail.com`: là hai địa chỉ khác nhau nhưng thư đều về hộp thư `tenban@gmail.com`.
- Email không được trùng với email của tài khoản thật bạn đang dùng trên hệ thống (lệnh sẽ báo lỗi và không xóa gì).
- Sau khi đặt, đăng nhập bằng email thật đó (không còn là `...@example.com`).
- Muốn quay về email giả: xóa hai dòng trong `.env`, vào trang quản trị xóa tài khoản `nag05`, `kh01` (đang mang email thật), rồi nạp lại.
- Tuyệt đối không đưa `.env` lên GitHub (đã được `.gitignore` chặn) và không gửi file `.env` hay nén cả thư mục có `.env` cho người khác.

# =====================================================================
# accounts/models.py  -  Module 7: Quản lý tài khoản & phân quyền
# Bảng User của FRAMIE. Kế thừa User có sẵn của Django nên đã có sẵn:
# username, password (lưu băm), first_name, last_name, email,
# is_active, is_staff, date_joined, last_login. Ở đây chỉ bổ sung
# những gì Django chưa có (theo feedback 6 của thầy).
# =====================================================================
from django.contrib.auth.models import AbstractUser   # bản mẫu User của Django
from django.core.validators import RegexValidator     # kiểm tra chuỗi theo mẫu
from django.db import models                          # các kiểu cột dữ liệu

from core.constants import TrangThaiHoSo              # tên trạng thái hồ sơ


class User(AbstractUser):
    # Ghi đè email của Django: bắt buộc nhập, không được trùng (đăng nhập bằng email).
    email = models.EmailField('email', max_length=100, unique=True)

    # Cột Django chưa có: số điện thoại. Bắt buộc, không trùng,
    # đúng 10 chữ số và bắt đầu bằng 0 (Bảng 54 của báo cáo).
    # Dùng chuỗi (CharField) vì kiểu số sẽ làm mất số 0 đầu.
    so_dien_thoai = models.CharField(
        'số điện thoại',
        max_length=10,
        unique=True,
        validators=[RegexValidator(r'^0\d{9}$',
                                   'Số điện thoại gồm 10 chữ số và bắt đầu bằng 0.')],
    )

    # Trạng thái hồ sơ Nhiếp ảnh gia: Chờ duyệt / Đã duyệt / Đã từ chối.
    # Chỉ nhiếp ảnh gia mới có giá trị; Khách hàng và Quản trị viên để trống (NULL).
    # Form đăng ký Nhiếp ảnh gia (P5) gán 'Chờ duyệt'; duyệt hồ sơ (K7) đổi sang
    # 'Đã duyệt' hoặc 'Đã từ chối'. Vai trò thì dùng Group của Django, không lưu ở đây.
    trang_thai_ho_so = models.CharField(
        'trạng thái hồ sơ',
        max_length=20,
        choices=TrangThaiHoSo.CHOICES,
        null=True,
        blank=True,
    )

    # Các cột bắt buộc khi tạo tài khoản quản trị bằng lệnh createsuperuser
    # (ngoài username và mật khẩu), để admin cũng có email và số điện thoại.
    REQUIRED_FIELDS = ['email', 'so_dien_thoai']
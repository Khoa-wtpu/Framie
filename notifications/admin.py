from django.contrib import admin  # công cụ trang quản trị của Django
from .models import ThongBao  # lấy model ThongBao ở models.py cùng app


@admin.register(ThongBao)  # đăng ký bảng THONGBAO vào trang quản trị
class ThongBaoAdmin(admin.ModelAdmin):  # cấu hình cách hiển thị
    list_display = ('MaThongBao', 'MaNguoiNhan', 'TieuDe',  # các cột hiện ở danh sách
                    'TrangThaiDoc', 'DanhDauSao', 'NgayTao')  # (tiếp) thêm các cột trạng thái và ngày
    list_filter = ('TrangThaiDoc', 'DanhDauSao')  # bộ lọc bên phải

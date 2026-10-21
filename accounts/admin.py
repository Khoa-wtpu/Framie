# =====================================================================
# accounts/admin.py
# Cấu hình hiển thị bảng User trong trang quản trị Django (/admin).
# Dùng lại UserAdmin có sẵn của Django, chỉ bổ sung các cột của FRAMIE.
# =====================================================================
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin   # trang quản trị User mẫu của Django

from .models import User                          # dấu . = lấy từ models.py cùng app


@admin.register(User)          # đăng ký bảng User vào trang quản trị
class CustomUserAdmin(UserAdmin):
    # Màn hình SỬA tài khoản: thêm một nhóm "Thông tin FRAMIE" ở cuối form.
    fieldsets = UserAdmin.fieldsets + (
        ('Thông tin FRAMIE', {'fields': ('so_dien_thoai', 'trang_thai_ho_so')}),
    )

    # Màn hình TẠO tài khoản: thêm email và số điện thoại (là các cột bắt buộc).
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Thông tin FRAMIE', {'fields': ('email', 'so_dien_thoai', 'trang_thai_ho_so')}),
    )

    # Các cột hiện ở danh sách tài khoản.
    list_display = ('username', 'email', 'so_dien_thoai',
                    'trang_thai_ho_so', 'is_staff', 'is_active')

    # Bộ lọc bên phải danh sách: lọc theo trạng thái hồ sơ.
    list_filter = UserAdmin.list_filter + ('trang_thai_ho_so',)

    # Ô tìm kiếm: tìm theo cả số điện thoại.
    search_fields = UserAdmin.search_fields + ('so_dien_thoai',)
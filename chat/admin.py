# chat/admin.py - đăng ký bảng để xem dữ liệu thử trong /admin/
from django.contrib import admin  # trang quản trị của Django

from chat.models import CuocTroChuyen, TinNhan  # hai bảng của Module 8


@admin.register(CuocTroChuyen)  # đăng ký bảng cuộc trò chuyện
class CuocTroChuyenAdmin(admin.ModelAdmin):  # cách hiển thị trong admin
    list_display = ('MaCuocTroChuyen', 'MaKhachHang', 'MaNhiepAnhGia', 'NgayTao')  # các cột hiện trong danh sách


@admin.register(TinNhan)  # đăng ký bảng tin nhắn
class TinNhanAdmin(admin.ModelAdmin):  # cách hiển thị trong admin
    list_display = ('MaTinNhan', 'MaCuocTroChuyen', 'MaNguoiGui', 'ThoiGianGui')  # các cột hiện trong danh sách
    list_filter = ('MaCuocTroChuyen',)  # bộ lọc theo cuộc trò chuyện
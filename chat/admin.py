# chat/admin.py - đăng ký bảng để xem dữ liệu thử trong /admin/. CẢ 4 bảng (cuộc trò chuyện, tin nhắn, trạng thái từng người, ảnh đính kèm) đều CHỈ ĐỌC (Quản trị viên xem khi có tranh chấp, không thêm, sửa, xóa).
from django.contrib import admin  # trang quản trị của Django

from chat.models import CuocTroChuyen, DinhKemTinNhan, ThamGia, TinNhan  # các bảng của Module 8


class ChiXemAdmin(admin.ModelAdmin):  # lớp cha: chặn thêm, sửa, xóa
    def has_add_permission(self, request):  # không cho thêm
        return False  # luôn False

    def has_change_permission(self, request, obj=None):  # không cho sửa
        return False  # luôn False (vẫn xem được)

    def has_delete_permission(self, request, obj=None):  # không cho xóa
        return False  # luôn False


@admin.register(CuocTroChuyen)  # đăng ký bảng cuộc trò chuyện
class CuocTroChuyenAdmin(ChiXemAdmin):  # chỉ xem: chặn thêm, sửa, xóa (xóa cuộc trò chuyện sẽ mất cả tin nhắn)
    list_display = ('MaCuocTroChuyen', 'MaKhachHang', 'MaNhiepAnhGia', 'NgayTao')  # các cột hiện trong danh sách


@admin.register(TinNhan)  # đăng ký bảng tin nhắn
class TinNhanAdmin(ChiXemAdmin):  # chỉ xem, kể cả tin đã thu hồi (nội dung vẫn còn để xử lý tranh chấp)
    list_display = ('MaTinNhan', 'MaCuocTroChuyen', 'MaNguoiGui', 'ThoiGianGui', 'DaThuHoi')  # các cột hiện trong danh sách
    list_filter = ('MaCuocTroChuyen', 'DaThuHoi')  # bộ lọc theo cuộc trò chuyện và tin đã thu hồi


@admin.register(ThamGia)  # đăng ký bảng trạng thái từng người
class ThamGiaAdmin(ChiXemAdmin):  # chỉ xem
    list_display = ('MaThamGia', 'MaCuocTroChuyen', 'MaNguoiDung', 'MaTinDaXemCuoi', 'DanhDauChuaDoc', 'DaAn', 'DaGhim', 'XoaDenMaTin')  # các cột hiện trong danh sách


@admin.register(DinhKemTinNhan)  # đăng ký bảng ảnh đính kèm
class DinhKemTinNhanAdmin(ChiXemAdmin):  # chỉ xem
    list_display = ('MaDinhKem', 'MaTinNhan', 'TenGoc', 'KichThuoc')  # các cột hiện trong danh sách

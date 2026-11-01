from django.contrib import admin

from .models import Booking, GiuCho, LichSuTrangThaiBooking, YeuCauHuy


class LichSuTrangThaiInline(admin.TabularInline):
    # Hiện lịch sử đổi trạng thái ngay trong trang chi tiết Booking
    model = LichSuTrangThaiBooking
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('MaBooking', 'MaKhachHang', 'MaNhiepAnhGia', 'MaGoi',
                    'NgayGioChup', 'TrangThai', 'TongGiaTri', 'NgayTao')
    list_filter = ('TrangThai',)
    search_fields = ('MaKhachHang__email', 'MaNhiepAnhGia__MaTaiKhoan__email', 'DiaDiem')
    list_select_related = ('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan', 'MaGoi')
    raw_id_fields = ('MaKhachHang', 'MaNhiepAnhGia', 'MaGoi', 'MaLich')  # ô nhập mã thay vì danh sách dài
    inlines = [LichSuTrangThaiInline]


@admin.register(GiuCho)
class GiuChoAdmin(admin.ModelAdmin):
    list_display = ('MaGiuCho', 'MaKhachHang', 'MaLich', 'ThoiDiemGiu', 'ThoiDiemHetHan', 'TrangThai')
    list_filter = ('TrangThai',)
    raw_id_fields = ('MaKhachHang', 'MaLich')


@admin.register(LichSuTrangThaiBooking)
class LichSuTrangThaiBookingAdmin(admin.ModelAdmin):
    list_display = ('MaLichSu', 'MaBooking', 'TrangThaiCu', 'TrangThaiMoi', 'BenThucHien', 'ThoiDiemThayDoi')
    list_filter = ('TrangThaiMoi', 'BenThucHien')
    raw_id_fields = ('MaBooking',)


@admin.register(YeuCauHuy)
class YeuCauHuyAdmin(admin.ModelAdmin):
    list_display = ('MaYeuCauHuy', 'MaBooking', 'BenYeuCau', 'XuLyTienCoc',
                    'TrangThaiHoanTien', 'ThoiDiemYeuCau')
    list_filter = ('BenYeuCau', 'XuLyTienCoc', 'TrangThaiHoanTien')
    raw_id_fields = ('MaBooking',)
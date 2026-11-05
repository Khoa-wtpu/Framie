# =====================================================================
# bookings/qua_han.py  -  T10: Tự động xử lý quá hạn
#
#   xu_ly_qua_han()  chạy cả 4 việc dưới đây, mỗi việc độc lập (một việc lỗi không chặn việc khác):
#     1. Giữ chỗ quá 5 phút                -> lượt giữ 'Hết hạn', khung giờ về 'Lịch trống'
#                                             (dùng lại hàm của UC4.1: giai_phong_giu_cho_het_han)
#     2. Quá 1 ngày chưa đặt cọc           -> Booking 'Hết thời hạn đặt cọc', khung giờ về 'Lịch trống'
#     3. Quá 2 ngày chưa thanh toán 60%    -> khoản thanh toán 'Quá hạn thanh toán'
#     4. Ảnh quá 3 ngày sau khi mở quyền tải -> xóa file ảnh, ảnh 'Đã xóa' (phần xóa: delivery/xoa_anh_het_han.py, dùng kho ảnh của Nguyên)
#
#   Được gọi từ 2 nơi:
#     - bookings/middleware.py : mỗi khi mở các trang liên quan (Booking, Tổng quan, Thanh toán, Bàn giao, Tìm kiếm)
#     - lệnh  python manage.py xu_ly_qua_han  : chạy định kỳ (mỗi phút) bằng Task Scheduler / cron
#   Hạn chót lấy từ cột trong database (HanDatCoc, HanThanhToanConLai, ThoiHanTaiAnh) do bookings/services.py gán,
#   nên các con số 1 ngày / 2 ngày / 3 ngày chỉ khai báo một chỗ, không lặp lại ở đây.
# =====================================================================
import logging

from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.utils import timezone

from bookings.giu_cho import giai_phong_giu_cho_het_han
from bookings.models import Booking
from bookings.services import chuyen_trang_thai_booking, gui_email_sau_commit
from core.constants import BenThucHien, LoaiThanhToan, LuuTruAnh, TrangThaiBooking, TrangThaiThanhToan
from delivery.models import BanGiao
from delivery.xoa_anh_het_han import xoa_anh_cua_booking
from notifications.services import gui_thong_bao
from payments.models import MinhChungThanhToan, ThanhToan

logger = logging.getLogger(__name__)

LY_DO_HET_HAN_COC = 'Quá 1 ngày chưa đặt cọc'


def _bao_ca_hai_ben(booking, tieu_de, noi_dung_khach, noi_dung_nag, gui_email_khach=False):
    """Gửi thông báo web cho Khách hàng và Nhiếp ảnh gia của Booking (lỗi gửi chỉ ghi log)."""
    tb = gui_thong_bao(booking.MaKhachHang, tieu_de, noi_dung_khach, booking=booking)
    if gui_email_khach:
        gui_email_sau_commit(tb, booking.MaKhachHang, tieu_de, noi_dung_khach)
    gui_thong_bao(booking.MaNhiepAnhGia.MaTaiKhoan, tieu_de, noi_dung_nag, booking=booking)


# ---------------------------------------------------------------------
# 1. Giữ chỗ quá 5 phút
# ---------------------------------------------------------------------
def xu_ly_giu_cho_het_han():
    return giai_phong_giu_cho_het_han()


# ---------------------------------------------------------------------
# 2. Quá 1 ngày chưa đặt cọc
# ---------------------------------------------------------------------
def xu_ly_het_han_dat_coc(bay_gio=None):
    """Booking 'Chờ đặt cọc' đã quá HanDatCoc -> 'Hết thời hạn đặt cọc' (Hệ thống), slot về 'Lịch trống'.
    Bỏ qua Booking mà Khách đã tải minh chứng cọc và đang chờ Nhiếp ảnh gia xác nhận (Khách đã đặt cọc rồi)."""
    bay_gio = bay_gio or timezone.now()
    da_tai_minh_chung = ThanhToan.objects.filter(
        MaBooking=OuterRef('pk'), LoaiThanhToan=LoaiThanhToan.TIEN_COC,
        TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_COC)
    ds_ma = list(Booking.objects.filter(TrangThai=TrangThaiBooking.CHO_DAT_COC, HanDatCoc__lte=bay_gio)
                 .exclude(Exists(da_tai_minh_chung)).values_list('pk', flat=True))
    so = 0
    for ma in ds_ma:
        try:
            bk = chuyen_trang_thai_booking(ma, TrangThaiBooking.HET_THOI_HAN_DAT_COC,
                                           BenThucHien.HE_THONG, ly_do=LY_DO_HET_HAN_COC)
        except ValidationError:      # người khác vừa đổi trạng thái (vd NAG vừa xác nhận cọc): bỏ qua
            logger.info('xu_ly_het_han_dat_coc: bỏ qua Booking %s (đã đổi trạng thái)', ma)
            continue
        bk = Booking.objects.select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan').get(pk=ma)
        _bao_ca_hai_ben(
            bk, f'Booking #{ma} đã hết thời hạn đặt cọc',
            f'Booking #{ma} đã bị hủy tự động vì quá 1 ngày chưa đặt cọc. Khung giờ đã được trả về lịch trống.',
            f'Booking #{ma} đã hết thời hạn đặt cọc (quá 1 ngày). Khung giờ đã được trả về lịch trống của bạn.',
            gui_email_khach=True)
        so += 1
    return so


# ---------------------------------------------------------------------
# 3. Quá 2 ngày chưa thanh toán 60%
# ---------------------------------------------------------------------
def xu_ly_qua_han_thanh_toan(bay_gio=None):
    """Khoản 'Phần còn lại' đang 'Chờ xác nhận thanh toán', Khách chưa tải minh chứng và Booking đã quá
    HanThanhToanConLai -> khoản thanh toán thành 'Quá hạn thanh toán'. Trạng thái Booking giữ nguyên
    (bảng chuyển của bookings/services.py không có bước nào từ 'Chờ xác nhận thanh toán' sang trạng thái khác)."""
    bay_gio = bay_gio or timezone.now()
    co_minh_chung = MinhChungThanhToan.objects.filter(MaThanhToan=OuterRef('pk'))
    ds_ma = list(ThanhToan.objects.filter(
        LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI, TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_60,
        NgayThanhToan__isnull=True,
        MaBooking__TrangThai=TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN,
        MaBooking__HanThanhToanConLai__lte=bay_gio,
    ).exclude(Exists(co_minh_chung)).values_list('pk', flat=True))
    so = 0
    for ma in ds_ma:
        # UPDATE có điều kiện "vẫn đang chờ": nếu Khách vừa thanh toán thì số dòng = 0 và bỏ qua
        if ThanhToan.objects.filter(pk=ma, TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_60,
                                    NgayThanhToan__isnull=True).update(TrangThai=TrangThaiThanhToan.QUA_HAN) != 1:
            continue
        tt = ThanhToan.objects.select_related('MaBooking__MaKhachHang', 'MaBooking__MaNhiepAnhGia__MaTaiKhoan').get(pk=ma)
        bk = tt.MaBooking
        _bao_ca_hai_ben(
            bk, f'Booking #{bk.pk}: quá hạn thanh toán',
            f'Khoản thanh toán 60% còn lại của Booking #{bk.pk} đã quá hạn (quá 2 ngày). '
            'Vui lòng liên hệ Nhiếp ảnh gia để được hỗ trợ.',
            f'Khách hàng chưa thanh toán 60% còn lại của Booking #{bk.pk} trong 2 ngày, khoản này đã chuyển sang Quá hạn thanh toán.')
        so += 1
    return so


# ---------------------------------------------------------------------
# 4. Ảnh quá 3 ngày sau khi mở quyền tải
# ---------------------------------------------------------------------
def xu_ly_xoa_anh_het_han(bay_gio=None):
    """Bàn giao đã quá ThoiHanTaiAnh (3 ngày kể từ lúc mở quyền tải): xóa file ảnh còn lưu của Booking đó.
    Phần xóa nằm ở delivery/xoa_anh_het_han.py (dùng kho_anh của Nguyên). Trả về số ảnh đã xóa."""
    bay_gio = bay_gio or timezone.now()
    tong = 0
    for bg in BanGiao.objects.filter(ThoiHanTaiAnh__isnull=False, ThoiHanTaiAnh__lte=bay_gio,
                                     MaBooking__anhs__TrangThaiLuuTru=LuuTruAnh.CON_LUU).distinct() \
            .select_related('MaBooking__MaKhachHang', 'MaBooking__MaNhiepAnhGia__MaTaiKhoan'):
        bk = bg.MaBooking
        so = xoa_anh_cua_booking(bk)
        if so:
            tong += so
            gui_thong_bao(bk.MaKhachHang, f'Ảnh Booking #{bk.pk} đã hết hạn tải',
                          f'Đã quá 3 ngày kể từ khi mở quyền tải, {so} ảnh của Booking #{bk.pk} đã được xóa khỏi hệ thống.',
                          booking=bk)
    return tong


# ---------------------------------------------------------------------
# Chạy cả bốn việc
# ---------------------------------------------------------------------
def xu_ly_qua_han():
    """Chạy cả 4 việc quá hạn. Việc nào lỗi thì ghi log rồi chạy tiếp việc sau. Trả về dict số mục đã xử lý."""
    ket_qua = {}
    for ten, ham in (('giu_cho', xu_ly_giu_cho_het_han), ('dat_coc', xu_ly_het_han_dat_coc),
                     ('thanh_toan_60', xu_ly_qua_han_thanh_toan), ('xoa_anh', xu_ly_xoa_anh_het_han)):
        try:
            ket_qua[ten] = ham()
        except Exception:  # noqa: BLE001  # lỗi ở một việc không được làm sập trang web hay các việc khác
            logger.exception('xu_ly_qua_han: việc "%s" bị lỗi', ten)
            ket_qua[ten] = None
    return ket_qua

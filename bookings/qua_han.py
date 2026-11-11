# =====================================================================
# bookings/qua_han.py  -  T10: Tự động xử lý quá hạn
#
#   xu_ly_qua_han()  chạy cả 5 việc dưới đây, mỗi việc độc lập (một việc lỗi không chặn việc khác):
#     1. Giữ chỗ quá 5 phút                -> lượt giữ 'Hết hạn', khung giờ về 'Lịch trống'
#                                             (dùng lại hàm của UC4.1: giai_phong_giu_cho_het_han)
#     2. Quá 1 ngày chưa đặt cọc           -> Booking 'Hết thời hạn đặt cọc', khung giờ về 'Lịch trống'
#     3. Quá 2 ngày chưa thanh toán 60%    -> khoản thanh toán 'Quá hạn thanh toán'
#     4. Ảnh quá 3 ngày sau khi mở quyền tải -> xóa file ảnh, ảnh 'Đã xóa' (phần xóa: delivery/xoa_anh_het_han.py, dùng kho ảnh của Nguyên)
#     5. Quá giờ chụp mà Nhiếp ảnh gia chưa xác nhận -> Booking 'Đã hủy' (Hệ thống tự hủy, không bắt Nhiếp ảnh gia từ chối), khung giờ về 'Lịch trống'
#
#   Được gọi từ 2 nơi:
#     - bookings/middleware.py : mỗi khi mở các trang liên quan (Booking, Tổng quan, Thanh toán, Bàn giao, Tìm kiếm)
#     - lệnh  python manage.py xu_ly_qua_han  : chạy định kỳ (mỗi phút) bằng Task Scheduler / cron
#   Hạn chót lấy từ cột trong database (HanDatCoc, HanThanhToanConLai, ThoiHanTaiAnh) do bookings/services.py gán,
#   nên các con số 1 ngày / 2 ngày / 3 ngày chỉ khai báo một chỗ, không lặp lại ở đây.
# =====================================================================
import logging

from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from bookings.giu_cho import giai_phong_giu_cho_het_han
from bookings.models import Booking
from bookings.services import (SO_NGAY_HAN_DAT_COC, SO_NGAY_HAN_THANH_TOAN_CON_LAI, chuyen_trang_thai_booking,
                               gui_email_sau_commit)
from core.constants import BenThucHien, LoaiThanhToan, LuuTruAnh, TrangThaiBooking, TrangThaiThanhToan
from delivery.models import BanGiao
from delivery.xoa_anh_het_han import xoa_anh_cua_booking
from notifications.services import gui_thong_bao
from payments.models import MinhChungThanhToan, ThanhToan

logger = logging.getLogger(__name__)

LY_DO_HET_HAN_COC = f'Quá {SO_NGAY_HAN_DAT_COC} ngày chưa đặt cọc'   # số ngày lấy từ bookings/services.py
LY_DO_QUA_GIO_CHUP = 'Quá giờ chụp mà Nhiếp ảnh gia chưa xác nhận'   # lý do ghi vào Lịch sử trạng thái khi hệ thống tự hủy


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
    CHỈ miễn hết hạn khi minh chứng cọc đang 'Chờ xác nhận cọc' VÀ Nhiếp ảnh gia chưa yêu cầu bổ sung (LyDoTuChoi rỗng):
    lúc đó Khách đã nộp và đang chờ Nhiếp ảnh gia xem. Nếu Nhiếp ảnh gia đã yêu cầu bổ sung (LyDoTuChoi có giá trị, trạng thái
    giữ nguyên) mà Khách không nộp lại thì vẫn hết hạn bình thường, tránh giữ khung giờ vô thời hạn.
    Lúc Nhiếp ảnh gia yêu cầu bổ sung, payments/services.py đã tính lại HanDatCoc = lúc yêu cầu + 1 ngày,
    nên Khách luôn có đủ 1 ngày để nộp lại (kể cả khi hạn cọc ban đầu đã qua trong lúc chờ Nhiếp ảnh gia xem)."""
    bay_gio = bay_gio or timezone.now()
    da_tai_minh_chung = ThanhToan.objects.filter(
        Q(LyDoTuChoi__isnull=True) | Q(LyDoTuChoi=''),
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
            f'Booking #{ma} đã bị hủy tự động vì quá {SO_NGAY_HAN_DAT_COC} ngày chưa đặt cọc. Khung giờ đã được trả về lịch trống.',
            f'Booking #{ma} đã hết thời hạn đặt cọc (quá {SO_NGAY_HAN_DAT_COC} ngày). Khung giờ đã được trả về lịch trống của bạn.',
            gui_email_khach=True)
        so += 1
    return so


# ---------------------------------------------------------------------
# 3. Quá 2 ngày chưa thanh toán 60%
# ---------------------------------------------------------------------
def xu_ly_qua_han_thanh_toan(bay_gio=None):
    """Khoản 'Phần còn lại' đang 'Chờ xác nhận thanh toán (60%)', Khách chưa tải minh chứng và Booking đã quá
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
            f'Khoản thanh toán 60% còn lại của Booking #{bk.pk} đã quá hạn (quá {SO_NGAY_HAN_THANH_TOAN_CON_LAI} ngày). '
            'Vui lòng liên hệ Nhiếp ảnh gia để được hỗ trợ.',
            f'Khách hàng chưa thanh toán 60% còn lại của Booking #{bk.pk} trong {SO_NGAY_HAN_THANH_TOAN_CON_LAI} ngày, khoản này đã chuyển sang Quá hạn thanh toán.')
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
                          f'Đã hết thời hạn tải ảnh kể từ khi mở quyền tải, {so} ảnh của Booking #{bk.pk} đã được xóa khỏi hệ thống.',
                          booking=bk)
    return tong


# ---------------------------------------------------------------------
# 5. Quá giờ chụp mà Nhiếp ảnh gia chưa xác nhận
# ---------------------------------------------------------------------
# Hàm tự hủy các Booking 'Chờ xác nhận' mà giờ chụp đã trôi qua. Trả về số Booking đã hủy.
def xu_ly_het_han_cho_xac_nhan(bay_gio=None):
    """Booking 'Chờ xác nhận' mà NgayGioChup <= bây giờ (Nhiếp ảnh gia chưa chấp nhận cũng chưa từ chối) -> 'Đã hủy'
    (bên thực hiện = Hệ thống), khung giờ về 'Lịch trống', báo Khách (web + Email) và Nhiếp ảnh gia (web).
    Chưa đặt cọc nên không phát sinh mất / hoàn tiền cọc, và không cần tạo Yêu cầu hủy (UC4.6 chỉ dành cho Booking đã được chấp nhận)."""
    # Không truyền mốc giờ thì lấy giờ hiện tại (test có thể truyền giờ giả để thử).
    bay_gio = bay_gio or timezone.now()
    # Lấy MÃ của các Booking đang 'Chờ xác nhận' mà giờ chụp đã đến hoặc đã qua (chỉ lấy mã, xử lý từng cái bên dưới).
    ds_ma = list(Booking.objects.filter(TrangThai=TrangThaiBooking.CHO_XAC_NHAN, NgayGioChup__lte=bay_gio)
                 .values_list('pk', flat=True))
    # Biến đếm số Booking đã hủy thành công.
    so = 0
    # Xử lý lần lượt từng Booking.
    for ma in ds_ma:
        # Đổi sang 'Đã hủy' bằng hàm DUY NHẤT của nhóm; hàm tự ghi Lịch sử và tự trả slot về 'Lịch trống' (bảng DOI_SLOT).
        try:
            chuyen_trang_thai_booking(ma, TrangThaiBooking.DA_HUY, BenThucHien.HE_THONG, ly_do=LY_DO_QUA_GIO_CHUP)
        # Người khác vừa đổi trạng thái (vd Nhiếp ảnh gia vừa từ chối), hoặc slot không đổi được: bỏ qua Booking này, làm tiếp Booking sau.
        except ValidationError as loi:
            logger.info('xu_ly_het_han_cho_xac_nhan: bỏ qua Booking %s (%s)', ma, ' '.join(loi.messages))
            continue
        # Đọc lại Booking kèm Khách và Nhiếp ảnh gia để gửi thông báo.
        bk = Booking.objects.select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan').get(pk=ma)
        # Đổi giờ chụp (lưu theo giờ quốc tế) sang giờ Việt Nam để ghi vào thông báo.
        gio_chup = timezone.localtime(bk.NgayGioChup)
        # Báo cả hai bên; Khách nhận thêm Email (gui_email_khach=True).
        _bao_ca_hai_ben(
            bk, f'Booking #{ma} đã bị hủy tự động',
            f'Booking #{ma} đã bị hủy tự động vì Nhiếp ảnh gia chưa xác nhận trước giờ chụp ({gio_chup:%H:%M %d/%m/%Y}). '
            'Khung giờ đã được trả về lịch trống, bạn có thể chọn khung giờ khác.',
            f'Booking #{ma} đã quá giờ chụp ({gio_chup:%H:%M %d/%m/%Y}) mà bạn chưa xác nhận nên hệ thống đã tự động hủy. '
            'Khung giờ đã được trả về lịch trống của bạn.',
            gui_email_khach=True)
        # Cộng vào số Booking đã hủy.
        so += 1
    # Trả về tổng số Booking đã hủy.
    return so


# ---------------------------------------------------------------------
# Chạy cả năm việc
# ---------------------------------------------------------------------
def xu_ly_qua_han():
    """Chạy cả 5 việc quá hạn. Việc nào lỗi thì ghi log rồi chạy tiếp việc sau. Trả về dict số mục đã xử lý."""
    ket_qua = {}
    # Danh sách (tên việc, hàm) - thêm ('cho_xac_nhan', ...) là việc thứ 5: tự hủy Booking 'Chờ xác nhận' đã quá giờ chụp.
    for ten, ham in (('giu_cho', xu_ly_giu_cho_het_han), ('dat_coc', xu_ly_het_han_dat_coc),
                     ('cho_xac_nhan', xu_ly_het_han_cho_xac_nhan),
                     ('thanh_toan_60', xu_ly_qua_han_thanh_toan), ('xoa_anh', xu_ly_xoa_anh_het_han)):
        try:
            ket_qua[ten] = ham()
        except Exception:  # noqa: BLE001  # lỗi ở một việc không được làm sập trang web hay các việc khác
            logger.exception('xu_ly_qua_han: việc "%s" bị lỗi', ten)
            ket_qua[ten] = None
    return ket_qua
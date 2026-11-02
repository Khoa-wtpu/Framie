# =====================================================================
# bookings/da_chup.py  -  T8 (Tuyền)
#   Nhiếp ảnh gia bấm "Đã chụp" (TO-BE mục 8.1)
#
# Yêu cầu (task T8):
#   Khi Booking đang "Chốt Booking" và buổi chụp đã diễn ra, Nhiếp ảnh gia bấm "Đã chụp".
#     - Gói "Giới hạn số lượng ảnh": Booking dừng ở "Đã chụp", chờ Nhiếp ảnh gia tải ảnh (Nguyên làm tiếp:
#       tải ảnh xong thì Nguyên đổi sang "Chờ Khách hàng lựa chọn ảnh").
#     - Gói "Hậu kỳ toàn bộ ảnh": Booking đi thẳng sang "Chờ hậu kỳ", không qua bước Khách chọn ảnh.
#
# Quy tắc nhóm: KHÔNG tự gán booking.TrangThai. Đổi trạng thái luôn qua
#   bookings.services.chuyen_trang_thai_booking (tự kiểm tra, tự ghi Lịch sử). Bảng chuyển trạng thái
#   đã có sẵn 2 bước: (Chốt Booking -> Đã chụp) và (Đã chụp -> Chờ hậu kỳ, chỉ gói Hậu kỳ toàn bộ).
#
# File gồm: PHẦN 1 import/hằng số, PHẦN 3 hàm nghiệp vụ, PHẦN 4 view + url
#   (nối vào config/urls.py bằng include('bookings.da_chup')).
# Nút "Đã chụp" nằm trên trang chi tiết của Nhiếp ảnh gia (bookings/nag_chi_tiet.html, view của tiep_nhan.py).
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ
# ---------------------------------------------------------------------
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import chi_nhiep_anh_gia_da_duyet   # chỉ Nhiếp ảnh gia ĐÃ DUYỆT
from bookings.services import chuyen_trang_thai_booking
# XuLyBookingLoi + lay_booking_cua_nag: dùng lại của UC4.3 (Booking của người khác -> "không tìm thấy", BR4.3-1).
from bookings.tiep_nhan import TB_LOI_HE_THONG, XuLyBookingLoi, lay_booking_cua_nag
from core.constants import BenThucHien, LoaiHauKy, TrangThaiBooking

logger = logging.getLogger(__name__)

# Câu thông báo.
TB_SAI_TRANG_THAI = 'Chỉ Booking đang ở trạng thái "Chốt Booking" mới bấm được "Đã chụp".'
TB_CHUA_DEN_GIO_CHUP = 'Buổi chụp chưa diễn ra nên chưa thể bấm "Đã chụp".'
TB_DA_CHUP_GIOI_HAN = 'Đã ghi nhận buổi chụp. Vui lòng tải ảnh lên để Khách hàng lựa chọn ảnh.'
TB_DA_CHUP_TOAN_BO = 'Đã ghi nhận buổi chụp. Booking chuyển sang "Chờ hậu kỳ".'

# Lý do ghi vào Lịch sử ở bước tự nhảy sang "Chờ hậu kỳ" (để Khách / Quản trị viên hiểu vì sao có 2 dòng liên tiếp).
LY_DO_BO_QUA_CHON_ANH = 'Gói Hậu kỳ toàn bộ ảnh: bỏ qua bước Khách hàng chọn ảnh'


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def da_den_gio_chup(booking):
    """Buổi chụp đã diễn ra chưa? Tính từ NgayGioChup (giờ bắt đầu buổi chụp). Muốn đổi sang 'hết khung giờ của slot'
    thì chỉ sửa đúng hàm này (view và template đều gọi qua đây)."""
    return booking.NgayGioChup <= timezone.now()


def co_the_bam_da_chup(booking):
    """Nút 'Đã chụp' có được hiện / có bấm được không: đang 'Chốt Booking' VÀ buổi chụp đã diễn ra."""
    return booking.TrangThai == TrangThaiBooking.CHOT_BOOKING and da_den_gio_chup(booking)


def danh_dau_da_chup(nag_user, ma_booking):
    """Nhiếp ảnh gia bấm 'Đã chụp'. Trả về Booking đã cập nhật.
      - Gói 'Giới hạn số lượng ảnh': Chốt Booking -> Đã chụp (dừng, chờ tải ảnh).
      - Gói 'Hậu kỳ toàn bộ ảnh'  : Chốt Booking -> Đã chụp -> Chờ hậu kỳ (2 dòng Lịch sử, cùng một transaction).
    Báo XuLyBookingLoi khi: không phải Booking của mình (.khong_tim_thay), không ở 'Chốt Booking', buổi chụp chưa
    diễn ra, có người vừa đổi trạng thái trước, hoặc lỗi hệ thống. Lỗi ở đâu thì không đổi gì (kể cả bước đầu)."""
    try:
        with transaction.atomic():
            booking = lay_booking_cua_nag(nag_user, ma_booking)            # BR4.3-1: chỉ Booking của mình
            if booking.TrangThai != TrangThaiBooking.CHOT_BOOKING:
                raise XuLyBookingLoi(TB_SAI_TRANG_THAI)
            if not da_den_gio_chup(booking):
                raise XuLyBookingLoi(TB_CHUA_DEN_GIO_CHUP)
            try:
                # Bước 1: Chốt Booking -> Đã chụp (hàm chung tự ghi Lịch sử).
                cap_nhat = chuyen_trang_thai_booking(booking, TrangThaiBooking.DA_CHUP, BenThucHien.NHIEP_ANH_GIA)
                # Bước 2 (chỉ gói Hậu kỳ toàn bộ): sang thẳng "Chờ hậu kỳ" - hàm chung tự chặn nếu gói không đúng loại.
                if booking.MaGoi.LoaiHauKy == LoaiHauKy.TOAN_BO:
                    cap_nhat = chuyen_trang_thai_booking(
                        cap_nhat, TrangThaiBooking.CHO_HAU_KY, BenThucHien.NHIEP_ANH_GIA, ly_do=LY_DO_BO_QUA_CHON_ANH)
            except ValidationError as loi:
                raise XuLyBookingLoi(' '.join(loi.messages))
    except DatabaseError:
        logger.exception('danh_dau_da_chup: lỗi hệ thống (booking %s)', ma_booking)
        raise XuLyBookingLoi(TB_LOI_HE_THONG)
    return cap_nhat


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
@chi_nhiep_anh_gia_da_duyet
@require_POST          # chỉ nhận POST + CSRF: không thể "Đã chụp" chỉ bằng cách mở một đường link
def da_chup(request, ma_booking):
    """Nút 'Đã chụp' trên trang chi tiết Booking của Nhiếp ảnh gia."""
    try:
        booking = danh_dau_da_chup(request.user, ma_booking)
    except XuLyBookingLoi as loi:
        if loi.khong_tim_thay:
            raise Http404(loi.thong_bao)
        messages.error(request, loi.thong_bao)
        return redirect('chi_tiet_yeu_cau_booking', ma_booking=ma_booking)
    if booking.TrangThai == TrangThaiBooking.CHO_HAU_KY:
        messages.success(request, TB_DA_CHUP_TOAN_BO)
    else:
        messages.success(request, TB_DA_CHUP_GIOI_HAN)
    return redirect('chi_tiet_yeu_cau_booking', ma_booking=ma_booking)


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.da_chup')),)
urlpatterns = [
    path('quan-ly/<int:ma_booking>/da-chup/', da_chup, name='da_chup_booking'),
]

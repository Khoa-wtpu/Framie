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
import logging  # thư viện ghi log của Python

from django.contrib import messages  # hệ thống thông báo nhỏ hiện trên đầu trang (xanh = thành công, đỏ = lỗi)
from django.core.exceptions import ValidationError  # loại lỗi mà chuyen_trang_thai_booking báo khi chuyển sai luật
from django.db import DatabaseError, transaction  # DatabaseError: lỗi cơ sở dữ liệu; transaction: "làm hết hoặc không làm gì"
from django.http import Http404  # lỗi "không tìm thấy trang" (404)
from django.shortcuts import redirect  # chuyển người dùng sang một trang khác
from django.urls import path  # khai báo địa chỉ URL
from django.utils import timezone  # lấy giờ hiện tại có múi giờ
from django.views.decorators.http import require_POST  # nhãn: chỉ nhận POST (gửi form), chặn GET

from accounts.permissions import chi_nhiep_anh_gia_da_duyet   # nhãn: chỉ Nhiếp ảnh gia ĐÃ DUYỆT mới vào được
from bookings.services import chuyen_trang_thai_booking  # hàm DUY NHẤT của nhóm để đổi trạng thái Booking
# XuLyBookingLoi + lay_booking_cua_nag: dùng lại của UC4.3 (Booking của người khác -> "không tìm thấy", BR4.3-1).
from bookings.tiep_nhan import TB_LOI_HE_THONG, XuLyBookingLoi, lay_booking_cua_nag  # câu lỗi hệ thống, loại lỗi nghiệp vụ, hàm lấy Booking của chính NAG
from core.constants import BenThucHien, LoaiHauKy, TrangThaiBooking  # tên bên thực hiện / loại hậu kỳ / trạng thái dùng chung

logger = logging.getLogger(__name__)  # "cây bút ghi log" mang tên file này

# Câu thông báo.
TB_SAI_TRANG_THAI = 'Chỉ Booking đang ở trạng thái "Chốt Booking" mới bấm được "Đã chụp".'  # báo khi Booking không ở "Chốt Booking"
TB_CHUA_DEN_GIO_CHUP = 'Buổi chụp chưa diễn ra nên chưa thể bấm "Đã chụp".'  # báo khi chưa tới giờ chụp
TB_DA_CHUP_GIOI_HAN = 'Đã ghi nhận buổi chụp. Vui lòng tải ảnh lên để Khách hàng lựa chọn ảnh.'  # thành công với gói Giới hạn số lượng ảnh
TB_DA_CHUP_TOAN_BO = 'Đã ghi nhận buổi chụp. Booking chuyển sang "Chờ hậu kỳ".'  # thành công với gói Hậu kỳ toàn bộ ảnh

# Lý do ghi vào Lịch sử ở bước tự nhảy sang "Chờ hậu kỳ" (để Khách / Quản trị viên hiểu vì sao có 2 dòng liên tiếp).
LY_DO_BO_QUA_CHON_ANH = 'Gói Hậu kỳ toàn bộ ảnh: bỏ qua bước Khách hàng chọn ảnh'  # chữ ghi vào cột "Lý do" của lịch sử


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def da_den_gio_chup(booking):  # buổi chụp đã diễn ra chưa (nút hiện và việc bấm đều dùng hàm này)
    """Buổi chụp đã diễn ra chưa? Tính từ NgayGioChup (giờ bắt đầu buổi chụp). Muốn đổi sang 'hết khung giờ của slot'
    thì chỉ sửa đúng hàm này (view và template đều gọi qua đây)."""
    return booking.NgayGioChup <= timezone.now()  # True nếu giờ chụp <= bây giờ (đã tới hoặc đã qua)


def co_the_bam_da_chup(booking):  # nút Đã chụp có bấm được không
    """Nút 'Đã chụp' có được hiện / có bấm được không: đang 'Chốt Booking' VÀ buổi chụp đã diễn ra."""
    return booking.TrangThai == TrangThaiBooking.CHOT_BOOKING and da_den_gio_chup(booking)  # phải thỏa CẢ HAI điều kiện


def danh_dau_da_chup(nag_user, ma_booking):  # service: đánh dấu Đã chụp, đổi trạng thái qua hàm chung
    """Nhiếp ảnh gia bấm 'Đã chụp'. Trả về Booking đã cập nhật.
      - Gói 'Giới hạn số lượng ảnh': Chốt Booking -> Đã chụp (dừng, chờ tải ảnh).
      - Gói 'Hậu kỳ toàn bộ ảnh'  : Chốt Booking -> Đã chụp -> Chờ hậu kỳ (2 dòng Lịch sử, cùng một transaction).
    Báo XuLyBookingLoi khi: không phải Booking của mình (.khong_tim_thay), không ở 'Chốt Booking', buổi chụp chưa
    diễn ra, có người vừa đổi trạng thái trước, hoặc lỗi hệ thống. Lỗi ở đâu thì không đổi gì (kể cả bước đầu)."""
    try:  # khối bắt lỗi cơ sở dữ liệu (xem except DatabaseError ở dưới)
        with transaction.atomic():  # mọi thay đổi bên trong: hoặc thành công hết, hoặc hủy hết nếu có lỗi
            booking = lay_booking_cua_nag(nag_user, ma_booking)            # lấy Booking; của Nhiếp ảnh gia khác -> báo "không tìm thấy" (BR4.3-1)
            if booking.TrangThai != TrangThaiBooking.CHOT_BOOKING:  # Booking không ở "Chốt Booking"
                raise XuLyBookingLoi(TB_SAI_TRANG_THAI)  # dừng, báo lỗi
            if not da_den_gio_chup(booking):  # chưa tới giờ chụp
                raise XuLyBookingLoi(TB_CHUA_DEN_GIO_CHUP)  # dừng, báo lỗi
            try:  # khối bắt lỗi "chuyển trạng thái sai luật" của hàm chung
                # Bước 1: Chốt Booking -> Đã chụp (hàm chung tự ghi Lịch sử).
                cap_nhat = chuyen_trang_thai_booking(booking, TrangThaiBooking.DA_CHUP, BenThucHien.NHIEP_ANH_GIA)  # đổi sang "Đã chụp", bên thực hiện = Nhiếp ảnh gia
                # Bước 2 (chỉ gói Hậu kỳ toàn bộ): sang thẳng "Chờ hậu kỳ" - hàm chung tự chặn nếu gói không đúng loại.
                if booking.MaGoi.LoaiHauKy == LoaiHauKy.TOAN_BO:  # gói là "Hậu kỳ toàn bộ ảnh"
                    cap_nhat = chuyen_trang_thai_booking(  # đổi tiếp sang "Chờ hậu kỳ"
                        cap_nhat, TrangThaiBooking.CHO_HAU_KY, BenThucHien.NHIEP_ANH_GIA, ly_do=LY_DO_BO_QUA_CHON_ANH)  # kèm lý do để ghi vào lịch sử
            except ValidationError as loi:  # hàm chung từ chối vì sai luật chuyển trạng thái
                raise XuLyBookingLoi(' '.join(loi.messages))  # đổi thành lỗi nghiệp vụ, nối các câu lỗi lại
    except DatabaseError:  # cơ sở dữ liệu gặp sự cố
        logger.exception('danh_dau_da_chup: lỗi hệ thống (booking %s)', ma_booking)  # ghi log chi tiết cho lập trình viên
        raise XuLyBookingLoi(TB_LOI_HE_THONG)  # báo người dùng câu lỗi chung, dễ hiểu
    return cap_nhat  # trả về Booking sau khi đã cập nhật


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
@chi_nhiep_anh_gia_da_duyet  # chỉ Nhiếp ảnh gia đã duyệt
@require_POST          # chỉ nhận POST + CSRF: không thể "Đã chụp" chỉ bằng cách mở một đường link
def da_chup(request, ma_booking):  # view: nhận POST từ nút Đã chụp
    """Nút 'Đã chụp' trên trang chi tiết Booking của Nhiếp ảnh gia."""
    try:  # thử thực hiện
        booking = danh_dau_da_chup(request.user, ma_booking)  # gọi service ở trên
    except XuLyBookingLoi as loi:  # service báo lỗi nghiệp vụ
        if loi.khong_tim_thay:  # lỗi kiểu "Booking này không phải của bạn / không tồn tại"
            raise Http404(loi.thong_bao)  # trả trang 404, không tiết lộ Booking có tồn tại
        messages.error(request, loi.thong_bao)  # lỗi khác: hiện thông báo đỏ
        return redirect('chi_tiet_booking', ma_booking=ma_booking)  # quay lại trang chi tiết Booking chung
    if booking.TrangThai == TrangThaiBooking.CHO_HAU_KY:  # Booking đã nhảy sang "Chờ hậu kỳ" (gói Hậu kỳ toàn bộ)
        messages.success(request, TB_DA_CHUP_TOAN_BO)  # thông báo xanh tương ứng
    else:  # còn lại: gói Giới hạn, dừng ở "Đã chụp"
        messages.success(request, TB_DA_CHUP_GIOI_HAN)  # thông báo xanh: nhớ tải ảnh lên
    return redirect('chi_tiet_booking', ma_booking=ma_booking)  # quay lại trang chi tiết Booking chung (tránh gửi lại form khi F5)


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.da_chup')),)
urlpatterns = [  # danh sách địa chỉ của file này
    path('quan-ly/<int:ma_booking>/da-chup/', da_chup, name='da_chup_booking'),  # /bookings/quan-ly/7/da-chup/ -> bấm "Đã chụp" cho Booking số 7
]

# =====================================================================
# bookings/huy_booking.py  -  T9 (Tuyền)
#   UC4.6 Yêu cầu hủy Booking  (+ Khách hàng xác nhận đã nhận lại tiền cọc)
#
# Yêu cầu (đặc tả UC4.6 + task T9):
#   - Khách hàng hủy được khi Booking đang "Chờ xác nhận" (rút yêu cầu trước khi Nhiếp ảnh gia phản hồi - C1),
#     "Chờ đặt cọc" hoặc "Chốt Booking". Nhiếp ảnh gia hủy được khi "Chờ đặt cọc" hoặc "Chốt Booking" (C3/C4);
#     lúc "Chờ xác nhận" Nhiếp ảnh gia dùng "Từ chối" (UC4.5) chứ không "Hủy".
#     Từ "Đã chụp" trở đi (và các trạng thái khác) KHÔNG hủy được.
#   - Bắt buộc nhập lý do ("Vui lòng nhập lý do hủy"), có bước xác nhận (trang xác nhận rồi mới hủy).
#   - Booking -> "Đã hủy", slot trả về "Lịch trống" (cả hai việc do chuyen_trang_thai_booking làm).
#   - Ghi bảng YEUCAUHUY: bên hủy, lý do, trạng thái lúc hủy, xử lý tiền cọc:
#       Chờ xác nhận (chỉ Khách)         -> Không phát sinh   (Nhiếp ảnh gia chưa chấp nhận, chưa có cọc)
#       Chờ đặt cọc                      -> Không phát sinh   (chưa có tiền cọc)
#       Chốt Booking + Khách hủy         -> Mất cọc           (mất 40%)
#       Chốt Booking + Nhiếp ảnh gia hủy -> Hoàn cọc, "Chờ hoàn tiền"
#   - "Hoàn cọc": khi Khách bấm xác nhận đã nhận lại tiền -> "Đã hoàn tiền" (+ thời điểm xác nhận).
#   - FRAMIE không giữ / thu / hoàn tiền (BR4.6-5): chỉ ghi nhận và theo dõi trạng thái.
#   - Thông báo web + Email cho cả hai bên.
#
# Quy tắc nhóm: KHÔNG tự gán booking.TrangThai. Đổi trạng thái luôn qua
#   bookings.services.chuyen_trang_thai_booking (bảng chuyển đã có sẵn 2 bước ... -> Đã hủy).
#
# File gồm: PHẦN 1 import/hằng số, PHẦN 2 form, PHẦN 3 hàm nghiệp vụ, PHẦN 4 view + url
#   (nối vào config/urls.py bằng include('bookings.huy_booking')).
# Nút "Hủy Booking" nằm ở trang chi tiết dùng chung của Khách / Nhiếp ảnh gia (bookings/theo_doi.py)
#   và ở trang xử lý của Nhiếp ảnh gia (bookings/nag_chi_tiet.html).
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ
# ---------------------------------------------------------------------
import logging  # thư viện ghi log có sẵn của Python (ghi lỗi kỹ thuật cho lập trình viên)

from django import forms  # công cụ tạo form (ô nhập liệu + kiểm tra dữ liệu)
from django.contrib import messages  # hệ thống "thông báo nhanh" hiện một lần trên đầu trang (xanh/đỏ)
from django.core.exceptions import ValidationError  # loại lỗi "dữ liệu không hợp lệ" của Django
from django.db import DatabaseError, transaction  # DatabaseError: lỗi CSDL; transaction: gói nhiều thao tác thành "một khối"
from django.http import Http404  # lỗi "không tìm thấy trang" (mã 404)
from django.shortcuts import redirect, render  # redirect: chuyển sang trang khác; render: dựng trang HTML từ template
from django.urls import path  # khai báo một địa chỉ (URL) trong urlpatterns
from django.utils import timezone  # lấy giờ hiện tại có múi giờ
from django.views.decorators.http import require_http_methods, require_POST  # nhãn giới hạn kiểu yêu cầu (GET/POST) được nhận

from accounts.permissions import lay_vai_tro, vai_tro_required  # lay_vai_tro: biết vai trò người dùng; vai_tro_required: nhãn chặn sai vai trò
from bookings.models import Booking, YeuCauHuy  # hai bảng dữ liệu: Booking và Yêu cầu hủy
from bookings.services import DO_DAI_LY_DO_TOI_DA, chuyen_trang_thai_booking, gui_email_sau_commit  # độ dài lý do tối đa / hàm đổi trạng thái chung / hàm gửi email sau khi lưu xong
# Dùng lại của UC4.3 - 4.5: loại lỗi nghiệp vụ, câu lỗi chung, định dạng tiền / tên / mô tả buổi chụp, gửi thông báo + Email.
from bookings.tiep_nhan import (TB_LOI_HE_THONG, XuLyBookingLoi, _mo_ta_booking, _ten_hien_thi,  # câu lỗi hệ thống / loại lỗi nghiệp vụ / mô tả buổi chụp / tên hiển thị
                                _thong_bao_khach, _tien)  # gửi thông báo cho Khách / định dạng tiền kiểu 1.500.000
from core.constants import BenThucHien, LoaiThanhToan, TrangThaiBooking, TrangThaiThanhToan, VaiTro  # các hằng số dùng chung: bên thực hiện, loại thanh toán, trạng thái Booking, vai trò
from core.constants import TrangThaiHoanTien as HangSoHoanTien      # cùng cách đặt tên với bookings/models.py
from core.constants import XuLyTienCoc as HangSoXuLyTienCoc  # hằng số cách xử lý tiền cọc, đặt tên ngắn lại cho dễ gọi
from notifications.services import gui_thong_bao  # hàm tạo một thông báo web cho người nhận
from payments.models import ThanhToan, tinh_so_tien  # ThanhToan: tìm minh chứng cọc đang chờ; hàm chia tiền 40% / 60% duy nhất của dự án

logger = logging.getLogger(__name__)  # tạo "cây bút ghi log" mang tên file này

# Trạng thái được hủy (BR4.6-1) tùy BÊN hủy. Từ "Đã chụp" trở đi, hoặc đã kết thúc, đều không hủy được.
TRANG_THAI_HUY_DUOC_NAG = (TrangThaiBooking.CHO_DAT_COC, TrangThaiBooking.CHOT_BOOKING)  # Nhiếp ảnh gia: chỉ sau khi đã chấp nhận (lúc chờ xác nhận thì dùng "Từ chối")
TRANG_THAI_HUY_DUOC_KHACH = (TrangThaiBooking.CHO_XAC_NHAN,) + TRANG_THAI_HUY_DUOC_NAG  # Khách: thêm "Chờ xác nhận" (rút yêu cầu)
TRANG_THAI_HUY_DUOC = TRANG_THAI_HUY_DUOC_KHACH  # hợp của hai bên (giữ tên cũ cho nơi khác import)

# Vai trò -> bên thực hiện ghi vào Lịch sử / YeuCauHuy. Vai trò khác (Quản trị viên) không có quyền hủy.
BEN_THEO_VAI_TRO = {VaiTro.KHACH_HANG: BenThucHien.KHACH_HANG,  # vai trò Khách hàng -> bên hủy là "Khách hàng"
                    VaiTro.NHIEP_ANH_GIA: BenThucHien.NHIEP_ANH_GIA}  # vai trò Nhiếp ảnh gia -> bên hủy là "Nhiếp ảnh gia"

# Câu thông báo.
TB_THIEU_LY_DO = 'Vui lòng nhập lý do hủy'                        # UC4.6, ngoại lệ 4a
TB_KHONG_THE_HUY = ('Chỉ Booking đang ở trạng thái "Chờ đặt cọc" hoặc "Chốt Booking" mới hủy được. '  # câu báo (Nhiếp ảnh gia) khi Booking không ở trạng thái được hủy (nửa đầu)
                    'Từ "Đã chụp" trở đi Booking không thể hủy.')  # (nửa sau của cùng câu)
TB_KHONG_THE_HUY_KHACH = ('Chỉ Booking đang ở trạng thái "Chờ xác nhận", "Chờ đặt cọc" hoặc "Chốt Booking" mới hủy được. '  # câu báo (Khách hàng): có thêm "Chờ xác nhận"
                          'Từ "Đã chụp" trở đi Booking không thể hủy.')  # nửa sau của cùng câu
# Hủy khi đang "Chờ đặt cọc" nhưng đã có minh chứng cọc chờ xác nhận: vẫn cho hủy, XuLyTienCoc giữ "Không phát sinh", chỉ đổi câu hiển thị.
TB_MINH_CHUNG_DANG_CHO_KHACH = ('Booking có minh chứng cọc đang chờ xác nhận. '
                                'Nếu bạn đã chuyển khoản, hãy liên hệ Nhiếp ảnh gia để xử lý hoàn tiền.')
TB_MINH_CHUNG_DANG_CHO_NAG = ('Booking có minh chứng cọc đang chờ xác nhận. '
                              'Nếu Khách hàng đã chuyển khoản, hãy liên hệ Khách hàng để xử lý hoàn tiền.')
TB_DA_HUY = 'Đã hủy Booking và trả khung giờ về lịch trống.'  # câu báo hủy thành công
TB_KHONG_CO_HOAN_COC = 'Booking này không có khoản cọc nào cần hoàn lại.'  # câu báo khi bấm xác nhận hoàn tiền nhưng không có khoản nào để hoàn
TB_DA_XAC_NHAN_HOAN_TIEN = 'Bạn đã xác nhận nhận lại tiền cọc của Booking này rồi.'  # câu báo khi bấm xác nhận lần thứ hai
TB_XAC_NHAN_HOAN_TIEN_XONG = 'Đã ghi nhận bạn đã nhận lại tiền cọc.'  # câu báo xác nhận hoàn tiền thành công


# ---------------------------------------------------------------------
# PHẦN 2: FORM NHẬP LÝ DO HỦY
# ---------------------------------------------------------------------
class HuyForm(forms.Form):  # form chỉ có đúng một ô: lý do hủy
    """UC4.6 bước 3-4. Lý do tối đa 255 ký tự vì cột LyDo của Lịch sử trạng thái chỉ chứa 255.
    Toàn dấu cách cũng tính là chưa nhập."""
    ly_do = forms.CharField(  # ô nhập chữ tên "ly_do"
        max_length=DO_DAI_LY_DO_TOI_DA, label='Lý do hủy',  # giới hạn 255 ký tự; nhãn hiện cạnh ô
        widget=forms.Textarea(attrs={'rows': 4, 'maxlength': DO_DAI_LY_DO_TOI_DA}),  # hiển thị dạng khung nhiều dòng (4 dòng), trình duyệt cũng chặn gõ quá dài
        error_messages={'required': TB_THIEU_LY_DO,  # để trống -> hiện câu "Vui lòng nhập lý do hủy"
                        'max_length': f'Lý do tối đa {DO_DAI_LY_DO_TOI_DA} ký tự.'})  # gõ quá dài -> hiện câu báo giới hạn


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def lay_booking_cua_ben(user, vai_tro, ma_booking):  # hàm lấy Booking theo đúng phạm vi của người dùng
    """'Cửa ngõ' lấy Booking của UC4.6: Khách chỉ thấy Booking mình đặt, Nhiếp ảnh gia chỉ thấy Booking gửi đến mình.
    Của người khác / không tồn tại -> XuLyBookingLoi(khong_tim_thay) để view trả 404 (không lộ là có tồn tại)."""
    if vai_tro == VaiTro.KHACH_HANG:  # nếu là Khách hàng
        goc = Booking.objects.filter(MaKhachHang=user)  # chỉ lấy Booking do chính khách này đặt
    elif vai_tro == VaiTro.NHIEP_ANH_GIA:  # nếu là Nhiếp ảnh gia
        goc = Booking.objects.filter(MaNhiepAnhGia__MaTaiKhoan=user)  # chỉ lấy Booking gửi tới chính nhiếp ảnh gia này
    else:  # vai trò khác (Quản trị viên...)
        goc = Booking.objects.none()  # không cho thấy Booking nào
    booking = (goc.select_related('MaKhachHang', 'MaGoi__MaLoaiHinh', 'MaLich', 'MaNhiepAnhGia__MaTaiKhoan')  # nạp sẵn các bảng liên quan trong 1 lần truy vấn cho nhanh
               .filter(pk=ma_booking).first())  # lọc đúng mã Booking, lấy dòng đầu tiên (không có thì None)
    if booking is None:  # không tìm thấy (không tồn tại hoặc của người khác)
        raise XuLyBookingLoi('Không tìm thấy Booking.', khong_tim_thay=True)  # ném lỗi, gắn cờ "không tìm thấy" để view trả 404
    return booking  # trả Booking tìm được


def trang_thai_huy_duoc(ben):  # bộ trạng thái được hủy của MỘT bên
    """Khách hàng -> 3 trạng thái (có 'Chờ xác nhận'); Nhiếp ảnh gia -> 2 trạng thái; bên khác/None -> hợp của hai bên."""
    if ben == BenThucHien.NHIEP_ANH_GIA:  # Nhiếp ảnh gia
        return TRANG_THAI_HUY_DUOC_NAG  # không hủy lúc "Chờ xác nhận" (đã có nút Từ chối)
    if ben == BenThucHien.KHACH_HANG:  # Khách hàng
        return TRANG_THAI_HUY_DUOC_KHACH  # được rút yêu cầu lúc "Chờ xác nhận"
    return TRANG_THAI_HUY_DUOC  # không rõ bên: dùng bộ hợp


def thong_bao_khong_the_huy(ben):  # câu báo lỗi đúng với bên hủy
    """Câu 'không hủy được' đúng với bên đang thao tác."""
    return TB_KHONG_THE_HUY_KHACH if ben == BenThucHien.KHACH_HANG else TB_KHONG_THE_HUY  # Khách có thêm 'Chờ xác nhận'


def co_the_huy(booking, ben=None):  # kiểm tra Booking này có hủy được không (theo bên hủy)
    """Nút 'Hủy Booking' có được hiện / bấm được không. ben = BenThucHien.KHACH_HANG / NHIEP_ANH_GIA (None = hợp hai bên)."""
    return booking.TrangThai in trang_thai_huy_duoc(ben)  # True nếu trạng thái hiện tại nằm trong bộ cho phép của bên này


def xac_dinh_xu_ly_tien_coc(trang_thai_luc_huy, ben):  # quyết định hệ quả tiền cọc
    """Hệ quả tiền cọc theo BR4.6-2/3/4 (khớp các CHECK trong bảng YEUCAUHUY)."""
    if trang_thai_luc_huy in (TrangThaiBooking.CHO_XAC_NHAN, TrangThaiBooking.CHO_DAT_COC):      # chưa có khoản cọc nào
        return HangSoXuLyTienCoc.KHONG_PHAT_SINH  # chưa cọc -> không phát sinh mất/hoàn tiền
    if ben == BenThucHien.KHACH_HANG:                           # đã chốt (đã cọc) và Khách hủy
        return HangSoXuLyTienCoc.MAT_COC  # Khách hủy sau khi cọc -> mất cọc
    return HangSoXuLyTienCoc.HOAN_COC                           # đã chốt (đã cọc) và Nhiếp ảnh gia hủy


def co_minh_chung_coc_dang_cho(booking):  # Khách đã tải minh chứng cọc mà Nhiếp ảnh gia chưa xác nhận?
    """True khi Booking có khoản cọc đang 'Chờ xác nhận thanh toán cọc' (Khách đã tải minh chứng, có thể đã chuyển khoản).
    Khoản ThanhToan chỉ được tạo khi Khách tải minh chứng đầu tiên. Tính cả trường hợp Nhiếp ảnh gia đã yêu cầu bổ sung
    (LyDoTuChoi có giá trị): Khách vẫn có thể đã chuyển tiền, nên vẫn cảnh báo."""
    return ThanhToan.objects.filter(MaBooking=booking, LoaiThanhToan=LoaiThanhToan.TIEN_COC,
                                    TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_COC).exists()


def mo_ta_hau_qua(booking, ben):  # tạo câu giải thích hệ quả để hiện trước khi hủy
    """Câu giải thích hệ quả của việc hủy, hiện ở trang xác nhận (UC4.6 bước 3)."""
    xu_ly = xac_dinh_xu_ly_tien_coc(booking.TrangThai, ben)  # xác định hệ quả tiền cọc theo trạng thái hiện tại và bên hủy
    coc = _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC))  # tính số tiền cọc 40% rồi định dạng 1.500.000
    if xu_ly == HangSoXuLyTienCoc.KHONG_PHAT_SINH and co_minh_chung_coc_dang_cho(booking):  # chưa chốt cọc nhưng Khách đã tải minh chứng
        return TB_MINH_CHUNG_DANG_CHO_KHACH if ben == BenThucHien.KHACH_HANG else TB_MINH_CHUNG_DANG_CHO_NAG
    if xu_ly == HangSoXuLyTienCoc.KHONG_PHAT_SINH:  # trường hợp chưa cọc
        return 'Booking chưa đặt cọc nên việc hủy không phát sinh mất hoặc hoàn tiền cọc.'  # câu giải thích cho trường hợp chưa cọc
    if xu_ly == HangSoXuLyTienCoc.MAT_COC:  # trường hợp Khách hủy sau khi cọc
        return f'Booking đã được đặt cọc: nếu bạn hủy, bạn sẽ mất 40% tiền cọc ({coc} VNĐ).'  # câu cảnh báo mất cọc, kèm số tiền
    return (f'Booking đã được đặt cọc: nếu bạn hủy, bạn có trách nhiệm hoàn lại 40% tiền cọc ({coc} VNĐ) cho Khách hàng. '  # trường hợp còn lại: Nhiếp ảnh gia hủy -> phải hoàn cọc (nửa đầu câu)
            'FRAMIE không trực tiếp hoàn tiền, chỉ ghi nhận và theo dõi việc hoàn tiền.')  # nhắc FRAMIE không giữ tiền (nửa sau câu)


def lay_yeu_cau_huy(booking):  # lấy yêu cầu hủy của một Booking
    """Yêu cầu hủy của Booking, hoặc None nếu Booking chưa bị hủy (booking.yeu_cau_huy báo lỗi khi chưa có)."""
    return YeuCauHuy.objects.filter(MaBooking=booking).first()  # tìm yêu cầu hủy theo Booking; không có thì trả None


def co_the_xac_nhan_hoan_tien(yeu_cau):  # kiểm tra có hiện nút "Tôi đã nhận lại tiền cọc" không
    """Khách có được bấm 'Tôi đã nhận lại tiền cọc' không: chỉ khi đang 'Chờ hoàn tiền'."""
    return yeu_cau is not None and yeu_cau.TrangThaiHoanTien == HangSoHoanTien.CHO_HOAN_TIEN  # có yêu cầu hủy VÀ đang ở "Chờ hoàn tiền"


def _noi_dung_huy(booking, ten_ben, ly_do, xu_ly, co_minh_chung=False, cho_nag=False):  # dựng nội dung thông báo hủy
    """Nội dung thông báo web + Email gửi cho cả hai bên. co_minh_chung = lúc hủy có minh chứng cọc đang chờ xác nhận
    (chỉ xảy ra khi hủy ở 'Chờ đặt cọc'); cho_nag = nội dung gửi Nhiếp ảnh gia (câu về minh chứng đổi cho đúng người đọc)."""
    coc = _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC))  # số tiền cọc 40%, định dạng kiểu Việt Nam
    noi_dung = (f'{ten_ben} đã hủy Booking #{booking.pk} ({_mo_ta_booking(booking)}). Lý do: {ly_do}. '  # phần chung: ai hủy, Booking nào, lý do (nửa đầu)
                'Khung giờ đã được trả về lịch trống.')  # phần chung: khung giờ đã trả về lịch trống (nửa sau)
    if xu_ly == HangSoXuLyTienCoc.KHONG_PHAT_SINH and co_minh_chung:  # chưa chốt cọc nhưng Khách đã tải minh chứng
        noi_dung += ' ' + (TB_MINH_CHUNG_DANG_CHO_NAG if cho_nag else TB_MINH_CHUNG_DANG_CHO_KHACH)  # nối câu cảnh báo minh chứng đang chờ
    elif xu_ly == HangSoXuLyTienCoc.KHONG_PHAT_SINH:  # chưa cọc
        noi_dung += ' Booking chưa đặt cọc nên không phát sinh mất hoặc hoàn tiền cọc.'  # nối thêm câu về tiền cọc: không phát sinh
    elif xu_ly == HangSoXuLyTienCoc.MAT_COC:  # Khách hủy sau khi cọc
        noi_dung += f' Khách hàng mất 40% tiền cọc ({coc} VNĐ).'  # nối thêm câu: Khách mất cọc
    else:  # Nhiếp ảnh gia hủy sau khi cọc
        noi_dung += (f' Nhiếp ảnh gia có trách nhiệm hoàn lại 40% tiền cọc ({coc} VNĐ) cho Khách hàng. '  # nối thêm câu: Nhiếp ảnh gia phải hoàn cọc (nửa đầu)
                     'FRAMIE không trực tiếp hoàn tiền; Khách hàng vui lòng xác nhận trên hệ thống khi đã nhận lại tiền.')  # nhắc Khách xác nhận khi đã nhận tiền (nửa sau)
    return noi_dung  # trả nội dung hoàn chỉnh


def huy_booking(user, ma_booking, ly_do):  # hàm chính: thực hiện hủy Booking
    """UC4.6 bước 4-11. Trả về Booking đã hủy.
    Báo XuLyBookingLoi khi: thiếu lý do (4a), lý do quá dài, không phải Booking của mình (.khong_tim_thay),
    Booking không ở 'Chờ đặt cọc' / 'Chốt Booking', có người vừa đổi trạng thái trước, hoặc lỗi hệ thống.
    Mọi thứ nằm trong MỘT transaction: lỗi ở đâu thì không đổi gì (Booking, slot, Lịch sử, Yêu cầu hủy, thông báo)."""
    vai_tro = lay_vai_tro(user)  # biết người đang hủy là Khách hay Nhiếp ảnh gia...
    ben = BEN_THEO_VAI_TRO.get(vai_tro)  # đổi vai trò thành "bên thực hiện"; vai trò lạ -> None
    if ben is None:                                                   # Quản trị viên hoặc vai trò khác
        raise XuLyBookingLoi('Không tìm thấy Booking.', khong_tim_thay=True)  # không có quyền hủy -> coi như không thấy Booking (404)
    ly_do = (ly_do or '').strip()  # bỏ khoảng trắng thừa hai đầu; None -> chuỗi rỗng
    if not ly_do:                                                     # ngoại lệ 4a
        raise XuLyBookingLoi(TB_THIEU_LY_DO)  # chưa nhập lý do -> báo lỗi
    if len(ly_do) > DO_DAI_LY_DO_TOI_DA:  # lý do dài quá giới hạn
        raise XuLyBookingLoi(f'Lý do tối đa {DO_DAI_LY_DO_TOI_DA} ký tự.')  # báo lỗi quá dài

    try:  # bắt lỗi cơ sở dữ liệu ở khối bên dưới
        with transaction.atomic():  # mở transaction: hoặc thành công TẤT CẢ, hoặc hoàn tác TẤT CẢ
            booking = lay_booking_cua_ben(user, vai_tro, ma_booking)  # lấy Booking của người này (của người khác -> lỗi 404)
            # KHÓA dòng Booking rồi mới đọc TrangThai: nếu Nhiếp ảnh gia vừa xác nhận cọc đúng lúc Khách hủy thì ta phải thấy
            # 'Chốt Booking' (mất cọc) chứ không phải bản 'Chờ đặt cọc' cũ. Từ đây trạng thái không đổi cho tới hết transaction.
            Booking.objects.select_for_update().filter(pk=booking.pk).first()   # chỉ để khóa dòng (người khác phải chờ)
            booking.refresh_from_db(fields=['TrangThai'])                       # đọc lại trạng thái mới nhất SAU khi khóa
            if not co_the_huy(booking, ben):                          # tiền điều kiện của UC4.6 (kiểm tra trên trạng thái mới nhất, theo bên hủy)
                raise XuLyBookingLoi(thong_bao_khong_the_huy(ben))  # trạng thái không cho hủy -> báo lỗi đúng với bên hủy
            trang_thai_luc_huy = booking.TrangThai  # nhớ lại trạng thái TRƯỚC khi hủy (để ghi vào Yêu cầu hủy)
            xu_ly = xac_dinh_xu_ly_tien_coc(trang_thai_luc_huy, ben)  # xác định hệ quả tiền cọc
            co_minh_chung = (xu_ly == HangSoXuLyTienCoc.KHONG_PHAT_SINH and co_minh_chung_coc_dang_cho(booking))  # có minh chứng cọc đang chờ?
            try:  # bắt lỗi do bảng chuyển trạng thái từ chối
                # Hàm chung: kiểm tra bước chuyển, ghi Lịch sử (bên hủy + lý do), trả slot về 'Lịch trống',
                # và chặn trường hợp hai người cùng đổi một lúc.
                cap_nhat = chuyen_trang_thai_booking(booking, TrangThaiBooking.DA_HUY, ben, ly_do=ly_do)  # đổi Booking sang "Đã hủy" qua hàm chung của nhóm
            except ValidationError as loi:  # hàm chung từ chối (vd: có người vừa đổi trạng thái trước)
                raise XuLyBookingLoi(' '.join(loi.messages))  # đổi lỗi đó thành lỗi nghiệp vụ, ghép các câu lại
            YeuCauHuy.objects.create(                                 # bước 9: ghi bên hủy, lý do, hệ quả tiền cọc
                MaBooking=booking, BenYeuCau=ben, LyDo=ly_do,  # Booking nào, bên nào hủy, lý do gì
                TrangThaiBookingLucHuy=trang_thai_luc_huy, XuLyTienCoc=xu_ly)   # 'Hoàn cọc' tự mặc định 'Chờ hoàn tiền'
            # Bước 10-11: thông báo web + Email cho CẢ HAI bên (Email gửi sau khi commit).
            ten_ben = _ten_hien_thi(user)  # tên người hủy để đưa vào nội dung thông báo
            noi_dung = _noi_dung_huy(booking, ten_ben, ly_do, xu_ly, co_minh_chung)  # nội dung gửi Khách
            noi_dung_nag = _noi_dung_huy(booking, ten_ben, ly_do, xu_ly, co_minh_chung, cho_nag=True)  # nội dung gửi Nhiếp ảnh gia
            _thong_bao_khach(booking, f'Booking #{booking.pk} đã bị hủy', noi_dung)            # Khách hàng
            nag_user = booking.MaNhiepAnhGia.MaTaiKhoan  # tài khoản của Nhiếp ảnh gia thuộc Booking
            _thong_bao_nguoi(nag_user, booking, f'Booking #{booking.pk} đã bị hủy', noi_dung_nag)  # Nhiếp ảnh gia
    except DatabaseError:  # lỗi cơ sở dữ liệu bất ngờ
        logger.exception('huy_booking: lỗi hệ thống (booking %s)', ma_booking)  # ghi log chi tiết lỗi cho lập trình viên
        raise XuLyBookingLoi(TB_LOI_HE_THONG)  # báo người dùng câu lỗi hệ thống chung
    cap_nhat.MaKhachHang, cap_nhat.MaNhiepAnhGia, cap_nhat.MaGoi = (  # gán lại 3 thông tin liên quan vào Booking đã cập nhật...
        booking.MaKhachHang, booking.MaNhiepAnhGia, booking.MaGoi)    # giữ lại thông tin đã nạp sẵn
    return cap_nhat  # trả Booking đã hủy


def _thong_bao_nguoi(nguoi_nhan, booking, tieu_de, noi_dung):  # gửi thông báo cho một người bất kỳ
    """Giống _thong_bao_khach của tiep_nhan.py nhưng cho người nhận bất kỳ (ở đây là Nhiếp ảnh gia)."""
    tb = gui_thong_bao(nguoi_nhan, tieu_de, noi_dung, booking=booking)  # tạo thông báo web, lưu vào CSDL
    gui_email_sau_commit(tb, nguoi_nhan, tieu_de, noi_dung)  # hẹn gửi Email sau khi transaction lưu xong (tránh gửi mà dữ liệu bị hoàn tác)


def xac_nhan_da_nhan_hoan_tien(khach_user, ma_booking):  # hàm chính: Khách xác nhận đã nhận lại cọc
    """Khách bấm 'Tôi đã nhận lại tiền cọc': 'Chờ hoàn tiền' -> 'Đã hoàn tiền' (ghi thời điểm xác nhận), báo Nhiếp ảnh gia.
    Chỉ Khách của Booking đó; chỉ khi Nhiếp ảnh gia hủy sau khi đã cọc (XuLyTienCoc = 'Hoàn cọc')."""
    try:  # bắt lỗi cơ sở dữ liệu ở khối bên dưới
        with transaction.atomic():  # gói trong transaction: lỗi thì hoàn tác hết
            booking = lay_booking_cua_ben(khach_user, VaiTro.KHACH_HANG, ma_booking)    # của người khác -> 404
            yeu_cau = lay_yeu_cau_huy(booking)  # lấy yêu cầu hủy của Booking
            if yeu_cau is None or yeu_cau.XuLyTienCoc != HangSoXuLyTienCoc.HOAN_COC:  # chưa bị hủy, hoặc hủy mà không thuộc diện "Hoàn cọc"
                raise XuLyBookingLoi(TB_KHONG_CO_HOAN_COC)  # báo không có khoản cọc nào cần hoàn
            # UPDATE có điều kiện 'vẫn đang Chờ hoàn tiền': bấm hai lần / hai tab cùng lúc thì chỉ một lần thành công.
            so_dong = YeuCauHuy.objects.filter(pk=yeu_cau.pk, TrangThaiHoanTien=HangSoHoanTien.CHO_HOAN_TIEN).update(  # chỉ cập nhật nếu yêu cầu này VẪN đang "Chờ hoàn tiền"; trả về số dòng đã sửa
                TrangThaiHoanTien=HangSoHoanTien.DA_HOAN_TIEN, ThoiDiemXacNhanHoanTien=timezone.now())  # đổi sang "Đã hoàn tiền" và ghi thời điểm xác nhận là bây giờ
            if so_dong != 1:  # không sửa được dòng nào = đã có lần bấm khác xử lý trước
                raise XuLyBookingLoi(TB_DA_XAC_NHAN_HOAN_TIEN)  # báo đã xác nhận rồi
            coc = _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC))  # số tiền cọc 40% để ghi vào thông báo
            _thong_bao_nguoi(  # gửi thông báo cho Nhiếp ảnh gia
                booking.MaNhiepAnhGia.MaTaiKhoan, booking, f'Khách hàng đã nhận lại tiền cọc - Booking #{booking.pk}',  # người nhận / Booking / tiêu đề
                f'{_ten_hien_thi(khach_user)} đã xác nhận nhận lại {coc} VNĐ tiền cọc của Booking #{booking.pk}. '  # nội dung: ai xác nhận, bao nhiêu tiền (nửa đầu)
                'Việc hoàn tiền cho Booking này đã hoàn tất.')  # nội dung: hoàn tất (nửa sau)
    except DatabaseError:  # lỗi cơ sở dữ liệu bất ngờ
        logger.exception('xac_nhan_da_nhan_hoan_tien: lỗi hệ thống (booking %s)', ma_booking)  # ghi log cho lập trình viên
        raise XuLyBookingLoi(TB_LOI_HE_THONG)  # báo người dùng câu lỗi hệ thống chung
    return lay_yeu_cau_huy(booking)  # trả yêu cầu hủy (đã cập nhật) cho người gọi


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
chi_khach_va_nag = vai_tro_required(VaiTro.KHACH_HANG, VaiTro.NHIEP_ANH_GIA)   # chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403
chi_khach_hang = vai_tro_required(VaiTro.KHACH_HANG)  # nhãn: chỉ Khách hàng được vào


@chi_khach_va_nag  # nhãn: chỉ Khách hàng / Nhiếp ảnh gia
@require_http_methods(['GET', 'POST'])  # nhãn: chỉ nhận GET (xem) và POST (gửi form)
def huy(request, ma_booking):  # view trang hủy Booking
    """UC4.6: GET = hệ thống yêu cầu nhập lý do + giải thích hệ quả (bước 3); POST = xác nhận hủy (bước 4-11)."""
    vai_tro = lay_vai_tro(request.user)  # vai trò người đang đăng nhập
    try:  # thử lấy Booking của người này
        booking = lay_booking_cua_ben(request.user, vai_tro, ma_booking)  # lấy Booking trong phạm vi của người này
    except XuLyBookingLoi:  # không tìm thấy (không tồn tại / của người khác)
        raise Http404('Không tìm thấy Booking.')  # trả trang 404
    ben = BEN_THEO_VAI_TRO[vai_tro]  # bên hủy (vai trò đã được nhãn chi_khach_va_nag giới hạn nên chắc chắn có trong bảng)
    if not co_the_huy(booking, ben):                                  # đã hủy rồi / đã chụp / Nhiếp ảnh gia hủy lúc chờ xác nhận...
        messages.error(request, thong_bao_khong_the_huy(ben))  # hiện thông báo lỗi đỏ đúng với bên hủy
        return redirect('chi_tiet_booking', ma_booking=booking.pk)  # đưa người dùng về trang chi tiết Booking

    if request.method == 'POST':  # người dùng vừa bấm gửi form
        form = HuyForm(request.POST)  # nạp dữ liệu người dùng gõ vào form
        if form.is_valid():  # kiểm tra hợp lệ (có lý do, không quá dài)
            try:  # thử thực hiện hủy
                huy_booking(request.user, booking.pk, form.cleaned_data['ly_do'])  # gọi hàm nghiệp vụ hủy với lý do đã làm sạch
            except XuLyBookingLoi as loi:  # hàm nghiệp vụ báo lỗi
                if loi.khong_tim_thay:  # lỗi kiểu "không tìm thấy"
                    raise Http404(loi.thong_bao)  # trả 404
                form.add_error(None, loi.thong_bao)                   # lỗi khác: hiện dòng đỏ trên form
            else:  # không có lỗi nào = hủy thành công
                messages.success(request, TB_DA_HUY)  # hiện thông báo xanh thành công
                return redirect('chi_tiet_booking', ma_booking=booking.pk)  # chuyển về trang chi tiết Booking
        # form không hợp lệ (ví dụ 4a: chưa nhập lý do) -> hiện lại form kèm lỗi, UC tiếp tục từ bước 4
    else:  # yêu cầu GET: mới mở trang
        form = HuyForm()  # tạo form trống

    return render(request, 'bookings/huy_xac_nhan.html', {  # dựng trang xác nhận hủy, kèm dữ liệu bên dưới
        'form': form,  # form nhập lý do
        'booking': booking,  # Booking đang định hủy
        'la_khach': vai_tro == VaiTro.KHACH_HANG,  # người xem có phải Khách không (để template chọn hiện tên ai)
        'ten_khach': _ten_hien_thi(booking.MaKhachHang),  # tên Khách
        'ten_nag': _ten_hien_thi(booking.MaNhiepAnhGia.MaTaiKhoan),  # tên Nhiếp ảnh gia
        'hau_qua': mo_ta_hau_qua(booking, ben),  # câu giải thích hệ quả tiền cọc
    })


@chi_khach_hang  # nhãn: chỉ Khách hàng
@require_POST            # chỉ nhận POST + CSRF: không thể xác nhận chỉ bằng cách mở một đường link
def xac_nhan_hoan_tien(request, ma_booking):  # view nút "Tôi đã nhận lại tiền cọc"
    """Nút 'Tôi đã nhận lại tiền cọc' trên trang chi tiết Booking của Khách hàng."""
    try:  # thử xác nhận
        xac_nhan_da_nhan_hoan_tien(request.user, ma_booking)  # gọi hàm nghiệp vụ
    except XuLyBookingLoi as loi:  # hàm nghiệp vụ báo lỗi
        if loi.khong_tim_thay:  # lỗi kiểu "không tìm thấy"
            raise Http404(loi.thong_bao)  # trả 404
        messages.error(request, loi.thong_bao)  # lỗi khác: hiện thông báo đỏ
    else:  # không lỗi = thành công
        messages.success(request, TB_XAC_NHAN_HOAN_TIEN_XONG)  # hiện thông báo xanh thành công
    return redirect('chi_tiet_booking', ma_booking=ma_booking)  # dù thành công hay lỗi đều quay về trang chi tiết Booking


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.huy_booking')),)
urlpatterns = [  # danh sách địa chỉ của file này
    path('cua-toi/<int:ma_booking>/huy/', huy, name='huy_booking'),                                    # trang nhập lý do + xác nhận hủy
    path('cua-toi/<int:ma_booking>/xac-nhan-hoan-tien/', xac_nhan_hoan_tien, name='xac_nhan_hoan_tien'),  # Khách xác nhận đã nhận lại cọc
]

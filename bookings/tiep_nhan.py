# =====================================================================
# CÁCH ĐỌC FILE NÀY (dành cho người không chuyên lập trình)
#   - Dòng bắt đầu bằng dấu # là CHÚ THÍCH: máy tính bỏ qua, chỉ để người đọc hiểu.
#   - Chú thích nằm NGAY PHÍA TRÊN dòng code mà nó giải thích.
#   - Toàn bộ chú thích dưới đây được thêm vào sau; KHÔNG dòng code nào bị thay đổi.
#   - Cấu trúc: Phần 1 (khai báo) -> Phần 2 (biểu mẫu) -> Phần 3 (xử lý nghiệp vụ) -> Phần 4 (trang web và đường dẫn).
# =====================================================================
# =====================================================================
# bookings/tiep_nhan.py  -  T5 + T6 (Tuyền)
#   UC4.3 Tiếp nhận yêu cầu Booking
#   UC4.4 Chấp nhận Booking
#   UC4.5 Từ chối Booking
#
# Yêu cầu:
#   UC4.3: Nhiếp ảnh gia vào "Quản lý Booking", thấy danh sách Booking gửi đến CHÍNH MÌNH, mặc định ở "Tất cả trạng thái"
#          (lọc riêng "Chờ xác nhận" hoặc trạng thái khác, sắp xếp theo thời gian), bấm vào một Booking để xem chi tiết.
#          Booking "Chờ xác nhận" mà đã quá giờ chụp thì HỆ THỐNG tự hủy (bookings/qua_han.py), Nhiếp ảnh gia không phải từ chối.
#          Không có Booking nào -> "Không có yêu cầu Booking mới". Không xem được Booking của người khác (BR4.3-1).
#   UC4.4: Chấp nhận -> Booking "Chờ đặt cọc", HanDatCoc = lúc chấp nhận + 1 ngày, thông báo web + Email cho Khách
#          (đặt cọc 40% trong 1 ngày, BR4.4-1).
#   UC4.5: Từ chối -> bắt buộc nhập lý do (BR4.5-1), Booking "Đã từ chối", slot về "Lịch trống" ngay (BR4.5-2),
#          thông báo web + Email kèm lý do cho Khách.
#
# File gồm 4 phần (giống bookings/giu_cho.py và bookings/gui_booking.py):
#   PHẦN 1. Import, hằng số, lỗi nghiệp vụ
#   PHẦN 2. Form nhập lý do từ chối
#   PHẦN 3. Hàm nghiệp vụ (service):
#           lay_danh_sach_booking(nag_user, trang_thai, sap_xep) -> UC4.3 bước 2 / luồng 2a
#           chap_nhan_booking(nag_user, ma_booking)               -> UC4.4 bước 3-5
#           tu_choi_booking(nag_user, ma_booking, ly_do)          -> UC4.5 bước 4-8 (+ ngoại lệ 4a)
#   PHẦN 4. View và urlpatterns (nối vào config/urls.py bằng include('bookings.tiep_nhan'))
#
# Quy tắc nhóm:
#   - KHÔNG tự gán booking.TrangThai. Đổi trạng thái luôn qua bookings.services.chuyen_trang_thai_booking:
#     hàm đó tự đặt HanDatCoc (+1 ngày), tự ghi LyDoTuChoi, tự ghi Lịch sử và tự trả slot về "Lịch trống"
#     khi từ chối (DOI_SLOT), tất cả trong một transaction. File này KHÔNG đụng vào slot nữa.
#   - Chữ trạng thái luôn lấy từ core/constants.py.
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ, LỖI NGHIỆP VỤ
# ---------------------------------------------------------------------
# Thư viện ghi nhật ký (log): dùng để ghi lại lỗi kỹ thuật cho lập trình viên tra cứu, người dùng không nhìn thấy.
import logging

# forms: công cụ của Django để tạo biểu mẫu nhập liệu và kiểm tra dữ liệu người dùng nhập.
from django import forms
# ValidationError: loại lỗi mà hàm đổi trạng thái của nhóm ném ra khi thao tác không hợp lệ.
from django.core.exceptions import ValidationError
# Paginator: chia danh sách dài thành từng trang (ở đây 10 dòng mỗi trang).
from django.core.paginator import Paginator
# DatabaseError: lỗi từ cơ sở dữ liệu.
# transaction: gom nhiều thao tác lưu thành MỘT KHỐI - hoặc lưu hết, hoặc hủy hết, không bao giờ lưu dở dang.
from django.db import DatabaseError, transaction
# messages: hiện dòng thông báo ngắn trên đầu trang sau khi thao tác (ví dụ 'Đã chấp nhận Booking').
from django.contrib import messages
# Http404: báo 'không tìm thấy trang' (mã lỗi 404).
from django.http import Http404
# render: dựng trang HTML từ file giao diện (template). redirect: chuyển người dùng sang trang khác.
from django.shortcuts import redirect, render
# path: khai báo một đường dẫn (URL).
from django.urls import path
# timezone: lấy giờ hiện tại và đổi giờ theo múi giờ Việt Nam.
from django.utils import timezone
# Các 'nhãn' giới hạn cách truy cập một trang: chỉ cho GET (chỉ xem), chỉ cho POST (gửi lệnh), hoặc cả hai.
from django.views.decorators.http import require_GET, require_http_methods, require_POST

# Kiểm tra quyền: chỉ Nhiếp ảnh gia có hồ sơ 'Đã duyệt' mới vào được; người khác bị chặn.
from accounts.permissions import chi_nhiep_anh_gia_da_duyet   # chỉ Nhiếp ảnh gia ĐÃ DUYỆT (pre-condition UC4.3)
# Booking: bảng dữ liệu Booking trong cơ sở dữ liệu.
from bookings.models import Booking
# Các hàm dùng chung của nhóm:
# chuyen_trang_thai_booking = hàm DUY NHẤT được phép đổi trạng thái Booking;
# DO_DAI_LY_DO_TOI_DA = độ dài lý do tối đa (255 ký tự).
# gui_email_sau_commit = hàm DÙNG CHUNG gửi Email sau khi lưu xong và ghi kết quả gửi vào thông báo web.
from bookings.services import DO_DAI_LY_DO_TOI_DA, chuyen_trang_thai_booking, gui_email_sau_commit
# Các hằng số tên trạng thái dùng chung toàn dự án (tránh gõ tay chữ 'Chờ xác nhận' ở nhiều nơi dễ sai chính tả).
from core.constants import BenThucHien, LoaiThanhToan, TrangThaiBooking
# gui_thong_bao: hàm của nhóm để tạo một thông báo trên web cho người nhận.
from notifications.services import gui_thong_bao
# tinh_so_tien: quy tắc tính tiền cọc 40% DUY NHẤT của dự án (Thanh toán dùng cùng hàm này để thu tiền thật).
from payments.models import tinh_so_tien

# Tạo 'sổ ghi lỗi' riêng cho file này; mỗi dòng log mang tên file nên dễ tìm.
logger = logging.getLogger(__name__)

# Thông báo cho người dùng (đúng chữ trong đặc tả UC4.3 - UC4.5).
# Câu hiện ra khi danh sách yêu cầu mới đang trống (UC4.3 ngoại lệ 2b).
TB_KHONG_CO_YEU_CAU = 'Không có yêu cầu Booking mới'                      # UC4.3, ngoại lệ 2b
# Câu hiện ra khi bấm từ chối mà chưa nhập lý do (UC4.5 ngoại lệ 4a).
TB_THIEU_LY_DO = 'Vui lòng nhập lý do từ chối'                              # UC4.5, ngoại lệ 4a
# Câu báo khi Booking đã được xử lý rồi (ví dụ đã chấp nhận) mà vẫn bấm xử lý lại.
TB_KHONG_CON_CHO_XAC_NHAN = 'Booking này không còn ở trạng thái "Chờ xác nhận" nên không thể xử lý.'
# Câu báo khi chấp nhận một Booking mà giờ chụp đã trôi qua.
TB_QUA_GIO_CHUP = ('Đã quá giờ chụp của Booking này nên không thể chấp nhận. '
                   'Hệ thống sẽ tự động hủy Booking và trả khung giờ về lịch trống.')
# Câu báo thành công sau khi chấp nhận.
TB_DA_CHAP_NHAN = 'Đã chấp nhận Booking. Khách hàng có 1 ngày để đặt cọc.'
# Câu báo thành công sau khi từ chối.
TB_DA_TU_CHOI = 'Đã từ chối Booking và trả khung giờ về lịch trống.'
# Câu chung khi gặp lỗi kỹ thuật (người dùng không cần biết chi tiết lỗi).
TB_LOI_HE_THONG = 'Không thể thực hiện yêu cầu, vui lòng thử lại sau.'

# Bộ lọc trạng thái của danh sách. Mặc định xem TẤT CẢ trạng thái (muốn xem riêng yêu cầu mới thì chọn 'Chờ xác nhận').
# Giá trị đặc biệt của bộ lọc, nghĩa là 'xem tất cả trạng thái'.
LOC_TAT_CA = 'tat_ca'
# Bộ lọc mặc định khi vừa mở trang (và khi ai đó gõ bậy giá trị lên thanh địa chỉ): xem tất cả trạng thái.
LOC_MAC_DINH = LOC_TAT_CA

# Các kiểu sắp xếp theo thời gian (luồng 2a): khóa dùng trên URL -> (nhãn, danh sách cột order_by).
# Danh sách các kiểu sắp xếp. Mỗi mục có dạng: tên gọi trên URL -> (nhãn hiển thị, các cột dùng để sắp xếp).
# Dấu '-' đứng trước tên cột = sắp giảm dần (lớn/mới nhất lên đầu); không có dấu = tăng dần.
# 'MaBooking' đặt sau cùng để hai Booking cùng thời điểm vẫn luôn có thứ tự cố định.
SAP_XEP = {
    # NgayTao = lúc khách gửi yêu cầu. Kiểu này: yêu cầu gửi gần đây nhất nằm trên cùng.
    'moi_nhat': ('Yêu cầu mới nhất', ['-NgayTao', '-MaBooking']),
    # Ngược lại: yêu cầu gửi lâu nhất nằm trên cùng.
    'cu_nhat': ('Yêu cầu cũ nhất', ['NgayTao', 'MaBooking']),
    # NgayGioChup = ngày giờ buổi chụp. Kiểu này: buổi chụp sắp diễn ra nằm trên cùng.
    'chup_gan': ('Ngày chụp gần nhất', ['NgayGioChup', 'MaBooking']),
    # Ngược lại: buổi chụp xa nhất nằm trên cùng.
    'chup_xa': ('Ngày chụp xa nhất', ['-NgayGioChup', '-MaBooking']),
}
# Kiểu sắp xếp mặc định: yêu cầu mới gửi nằm trên cùng.
SAP_XEP_MAC_DINH = 'moi_nhat'

# Số dòng hiển thị trên mỗi trang danh sách.
SO_DONG_MOI_TRANG = 10


# Loại lỗi riêng của chức năng này. Mỗi khi có điều không hợp lệ (không đúng quyền, sai trạng thái, thiếu lý do...),
# code 'ném' (raise) lỗi này để dừng lại và mang theo câu thông báo hiển thị cho người dùng.
class XuLyBookingLoi(Exception):
    """Lỗi nghiệp vụ của UC4.3 - UC4.5.
    .thong_bao       : câu tiếng Việt hiện cho người dùng.
    .khong_tim_thay  : True khi Booking không tồn tại HOẶC không gửi đến Nhiếp ảnh gia này (BR4.3-1);
                       view trả 404 để không lộ Booking của người khác có tồn tại hay không."""

    # Hàm khởi tạo: chạy mỗi khi tạo ra một lỗi mới. Nhận câu thông báo và cờ 'khong_tim_thay'.
    def __init__(self, thong_bao, khong_tim_thay=False):
        # Gọi hàm khởi tạo của lớp lỗi gốc của Python để lỗi hoạt động bình thường.
        super().__init__(thong_bao)
        # Lưu câu thông báo để nơi bắt lỗi lấy ra hiển thị.
        self.thong_bao = thong_bao
        # Lưu cờ: True = Booking không tồn tại hoặc không thuộc về người này -> trang web sẽ trả lỗi 404.
        self.khong_tim_thay = khong_tim_thay


# ---------------------------------------------------------------------
# PHẦN 2: FORM NHẬP LÝ DO TỪ CHỐI
# ---------------------------------------------------------------------
# Biểu mẫu nhập lý do từ chối (chỉ có đúng một ô nhập).
class TuChoiForm(forms.Form):
    """UC4.5 bước 3-4. Lý do tối đa 255 ký tự vì cột LyDo của Lịch sử trạng thái chỉ chứa 255
    (xem DO_DAI_LY_DO_TOI_DA trong bookings/services.py). Toàn dấu cách cũng tính là chưa nhập."""

    # Ô nhập chữ tên 'ly_do'. Mặc định là BẮT BUỘC nhập và tự cắt khoảng trắng hai đầu,
    # nên nhập toàn dấu cách cũng bị coi là chưa nhập.
    ly_do = forms.CharField(
        # Giới hạn tối đa 255 ký tự; nhãn 'Lý do từ chối' hiện cạnh ô.
        max_length=DO_DAI_LY_DO_TOI_DA, label='Lý do từ chối',
        # Hiển thị thành ô nhập nhiều dòng (4 dòng); trình duyệt cũng tự chặn gõ quá 255 ký tự.
        widget=forms.Textarea(attrs={'rows': 4, 'maxlength': DO_DAI_LY_DO_TOI_DA}),
        # Câu lỗi tiếng Việt: thiếu lý do -> 'Vui lòng nhập lý do từ chối'; quá dài -> báo giới hạn ký tự.
        error_messages={'required': TB_THIEU_LY_DO,
                        'max_length': f'Lý do tối đa {DO_DAI_LY_DO_TOI_DA} ký tự.'})


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
# Tên hiển thị của một tài khoản. (Tên hàm bắt đầu bằng dấu _ nghĩa là hàm nội bộ, chỉ dùng trong file này.)
def _ten_hien_thi(user):
    # Lấy họ tên đầy đủ; nếu rỗng thì lấy tên đăng nhập. ('A or B' = dùng A, nếu A rỗng thì dùng B.)
    return user.get_full_name() or user.username


# Định dạng số tiền kiểu Việt Nam: 1500000 -> '1.500.000'.
def _tien(so):
    # int(): bỏ phần lẻ; ':,' thêm dấu phẩy ngăn cách hàng nghìn (1,500,000); .replace đổi dấu phẩy thành dấu chấm.
    return f'{int(so):,}'.replace(',', '.')


# HÀM 'CỬA NGÕ' LẤY DỮ LIỆU: chỉ trả về các Booking gửi đến đúng Nhiếp ảnh gia này.
# Mọi chỗ khác trong file đều lấy Booking qua hàm này, nên Nhiếp ảnh gia không thể xem hay sửa Booking của người khác (BR4.3-1).
def _booking_cua_nag(nag_user):
    """QuerySet CHỈ gồm Booking gửi đến Nhiếp ảnh gia này (BR4.3-1). Mọi truy vấn của file này đều đi qua đây."""
    # Bắt đầu từ toàn bộ bảng Booking...
    return (Booking.objects
            # ...chỉ giữ lại Booking có Nhiếp ảnh gia chính là tài khoản đang đăng nhập (dòng bảo đảm quy tắc BR4.3-1).
            .filter(MaNhiepAnhGia__MaTaiKhoan=nag_user)
            # Nạp sẵn thông tin Khách, Gói, Loại hình, Lịch, Nhiếp ảnh gia trong một lần truy vấn để trang chạy nhanh (đỡ phải truy vấn lẻ từng dòng).
            .select_related('MaKhachHang', 'MaGoi__MaLoaiHinh', 'MaLich', 'MaNhiepAnhGia__MaTaiKhoan'))


# Lấy đúng MỘT Booking theo mã, nhưng chỉ khi nó thuộc về Nhiếp ảnh gia này.
def lay_booking_cua_nag(nag_user, ma_booking):
    """Lấy một Booking của Nhiếp ảnh gia này; không phải của mình hoặc không tồn tại -> XuLyBookingLoi(khong_tim_thay)."""
    # Tìm theo mã; .first() trả về Booking đầu tiên tìm được, hoặc None nếu không có.
    booking = _booking_cua_nag(nag_user).filter(pk=ma_booking).first()
    # Không có = Booking không tồn tại, hoặc là của người khác.
    if booking is None:
        # Báo lỗi với cờ khong_tim_thay=True. Cố ý không nói rõ 'là của người khác' để không lộ thông tin.
        raise XuLyBookingLoi('Không tìm thấy Booking.', khong_tim_thay=True)
    # Tìm thấy -> trả Booking về cho nơi gọi.
    return booking


# Làm sạch giá trị bộ lọc đọc từ thanh địa chỉ. Người dùng có thể gõ bậy lên URL nên phải kiểm tra, không tin ngay.
def chuan_hoa_bo_loc(trang_thai, sap_xep):
    """Giá trị lạ trên URL (gõ tay) -> quay về mặc định, không gây lỗi."""
    # Nếu giá trị không phải 'tất cả' và cũng không phải trạng thái hợp lệ nào...
    if trang_thai != LOC_TAT_CA and trang_thai not in TrangThaiBooking.ALL:
        # ...thì dùng trạng thái mặc định.
        trang_thai = LOC_MAC_DINH
    # Kiểu sắp xếp lạ cũng quay về mặc định.
    if sap_xep not in SAP_XEP:
        sap_xep = SAP_XEP_MAC_DINH
    # Trả về cặp giá trị đã được làm sạch.
    return trang_thai, sap_xep


# Kiểm tra giờ chụp của Booking đã trôi qua chưa.
def da_qua_gio_chup(booking):
    """Booking đã qua giờ chụp chưa? Qua rồi thì không chấp nhận nữa (hệ thống sẽ tự hủy Booking và trả slot về lịch trống)."""
    # So sánh giờ chụp với thời điểm hiện tại: True nếu giờ chụp đã qua (hoặc đúng bây giờ).
    return booking.NgayGioChup <= timezone.now()


# Trả về danh sách Booking để hiển thị ở trang 'Quản lý Booking' (UC4.3).
def lay_danh_sach_booking(nag_user, trang_thai=LOC_MAC_DINH, sap_xep=SAP_XEP_MAC_DINH):
    """UC4.3 bước 2 và luồng 2a: danh sách Booking của Nhiếp ảnh gia, lọc theo trạng thái, sắp xếp theo thời gian."""
    # Làm sạch tham số trước khi dùng.
    trang_thai, sap_xep = chuan_hoa_bo_loc(trang_thai, sap_xep)
    # Bắt đầu từ các Booking của Nhiếp ảnh gia này.
    ds = _booking_cua_nag(nag_user)
    # Nếu không chọn 'tất cả' thì chỉ giữ Booking đúng trạng thái đã chọn.
    if trang_thai != LOC_TAT_CA:
        ds = ds.filter(TrangThai=trang_thai)
    # Sắp xếp theo kiểu đã chọn. SAP_XEP[sap_xep][1] là danh sách cột dùng để sắp; dấu * 'bung' danh sách đó ra thành từng tham số riêng.
    return ds.order_by(*SAP_XEP[sap_xep][1])


# Đếm số yêu cầu đang chờ xác nhận (hiện ở đầu trang Quản lý Booking).
def dem_cho_xac_nhan(nag_user):
    """Số yêu cầu đang chờ xác nhận (hiện ở đầu trang Quản lý Booking)."""
    # Lọc các Booking 'Chờ xác nhận' của Nhiếp ảnh gia rồi đếm số lượng (.count()).
    return _booking_cua_nag(nag_user).filter(TrangThai=TrangThaiBooking.CHO_XAC_NHAN).count()


# Tạo câu mô tả ngắn một Booking để đưa vào nội dung thông báo cho Khách.
def _mo_ta_booking(booking):
    # Đổi giờ chụp (hệ thống lưu theo giờ quốc tế UTC) sang giờ Việt Nam để hiển thị đúng.
    gio_chup = timezone.localtime(booking.NgayGioChup)
    # Ghép thành câu: tên gói, loại hình chụp, giờ chụp dạng 'giờ:phút ngày/tháng/năm', địa điểm.
    # Cú pháp f'...{...}' là cách chèn giá trị của biến vào giữa câu.
    return (f'gói "{booking.MaGoi.TenGoi}" ({booking.MaGoi.MaLoaiHinh.TenLoaiHinh}), '
            f'{gio_chup:%H:%M %d/%m/%Y}, địa điểm {booking.DiaDiem}')


# Báo cho Khách bằng 2 kênh: thông báo trên web (làm ngay) và Email (làm sau khi dữ liệu đã lưu xong chắc chắn).
def _thong_bao_khach(booking, tieu_de, noi_dung):
    """Thông báo web cho Khách ngay trong transaction + Email sau khi commit. gui_thong_bao (của Phanh)
    tự nuốt lỗi nên không phá việc chấp nhận / từ chối."""
    # Lấy tài khoản của Khách đã đặt Booking.
    khach = booking.MaKhachHang
    # Tạo thông báo trên web cho Khách, gắn với Booking này; biến tb giữ thông báo vừa tạo.
    tb = gui_thong_bao(khach, tieu_de, noi_dung, booking=booking)
    # Hẹn gửi Email bằng hàm dùng chung (bookings/services.py): CHỈ khi toàn bộ việc lưu đã thành công (commit) thì mới gửi,
    # nên nếu việc lưu bị hủy giữa chừng thì Khách không nhận mail sai sự thật. Gửi lỗi chỉ đánh dấu 'Gửi thất bại'.
    gui_email_sau_commit(tb, khach, tieu_de, noi_dung)


# Phần DÙNG CHUNG của Chấp nhận và Từ chối: kiểm tra điều kiện rồi đổi trạng thái.
def _doi_trang_thai(nag_user, ma_booking, trang_thai_moi, ly_do=None, can_chua_qua_gio_chup=False):
    """Phần chung của UC4.4 và UC4.5: kiểm tra quyền sở hữu + trạng thái, rồi gọi hàm của nhóm để đổi trạng thái.
    Gọi trong transaction.atomic() của hàm ngoài. Trả về Booking đã cập nhật."""
    # Bước 1: lấy Booking và bảo đảm là của đúng Nhiếp ảnh gia này (không phải thì báo lỗi 'không tìm thấy').
    booking = lay_booking_cua_nag(nag_user, ma_booking)            # BR4.3-1
    # Bước 2: chỉ Booking đang 'Chờ xác nhận' mới được xử lý (tránh chấp nhận hoặc từ chối hai lần).
    if booking.TrangThai != TrangThaiBooking.CHO_XAC_NHAN:         # tiền điều kiện của UC4.4 / UC4.5
        # Không đúng trạng thái -> dừng lại, báo lỗi.
        raise XuLyBookingLoi(TB_KHONG_CON_CHO_XAC_NHAN)
    # Bước 3 (chỉ khi đang CHẤP NHẬN): nếu giờ chụp đã qua thì không cho chấp nhận.
    if can_chua_qua_gio_chup and da_qua_gio_chup(booking):         # chấp nhận Booking đã qua giờ chụp là vô nghĩa
        # Dừng lại và báo lỗi quá giờ chụp.
        raise XuLyBookingLoi(TB_QUA_GIO_CHUP)
    # Bước 4: gọi hàm đổi trạng thái của nhóm.
    try:
        # Hàm này tự: kiểm tra bước chuyển, đặt HanDatCoc / LyDoTuChoi, ghi Lịch sử, trả slot về "Lịch trống"
        # (khi từ chối) và chặn trường hợp hai người cùng đổi một lúc.
        # Thực hiện đổi trạng thái. Bên thực hiện ghi nhận là 'Nhiếp ảnh gia'; ly_do chỉ có khi từ chối.
        # Hàm này tự làm: đặt hạn đặt cọc +1 ngày (khi chấp nhận), ghi lý do từ chối, ghi lịch sử đổi trạng thái, trả khung giờ về 'Lịch trống' (khi từ chối).
        cap_nhat = chuyen_trang_thai_booking(booking, trang_thai_moi, BenThucHien.NHIEP_ANH_GIA, ly_do=ly_do)
    # Nếu hàm trên báo bước chuyển không hợp lệ...
    except ValidationError as loi:
        # ...thì đổi sang loại lỗi của file này, ghép các câu báo lỗi thành một câu.
        raise XuLyBookingLoi(' '.join(loi.messages))
    # Hàm đổi trạng thái trả về bản Booking mới đọc lại từ cơ sở dữ liệu, chưa kèm thông tin Khách / Nhiếp ảnh gia / Gói.
    # Ba dòng dưới gắn lại thông tin đã nạp sẵn để khỏi phải truy vấn lại.
    cap_nhat.MaKhachHang = booking.MaKhachHang   # hàm trên trả bản mới đọc từ DB; giữ lại Khách đã nạp sẵn
    cap_nhat.MaNhiepAnhGia = booking.MaNhiepAnhGia
    cap_nhat.MaGoi = booking.MaGoi
    # Trả về Booking đã được cập nhật.
    return cap_nhat


# UC4.4 - CHẤP NHẬN BOOKING: đổi sang 'Chờ đặt cọc' và báo Khách đặt cọc.
def chap_nhan_booking(nag_user, ma_booking):
    """UC4.4 bước 3-5: Booking 'Chờ xác nhận' -> 'Chờ đặt cọc' (HanDatCoc = bây giờ + 1 ngày), thông báo web
    + Email cho Khách yêu cầu đặt cọc 40% trong 1 ngày. Trả về Booking đã cập nhật.
    Báo XuLyBookingLoi khi: không phải Booking của mình (.khong_tim_thay), Booking không còn 'Chờ xác nhận',
    đã quá giờ chụp, có người vừa đổi trạng thái trước, hoặc lỗi hệ thống. Lỗi ở đâu thì không đổi gì."""
    # Bọc toàn bộ để bắt lỗi cơ sở dữ liệu ở cuối hàm.
    try:
        # Khối 'tất cả hoặc không gì cả': nếu có lỗi giữa chừng thì mọi thay đổi trong khối bị hủy, Booking không bao giờ bị đổi dở dang.
        with transaction.atomic():
            # Đổi sang 'Chờ đặt cọc'; cờ True nghĩa là có kiểm tra 'đã quá giờ chụp'.
            booking = _doi_trang_thai(nag_user, ma_booking, TrangThaiBooking.CHO_DAT_COC, can_chua_qua_gio_chup=True)
            # Tiền cọc lấy từ tinh_so_tien (payments/models.py) để khớp đúng số tiền hệ thống sẽ thu.
            coc = tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC)
            # Hạn đặt cọc (đã được đặt = lúc chấp nhận + 1 ngày), đổi sang giờ Việt Nam để ghi vào thông báo.
            han = timezone.localtime(booking.HanDatCoc)
            # Gửi thông báo + Email cho Khách. Nội dung gồm: tên Nhiếp ảnh gia, mã Booking, mô tả buổi chụp, số tiền cọc và hạn cọc.
            _thong_bao_khach(
                booking, 'Booking đã được chấp nhận - vui lòng đặt cọc',
                f'{_ten_hien_thi(nag_user)} đã chấp nhận Booking #{booking.pk} ({_mo_ta_booking(booking)}). '
                f'Vui lòng đặt cọc {_tien(coc)} VNĐ (40% giá trị buổi chụp) trong vòng 1 ngày, '
                f'trước {han:%H:%M %d/%m/%Y}. Quá hạn, Booking sẽ tự hết hiệu lực và khung giờ được trả lại lịch trống.')
    # Gặp lỗi cơ sở dữ liệu: ghi log chi tiết cho lập trình viên, và báo người dùng một câu chung chung.
    except DatabaseError:
        # Ghi lỗi vào log.
        logger.exception('chap_nhan_booking: lỗi hệ thống (booking %s)', ma_booking)
        # Báo lỗi hệ thống cho người dùng.
        raise XuLyBookingLoi(TB_LOI_HE_THONG)
    # Thành công -> trả về Booking đã chấp nhận.
    return booking


# UC4.5 - TỪ CHỐI BOOKING: bắt buộc có lý do, đổi sang 'Đã từ chối', trả khung giờ về 'Lịch trống', báo Khách.
def tu_choi_booking(nag_user, ma_booking, ly_do):
    """UC4.5 bước 4-8: kiểm tra lý do (ngoại lệ 4a) -> Booking 'Đã từ chối' + slot về 'Lịch trống' ngay
    -> thông báo web + Email kèm lý do cho Khách. Trả về Booking đã cập nhật.
    Báo XuLyBookingLoi khi: thiếu lý do (BR4.5-1), lý do quá dài, không phải Booking của mình (.khong_tim_thay),
    Booking không còn 'Chờ xác nhận', có người vừa đổi trạng thái trước, hoặc lỗi hệ thống."""
    # Chuẩn hóa lý do: nếu chưa có (None) thì coi là chuỗi rỗng; .strip() cắt khoảng trắng hai đầu.
    ly_do = (ly_do or '').strip()
    # Lý do rỗng (hoặc chỉ toàn dấu cách) -> không cho từ chối (BR4.5-1).
    if not ly_do:                                                   # ngoại lệ 4a
        # Báo 'Vui lòng nhập lý do từ chối'.
        raise XuLyBookingLoi(TB_THIEU_LY_DO)
    # Lý do dài quá 255 ký tự thì không nhận (vì cột lịch sử chỉ chứa 255 ký tự).
    if len(ly_do) > DO_DAI_LY_DO_TOI_DA:
        raise XuLyBookingLoi(f'Lý do tối đa {DO_DAI_LY_DO_TOI_DA} ký tự.')
    # Bọc để bắt lỗi cơ sở dữ liệu.
    try:
        # Cũng là khối 'tất cả hoặc không gì cả' như bên chấp nhận.
        with transaction.atomic():
            # Đổi sang 'Đã từ chối' kèm lý do. Khung giờ được trả về 'Lịch trống' ngay trong bước này.
            # Không truyền cờ kiểm tra giờ chụp nên Booking đã quá giờ vẫn từ chối được.
            booking = _doi_trang_thai(nag_user, ma_booking, TrangThaiBooking.DA_TU_CHOI, ly_do=ly_do)
            # Báo cho Khách: thông báo trên web + Email, có kèm lý do từ chối.
            _thong_bao_khach(
                booking, 'Booking đã bị từ chối',
                f'{_ten_hien_thi(nag_user)} đã từ chối Booking #{booking.pk} ({_mo_ta_booking(booking)}). '
                f'Lý do: {ly_do}. Khung giờ đã được trả về lịch trống, bạn có thể chọn khung giờ khác.')
    # Lỗi cơ sở dữ liệu: ghi log và báo câu chung chung.
    except DatabaseError:
        # Ghi lỗi vào log.
        logger.exception('tu_choi_booking: lỗi hệ thống (booking %s)', ma_booking)
        # Báo lỗi hệ thống cho người dùng.
        raise XuLyBookingLoi(TB_LOI_HE_THONG)
    # Thành công -> trả về Booking đã từ chối.
    return booking


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
# Hai 'nhãn' đặt trên hàm xem trang: (1) chỉ Nhiếp ảnh gia đã được duyệt mới vào được; (2) chỉ cho phép cách truy cập GET (mở trang để xem).
@chi_nhiep_anh_gia_da_duyet
@require_GET
# TRANG 'QUẢN LÝ BOOKING' (UC4.3). Tham số 'request' chứa mọi thông tin về lần truy cập này: người dùng, các tham số trên địa chỉ...
def danh_sach_yeu_cau(request):
    """UC4.3 bước 1-2 và luồng 2a. Tên URL 'manage_bookings' đã có sẵn trong menu Nhiếp ảnh gia (core/navigation.py)."""
    # Đọc bộ lọc từ thanh địa chỉ (ví dụ ?trang_thai=...&sap_xep=...); không có thì dùng mặc định; rồi làm sạch giá trị.
    trang_thai, sap_xep = chuan_hoa_bo_loc(request.GET.get('trang_thai', LOC_MAC_DINH),
                                           request.GET.get('sap_xep', SAP_XEP_MAC_DINH))
    # Lấy danh sách Booking của Nhiếp ảnh gia đang đăng nhập (request.user), đã lọc và sắp xếp.
    ds = lay_danh_sach_booking(request.user, trang_thai, sap_xep)
    # Chia thành từng trang 10 dòng và lấy trang số ?page=...; số trang lạ thì tự về trang hợp lệ.
    trang = Paginator(ds, SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))
    # Dựng trang HTML từ file giao diện 'nag_danh_sach.html', kèm bộ dữ liệu bên dưới để file giao diện hiển thị.
    return render(request, 'bookings/nag_danh_sach.html', {
        # Các dòng của trang hiện tại.
        'page_obj': trang,
        # Bộ lọc và kiểu sắp xếp đang chọn, để các ô chọn hiển thị đúng giá trị.
        'trang_thai': trang_thai,
        'sap_xep': sap_xep,
        # Các lựa chọn trong ô 'Trạng thái': 'Tất cả' cộng toàn bộ trạng thái Booking.
        'lua_chon_trang_thai': [(LOC_TAT_CA, 'Tất cả trạng thái')] + list(TrangThaiBooking.CHOICES),
        # Các lựa chọn trong ô 'Sắp xếp theo thời gian' (lấy nhãn từ bảng SAP_XEP).
        'lua_chon_sap_xep': [(khoa, nhan) for khoa, (nhan, _) in SAP_XEP.items()],
        # True nếu đang lọc riêng 'Chờ xác nhận' -> khi trống thì hiện câu 'Không có yêu cầu Booking mới'.
        'dang_xem_yeu_cau_moi': trang_thai == TrangThaiBooking.CHO_XAC_NHAN,
        # Giá trị 'Chờ xác nhận' để template làm đường link 'Xem các yêu cầu này' (lọc nhanh) ở dòng nhắc đầu trang.
        'trang_thai_cho_xac_nhan': TrangThaiBooking.CHO_XAC_NHAN,
        # Số yêu cầu đang chờ, để hiện dòng nhắc trên đầu trang.
        'so_cho_xac_nhan': dem_cho_xac_nhan(request.user),
        # Câu thông báo khi danh sách rỗng.
        'TB_KHONG_CO_YEU_CAU': TB_KHONG_CO_YEU_CAU,
    })


# Trang chi tiết: cũng chỉ Nhiếp ảnh gia đã duyệt, chỉ cho GET.
@chi_nhiep_anh_gia_da_duyet
@require_GET
# TRANG CHI TIẾT MỘT BOOKING (UC4.3 bước 3-4). 'ma_booking' là số mã lấy từ đường dẫn.
def chi_tiet_yeu_cau(request, ma_booking):
    """UC4.3 bước 3-4: chi tiết một Booking. Booking của người khác -> 404 (BR4.3-1)."""
    # Lấy Booking, bảo đảm là của đúng Nhiếp ảnh gia này.
    try:
        booking = lay_booking_cua_nag(request.user, ma_booking)
    # Không có, hoặc là của người khác...
    except XuLyBookingLoi:
        # ...thì trả trang 404 'không tìm thấy'.
        raise Http404('Không tìm thấy Booking.')
    # T8: import BÊN TRONG hàm vì da_chup.py đã import tiep_nhan.py ở đầu file; import ở đầu file này sẽ bị vòng import.
    from bookings.da_chup import da_den_gio_chup
    # Dựng trang chi tiết từ 'nag_chi_tiet.html' với các dữ liệu bên dưới.
    return render(request, 'bookings/nag_chi_tiet.html', {
        # Toàn bộ thông tin Booking.
        'booking': booking,
        # Tên khách hiển thị.
        'ten_khach': _ten_hien_thi(booking.MaKhachHang),
        # Cờ 'đã quá giờ chụp' để giao diện ẩn nút Chấp nhận.
        'da_qua_gio_chup': da_qua_gio_chup(booking),                          # qua giờ chụp: ẩn nút Chấp nhận, vẫn cho Từ chối
        # T8: cờ 'buổi chụp đã diễn ra' cho khối nút 'Đã chụp'. Lấy từ CHÍNH hàm mà da_chup.danh_dau_da_chup dùng khi kiểm tra lúc bấm,
        # nên nút hiện ra và việc bấm được luôn khớp nhau (sau này đổi cách tính giờ ở da_chup.da_den_gio_chup thì cả hai cùng đổi).
        'da_den_gio_chup': da_den_gio_chup(booking),
        # Cờ 'còn xử lý được' để giao diện chỉ hiện nút khi Booking đang chờ xác nhận.
        'co_the_xu_ly': booking.TrangThai == TrangThaiBooking.CHO_XAC_NHAN,   # chỉ lúc này mới hiện nút xử lý
        # T8: Booking đang 'Chốt Booking' -> hiện khối 'Đã chụp'; nút chỉ bấm được khi buổi chụp đã diễn ra.
        'dang_chot_booking': booking.TrangThai == TrangThaiBooking.CHOT_BOOKING,   # True nếu Booking đang 'Chốt Booking' -> template hiện khối nút 'Đã chụp'
        # Tổng giá trị Booking đã định dạng (ví dụ 1.500.000).
        'tong_gia': _tien(booking.TongGiaTri),
        # Số tiền cọc 40% (tính bằng tinh_so_tien) đã định dạng, để báo trước cho Nhiếp ảnh gia.
        'tien_coc': _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC)),
    })


# Nút chấp nhận: chỉ Nhiếp ảnh gia đã duyệt, và chỉ nhận cách gửi POST.
@chi_nhiep_anh_gia_da_duyet
@require_POST
# NÚT 'CHẤP NHẬN BOOKING' (UC4.4). Chỉ nhận POST (gửi lệnh kèm mã bảo mật CSRF) nên không thể chấp nhận chỉ bằng cách mở một đường link.
def chap_nhan(request, ma_booking):
    """UC4.4: nút 'Chấp nhận Booking' trên trang chi tiết (chỉ nhận POST + CSRF, không chấp nhận bằng đường dẫn GET)."""
    # Gọi hàm nghiệp vụ chấp nhận.
    try:
        # Thực hiện chấp nhận cho Booking này, nhân danh người đang đăng nhập.
        chap_nhan_booking(request.user, ma_booking)
    # Nếu hàm báo lỗi nghiệp vụ...
    except XuLyBookingLoi as loi:
        # ...Booking không phải của mình -> trang 404.
        if loi.khong_tim_thay:
            raise Http404(loi.thong_bao)
        # ...lỗi khác (đã xử lý rồi, quá giờ chụp...) -> hiện dòng báo lỗi màu đỏ...
        messages.error(request, loi.thong_bao)
        # ...rồi quay lại trang chi tiết.
        return redirect('chi_tiet_yeu_cau_booking', ma_booking=ma_booking)
    # Thành công -> hiện dòng báo màu xanh...
    messages.success(request, TB_DA_CHAP_NHAN)
    # ...rồi đưa về danh sách Quản lý Booking.
    return redirect('manage_bookings')


# Trang từ chối: chỉ Nhiếp ảnh gia đã duyệt.
@chi_nhiep_anh_gia_da_duyet
# Trang này nhận cả GET (mở form nhập lý do) lẫn POST (gửi form).
@require_http_methods(['GET', 'POST'])
# TRANG 'TỪ CHỐI BOOKING' (UC4.5).
def tu_choi(request, ma_booking):
    """UC4.5: GET = hệ thống yêu cầu nhập lý do (bước 3); POST = xác nhận từ chối (bước 4-8)."""
    # Lấy Booking của chính mình; không có thì trang 404.
    try:
        booking = lay_booking_cua_nag(request.user, ma_booking)
    # Không có, hoặc là của người khác...
    except XuLyBookingLoi:
        # ...thì trả trang 404.
        raise Http404('Không tìm thấy Booking.')
    # Booking đã được xử lý rồi -> báo lỗi và quay lại trang chi tiết, không mở form.
    if booking.TrangThai != TrangThaiBooking.CHO_XAC_NHAN:
        messages.error(request, TB_KHONG_CON_CHO_XAC_NHAN)
        return redirect('chi_tiet_yeu_cau_booking', ma_booking=booking.pk)

    # POST = người dùng vừa bấm 'Xác nhận từ chối'.
    if request.method == 'POST':
        # Nạp dữ liệu người dùng vừa gửi vào biểu mẫu.
        form = TuChoiForm(request.POST)
        # Kiểm tra biểu mẫu: có nhập lý do và không quá dài. Không hợp lệ thì bỏ qua khối này, hiện lại form kèm lời báo lỗi.
        if form.is_valid():
            # Thực hiện từ chối với lý do đã nhập.
            try:
                # Gọi hàm nghiệp vụ từ chối (đổi trạng thái, trả khung giờ, báo Khách).
                tu_choi_booking(request.user, booking.pk, form.cleaned_data['ly_do'])
            # Có lỗi nghiệp vụ...
            except XuLyBookingLoi as loi:
                # ...không phải Booking của mình -> trang 404.
                if loi.khong_tim_thay:
                    raise Http404(loi.thong_bao)
                # ...lỗi khác thì gắn vào biểu mẫu để hiện thành dòng đỏ trên form.
                form.add_error(None, loi.thong_bao)
            # 'else' của khối try: chạy khi KHÔNG có lỗi, tức là từ chối thành công.
            else:
                # Hiện dòng báo màu xanh...
                messages.success(request, TB_DA_TU_CHOI)
                # ...rồi đưa về danh sách.
                return redirect('manage_bookings')
        # form không hợp lệ (ví dụ 4a: chưa nhập lý do) -> hiện lại form kèm lỗi, UC tiếp tục từ bước 4
    # Không phải POST (tức là GET) = người dùng mới mở trang: hiện form trống để nhập lý do (UC4.5 bước 3).
    else:
        # Tạo biểu mẫu trống.
        form = TuChoiForm()

    # Hiện (hoặc hiện lại, nếu có lỗi) trang nhập lý do bằng file giao diện 'nag_tu_choi.html'.
    return render(request, 'bookings/nag_tu_choi.html', {
        'form': form,
        'booking': booking,
        'ten_khach': _ten_hien_thi(booking.MaKhachHang),
    })


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.tiep_nhan')),)
# Danh sách đường dẫn của chức năng này. 'name' là tên gọi để các nơi khác (menu, giao diện) gọi tới mà không cần gõ đường dẫn.
urlpatterns = [
    # /bookings/quan-ly/  -> danh sách yêu cầu Booking (UC4.3).
    path('quan-ly/', danh_sach_yeu_cau, name='manage_bookings'),
    # /bookings/quan-ly/<mã>/  -> chi tiết một Booking (UC4.3).
    path('quan-ly/<int:ma_booking>/', chi_tiet_yeu_cau, name='chi_tiet_yeu_cau_booking'),
    # /bookings/quan-ly/<mã>/chap-nhan/  -> nút Chấp nhận (UC4.4).
    path('quan-ly/<int:ma_booking>/chap-nhan/', chap_nhan, name='chap_nhan_booking'),
    # /bookings/quan-ly/<mã>/tu-choi/  -> trang Từ chối (UC4.5).
    path('quan-ly/<int:ma_booking>/tu-choi/', tu_choi, name='tu_choi_booking'),
    path('quan-ly/<int:ma_booking>/tu-choi/', tu_choi, name='tu_choi_booking'),
]

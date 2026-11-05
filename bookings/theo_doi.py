# =====================================================================
# bookings/theo_doi.py  -  T7 (Tuyền)
#   UC4.7 Theo dõi trạng thái Booking
#
# Yêu cầu (đặc tả UC4.7 + task T7):
#   - Khách hàng và Nhiếp ảnh gia vào "Booking của tôi": thấy danh sách Booking CỦA CHÍNH MÌNH kèm
#     trạng thái hiện tại; lọc theo trạng thái (luồng 2a); bấm vào một Booking để xem chi tiết +
#     dòng thời gian lịch sử đổi trạng thái (bước 3-4).
#   - Chưa có Booking nào -> "Chưa có Booking nào" (ngoại lệ 1a).
#   - BR4.7-1: chỉ xem Booking liên quan đến chính mình (của người khác -> 404, không lộ là có tồn tại).
#   - Quản trị viên tra cứu TẤT CẢ Booking (danh sách + chi tiết, có ô tìm kiếm).
#   - Mỗi trạng thái có nhãn + màu thống nhất ở mọi màn hình: LUÔN dùng {% status_badge %}
#     (core/status_tones.py), KHÔNG tự tô màu ở file này hay trong template.
#   - BR4.7-2: trạng thái luôn khớp dữ liệu Thanh toán. Cách làm:
#       (1) Trạng thái hiển thị đọc thẳng từ cột Booking.TrangThai (nguồn duy nhất). Mọi thay đổi đều đi qua
#           bookings.services.chuyen_trang_thai_booking nên khi Thanh toán đổi, Booking đổi theo cùng transaction.
#       (2) Màn hình chi tiết hiện kèm các khoản thanh toán (cọc 40%, phần còn lại 60%) ngay cạnh trạng thái.
#       (3) doi_chieu_thanh_toan() soát xem trạng thái Booking có lệch dữ liệu thanh toán không; lệch thì
#           ghi log và báo cho Quản trị viên ở trang chi tiết (Khách / Nhiếp ảnh gia không thấy cảnh báo này).
#
# File gồm 4 phần (giống bookings/tiep_nhan.py):
#   PHẦN 1. Import, hằng số
#   PHẦN 2. (không cần form - bộ lọc đọc trực tiếp từ thanh địa chỉ)
#   PHẦN 3. Hàm nghiệp vụ (service)
#   PHẦN 4. View và urlpatterns  (nối vào config/urls.py bằng include('bookings.theo_doi'))
#
# TÊN URL (các nơi khác đã gọi sẵn):
#   my_bookings        : menu "Booking của tôi" của Khách hàng (core/navigation.py)
#   chi_tiet_booking   : bookings/gui_booking.py tự chuyển Khách tới đây sau khi gửi Booking (UC4.2 bước 8)
#   admin_bookings     : menu "Booking" của Quản trị viên (core/navigation.py)
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ
# ---------------------------------------------------------------------
# Thư viện ghi log: ghi cảnh báo kỹ thuật cho lập trình viên (người dùng không thấy).
import logging  # nạp thư viện ghi log có sẵn của Python

# Q: ghép nhiều điều kiện tìm kiếm bằng "HOẶC" (ô tìm kiếm của Quản trị viên).
from django.db.models import Q  # Q: công cụ ghép điều kiện lọc bằng "HOẶC" / "VÀ"
# Paginator: chia danh sách dài thành từng trang 10 dòng.
from django.core.paginator import Paginator  # Paginator: cắt danh sách dài thành nhiều trang
# get_object_or_404: lấy một dòng dữ liệu, không có thì trả trang 404. render: dựng trang HTML.
from django.shortcuts import get_object_or_404, render  # lấy 1 dòng dữ liệu (không có -> 404) / dựng trang HTML
# path: khai báo đường dẫn. reverse: từ tên URL suy ra địa chỉ.
from django.urls import NoReverseMatch, path, reverse  # path: khai báo địa chỉ; reverse: từ TÊN url suy ra địa chỉ thật; NoReverseMatch: lỗi khi tên url chưa tồn tại
# Chỉ cho phép mở trang bằng GET (xem), không nhận POST.
from django.views.decorators.http import require_GET  # nhãn: chỉ cho mở trang bằng GET (xem), chặn POST

# lay_vai_tro: biết người đang đăng nhập là Khách hàng / Nhiếp ảnh gia / Quản trị viên.
# vai_tro_required: nhãn chặn người sai vai trò (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403).
from accounts.permissions import lay_vai_tro, vai_tro_required  # biết vai trò người đăng nhập / nhãn chặn sai vai trò
from bookings.huy_booking import co_the_huy, co_the_xac_nhan_hoan_tien, lay_yeu_cau_huy  # T9: nút Hủy + khối thông tin hủy
from bookings.models import Booking  # bảng Booking trong cơ sở dữ liệu
# Hằng số tên trạng thái / vai trò dùng chung của nhóm (không tự gõ chữ tiếng Việt).
from core.constants import LoaiThanhToan, TrangThaiBooking, TrangThaiThanhToan, VaiTro  # tên các trạng thái/vai trò dùng chung
# tinh_so_tien: quy tắc chia 40% / 60% DUY NHẤT của dự án (cùng hàm Thanh toán dùng để thu tiền thật).
from payments.models import tinh_so_tien  # hàm chia tiền cọc 40% / còn lại 60% của nhóm

logger = logging.getLogger(__name__)  # tạo "cây bút ghi log" mang tên file này

# Câu thông báo (đúng chữ trong đặc tả UC4.7).
TB_CHUA_CO_BOOKING = 'Chưa có Booking nào'                      # câu hiện khi người dùng chưa có Booking nào (UC4.7, ngoại lệ 1a)
TB_KHONG_KHOP_BO_LOC = 'Không có Booking nào khớp bộ lọc.'      # câu hiện khi LỌC ra rỗng nhưng người dùng vẫn có Booking

# Giá trị đặc biệt của bộ lọc, nghĩa là "xem tất cả trạng thái" (mặc định của "Booking của tôi").
LOC_TAT_CA = 'tat_ca'  # chữ quy ước cho lựa chọn "Tất cả trạng thái" của ô lọc

# Số dòng trên mỗi trang danh sách.
SO_DONG_MOI_TRANG = 10  # mỗi trang danh sách hiện tối đa 10 Booking

# Nhóm trạng thái dùng cho việc soát khớp với dữ liệu thanh toán (BR4.7-2).
# Từ "Chốt Booking" trở đi (cho tới "Hoàn thành") là các trạng thái mà cọc 40% PHẢI đã được xác nhận.
TRANG_THAI_DA_XAC_NHAN_COC = {  # tập hợp các trạng thái mà cọc 40% bắt buộc phải đã được xác nhận
    TrangThaiBooking.CHOT_BOOKING, TrangThaiBooking.DA_CHUP, TrangThaiBooking.CHO_KH_CHON_ANH,  # chốt -> đã chụp -> chờ chọn ảnh
    TrangThaiBooking.CHO_HAU_KY, TrangThaiBooking.DANG_HAU_KY, TrangThaiBooking.CHO_KH_KIEM_TRA,  # các bước hậu kỳ
    TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN, TrangThaiBooking.HOAN_THANH,  # chờ xác nhận thanh toán, hoàn thành
}
# Các trạng thái mà cọc CHƯA THỂ được xác nhận (Booking chưa tới bước Chốt, hoặc đã kết thúc vì không cọc).
TRANG_THAI_CHUA_CO_COC = {  # tập hợp các trạng thái mà cọc CHƯA ĐƯỢC phép ở trạng thái "đã xác nhận"
    TrangThaiBooking.CHO_XAC_NHAN, TrangThaiBooking.CHO_DAT_COC,  # chưa tới bước chốt
    TrangThaiBooking.DA_TU_CHOI, TrangThaiBooking.HET_THOI_HAN_DAT_COC,  # đã kết thúc mà không có cọc
}


# Trạng thái mà Nhiếp ảnh gia còn việc với ảnh (module Bàn giao ảnh của Nguyên): tải ảnh gốc / bắt đầu hậu kỳ / đang hậu kỳ.
TRANG_THAI_NAG_XU_LY_ANH = (TrangThaiBooking.DA_CHUP, TrangThaiBooking.CHO_HAU_KY, TrangThaiBooking.DANG_HAU_KY)  # 3 trạng thái hiện nút "Tải ảnh / Bắt đầu hậu kỳ"
# Trạng thái mà Khách hàng phải chọn ảnh cần hậu kỳ.
TRANG_THAI_KHACH_CHON_ANH = (TrangThaiBooking.CHO_KH_CHON_ANH,)  # chỉ "Chờ Khách hàng lựa chọn ảnh" hiện nút "Chọn ảnh cần hậu kỳ"


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def _url_neu_co(ten_url, ma_booking):  # đổi tên url của module khác thành địa chỉ; chưa có thì trả None
    """Tên URL -> địa chỉ trang của module khác (delivery, của Nguyên). Trang đó chưa có trên máy này (chưa merge)
    thì trả None để template ẩn nút, không báo lỗi - cùng cách với hàm _url ở core/views_tong_quan.py (B9)."""
    try:  # thử suy ra địa chỉ
        return reverse(ten_url, kwargs={'ma_booking': ma_booking})  # có tên url -> trả địa chỉ thật
    except NoReverseMatch:  # tên url chưa tồn tại
        return None  # None: template không hiện nút


def _ten_hien_thi(user):  # tên hiển thị của một người
    """Họ tên đầy đủ; rỗng thì lấy tên đăng nhập."""
    return user.get_full_name() or user.username  # có họ tên thì dùng, trống thì lấy tên đăng nhập


def _tien(so):  # định dạng tiền kiểu Việt Nam
    """Định dạng tiền kiểu Việt Nam: 1500000 -> '1.500.000'."""
    return f'{int(so):,}'.replace(',', '.')  # int(): bỏ phần lẻ; :, thêm dấu phẩy ngăn nghìn; replace: đổi phẩy thành chấm


def booking_cua_nguoi_dung(user, vai_tro):  # cửa ngõ lấy Booking đúng phạm vi của người dùng
    """HÀM 'CỬA NGÕ' LẤY DỮ LIỆU của UC4.7 - mọi truy vấn của file này đều đi qua đây nên không thể xem lọt
    Booking của người khác (BR4.7-1).
      Khách hàng     -> chỉ Booking do chính mình đặt.
      Nhiếp ảnh gia  -> chỉ Booking gửi đến chính mình.
      Quản trị viên  -> tất cả Booking.
      Vai trò khác   -> không có Booking nào."""
    if vai_tro == VaiTro.KHACH_HANG:  # là Khách hàng
        goc = Booking.objects.filter(MaKhachHang=user)  # chỉ lấy Booking do chính khách này đặt
    elif vai_tro == VaiTro.NHIEP_ANH_GIA:  # là Nhiếp ảnh gia
        goc = Booking.objects.filter(MaNhiepAnhGia__MaTaiKhoan=user)  # chỉ lấy Booking gửi tới chính mình
    elif vai_tro == VaiTro.QUAN_TRI_VIEN:  # là Quản trị viên
        goc = Booking.objects.all()  # lấy tất cả
    else:  # vai trò khác (không liên quan)
        goc = Booking.objects.none()  # không lấy gì cả
    # Nạp sẵn Khách, Gói, Loại hình, Lịch, Nhiếp ảnh gia trong một lần truy vấn để trang chạy nhanh.
    return goc.select_related('MaKhachHang', 'MaGoi__MaLoaiHinh', 'MaLich', 'MaNhiepAnhGia__MaTaiKhoan')  # nạp kèm các bảng liên quan trong 1 lần truy vấn


def chuan_hoa_trang_thai(trang_thai):  # làm sạch giá trị lọc trạng thái
    """Giá trị lạ trên URL (gõ tay) -> quay về 'tất cả', không gây lỗi."""
    return trang_thai if trang_thai in TrangThaiBooking.ALL else LOC_TAT_CA  # hợp lệ thì giữ, lạ thì coi như "tất cả"


def lay_danh_sach_booking(user, vai_tro, trang_thai=LOC_TAT_CA, tu_khoa=''):  # danh sách Booking đã lọc, mới nhất lên đầu
    """UC4.7 bước 2 và luồng 2a: danh sách Booking của người dùng, lọc theo trạng thái, mới nhất lên đầu.
    tu_khoa (chỉ Quản trị viên dùng): mã Booking hoặc tên / email / tên đăng nhập của Khách hay Nhiếp ảnh gia."""
    ds = booking_cua_nguoi_dung(user, vai_tro)  # bước 1: lấy đúng phạm vi Booking của người này (BR4.7-1)
    trang_thai = chuan_hoa_trang_thai(trang_thai)  # bước 2: làm sạch giá trị lọc
    if trang_thai != LOC_TAT_CA:  # nếu người dùng chọn 1 trạng thái cụ thể...
        ds = ds.filter(TrangThai=trang_thai)  # ...thì chỉ giữ Booking có đúng trạng thái đó
    tu_khoa = (tu_khoa or '').strip()  # bỏ khoảng trắng thừa; None -> chuỗi rỗng
    if tu_khoa and vai_tro == VaiTro.QUAN_TRI_VIEN:  # chỉ Quản trị viên mới được tìm kiếm
        dieu_kien = Q()  # điều kiện rỗng, sẽ cộng dần các điều kiện "HOẶC"
        for tien_to in ('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan'):  # tìm ở cả hai phía: Khách và Nhiếp ảnh gia
            dieu_kien |= (Q(**{f'{tien_to}__username__icontains': tu_khoa})  # tên đăng nhập chứa từ khóa (không phân biệt hoa/thường)
                          | Q(**{f'{tien_to}__email__icontains': tu_khoa})  # HOẶC email chứa từ khóa
                          | Q(**{f'{tien_to}__first_name__icontains': tu_khoa})  # HOẶC tên chứa từ khóa
                          | Q(**{f'{tien_to}__last_name__icontains': tu_khoa}))  # HOẶC họ chứa từ khóa
        if tu_khoa.lstrip('#').isdigit():                              # gõ '7' hoặc '#7' -> tìm theo mã Booking
            dieu_kien |= Q(pk=int(tu_khoa.lstrip('#')))  # HOẶC mã Booking đúng bằng số đó
        ds = ds.filter(dieu_kien)  # áp điều kiện tìm kiếm lên danh sách
    # '-MaBooking' đặt sau cùng để hai Booking cùng thời điểm vẫn có thứ tự cố định.
    return ds.order_by('-NgayTao', '-MaBooking')  # dấu '-' = giảm dần: Booking mới nhất lên đầu


def lay_chi_tiet_booking(user, vai_tro, ma_booking):  # một Booking của người dùng; của người khác -> 404
    """UC4.7 bước 3-4: một Booking của người dùng. Của người khác hoặc không tồn tại -> Http404 (BR4.7-1)."""
    return get_object_or_404(booking_cua_nguoi_dung(user, vai_tro), pk=ma_booking)  # tìm trong phạm vi của người này; không có -> 404


def lay_thanh_toan(booking):  # các khoản thanh toán của Booking, cọc trước còn lại sau
    """Các khoản thanh toán của Booking (cọc 40% trước, phần còn lại 60% sau) để hiện cạnh trạng thái (BR4.7-2)."""
    thu_tu = {LoaiThanhToan.TIEN_COC: 0, LoaiThanhToan.PHAN_CON_LAI: 1}  # bảng thứ tự: cọc trước (0), còn lại sau (1)
    cac_khoan = list(booking.thanh_toans.all())  # lấy mọi khoản thanh toán của Booking này thành danh sách
    cac_khoan.sort(key=lambda k: thu_tu.get(k.LoaiThanhToan, 9))  # sắp theo bảng thứ tự trên; loại lạ xếp cuối (9)
    return cac_khoan  # trả danh sách đã sắp


def doi_chieu_thanh_toan(booking):  # soát trạng thái Booking có lệch dữ liệu thanh toán không
    """BR4.7-2: soát xem trạng thái Booking có KHỚP dữ liệu thanh toán không.
    Trả về danh sách câu mô tả chỗ lệch (rỗng = khớp). Chỉ đọc, không sửa gì: sửa là việc của người gọi
    chuyen_trang_thai_booking (Nguyên - Thanh toán). Lệch là dấu hiệu có ai đó đổi trạng thái / thanh toán
    mà không đi qua hàm chung của nhóm."""
    khoan = {k.LoaiThanhToan: k for k in booking.thanh_toans.all()}  # tra nhanh khoản thanh toán theo loại (cọc / còn lại)
    coc = khoan.get(LoaiThanhToan.TIEN_COC)  # khoản cọc 40% (có thể chưa tồn tại -> None)
    con_lai = khoan.get(LoaiThanhToan.PHAN_CON_LAI)  # khoản còn lại 60% (có thể chưa tồn tại)
    coc_da_xac_nhan = coc is not None and coc.TrangThai == TrangThaiThanhToan.DA_DAT_COC  # True nếu cọc có và đã "Đã đặt cọc"
    con_lai_da_tra = con_lai is not None and con_lai.TrangThai == TrangThaiThanhToan.DA_THANH_TOAN  # True nếu 60% có và đã "Đã thanh toán"
    tt = booking.TrangThai  # trạng thái hiện tại của Booking, viết tắt cho gọn
    loi = []  # danh sách chỗ lệch, bắt đầu rỗng
    if tt in TRANG_THAI_DA_XAC_NHAN_COC and not coc_da_xac_nhan:  # Booking đã qua bước cọc mà cọc chưa được xác nhận
        loi.append(f'Booking đang ở "{tt}" nhưng khoản cọc 40% chưa được xác nhận.')  # ghi 1 chỗ lệch
    if tt in TRANG_THAI_CHUA_CO_COC and coc_da_xac_nhan:  # Booking chưa tới bước cọc mà cọc đã xác nhận
        loi.append(f'Khoản cọc 40% đã được xác nhận nhưng Booking vẫn ở "{tt}".')  # ghi 1 chỗ lệch
    if tt == TrangThaiBooking.HOAN_THANH and not con_lai_da_tra:  # đã Hoàn thành mà chưa thu đủ 60%
        loi.append('Booking đã "Hoàn thành" nhưng khoản còn lại 60% chưa được xác nhận thanh toán.')  # ghi 1 chỗ lệch
    if con_lai_da_tra and tt in TRANG_THAI_DA_XAC_NHAN_COC and tt != TrangThaiBooking.HOAN_THANH:  # đã thu đủ 60% mà chưa Hoàn thành
        loi.append(f'Khoản còn lại 60% đã thanh toán nhưng Booking vẫn ở "{tt}".')  # ghi 1 chỗ lệch
    return loi  # rỗng = khớp; có phần tử = lệch


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
# Khách hàng và Nhiếp ảnh gia dùng chung "Booking của tôi"; Quản trị viên có trang riêng.
chi_khach_va_nag = vai_tro_required(VaiTro.KHACH_HANG, VaiTro.NHIEP_ANH_GIA)  # nhãn: chỉ Khách hàng hoặc Nhiếp ảnh gia vào được
chi_quan_tri = vai_tro_required(VaiTro.QUAN_TRI_VIEN)  # nhãn: chỉ Quản trị viên vào được


def _trang_danh_sach(request, ten_url_chi_tiet, tieu_de, co_tim_kiem):  # phần chung của hai trang danh sách
    """Phần chung của hai trang danh sách (Khách / Nhiếp ảnh gia và Quản trị viên)."""
    vai_tro = lay_vai_tro(request.user)  # biết người đang xem là ai
    trang_thai = chuan_hoa_trang_thai(request.GET.get('trang_thai', LOC_TAT_CA))  # đọc ô lọc trên thanh địa chỉ (?trang_thai=...), làm sạch
    tu_khoa = (request.GET.get('q', '') or '').strip() if co_tim_kiem else ''  # đọc ô tìm kiếm (?q=...) nếu trang này có tìm kiếm, không thì rỗng
    ds = lay_danh_sach_booking(request.user, vai_tro, trang_thai, tu_khoa)  # gọi service lấy danh sách đã lọc
    trang = Paginator(ds, SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))  # cắt thành trang 10 dòng, lấy trang số ?page=...
    # Người dùng này có Booking nào không (KHÔNG tính bộ lọc)? Để phân biệt "chưa có Booking nào" với "lọc ra rỗng".
    co_booking = booking_cua_nguoi_dung(request.user, vai_tro).exists()  # True/False: có ít nhất 1 Booking trong phạm vi
    return render(request, 'bookings/theo_doi_danh_sach.html', {  # dựng trang HTML từ template, kèm dữ liệu bên dưới
        'tieu_de': tieu_de,  # tiêu đề trang
        'vai_tro': vai_tro,  # vai trò người xem
        'page_obj': trang,  # trang Booking hiện tại (template duyệt qua để vẽ từng dòng)
        'trang_thai': trang_thai,  # trạng thái đang lọc (để ô chọn giữ nguyên lựa chọn)
        'tu_khoa': tu_khoa,  # từ khóa đang tìm (để ô tìm giữ nguyên chữ đã gõ)
        'co_tim_kiem': co_tim_kiem,  # có hiện ô tìm kiếm không
        'co_booking': co_booking,  # người dùng có Booking nào không
        'ten_url_chi_tiet': ten_url_chi_tiet,  # tên url của trang chi tiết (Khách/NAG hoặc Quản trị)
        'lua_chon_trang_thai': [(LOC_TAT_CA, 'Tất cả trạng thái')] + list(TrangThaiBooking.CHOICES),  # các lựa chọn cho ô lọc: "Tất cả" + 13 trạng thái
        'la_khach': vai_tro == VaiTro.KHACH_HANG,  # người xem là Khách? (template ẩn/hiện cột)
        'la_nag': vai_tro == VaiTro.NHIEP_ANH_GIA,  # người xem là Nhiếp ảnh gia?
        'la_quan_tri': vai_tro == VaiTro.QUAN_TRI_VIEN,  # người xem là Quản trị viên?
        'TB_CHUA_CO_BOOKING': TB_CHUA_CO_BOOKING,  # câu "Chưa có Booking nào" để template in ra
        'TB_KHONG_KHOP_BO_LOC': TB_KHONG_KHOP_BO_LOC,  # câu "Không có Booking nào khớp bộ lọc."
    })


def _trang_chi_tiet(request, ma_booking, ten_url_danh_sach):  # phần chung của hai trang chi tiết
    """Phần chung của hai trang chi tiết."""
    vai_tro = lay_vai_tro(request.user)  # biết người đang xem là ai
    booking = lay_chi_tiet_booking(request.user, vai_tro, ma_booking)   # lấy Booking; của người khác -> 404 (BR4.7-1)
    canh_bao = []  # danh sách cảnh báo lệch thanh toán, mặc định rỗng
    if vai_tro == VaiTro.QUAN_TRI_VIEN:                                  # chỉ Quản trị viên thấy cảnh báo lệch dữ liệu
        canh_bao = doi_chieu_thanh_toan(booking)  # soát lệch giữa trạng thái Booking và thanh toán
        for cau in canh_bao:  # với mỗi chỗ lệch...
            logger.warning('Booking #%s lệch dữ liệu thanh toán: %s', booking.pk, cau)  # ...ghi log để lập trình viên biết
    la_nag = vai_tro == VaiTro.NHIEP_ANH_GIA  # người xem có phải Nhiếp ảnh gia không
    la_khach = vai_tro == VaiTro.KHACH_HANG  # người xem có phải Khách hàng không
    yeu_cau_huy = lay_yeu_cau_huy(booking)  # T9: yêu cầu hủy của Booking (None nếu chưa bị hủy)
    return render(request, 'bookings/theo_doi_chi_tiet.html', {  # dựng trang chi tiết, kèm dữ liệu bên dưới
        'booking': booking,  # Booking đang xem
        'vai_tro': vai_tro,  # vai trò người xem
        'la_khach': vai_tro == VaiTro.KHACH_HANG,  # người xem là Khách?
        'la_nag': la_nag,  # người xem là Nhiếp ảnh gia?
        'la_quan_tri': vai_tro == VaiTro.QUAN_TRI_VIEN,  # người xem là Quản trị viên?
        'ten_khach': _ten_hien_thi(booking.MaKhachHang),  # tên Khách để hiển thị
        'ten_nag': _ten_hien_thi(booking.MaNhiepAnhGia.MaTaiKhoan),  # tên Nhiếp ảnh gia để hiển thị
        'tong_gia': _tien(booking.TongGiaTri),  # tổng giá trị, định dạng 1.500.000
        'tien_coc': _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC)),  # số tiền cọc 40%
        'tien_con_lai': _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.PHAN_CON_LAI)),  # số tiền còn lại 60%
        'lich_su': booking.lich_su_trang_thai.all(),                     # lịch sử đổi trạng thái, đã sắp từ cũ đến mới (Meta.ordering)
        'thanh_toan': lay_thanh_toan(booking),  # các khoản thanh toán của Booking
        'canh_bao': canh_bao,  # cảnh báo lệch (chỉ Quản trị viên có nội dung)
        'co_the_huy': (la_khach or la_nag) and co_the_huy(booking),  # T9: hiện nút "Hủy Booking" (Quản trị viên không hủy)
        'yeu_cau_huy': yeu_cau_huy,  # T9: khối "Thông tin hủy" (bên hủy, lý do, xử lý tiền cọc, hoàn tiền)
        'co_the_xac_nhan_hoan_tien': la_khach and co_the_xac_nhan_hoan_tien(yeu_cau_huy),  # T9: nút "Tôi đã nhận lại tiền cọc"
        'url_danh_sach': reverse(ten_url_danh_sach),  # địa chỉ của nút "Quay lại danh sách"
        # Nhiếp ảnh gia còn việc phải làm với Booking này ("Chờ xác nhận" / "Chốt Booking") -> link tới màn xử lý của T5/T8.
        'url_xu_ly': (reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': booking.pk})  # địa chỉ màn xử lý của Nhiếp ảnh gia...
                      if la_nag and booking.TrangThai in (TrangThaiBooking.CHO_XAC_NHAN,  # ...chỉ khi là Nhiếp ảnh gia VÀ Booking đang ở
                                                          TrangThaiBooking.CHOT_BOOKING) else None),  # "Chờ xác nhận"/"Chốt Booking"; không thì None
        # Khách hàng khi Booking "Chờ Khách hàng lựa chọn ảnh" -> nút tới trang chọn ảnh (N6). Quản trị viên và Nhiếp ảnh gia không có nút này.
        'url_chon_anh': (_url_neu_co('chon_anh_hau_ky', booking.pk)  # địa chỉ trang chọn ảnh cần hậu kỳ (tên url của Nguyên)...
                         if la_khach and booking.TrangThai in TRANG_THAI_KHACH_CHON_ANH else None),  # ...chỉ khi là Khách VÀ đúng trạng thái; không thì None
        # Nhiếp ảnh gia khi Booking "Đã chụp" / "Chờ hậu kỳ" / "Đang hậu kỳ" -> nút tới trang tải ảnh / hậu kỳ (N4, N5). Khách và Quản trị viên không có nút này.
        'url_tai_anh': (_url_neu_co('tai_anh_len', booking.pk)  # địa chỉ trang tải ảnh / hậu kỳ (tên url của Nguyên)...
                        if la_nag and booking.TrangThai in TRANG_THAI_NAG_XU_LY_ANH else None),  # ...chỉ khi là Nhiếp ảnh gia VÀ đúng trạng thái; không thì None
    })


@chi_khach_va_nag  # nhãn: chặn người sai vai trò (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
@require_GET  # nhãn: chỉ nhận yêu cầu xem (GET)
def danh_sach_cua_toi(request):  # view: Booking của tôi (Khách / Nhiếp ảnh gia)
    """UC4.7 bước 1-2 và luồng 2a: "Booking của tôi" của Khách hàng / Nhiếp ảnh gia."""
    return _trang_danh_sach(request, 'chi_tiet_booking', 'Booking của tôi', co_tim_kiem=False)  # không có ô tìm kiếm; link chi tiết = chi_tiet_booking


@chi_khach_va_nag  # chặn sai vai trò
@require_GET  # chỉ GET
def chi_tiet_cua_toi(request, ma_booking):  # view: chi tiết Booking của tôi
    """UC4.7 bước 3-4: chi tiết + lịch sử đổi trạng thái. Booking của người khác -> 404."""
    return _trang_chi_tiet(request, ma_booking, 'my_bookings')  # nút quay lại trỏ về "Booking của tôi"


@chi_quan_tri  # chỉ Quản trị viên
@require_GET  # chỉ GET
def danh_sach_quan_tri(request):  # view: Quản trị viên xem tất cả Booking
    """Quản trị viên tra cứu tất cả Booking (lọc theo trạng thái + tìm theo mã / tên / email)."""
    return _trang_danh_sach(request, 'admin_booking_detail', 'Tất cả Booking', co_tim_kiem=True)  # có ô tìm kiếm; link chi tiết dành cho Quản trị


@chi_quan_tri  # chỉ Quản trị viên
@require_GET  # chỉ GET
def chi_tiet_quan_tri(request, ma_booking):  # view: Quản trị viên xem chi tiết một Booking
    """Quản trị viên xem chi tiết một Booking bất kỳ (kèm cảnh báo nếu lệch dữ liệu thanh toán)."""
    return _trang_chi_tiet(request, ma_booking, 'admin_bookings')  # nút quay lại trỏ về danh sách của Quản trị


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.theo_doi')),)
urlpatterns = [  # danh sách địa chỉ của file này
    path('cua-toi/', danh_sach_cua_toi, name='my_bookings'),  # /bookings/cua-toi/ -> danh sách "Booking của tôi"
    path('cua-toi/<int:ma_booking>/', chi_tiet_cua_toi, name='chi_tiet_booking'),  # /bookings/cua-toi/7/ -> chi tiết Booking số 7
    path('quan-tri/', danh_sach_quan_tri, name='admin_bookings'),  # /bookings/quan-tri/ -> Quản trị viên xem tất cả
    path('quan-tri/<int:ma_booking>/', chi_tiet_quan_tri, name='admin_booking_detail'),  # /bookings/quan-tri/7/ -> Quản trị xem chi tiết
]

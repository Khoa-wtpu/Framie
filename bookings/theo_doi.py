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
import logging

# Q: ghép nhiều điều kiện tìm kiếm bằng "HOẶC" (ô tìm kiếm của Quản trị viên).
from django.db.models import Q
# Paginator: chia danh sách dài thành từng trang 10 dòng.
from django.core.paginator import Paginator
# get_object_or_404: lấy một dòng dữ liệu, không có thì trả trang 404. render: dựng trang HTML.
from django.shortcuts import get_object_or_404, render
# path: khai báo đường dẫn. reverse: từ tên URL suy ra địa chỉ.
from django.urls import path, reverse
# Chỉ cho phép mở trang bằng GET (xem), không nhận POST.
from django.views.decorators.http import require_GET

# lay_vai_tro: biết người đang đăng nhập là Khách hàng / Nhiếp ảnh gia / Quản trị viên.
# vai_tro_required: nhãn chặn người sai vai trò (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403).
from accounts.permissions import lay_vai_tro, vai_tro_required
from bookings.models import Booking
# Hằng số tên trạng thái / vai trò dùng chung của nhóm (không tự gõ chữ tiếng Việt).
from core.constants import LoaiThanhToan, TrangThaiBooking, TrangThaiThanhToan, VaiTro
# tinh_so_tien: quy tắc chia 40% / 60% DUY NHẤT của dự án (cùng hàm Thanh toán dùng để thu tiền thật).
from payments.models import tinh_so_tien

logger = logging.getLogger(__name__)

# Câu thông báo (đúng chữ trong đặc tả UC4.7).
TB_CHUA_CO_BOOKING = 'Chưa có Booking nào'                      # UC4.7, ngoại lệ 1a
TB_KHONG_KHOP_BO_LOC = 'Không có Booking nào khớp bộ lọc.'      # lọc ra rỗng (luồng 2a) nhưng người dùng CÓ Booking

# Giá trị đặc biệt của bộ lọc, nghĩa là "xem tất cả trạng thái" (mặc định của "Booking của tôi").
LOC_TAT_CA = 'tat_ca'

# Số dòng trên mỗi trang danh sách.
SO_DONG_MOI_TRANG = 10

# Nhóm trạng thái dùng cho việc soát khớp với dữ liệu thanh toán (BR4.7-2).
# Từ "Chốt Booking" trở đi (cho tới "Hoàn thành") là các trạng thái mà cọc 40% PHẢI đã được xác nhận.
TRANG_THAI_DA_XAC_NHAN_COC = {
    TrangThaiBooking.CHOT_BOOKING, TrangThaiBooking.DA_CHUP, TrangThaiBooking.CHO_KH_CHON_ANH,
    TrangThaiBooking.CHO_HAU_KY, TrangThaiBooking.DANG_HAU_KY, TrangThaiBooking.CHO_KH_KIEM_TRA,
    TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN, TrangThaiBooking.HOAN_THANH,
}
# Các trạng thái mà cọc CHƯA THỂ được xác nhận (Booking chưa tới bước Chốt, hoặc đã kết thúc vì không cọc).
TRANG_THAI_CHUA_CO_COC = {
    TrangThaiBooking.CHO_XAC_NHAN, TrangThaiBooking.CHO_DAT_COC,
    TrangThaiBooking.DA_TU_CHOI, TrangThaiBooking.HET_THOI_HAN_DAT_COC,
}


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def _ten_hien_thi(user):
    """Họ tên đầy đủ; rỗng thì lấy tên đăng nhập."""
    return user.get_full_name() or user.username


def _tien(so):
    """Định dạng tiền kiểu Việt Nam: 1500000 -> '1.500.000'."""
    return f'{int(so):,}'.replace(',', '.')


def booking_cua_nguoi_dung(user, vai_tro):
    """HÀM 'CỬA NGÕ' LẤY DỮ LIỆU của UC4.7 - mọi truy vấn của file này đều đi qua đây nên không thể xem lọt
    Booking của người khác (BR4.7-1).
      Khách hàng     -> chỉ Booking do chính mình đặt.
      Nhiếp ảnh gia  -> chỉ Booking gửi đến chính mình.
      Quản trị viên  -> tất cả Booking.
      Vai trò khác   -> không có Booking nào."""
    if vai_tro == VaiTro.KHACH_HANG:
        goc = Booking.objects.filter(MaKhachHang=user)
    elif vai_tro == VaiTro.NHIEP_ANH_GIA:
        goc = Booking.objects.filter(MaNhiepAnhGia__MaTaiKhoan=user)
    elif vai_tro == VaiTro.QUAN_TRI_VIEN:
        goc = Booking.objects.all()
    else:
        goc = Booking.objects.none()
    # Nạp sẵn Khách, Gói, Loại hình, Lịch, Nhiếp ảnh gia trong một lần truy vấn để trang chạy nhanh.
    return goc.select_related('MaKhachHang', 'MaGoi__MaLoaiHinh', 'MaLich', 'MaNhiepAnhGia__MaTaiKhoan')


def chuan_hoa_trang_thai(trang_thai):
    """Giá trị lạ trên URL (gõ tay) -> quay về 'tất cả', không gây lỗi."""
    return trang_thai if trang_thai in TrangThaiBooking.ALL else LOC_TAT_CA


def lay_danh_sach_booking(user, vai_tro, trang_thai=LOC_TAT_CA, tu_khoa=''):
    """UC4.7 bước 2 và luồng 2a: danh sách Booking của người dùng, lọc theo trạng thái, mới nhất lên đầu.
    tu_khoa (chỉ Quản trị viên dùng): mã Booking hoặc tên / email / tên đăng nhập của Khách hay Nhiếp ảnh gia."""
    ds = booking_cua_nguoi_dung(user, vai_tro)
    trang_thai = chuan_hoa_trang_thai(trang_thai)
    if trang_thai != LOC_TAT_CA:
        ds = ds.filter(TrangThai=trang_thai)
    tu_khoa = (tu_khoa or '').strip()
    if tu_khoa and vai_tro == VaiTro.QUAN_TRI_VIEN:
        dieu_kien = Q()
        for tien_to in ('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan'):  # tìm ở cả hai phía
            dieu_kien |= (Q(**{f'{tien_to}__username__icontains': tu_khoa})
                          | Q(**{f'{tien_to}__email__icontains': tu_khoa})
                          | Q(**{f'{tien_to}__first_name__icontains': tu_khoa})
                          | Q(**{f'{tien_to}__last_name__icontains': tu_khoa}))
        if tu_khoa.lstrip('#').isdigit():                              # gõ '7' hoặc '#7' -> tìm theo mã Booking
            dieu_kien |= Q(pk=int(tu_khoa.lstrip('#')))
        ds = ds.filter(dieu_kien)
    # '-MaBooking' đặt sau cùng để hai Booking cùng thời điểm vẫn có thứ tự cố định.
    return ds.order_by('-NgayTao', '-MaBooking')


def lay_chi_tiet_booking(user, vai_tro, ma_booking):
    """UC4.7 bước 3-4: một Booking của người dùng. Của người khác hoặc không tồn tại -> Http404 (BR4.7-1)."""
    return get_object_or_404(booking_cua_nguoi_dung(user, vai_tro), pk=ma_booking)


def lay_thanh_toan(booking):
    """Các khoản thanh toán của Booking (cọc 40% trước, phần còn lại 60% sau) để hiện cạnh trạng thái (BR4.7-2)."""
    thu_tu = {LoaiThanhToan.TIEN_COC: 0, LoaiThanhToan.PHAN_CON_LAI: 1}
    cac_khoan = list(booking.thanh_toans.all())
    cac_khoan.sort(key=lambda k: thu_tu.get(k.LoaiThanhToan, 9))
    return cac_khoan


def doi_chieu_thanh_toan(booking):
    """BR4.7-2: soát xem trạng thái Booking có KHỚP dữ liệu thanh toán không.
    Trả về danh sách câu mô tả chỗ lệch (rỗng = khớp). Chỉ đọc, không sửa gì: sửa là việc của người gọi
    chuyen_trang_thai_booking (Nguyên - Thanh toán). Lệch là dấu hiệu có ai đó đổi trạng thái / thanh toán
    mà không đi qua hàm chung của nhóm."""
    khoan = {k.LoaiThanhToan: k for k in booking.thanh_toans.all()}
    coc = khoan.get(LoaiThanhToan.TIEN_COC)
    con_lai = khoan.get(LoaiThanhToan.PHAN_CON_LAI)
    coc_da_xac_nhan = coc is not None and coc.TrangThai == TrangThaiThanhToan.DA_DAT_COC
    con_lai_da_tra = con_lai is not None and con_lai.TrangThai == TrangThaiThanhToan.DA_THANH_TOAN
    tt = booking.TrangThai
    loi = []
    if tt in TRANG_THAI_DA_XAC_NHAN_COC and not coc_da_xac_nhan:
        loi.append(f'Booking đang ở "{tt}" nhưng khoản cọc 40% chưa được xác nhận.')
    if tt in TRANG_THAI_CHUA_CO_COC and coc_da_xac_nhan:
        loi.append(f'Khoản cọc 40% đã được xác nhận nhưng Booking vẫn ở "{tt}".')
    if tt == TrangThaiBooking.HOAN_THANH and not con_lai_da_tra:
        loi.append('Booking đã "Hoàn thành" nhưng khoản còn lại 60% chưa được xác nhận thanh toán.')
    if con_lai_da_tra and tt in TRANG_THAI_DA_XAC_NHAN_COC and tt != TrangThaiBooking.HOAN_THANH:
        loi.append(f'Khoản còn lại 60% đã thanh toán nhưng Booking vẫn ở "{tt}".')
    return loi


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
# Khách hàng và Nhiếp ảnh gia dùng chung "Booking của tôi"; Quản trị viên có trang riêng.
chi_khach_va_nag = vai_tro_required(VaiTro.KHACH_HANG, VaiTro.NHIEP_ANH_GIA)
chi_quan_tri = vai_tro_required(VaiTro.QUAN_TRI_VIEN)


def _trang_danh_sach(request, ten_url_chi_tiet, tieu_de, co_tim_kiem):
    """Phần chung của hai trang danh sách (Khách / Nhiếp ảnh gia và Quản trị viên)."""
    vai_tro = lay_vai_tro(request.user)
    trang_thai = chuan_hoa_trang_thai(request.GET.get('trang_thai', LOC_TAT_CA))
    tu_khoa = (request.GET.get('q', '') or '').strip() if co_tim_kiem else ''
    ds = lay_danh_sach_booking(request.user, vai_tro, trang_thai, tu_khoa)
    trang = Paginator(ds, SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))
    # Người dùng này có Booking nào không (KHÔNG tính bộ lọc)? Để phân biệt "chưa có Booking nào" với "lọc ra rỗng".
    co_booking = booking_cua_nguoi_dung(request.user, vai_tro).exists()
    return render(request, 'bookings/theo_doi_danh_sach.html', {
        'tieu_de': tieu_de,
        'vai_tro': vai_tro,
        'page_obj': trang,
        'trang_thai': trang_thai,
        'tu_khoa': tu_khoa,
        'co_tim_kiem': co_tim_kiem,
        'co_booking': co_booking,
        'ten_url_chi_tiet': ten_url_chi_tiet,
        'lua_chon_trang_thai': [(LOC_TAT_CA, 'Tất cả trạng thái')] + list(TrangThaiBooking.CHOICES),
        'la_khach': vai_tro == VaiTro.KHACH_HANG,
        'la_nag': vai_tro == VaiTro.NHIEP_ANH_GIA,
        'la_quan_tri': vai_tro == VaiTro.QUAN_TRI_VIEN,
        'TB_CHUA_CO_BOOKING': TB_CHUA_CO_BOOKING,
        'TB_KHONG_KHOP_BO_LOC': TB_KHONG_KHOP_BO_LOC,
    })


def _trang_chi_tiet(request, ma_booking, ten_url_danh_sach):
    """Phần chung của hai trang chi tiết."""
    vai_tro = lay_vai_tro(request.user)
    booking = lay_chi_tiet_booking(request.user, vai_tro, ma_booking)   # của người khác -> 404 (BR4.7-1)
    canh_bao = []
    if vai_tro == VaiTro.QUAN_TRI_VIEN:                                  # chỉ Quản trị viên thấy cảnh báo lệch dữ liệu
        canh_bao = doi_chieu_thanh_toan(booking)
        for cau in canh_bao:
            logger.warning('Booking #%s lệch dữ liệu thanh toán: %s', booking.pk, cau)
    la_nag = vai_tro == VaiTro.NHIEP_ANH_GIA
    return render(request, 'bookings/theo_doi_chi_tiet.html', {
        'booking': booking,
        'vai_tro': vai_tro,
        'la_khach': vai_tro == VaiTro.KHACH_HANG,
        'la_nag': la_nag,
        'la_quan_tri': vai_tro == VaiTro.QUAN_TRI_VIEN,
        'ten_khach': _ten_hien_thi(booking.MaKhachHang),
        'ten_nag': _ten_hien_thi(booking.MaNhiepAnhGia.MaTaiKhoan),
        'tong_gia': _tien(booking.TongGiaTri),
        'tien_coc': _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.TIEN_COC)),
        'tien_con_lai': _tien(tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.PHAN_CON_LAI)),
        'lich_su': booking.lich_su_trang_thai.all(),                     # đã sắp từ cũ đến mới (Meta.ordering)
        'thanh_toan': lay_thanh_toan(booking),
        'canh_bao': canh_bao,
        'url_danh_sach': reverse(ten_url_danh_sach),
        # Nhiếp ảnh gia còn việc phải làm với Booking này ("Chờ xác nhận" / "Chốt Booking") -> link tới màn xử lý của T5/T8.
        'url_xu_ly': (reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': booking.pk})
                      if la_nag and booking.TrangThai in (TrangThaiBooking.CHO_XAC_NHAN,
                                                          TrangThaiBooking.CHOT_BOOKING) else None),
    })


@chi_khach_va_nag
@require_GET
def danh_sach_cua_toi(request):
    """UC4.7 bước 1-2 và luồng 2a: "Booking của tôi" của Khách hàng / Nhiếp ảnh gia."""
    return _trang_danh_sach(request, 'chi_tiet_booking', 'Booking của tôi', co_tim_kiem=False)


@chi_khach_va_nag
@require_GET
def chi_tiet_cua_toi(request, ma_booking):
    """UC4.7 bước 3-4: chi tiết + lịch sử đổi trạng thái. Booking của người khác -> 404."""
    return _trang_chi_tiet(request, ma_booking, 'my_bookings')


@chi_quan_tri
@require_GET
def danh_sach_quan_tri(request):
    """Quản trị viên tra cứu tất cả Booking (lọc theo trạng thái + tìm theo mã / tên / email)."""
    return _trang_danh_sach(request, 'admin_booking_detail', 'Tất cả Booking', co_tim_kiem=True)


@chi_quan_tri
@require_GET
def chi_tiet_quan_tri(request, ma_booking):
    """Quản trị viên xem chi tiết một Booking bất kỳ (kèm cảnh báo nếu lệch dữ liệu thanh toán)."""
    return _trang_chi_tiet(request, ma_booking, 'admin_bookings')


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.theo_doi')),)
urlpatterns = [
    path('cua-toi/', danh_sach_cua_toi, name='my_bookings'),
    path('cua-toi/<int:ma_booking>/', chi_tiet_cua_toi, name='chi_tiet_booking'),
    path('quan-tri/', danh_sach_quan_tri, name='admin_bookings'),
    path('quan-tri/<int:ma_booking>/', chi_tiet_quan_tri, name='admin_booking_detail'),
]

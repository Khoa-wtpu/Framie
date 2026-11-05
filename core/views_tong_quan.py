# =====================================================================
# core/views_tong_quan.py  -  B9: Trang tổng quan sau đăng nhập
#
#   Khách hàng    : Booking đang xử lý + thông báo mới.
#   Nhiếp ảnh gia : yêu cầu Booking mới + lịch sắp tới + tình trạng hồ sơ.
#                   (hồ sơ chưa được duyệt chỉ thấy tình trạng hồ sơ, giống menu bị rút gọn ở header)
#   Quản trị viên : chuyển sang trang tổng quan riêng của Quản trị (B7, name='admin_dashboard').
#
# Trang này KHÔNG tự tính nghiệp vụ: chỉ gọi lại các hàm/bảng có sẵn của module khác
# (bookings.theo_doi, bookings.tiep_nhan, notifications, schedule, profiles) rồi gom lại.
# =====================================================================
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.permissions import lay_vai_tro
from bookings.theo_doi import booking_cua_nguoi_dung          # "cửa ngõ" lấy Booking của chính người dùng (BR4.7-1)
from bookings.tiep_nhan import dem_cho_xac_nhan               # số yêu cầu đang chờ Nhiếp ảnh gia xác nhận
from core.constants import TrangThaiBooking as BK, TrangThaiDoc, TrangThaiHoSo, VaiTro
from notifications.models import ThongBao
from notifications.services import dem_chua_doc
from profiles.models import DuyetHoSo
from schedule.services import dem_khung_gio_trong

SO_DONG_TOI_DA = 5          # mỗi danh sách trên trang chỉ hiện 5 dòng đầu, còn lại bấm "Xem tất cả"
SO_NGAY_KHUNG_GIO = 7       # "khung giờ còn trống trong 7 ngày tới" (cùng cách tính với Trang chủ)

# 4 trạng thái kết thúc: Booking ở đây không còn "đang xử lý" nữa.
TRANG_THAI_KET_THUC = [BK.HOAN_THANH, BK.DA_TU_CHOI, BK.HET_THOI_HAN_DAT_COC, BK.DA_HUY]


def _url(ten_url, args=None):
    """Tên URL -> đường dẫn; trang của bạn khác chưa có thì trả '' (template ẩn nút, không báo lỗi)."""
    try:
        return reverse(ten_url, args=args)
    except NoReverseMatch:
        return ''


def _dong_booking(booking, ten_url_chi_tiet, ben_kia):
    """Một dòng Booking trên trang. ben_kia: tên người đối diện (Nhiếp ảnh gia nếu là Khách, Khách nếu là Nhiếp ảnh gia)."""
    return {'ma': booking.pk, 'goi': booking.MaGoi.TenGoi, 'ben_kia': ben_kia,
            'gio_chup': booking.NgayGioChup, 'trang_thai': booking.TrangThai,
            'href': _url(ten_url_chi_tiet, [booking.pk])}


def _ten(user):
    return user.get_full_name() or user.username


# ---------------------------------------------------------------- Khách hàng
def _du_lieu_khach_hang(user):
    dang_xu_ly = (booking_cua_nguoi_dung(user, VaiTro.KHACH_HANG)
                  .exclude(TrangThai__in=TRANG_THAI_KET_THUC).order_by('-NgayTao', '-MaBooking'))
    thong_bao = ThongBao.objects.filter(MaNguoiNhan=user, TrangThaiDoc=TrangThaiDoc.CHUA_DOC)   # mặc định mới nhất lên đầu
    return {
        'so_dang_xu_ly': dang_xu_ly.count(),
        'dang_xu_ly': [_dong_booking(b, 'chi_tiet_booking', _ten(b.MaNhiepAnhGia.MaTaiKhoan))
                       for b in dang_xu_ly[:SO_DONG_TOI_DA]],
        'so_thong_bao': dem_chua_doc(user),
        'thong_bao': [{'tieu_de': t.TieuDe, 'noi_dung': t.NoiDung, 'ngay_tao': t.NgayTao,
                       'href': _url('chi_tiet_booking', [t.MaBooking_id]) if t.MaBooking_id else ''}
                      for t in thong_bao[:SO_DONG_TOI_DA]],
        'url_booking_cua_toi': _url('my_bookings'),
        'url_thong_bao': _url('notifications'),
        'url_tim_kiem': _url('search'),
    }


# ------------------------------------------------------------- Nhiếp ảnh gia
def _phan_hoi_gan_nhat(nag):
    """Lý do Quản trị viên đã ghi ở lượt duyệt gần nhất (hiện khi hồ sơ chưa được duyệt)."""
    luot = DuyetHoSo.objects.filter(MaNhiepAnhGia=nag, KetQua__isnull=False).first()   # mặc định lượt mới nhất lên đầu
    return luot.NoiDungPhanHoi if luot and luot.NoiDungPhanHoi else ''


def _du_lieu_nhiep_anh_gia(user):
    trang_thai = user.trang_thai_ho_so
    da_duyet = trang_thai == TrangThaiHoSo.DA_DUYET
    try:
        nag = user.ho_so_nhiep_anh_gia
    except ObjectDoesNotExist:          # tài khoản có vai trò Nhiếp ảnh gia nhưng chưa tạo hồ sơ
        nag = None

    du_lieu = {
        'da_duyet': da_duyet,
        'da_tu_choi': trang_thai == TrangThaiHoSo.DA_TU_CHOI,
        'trang_thai_ho_so': trang_thai,
        'phan_hoi': '' if da_duyet or nag is None else _phan_hoi_gan_nhat(nag),
        'url_ho_so': _url('photographer_profile') or _url('cap_nhat_ho_so'),
    }
    if not da_duyet:                    # Chờ duyệt / Đã từ chối: chỉ có tình trạng hồ sơ
        return du_lieu

    cua_toi = booking_cua_nguoi_dung(user, VaiTro.NHIEP_ANH_GIA)
    yeu_cau_moi = cua_toi.filter(TrangThai=BK.CHO_XAC_NHAN).order_by('-NgayTao', '-MaBooking')
    lich_sap_toi = (cua_toi.filter(TrangThai=BK.CHOT_BOOKING, NgayGioChup__gte=timezone.now())
                    .order_by('NgayGioChup', 'MaBooking'))
    du_lieu.update({
        'so_yeu_cau_moi': dem_cho_xac_nhan(user),
        'yeu_cau_moi': [_dong_booking(b, 'chi_tiet_yeu_cau_booking', _ten(b.MaKhachHang))
                        for b in yeu_cau_moi[:SO_DONG_TOI_DA]],
        'so_lich_sap_toi': lich_sap_toi.count(),
        'lich_sap_toi': [_dong_booking(b, 'chi_tiet_yeu_cau_booking', _ten(b.MaKhachHang))
                         for b in lich_sap_toi[:SO_DONG_TOI_DA]],
        'so_khung_gio_trong': dem_khung_gio_trong(nag, SO_NGAY_KHUNG_GIO) if nag else 0,
        'so_ngay_khung_gio': SO_NGAY_KHUNG_GIO,
        'url_quan_ly_booking': _url('manage_bookings'),
        'url_lich': _url('my_calendar'),
    })
    return du_lieu


# ------------------------------------------------------------------- View
@login_required
@require_GET
def tong_quan(request):
    vai_tro = lay_vai_tro(request.user)
    if vai_tro == VaiTro.QUAN_TRI_VIEN:      # Quản trị viên có trang tổng quan riêng (B7)
        return redirect(_url('admin_dashboard') or 'home')
    la_nag = vai_tro == VaiTro.NHIEP_ANH_GIA
    return render(request, 'core/tong_quan.html', {
        'la_nhiep_anh_gia': la_nag,
        'khach': None if la_nag else _du_lieu_khach_hang(request.user),
        'nag': _du_lieu_nhiep_anh_gia(request.user) if la_nag else None,
    })

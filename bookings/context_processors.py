# bookings/context_processors.py - Banner "Bạn đang giữ khung giờ ..." hiện trên mọi trang cho Khách hàng đang giữ chỗ.
# Đăng ký trong config/settings.py (TEMPLATES -> context_processors) và include trong templates/base.html.
# Chỉ ĐỌC (không nhả slot, không ghi gì): lượt giữ đã quá hạn thì không hiện; việc nhả slot do giai_phong_giu_cho_het_han lo.
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from bookings.models import GiuCho
from core.constants import TrangThaiGiuCho

# Các trang đã tự có khung giữ chỗ/đếm ngược riêng, không hiện banner chung để khỏi trùng.
TRANG_KHONG_HIEN = {'man_hinh_giu_cho', 'gui_booking', 'lich_chon_slot'}


def giu_cho_banner(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    khop = getattr(request, 'resolver_match', None)
    if khop is not None and khop.url_name in TRANG_KHONG_HIEN:
        return {}
    bay_gio = timezone.now()
    giu_cho = (GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan')
               .filter(MaKhachHang=user, TrangThai=TrangThaiGiuCho.DANG_GIU, ThoiDiemHetHan__gt=bay_gio)
               .order_by('-ThoiDiemGiu').first())
    if giu_cho is None:
        return {}
    try:
        url_tiep_tuc = reverse('gui_booking', kwargs={'ma_giu_cho': giu_cho.pk})
        url_trang_thai = reverse('trang_thai_giu_cho', kwargs={'ma_giu_cho': giu_cho.pk})
    except NoReverseMatch:
        return {}
    lich = giu_cho.MaLich
    nag_user = lich.MaNhiepAnhGia.MaTaiKhoan
    con_lai = max(0, int((giu_cho.ThoiDiemHetHan - bay_gio).total_seconds()))
    return {'giu_cho_banner': {
        'khung_gio': f'{lich.Ngay:%d/%m/%Y} {lich.GioBatDau:%H:%M}–{lich.GioKetThuc:%H:%M}',
        'ten_nag': nag_user.get_full_name() or nag_user.username,
        'con_lai_giay': con_lai,
        'con_lai_chu': f'{con_lai // 60:02d}:{con_lai % 60:02d}',
        'url_tiep_tuc': url_tiep_tuc,
        'url_trang_thai': url_trang_thai,
    }}

# profiles/views_cong_khai.py - K9: Hồ sơ công khai của Nhiếp ảnh gia (UC2.3, wireframe SC2.3 và SC2.4). Không cần đăng nhập.
#   photographer_detail  : giới thiệu, gói dịch vụ, Portfolio, LỊCH KHẢ DỤNG theo tuần, đánh giá; nút "Liên hệ" và "Đặt lịch"
#   photographer_project : các ảnh của một project trong Portfolio (xem phóng to)
# Chỉ hồ sơ "Đã duyệt" và tài khoản còn hoạt động mới xem được (dùng chung quy tắc với trang Tìm kiếm); còn lại báo 404.
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib.auth.views import redirect_to_login
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from bookings.models import GiuCho
from core.constants import LoaiHauKy, TrangThaiGiuCho, TrangThaiGoi, TrangThaiSlot, VaiTro
from core.status_tones import tone_of
from profiles.models import GoiDichVu
from reviews.models import DanhGia
from schedule import quan_ly
from schedule.models import LichKhaDung
from search.services import dinh_dang_tien, nhiep_anh_gia_cong_khai

SO_DANH_GIA_HIEN = 10     # chỉ hiện các đánh giá mới nhất
SO_TUAN_TOI_DA = 8        # cho xem lịch tối đa 8 tuần sau tuần hiện tại
MO_TA_LICH = 'lich-kha-dung'


def _lay_nhiep_anh_gia(ma):
    """Hồ sơ công khai kèm điểm trung bình và số đánh giá; không công khai hoặc không tồn tại thì 404."""
    ds = (nhiep_anh_gia_cong_khai()
          .select_related('MaTaiKhoan')
          .prefetch_related('loai_hinh_chup', 'phong_cach', 'khu_vuc')
          .annotate(diem_tb=Avg('danh_gias__Diem'), so_dg=Count('danh_gias')))
    return get_object_or_404(ds, pk=ma)


def _ten(user):
    return user.get_full_name() or user.username


def nhan_thoi_luong(phut):
    """90 -> '1 giờ 30 phút', 60 -> '1 giờ', 45 -> '45 phút'."""
    gio, du = divmod(int(phut), 60)
    if not gio:
        return f'{du} phút'
    return f'{gio} giờ' + (f' {du} phút' if du else '')


def _url_co_the(ten_url, **kwargs):
    try:
        return reverse(ten_url, kwargs=kwargs)
    except NoReverseMatch:
        return ''


# ---------------------------------------------------------------------
# Gói dịch vụ
# ---------------------------------------------------------------------
def _goi_duoc_chon(nag, chuoi):
    """?goi=<mã>: chỉ nhận gói 'Đang áp dụng' của chính Nhiếp ảnh gia này; gõ bậy thì coi như chưa chọn."""
    try:
        ma = int(chuoi)
    except (TypeError, ValueError):
        return None
    return GoiDichVu.objects.filter(pk=ma, MaNhiepAnhGia=nag, TrangThai=TrangThaiGoi.DANG_AP_DUNG).first()


def _hau_ky(goi):
    if goi.LoaiHauKy == LoaiHauKy.GIOI_HAN and goi.SoAnhHauKyToiDa:
        return f'giới hạn {goi.SoAnhHauKyToiDa} ảnh'
    return 'toàn bộ ảnh'


def _cac_goi(nag, goi_chon, url_goi):
    """Gói 'Đang áp dụng' chọn được; 'Ngừng áp dụng' hiện mờ, không chọn được; 'Đã ẩn' không hiện (ghi chú wireframe SC2.3)."""
    ds = (GoiDichVu.objects.filter(MaNhiepAnhGia=nag).exclude(TrangThai=TrangThaiGoi.DA_AN)
          .select_related('MaLoaiHinh').order_by('MaLoaiHinh__TenLoaiHinh', 'Gia', 'pk'))
    ket_qua = []
    for g in ds:
        ap_dung = g.TrangThai == TrangThaiGoi.DANG_AP_DUNG
        ket_qua.append({
            'pk': g.pk, 'ten': g.TenGoi, 'mo_ta': g.MoTa or '', 'gia': dinh_dang_tien(g.Gia),
            'loai_hinh': g.MaLoaiHinh.TenLoaiHinh, 'thoi_luong': nhan_thoi_luong(g.ThoiLuongChup),
            'hau_ky': _hau_ky(g), 'ap_dung': ap_dung, 'trang_thai': g.TrangThai,
            'dang_chon': bool(goi_chon and goi_chon.pk == g.pk),
            'url_chon': url_goi(g.pk) if ap_dung else '',
        })
    return ket_qua


# ---------------------------------------------------------------------
# Lịch khả dụng theo tuần
# ---------------------------------------------------------------------
def _tuan_hien_thi(chuoi, hom_nay):
    """Thứ Hai của tuần cần xem, ép vào khoảng [tuần hiện tại, tuần hiện tại + SO_TUAN_TOI_DA tuần]."""
    tuan_nay = quan_ly.dau_tuan(hom_nay)
    dau = quan_ly.dau_tuan(quan_ly.phan_tich_ngay(chuoi, hom_nay))
    return min(max(dau, tuan_nay), tuan_nay + timedelta(weeks=SO_TUAN_TOI_DA))


def _so_phut(lich):
    bd = datetime.combine(lich.Ngay, lich.GioBatDau)
    kt = datetime.combine(lich.Ngay, lich.GioKetThuc)
    return int((kt - bd).total_seconds() // 60)


_LOP_SLOT = {TrangThaiSlot.TRONG: 'trong', TrangThaiSlot.DANG_GIU: 'giu', TrangThaiSlot.DA_DAT: 'dat'}


def _lich_tuan(nag, dau_tuan, bg, goi_chon, ma_lich_cua_toi=None):
    """7 ngày của tuần, mỗi ngày là danh sách khung giờ CHƯA bắt đầu. Khung giờ ngắn hơn gói đang chọn thì không chọn được."""
    cuoi = dau_tuan + timedelta(days=6)
    theo_ngay = {dau_tuan + timedelta(days=i): [] for i in range(7)}
    cac_lich = (LichKhaDung.objects.filter(MaNhiepAnhGia=nag, Ngay__range=(dau_tuan, cuoi))
                .order_by('Ngay', 'GioBatDau'))
    for lich in cac_lich:
        if quan_ly.da_bat_dau(lich, bg):
            continue
        ngan = bool(goi_chon and lich.TrangThai == TrangThaiSlot.TRONG and _so_phut(lich) < goi_chon.ThoiLuongChup)
        theo_ngay[lich.Ngay].append({
            'lich': lich,
            'gio': f'{lich.GioBatDau:%H:%M} – {lich.GioKetThuc:%H:%M}',
            'nhan': 'Lịch trống' if lich.TrangThai == TrangThaiSlot.TRONG else lich.TrangThai,
            'lop': _LOP_SLOT.get(lich.TrangThai, 'dat'),
            'mau': tone_of(lich.TrangThai),                  # sky / amber / blue, giống màn Quản lý lịch của Nhiếp ảnh gia
            'ngan': ngan,
            'chon_duoc': lich.TrangThai == TrangThaiSlot.TRONG and not ngan,
            'cua_toi': ma_lich_cua_toi is not None and lich.pk == ma_lich_cua_toi,   # khung giờ chính Khách đang giữ (còn hạn)
        })
    return [{'ngay': ngay, 'nhan': quan_ly.nhan_ngay(ngay), 'la_hom_nay': ngay == bg.date(), 'cac_slot': slots}
            for ngay, slots in theo_ngay.items()]


# ---------------------------------------------------------------------
# Đánh giá, vai trò người xem
# ---------------------------------------------------------------------
def _danh_gia_moi_nhat(nag):
    cac = (DanhGia.objects.filter(MaNhiepAnhGia=nag)
           .select_related('MaBooking__MaKhachHang').order_by('-NgayDanhGia', '-pk')[:SO_DANH_GIA_HIEN])
    ket_qua = []
    for dg in cac:
        khach = dg.MaBooking.MaKhachHang
        ket_qua.append({'ten': khach.first_name or khach.username, 'diem': dg.Diem,
                        'sao': '★' * dg.Diem + '☆' * (5 - dg.Diem), 'nhan_xet': dg.NhanXet or '',
                        'ngay': dg.NgayDanhGia})
    return ket_qua


def _vai_tro_xem(user):
    """'khach' = chưa đăng nhập; 'khach_hang'; 'khac' = Nhiếp ảnh gia / Quản trị viên (chỉ xem, không đặt lịch)."""
    if not user.is_authenticated:
        return 'khach'
    return 'khach_hang' if user.groups.filter(name=VaiTro.KHACH_HANG).exists() else 'khac'


# ---------------------------------------------------------------------
# View
# ---------------------------------------------------------------------
def photographer_detail(request, ma_nhiep_anh_gia):
    nag = _lay_nhiep_anh_gia(ma_nhiep_anh_gia)
    quan_ly.nha_giu_cho_het_han()          # nhả các lượt giữ quá 5 phút để lịch hiện đúng (BR4.1-1)
    bg = quan_ly.bay_gio()
    hom_nay = bg.date()
    tuan_nay = quan_ly.dau_tuan(hom_nay)
    dau_tuan = _tuan_hien_thi(request.GET.get('tuan'), hom_nay)
    goi_chon = _goi_duoc_chon(nag, request.GET.get('goi'))

    def url_trang(tuan=None, goi=None):
        tham_so = {}
        if tuan and tuan != tuan_nay:
            tham_so['tuan'] = tuan.isoformat()
        if goi:
            tham_so['goi'] = goi
        return request.path + ('?' + urlencode(tham_so) if tham_so else '') + '#' + MO_TA_LICH

    vai_tro = _vai_tro_xem(request.user)
    url_chat = _url_co_the('chat_start', ma_nhiep_anh_gia=nag.pk)   # Module 8 đặt tên URL này; chưa có thì nút "Liên hệ" tạm khóa
    dang_nhap = redirect_to_login(request.get_full_path()).url
    cac_goi = _cac_goi(nag, goi_chon, lambda ma: url_trang(dau_tuan, ma))
    co_goi = any(g['ap_dung'] for g in cac_goi)
    projects = nag.projects.select_related('MaLoaiHinh').annotate(so_anh=Count('hinh_anh')).order_by('-NgayTao', '-pk')
    ma_goi_chon = goi_chon.pk if goi_chon else None
    giu_cho_cua_toi = None                  # lượt giữ còn hạn của chính Khách đang xem: để hiện nút "Tiếp tục đặt lịch" thay vì chỉ nhãn "Đang giữ chỗ"
    if vai_tro == 'khach_hang':
        giu_cho_cua_toi = GiuCho.objects.filter(MaKhachHang=request.user, TrangThai=TrangThaiGiuCho.DANG_GIU,
                                                ThoiDiemHetHan__gt=timezone.now()).first()

    return render(request, 'profiles/ho_so_cong_khai.html', {
        'nag': nag,
        'ten': _ten(nag.MaTaiKhoan),
        'ma': f'NAG-{nag.pk:04d}',
        'diem': f'{nag.diem_tb:.1f}' if nag.diem_tb is not None else '',
        'so_dg': nag.so_dg,
        'cac_goi': cac_goi,
        'co_goi': co_goi,
        'goi_chon': goi_chon,
        'thoi_luong_goi_chon': nhan_thoi_luong(goi_chon.ThoiLuongChup) if goi_chon else '',
        'url_bo_chon_goi': url_trang(dau_tuan) if goi_chon else '',
        'projects': list(projects),
        'cac_danh_gia': _danh_gia_moi_nhat(nag),
        'so_danh_gia_hien': SO_DANH_GIA_HIEN,
        # --- lịch khả dụng ---
        'cac_ngay': _lich_tuan(nag, dau_tuan, bg, goi_chon, giu_cho_cua_toi.MaLich_id if giu_cho_cua_toi else None),
        'url_tiep_tuc_giu_cho': _url_co_the('gui_booking', ma_giu_cho=giu_cho_cua_toi.pk) if giu_cho_cua_toi else '',
        'nhan_tuan': f'Tuần {dau_tuan:%d/%m} – {dau_tuan + timedelta(days=6):%d/%m/%Y}',
        'url_tuan_truoc': url_trang(dau_tuan - timedelta(weeks=1), ma_goi_chon) if dau_tuan > tuan_nay else '',
        'url_tuan_sau': (url_trang(dau_tuan + timedelta(weeks=1), ma_goi_chon)
                         if dau_tuan < tuan_nay + timedelta(weeks=SO_TUAN_TOI_DA) else ''),
        'url_tuan_nay': url_trang(tuan_nay, ma_goi_chon),
        'chu_thich': [TrangThaiSlot.TRONG, TrangThaiSlot.DANG_GIU, TrangThaiSlot.DA_DAT],
        'ma_goi_chon': ma_goi_chon or '',
        'co_chon_slot': bool(_url_co_the('chon_slot', ma_lich=1)),
        # --- người xem ---
        'vai_tro': vai_tro,
        'url_lien_he': (url_chat if vai_tro == 'khach_hang' else dang_nhap) if url_chat else '',
        'url_dang_nhap': dang_nhap,
        'url_chon_lich': _url_co_the('lich_chon_slot', ma_nhiep_anh_gia=nag.pk),
        'mo_ta_lich': MO_TA_LICH,
    })


def photographer_project(request, ma_nhiep_anh_gia, ma_project):
    nag = _lay_nhiep_anh_gia(ma_nhiep_anh_gia)
    cac_project = nag.projects.select_related('MaLoaiHinh').order_by('-NgayTao', '-pk')
    project = get_object_or_404(cac_project, pk=ma_project)          # project của người khác thì 404
    ma_cac_project = list(cac_project.values_list('pk', flat=True))
    vi_tri = ma_cac_project.index(project.pk)
    truoc = cac_project.filter(pk=ma_cac_project[vi_tri - 1]).first() if vi_tri > 0 else None
    sau = cac_project.filter(pk=ma_cac_project[vi_tri + 1]).first() if vi_tri < len(ma_cac_project) - 1 else None
    cac_anh = list(project.hinh_anh.all())
    return render(request, 'profiles/du_an_cong_khai.html', {
        'nag': nag, 'ten': _ten(nag.MaTaiKhoan), 'project': project,
        'cac_anh': cac_anh, 'so_anh': len(cac_anh), 'truoc': truoc, 'sau': sau,
        'url_ho_so': reverse('photographer_detail', args=[nag.pk]),
    })

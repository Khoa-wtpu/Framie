# =====================================================================
# search/services.py  -  K8: tìm kiếm và lọc nhiếp ảnh gia (UC2.1, UC2.2) (Khoa)
#
#   tim_kiem_nhiep_anh_gia(tieu_chi) -> QuerySet[NhiepAnhGia]   (đã gắn điểm, giá, số đánh giá)
#   dinh_dang_tien(so)               -> '1.500.000đ'
#
# Quy tắc:
#   - Chỉ nhiếp ảnh gia hồ sơ 'Đã duyệt' và tài khoản còn hoạt động.
#   - Từ khóa: khớp KHÔNG phân biệt hoa/thường và KHÔNG cần gõ dấu (gõ "le minh" vẫn ra "Lê Minh").
#     Tìm trong: họ tên, giới thiệu, tên loại hình / phong cách / khu vực. Nhiều từ => phải có đủ các từ.
#   - ID: gõ "NAG-0012", "nag 12", "0012" hoặc "12" => tìm đúng nhiếp ảnh gia có mã đó.
#   - Lọc: trong MỘT nhóm chọn nhiều mục thì chỉ cần khớp một mục (HOẶC); giữa các nhóm thì phải khớp hết (VÀ).
#   - Khoảng giá: có ít nhất một gói 'Đang áp dụng' có giá nằm trong khoảng.
# =====================================================================
import re
import unicodedata

from django.db.models import Avg, Count, Exists, F, Min, OuterRef, Subquery

from core.constants import TrangThaiGoi, TrangThaiHoSo
from profiles.models import (GoiDichVu, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach)

SO_MOI_TRANG = 12

# khóa -> (nhãn hiển thị, thứ tự sắp xếp). pk đứng cuối để thứ tự luôn ổn định giữa các trang.
SAP_XEP = {
    'goi_y': ('Gợi ý cho bạn', (F('diem_tb').desc(nulls_last=True), '-so_dg', 'pk')),
    'danh_gia': ('Nhiều đánh giá nhất', ('-so_dg', F('diem_tb').desc(nulls_last=True), 'pk')),
    'gia_tang': ('Giá thấp đến cao', (F('gia_tu').asc(nulls_last=True), 'pk')),
    'gia_giam': ('Giá cao đến thấp', (F('gia_tu').desc(nulls_last=True), 'pk')),
}
SAP_XEP_MAC_DINH = 'goi_y'

_MAU_ID = re.compile(r'^(?:nag)?[-\s]*0*(\d+)$')    # "nag-0012", "nag 12", "0012", "12"


def bo_dau(chuoi):
    """'Lê Đức Anh' -> 'le duc anh' (bỏ dấu, hạ chữ thường) để so khớp không cần gõ dấu."""
    chuoi = chuoi.replace('đ', 'd').replace('Đ', 'D')
    chuoi = unicodedata.normalize('NFD', chuoi)
    return ''.join(c for c in chuoi if unicodedata.category(c) != 'Mn').lower()


def dinh_dang_tien(so):
    """Decimal/int -> '1.500.000đ' (dấu chấm ngăn cách hàng nghìn, theo cách viết của Việt Nam)."""
    return f'{int(so):,}'.replace(',', '.') + 'đ'


def nhiep_anh_gia_cong_khai():
    """Nhiếp ảnh gia được phép hiện công khai: hồ sơ 'Đã duyệt' và tài khoản chưa bị khóa."""
    return NhiepAnhGia.objects.filter(
        MaTaiKhoan__trang_thai_ho_so=TrangThaiHoSo.DA_DUYET, MaTaiKhoan__is_active=True)


def _goi_ap_dung():
    return GoiDichVu.objects.filter(MaNhiepAnhGia=OuterRef('pk'), TrangThai=TrangThaiGoi.DANG_AP_DUNG)


def _ma_theo_tu_khoa(tu_khoa, goc):
    """Danh sách mã nhiếp ảnh gia khớp từ khóa. Dữ liệu ít nên so khớp trong Python để bỏ được dấu
    (SQLite chỉ phân biệt hoa/thường đúng với chữ không dấu)."""
    chuan = bo_dau(tu_khoa).strip()
    khop_id = _MAU_ID.match(chuan)
    if khop_id and goc.filter(pk=int(khop_id.group(1))).exists():
        return [int(khop_id.group(1))]               # đúng ID thì chỉ trả người đó

    van_ban = {pk: f'{ho} {ten} {gioi_thieu}' for pk, ho, ten, gioi_thieu in goc.values_list(
        'pk', 'MaTaiKhoan__last_name', 'MaTaiKhoan__first_name', 'GioiThieu')}
    nguon = ((NhiepAnhGia_LoaiHinhChup, 'MaLoaiHinh__TenLoaiHinh'),
             (NhiepAnhGia_PhongCach, 'MaPhongCach__TenPhongCach'),
             (NhiepAnhGia_KhuVuc, 'MaKhuVuc__TenKhuVuc'))
    for bang_noi, cot in nguon:
        for ma, ten in bang_noi.objects.filter(MaNhiepAnhGia__in=goc.values('pk')).values_list(
                'MaNhiepAnhGia', cot):
            van_ban[ma] += ' ' + ten
    cac_tu = chuan.split()
    return [ma for ma, chu in van_ban.items() if all(tu in bo_dau(chu) for tu in cac_tu)]


def tim_kiem_nhiep_anh_gia(tieu_chi):
    """tieu_chi: dict đã làm sạch (cleaned_data của TimKiemForm); khóa nào thiếu/rỗng thì bỏ qua."""
    goc = nhiep_anh_gia_cong_khai()
    ds = goc.annotate(
        # giá thấp nhất trong các gói đang áp dụng (hiện "Từ ...đ" trên thẻ)
        gia_tu=Subquery(_goi_ap_dung().order_by().values('MaNhiepAnhGia')
                        .annotate(m=Min('Gia')).values('m')),
        diem_tb=Avg('danh_gias__Diem'),
        so_dg=Count('danh_gias'),
    )

    tu_khoa = (tieu_chi.get('q') or '').strip()
    if tu_khoa:
        ds = ds.filter(pk__in=_ma_theo_tu_khoa(tu_khoa, goc))

    for khoa, bang_noi, cot in (('loai_hinh', NhiepAnhGia_LoaiHinhChup, 'MaLoaiHinh'),
                                ('phong_cach', NhiepAnhGia_PhongCach, 'MaPhongCach'),
                                ('khu_vuc', NhiepAnhGia_KhuVuc, 'MaKhuVuc')):
        da_chon = tieu_chi.get(khoa)
        if da_chon:
            ds = ds.filter(pk__in=bang_noi.objects.filter(**{cot + '__in': da_chon})
                           .values('MaNhiepAnhGia'))

    gia_tu, gia_den = tieu_chi.get('gia_tu'), tieu_chi.get('gia_den')
    if gia_tu is not None or gia_den is not None:
        goi = _goi_ap_dung()
        if gia_tu is not None:
            goi = goi.filter(Gia__gte=gia_tu)
        if gia_den is not None:
            goi = goi.filter(Gia__lte=gia_den)
        ds = ds.filter(Exists(goi))

    thu_tu = SAP_XEP[tieu_chi.get('sap_xep') or SAP_XEP_MAC_DINH][1]
    return (ds.select_related('MaTaiKhoan')
            .prefetch_related('loai_hinh_chup', 'khu_vuc')
            .order_by(*thu_tu))

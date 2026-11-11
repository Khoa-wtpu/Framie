# =====================================================================
# search/goi_y.py  -  E3: Trợ lý chọn Nhiếp ảnh gia (UC2.3, FR-39) (Khoa)
#
#   goi_y_nhiep_anh_gia(cau_tra_loi, toi_da=5) -> list[KetQuaGoiY]   (rỗng = không có ai phù hợp)
#   goi_y_noi_tieu_chi(cau_tra_loi)            -> list[str]          (câu gợi ý khi kết quả rỗng)
#   kiem_tra_cau_tra_loi(cau_tra_loi)          -> CauTraLoi          (ValidationError tiếng Việt nếu sai)
#
# Hợp đồng đầu vào (dict đã làm sạch từ form của Phanh, E4):
#   loai_hinh: int (MaLoaiHinh) | khu_vuc: int (MaKhuVuc) | ngan_sach: Decimal | None (None = không giới hạn)
#   ngay_chup: datetime.date    | phong_cach: list[int] (MaPhongCach), có thể rỗng = "Chưa rõ, bỏ qua"
#
# Công thức điểm (thiết kế chốt ở E1, mục 2.2 - 2.3):
#   Loại hình 30 | Khu vực 20 | Ngân sách 20 | Phong cách 20 | Đánh giá 10
#   - Ngày chụp là điều kiện BẮT BUỘC (không tính điểm): phải có ít nhất một khung giờ trống HỢP LỆ đúng ngày,
#     hợp lệ = khung giờ đủ dài cho ít nhất một gói trong "tập gói áp dụng" của Nhiếp ảnh gia.
#   - Tập gói áp dụng: các gói "Đang áp dụng" đúng loại hình khách chọn; nếu không có gói nào của loại hình đó
#     thì lấy mọi gói đang áp dụng. Cùng một tập này dùng cho cả chấm Ngân sách lẫn lọc khung giờ.
#   - Ngân sách: giá gói rẻ nhất <= ngân sách: đủ điểm; <= 120% ngân sách: một nửa; cao hơn: 0.
#   - Phong cách: (số phong cách khớp / số phong cách khách chọn) x 20. Khách bỏ qua thì không tính tiêu chí này
#     và tổng điểm tối đa là 80 (không phải 100) để không bị trừ oan.
#   - Đánh giá: (điểm trung bình / 5) x 10; chưa có đánh giá = 0 điểm (vẫn chia cho tổng).
#   - Phần trăm = điểm đạt / tổng tối đa x 100, làm tròn half-up bằng Decimal (không dùng round() của Python
#     vì nó làm tròn về số chẵn: 62,5 ra 62). Ngưỡng hiển thị so với số ĐÃ làm tròn.
#   - Sắp xếp: phần trăm CHƯA làm tròn giảm dần, rồi điểm đánh giá trung bình, rồi số lượt đánh giá, rồi mã.
#
# Không thêm bảng, không migration. Chỉ đọc dữ liệu; không ghi gì vào CSDL.
# =====================================================================
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count
from django.utils import timezone

from bookings.models import so_phut_slot
from core.constants import TrangThaiGoi
from profiles.models import (GoiDichVu, KhuVuc, LoaiHinhChup, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach, PhongCach)
from schedule.services import khung_gio_trong
from search.services import dinh_dang_tien, nhiep_anh_gia_cong_khai

# ---- Hằng số (đổi ở đây, không rải trong code) ----
NGUONG_HIEN_THI = 60          # chỉ hiện người có phần trăm (đã làm tròn) >= 60
TOI_DA_KET_QUA = 5            # mặc định hiện tối đa 5 Nhiếp ảnh gia
TOI_DA_PHONG_CACH = 3         # khách chọn tối đa 3 phong cách
SO_NGAY_CHON_TOI_DA = 30      # ngày chụp: từ hôm nay đến hôm nay + 29 (khớp SO_NGAY_HIEN_THI_LICH của trang lịch)
HE_SO_NGAN_SACH_GAN = Decimal('1.2')   # "gần ngân sách" = tới 120% ngân sách

DIEM_LOAI_HINH = 30
DIEM_KHU_VUC = 20
DIEM_NGAN_SACH = 20
DIEM_PHONG_CACH = 20
DIEM_DANH_GIA = 10
TOI_DA_CHIP_LY_DO = 3


@dataclass
class KetQuaGoiY:
    nhiep_anh_gia: NhiepAnhGia
    diem: int                          # 0-100 (đã chuẩn hóa theo tiêu chí áp dụng, đã làm tròn half-up)
    ly_do: list                        # tối đa 3 chuỗi ngắn, tiếng Việt
    khung_gio: list                    # list[LichKhaDung]: khung giờ trống hợp lệ của ngày chụp, xếp theo giờ
    gia_tu: Decimal                    # giá gói rẻ nhất (trong tập gói áp dụng) đã dùng để chấm Ngân sách
    diem_tb: float = None              # điểm đánh giá trung bình, None nếu chưa có
    so_danh_gia: int = 0


@dataclass
class CauTraLoi:
    """Câu trả lời đã được kiểm tra và đổi kiểu (kết quả của kiem_tra_cau_tra_loi)."""
    loai_hinh: LoaiHinhChup
    khu_vuc: KhuVuc
    ngan_sach: Decimal                 # None = không giới hạn
    ngay_chup: date
    phong_cach: list = field(default_factory=list)      # list[PhongCach], không trùng, giữ thứ tự khách chọn


@dataclass
class _UngVien:
    """Một Nhiếp ảnh gia đã chấm điểm xong, chưa lọc theo khung giờ."""
    nag: NhiepAnhGia
    diem: Decimal
    tong: int
    ty_le: Decimal                     # phần trăm CHƯA làm tròn (dùng để xếp hạng)
    phan_tram: int                     # phần trăm ĐÃ làm tròn half-up (hiện cho khách, so với ngưỡng)
    ly_do: list
    gia_tu: Decimal
    thoi_luong_ngan_nhat: int          # số phút của gói ngắn nhất trong tập gói áp dụng
    diem_tb: Decimal
    so_dg: int


def lam_tron_half_up(so):
    """Decimal -> int, làm tròn nửa lên (62,5 -> 63). Không dùng round() vì nó làm tròn về số chẵn."""
    return int(Decimal(so).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------
# Kiểm tra và đổi kiểu đầu vào
# ---------------------------------------------------------------------
def _so_nguyen(gia_tri, ten):
    if isinstance(gia_tri, bool) or gia_tri is None:
        raise ValidationError(f'Thiếu hoặc sai {ten}.')
    try:
        return int(gia_tri)
    except (TypeError, ValueError):
        raise ValidationError(f'Thiếu hoặc sai {ten}.')


def kiem_tra_cau_tra_loi(cau_tra_loi):
    """Kiểm tra dict câu trả lời, trả về CauTraLoi. Sai thì báo ValidationError (tiếng Việt).

    Form của Phanh nên kiểm tra trước; hàm này là lớp phòng thủ (và nơi duy nhất giữ luật ngày chụp:
    từ hôm nay đến hôm nay + 29, ngày thứ 31 trở đi bị từ chối).
    """
    if not isinstance(cau_tra_loi, dict):
        raise ValidationError('Câu trả lời không hợp lệ.')

    try:
        loai_hinh = LoaiHinhChup.objects.get(pk=_so_nguyen(cau_tra_loi.get('loai_hinh'), 'loại hình chụp'))
    except LoaiHinhChup.DoesNotExist:
        raise ValidationError('Loại hình chụp không tồn tại.')
    try:
        khu_vuc = KhuVuc.objects.get(pk=_so_nguyen(cau_tra_loi.get('khu_vuc'), 'khu vực'))
    except KhuVuc.DoesNotExist:
        raise ValidationError('Khu vực không tồn tại.')

    ngan_sach = cau_tra_loi.get('ngan_sach')
    if ngan_sach is not None:
        if isinstance(ngan_sach, bool):
            raise ValidationError('Ngân sách không hợp lệ.')
        try:
            ngan_sach = Decimal(str(ngan_sach))
        except Exception:
            raise ValidationError('Ngân sách không hợp lệ.')
        if not ngan_sach.is_finite() or ngan_sach <= 0:
            raise ValidationError('Ngân sách phải lớn hơn 0.')

    ngay_chup = cau_tra_loi.get('ngay_chup')
    if isinstance(ngay_chup, datetime) or not isinstance(ngay_chup, date):
        raise ValidationError('Ngày chụp không hợp lệ.')
    hom_nay = timezone.localdate()
    if ngay_chup < hom_nay:
        raise ValidationError('Ngày chụp không được ở quá khứ.')
    if ngay_chup > hom_nay + timedelta(days=SO_NGAY_CHON_TOI_DA - 1):
        raise ValidationError(f'Chỉ chọn được ngày chụp trong {SO_NGAY_CHON_TOI_DA} ngày tới.')

    ma_phong_cach = []
    for ma in (cau_tra_loi.get('phong_cach') or []):
        ma = _so_nguyen(ma, 'phong cách')
        if ma not in ma_phong_cach:
            ma_phong_cach.append(ma)
    if len(ma_phong_cach) > TOI_DA_PHONG_CACH:
        raise ValidationError(f'Chỉ được chọn tối đa {TOI_DA_PHONG_CACH} phong cách.')
    phong_cach = []
    if ma_phong_cach:
        co = {p.pk: p for p in PhongCach.objects.filter(pk__in=ma_phong_cach)}
        if len(co) != len(ma_phong_cach):
            raise ValidationError('Phong cách không tồn tại.')
        phong_cach = [co[ma] for ma in ma_phong_cach]

    return CauTraLoi(loai_hinh=loai_hinh, khu_vuc=khu_vuc, ngan_sach=ngan_sach,
                     ngay_chup=ngay_chup, phong_cach=phong_cach)


# ---------------------------------------------------------------------
# Chấm điểm
# ---------------------------------------------------------------------
def _tap_theo_nag(bang, cot):
    """{MaNhiepAnhGia: {giá trị cột}} lấy một lần cho tất cả (tránh truy vấn lặp từng người)."""
    ket_qua = defaultdict(set)
    for ma_nag, gia_tri in bang.objects.values_list('MaNhiepAnhGia', cot):
        ket_qua[ma_nag].add(gia_tri)
    return ket_qua


def _goi_ap_dung_theo_nag(ma_loai_hinh):
    """{MaNhiepAnhGia: (giá rẻ nhất, thời lượng ngắn nhất)} trong TẬP GÓI ÁP DỤNG của từng người.

    Tập gói áp dụng = gói 'Đang áp dụng' đúng loại hình; nếu người đó không có gói nào của loại hình
    thì lấy mọi gói đang áp dụng. Không có gói đang áp dụng nào thì không có trong kết quả.
    """
    dung_loai, moi_goi = defaultdict(list), defaultdict(list)
    for ma_nag, ma_loai, gia, phut in GoiDichVu.objects.filter(
            TrangThai=TrangThaiGoi.DANG_AP_DUNG).values_list(
            'MaNhiepAnhGia', 'MaLoaiHinh', 'Gia', 'ThoiLuongChup'):
        moi_goi[ma_nag].append((gia, phut))
        if ma_loai == ma_loai_hinh:
            dung_loai[ma_nag].append((gia, phut))
    ket_qua = {}
    for ma_nag, tat_ca in moi_goi.items():
        tap = dung_loai.get(ma_nag) or tat_ca
        ket_qua[ma_nag] = (min(g for g, _ in tap), min(p for _, p in tap))
    return ket_qua


def _diem_ngan_sach(gia_tu, ngan_sach):
    """(điểm, trạng thái) trong đó trạng thái: 'trong' | 'gan' | 'khong_gioi_han' | 'vuot'."""
    if ngan_sach is None:
        return Decimal(DIEM_NGAN_SACH), 'khong_gioi_han'
    if gia_tu <= ngan_sach:
        return Decimal(DIEM_NGAN_SACH), 'trong'
    if gia_tu <= ngan_sach * HE_SO_NGAN_SACH_GAN:       # Decimal x Decimal: mốc đúng 120% chính xác, không dính float
        return Decimal(DIEM_NGAN_SACH) / 2, 'gan'
    return Decimal(0), 'vuot'


def _danh_sach_ung_vien(c, bo_gioi_han_ngan_sach=False):
    """Chấm điểm mọi Nhiếp ảnh gia công khai có gói đang áp dụng. Chưa lọc ngưỡng, chưa lọc khung giờ."""
    ngan_sach = None if bo_gioi_han_ngan_sach else c.ngan_sach
    goi = _goi_ap_dung_theo_nag(c.loai_hinh.pk)
    loai_cua = _tap_theo_nag(NhiepAnhGia_LoaiHinhChup, 'MaLoaiHinh')
    vuc_cua = _tap_theo_nag(NhiepAnhGia_KhuVuc, 'MaKhuVuc')
    cach_cua = _tap_theo_nag(NhiepAnhGia_PhongCach, 'MaPhongCach')

    co_phong_cach = bool(c.phong_cach)
    tong = (DIEM_LOAI_HINH + DIEM_KHU_VUC + DIEM_NGAN_SACH + DIEM_DANH_GIA
            + (DIEM_PHONG_CACH if co_phong_cach else 0))

    nags = (nhiep_anh_gia_cong_khai().select_related('MaTaiKhoan')
            .annotate(diem_tb=Avg('danh_gias__Diem'), so_dg=Count('danh_gias')).order_by('pk'))

    ds = []
    for nag in nags:
        if nag.pk not in goi:
            continue                                   # không có gói đang áp dụng -> không thể có khung giờ hợp lệ
        gia_tu, phut_ngan_nhat = goi[nag.pk]
        diem = Decimal(0)
        chip = {}

        if c.loai_hinh.pk in loai_cua[nag.pk]:
            diem += DIEM_LOAI_HINH
            chip['loai'] = f'Chụp {c.loai_hinh.TenLoaiHinh}'
        if c.khu_vuc.pk in vuc_cua[nag.pk]:
            diem += DIEM_KHU_VUC
            chip['vuc'] = f'Hoạt động tại {c.khu_vuc.TenKhuVuc}'
        if co_phong_cach:
            khop = [p for p in c.phong_cach if p.pk in cach_cua[nag.pk]]
            if khop:
                diem += Decimal(DIEM_PHONG_CACH) * len(khop) / len(c.phong_cach)
                chip['cach'] = 'Phong cách ' + ', '.join(p.TenPhongCach for p in khop) + ' phù hợp'

        d_ns, trang_thai_ns = _diem_ngan_sach(gia_tu, ngan_sach)
        diem += d_ns
        if trang_thai_ns == 'trong':
            chip['tien'] = f'Gói từ {dinh_dang_tien(gia_tu)} trong ngân sách'
        elif trang_thai_ns == 'gan':
            chip['tien'] = f'Gói từ {dinh_dang_tien(gia_tu)} gần ngân sách'
        # "Không giới hạn": đủ điểm nhưng không có chip, vì câu "trong ngân sách" không có nghĩa khi không đặt ngân sách

        if nag.so_dg:
            diem_tb = Decimal(str(nag.diem_tb))
            diem += diem_tb / 5 * DIEM_DANH_GIA
            chip['dg'] = f'Đánh giá {float(diem_tb):.1f}/5'
        else:
            diem_tb = None
            chip['dg'] = 'Chưa có đánh giá'

        ty_le = diem / tong * 100
        ly_do = [chip[k] for k in ('loai', 'vuc', 'cach', 'tien', 'dg') if k in chip][:TOI_DA_CHIP_LY_DO]
        ds.append(_UngVien(nag=nag, diem=diem, tong=tong, ty_le=ty_le, phan_tram=lam_tron_half_up(ty_le),
                           ly_do=ly_do, gia_tu=gia_tu, thoi_luong_ngan_nhat=phut_ngan_nhat,
                           diem_tb=diem_tb, so_dg=nag.so_dg))
    return ds


def _khung_gio_hop_le(uv, ngay_chup):
    """Khung giờ trống CHƯA bắt đầu, đúng ngày chụp, đủ dài cho ít nhất một gói trong tập gói áp dụng."""
    return [lich for lich in khung_gio_trong(uv.nag).filter(Ngay=ngay_chup)
            if so_phut_slot(lich) >= uv.thoi_luong_ngan_nhat]


def _khoa_xep_hang(kq):
    uv = kq[0]
    return (-uv.ty_le, -(uv.diem_tb if uv.diem_tb is not None else Decimal(-1)), -uv.so_dg, uv.nag.pk)


def _xep_hang(c, toi_da, bo_gioi_han_ngan_sach=False):
    """[(ứng viên, khung giờ)] đã qua ngưỡng + ngày chụp, đã xếp hạng, cắt còn toi_da."""
    dat = []
    for uv in _danh_sach_ung_vien(c, bo_gioi_han_ngan_sach):
        if uv.phan_tram < NGUONG_HIEN_THI:
            continue                                   # lọc ngưỡng TRƯỚC khi truy vấn khung giờ để đỡ tốn truy vấn
        khung = _khung_gio_hop_le(uv, c.ngay_chup)
        if khung:
            dat.append((uv, khung))
    dat.sort(key=_khoa_xep_hang)
    return dat if toi_da is None else dat[:max(toi_da, 0)]


# ---------------------------------------------------------------------
# Hai hàm công khai cho giao diện (E4, E5)
# ---------------------------------------------------------------------
def goi_y_nhiep_anh_gia(cau_tra_loi, toi_da=TOI_DA_KET_QUA):
    """Danh sách KetQuaGoiY đã xếp hạng (tối đa toi_da người). Rỗng = không có ai phù hợp."""
    c = kiem_tra_cau_tra_loi(cau_tra_loi)
    return [KetQuaGoiY(nhiep_anh_gia=uv.nag, diem=uv.phan_tram, ly_do=uv.ly_do, khung_gio=khung,
                       gia_tu=uv.gia_tu, diem_tb=None if uv.diem_tb is None else float(uv.diem_tb),
                       so_danh_gia=uv.so_dg)
            for uv, khung in _xep_hang(c, toi_da)]


def goi_y_noi_tieu_chi(cau_tra_loi):
    """Câu gợi ý nới tiêu chí khi goi_y_nhiep_anh_gia trả rỗng (trả [] nếu thực ra vẫn có kết quả).

    Thứ tự kiểm tra (E1, mục 2.4):
      1. Không Nhiếp ảnh gia nào có khung giờ trống hợp lệ đúng ngày  -> gợi ý đổi ngày.
      2. Bỏ ràng buộc ngân sách thì có kết quả                       -> gợi ý nâng ngân sách.
      3. Còn lại                                                      -> gợi ý đổi khu vực hoặc loại hình.
    """
    c = kiem_tra_cau_tra_loi(cau_tra_loi)
    if _xep_hang(c, 1):
        return []
    if not any(_khung_gio_hop_le(uv, c.ngay_chup) for uv in _danh_sach_ung_vien(c)):
        return ['Thử chọn ngày khác']
    if c.ngan_sach is not None and _xep_hang(c, 1, bo_gioi_han_ngan_sach=True):
        return ['Thử nâng ngân sách hoặc chọn “Không giới hạn”']
    return ['Thử chọn khu vực khác', 'Thử chọn loại hình khác']

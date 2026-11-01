# =====================================================================
# schedule/quan_ly.py  -  K10: Quản lý lịch khả dụng (UC3.1) - phần nghiệp vụ (Khoa)
#
# View (views_lich.py) và form (forms.py) chỉ gọi các hàm ở đây, không tự đổi dữ liệu.
#   Quy tắc nghiệp vụ (đặc tả UC3.1 + ghi chú wireframe Module 3):
#   - Nhiếp ảnh gia ĐÃ DUYỆT thêm / sửa / xóa khung giờ nhận Booking (ngày, giờ bắt đầu, giờ kết thúc).
#   - Giờ kết thúc phải sau giờ bắt đầu; khung giờ không được chồng nhau (kiểm tra ở LichKhaDung.clean()).
#   - Chỉ SỬA / XÓA được khung giờ "Lịch trống" CHƯA bắt đầu. "Đang giữ chỗ" / "Đã đặt lịch" chỉ để xem.
#   - Chỉ XÓA được khung giờ chưa từng có lượt giữ chỗ hay Booking (kể cả đã hết hạn / bị từ chối), vì
#     bảng GIUCHO và BOOKING trỏ vào khung giờ bằng khóa ngoại PROTECT (xóa sẽ bị cơ sở dữ liệu chặn).
# =====================================================================
import calendar
import logging
from datetime import date, timedelta
from urllib.parse import urlencode

from django.db import DatabaseError, transaction
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from core.constants import TrangThaiSlot
from core.status_tones import tone_of
from schedule.models import LichKhaDung

logger = logging.getLogger(__name__)

# Câu thông báo (UC3.1 bước 7 và các ngoại lệ)
TB_THANH_CONG = 'Cập nhật lịch thành công.'
TB_KHONG_TIM_THAY = 'Không tìm thấy khung giờ.'
TB_CHI_XEM = 'Chỉ sửa hoặc xóa được khung giờ ở trạng thái "Lịch trống". Khung giờ đang giữ chỗ hoặc đã đặt lịch chỉ để xem.'
TB_DA_QUA = 'Khung giờ này đã bắt đầu hoặc đã qua nên chỉ để xem.'
TB_CO_LICH_SU = 'Khung giờ này đã có lượt giữ chỗ hoặc Booking nên không thể xóa.'
TB_LOI_LUU = 'Không thể cập nhật lịch lúc này. Vui lòng thử lại.'    # UC3.1 ngoại lệ 6a

CHE_DO_TUAN = 'tuan'
CHE_DO_THANG = 'thang'
TEN_THU = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']    # date.weekday(): thứ Hai = 0 ... Chủ nhật = 6
SO_NAM_TOI_DA = 3                                       # chỉ cho xem lịch trong khoảng 3 năm trước / sau hôm nay


class LichLoi(Exception):
    """Lỗi nghiệp vụ của UC3.1. .thong_bao: câu tiếng Việt cho người dùng;
    .khong_tim_thay: True khi khung giờ không tồn tại HOẶC không phải của Nhiếp ảnh gia này (view trả 404)."""

    def __init__(self, thong_bao, khong_tim_thay=False):
        super().__init__(thong_bao)
        self.thong_bao = thong_bao
        self.khong_tim_thay = khong_tim_thay


def bay_gio():
    """Giờ hiện tại theo múi giờ Việt Nam. Mọi chỗ cần 'bây giờ' đều gọi hàm này (test dễ giả lập)."""
    return timezone.localtime()


def da_bat_dau(lich, bg=None):
    """Khung giờ đã bắt đầu (hoặc đã qua) chưa. Đúng bằng giờ bắt đầu cũng tính là đã bắt đầu."""
    bg = bg or bay_gio()
    return (lich.Ngay, lich.GioBatDau) <= (bg.date(), bg.time())


def co_lich_su(lich):
    """Khung giờ đã từng có lượt giữ chỗ hoặc Booking (kể cả đã hết hạn / bị từ chối) chưa."""
    return lich.giu_cho.exists() or lich.booking.exists()


# ---------------------------------------------------------------------
# Kiểm tra quyền thao tác trên một khung giờ
# ---------------------------------------------------------------------
def lay_khung_gio_cua_nag(nag, ma_lich, khoa=False):
    """Lấy khung giờ CỦA Nhiếp ảnh gia này. khoa=True: khóa dòng (chỉ dùng trong transaction.atomic())."""
    ds = LichKhaDung.objects.filter(MaNhiepAnhGia=nag)
    if khoa:
        ds = ds.select_for_update()
    lich = ds.filter(pk=ma_lich).first()
    if lich is None:
        raise LichLoi(TB_KHONG_TIM_THAY, khong_tim_thay=True)
    return lich


def kiem_tra_duoc_sua(lich):
    if lich.TrangThai != TrangThaiSlot.TRONG:
        raise LichLoi(TB_CHI_XEM)
    if da_bat_dau(lich):
        raise LichLoi(TB_DA_QUA)


def kiem_tra_duoc_xoa(lich):
    kiem_tra_duoc_sua(lich)         # cùng điều kiện với sửa, thêm điều kiện dưới
    if co_lich_su(lich):
        raise LichLoi(TB_CO_LICH_SU)


# ---------------------------------------------------------------------
# Thêm / sửa / xóa (đều trong một transaction; lỗi cơ sở dữ liệu -> UC3.1 ngoại lệ 6a)
# ---------------------------------------------------------------------
def luu_khung_gio_moi(form):
    """Lưu form thêm khung giờ (form đã hợp lệ). Trả về LichKhaDung vừa tạo, trạng thái mặc định 'Lịch trống'."""
    try:
        with transaction.atomic():
            return form.save()
    except DatabaseError:
        logger.exception('luu_khung_gio_moi: lỗi lưu dữ liệu')
        raise LichLoi(TB_LOI_LUU)


def luu_khung_gio_sua(nag, form):
    """Lưu form sửa khung giờ (form đã hợp lệ). Khóa dòng rồi kiểm tra lại trạng thái, phòng khi một Khách
    vừa giữ chỗ đúng lúc Nhiếp ảnh gia bấm Lưu. Chỉ ghi ba cột ngày / giờ, không đụng tới trạng thái."""
    try:
        with transaction.atomic():
            hien_tai = lay_khung_gio_cua_nag(nag, form.instance.pk, khoa=True)
            kiem_tra_duoc_sua(hien_tai)
            lich = form.save(commit=False)
            lich.save(update_fields=['Ngay', 'GioBatDau', 'GioKetThuc'])
            return lich
    except DatabaseError:
        logger.exception('luu_khung_gio_sua: lỗi lưu dữ liệu (khung giờ %s)', form.instance.pk)
        raise LichLoi(TB_LOI_LUU)


def xoa_khung_gio(nag, ma_lich):
    """Xóa khung giờ. Trả về NGÀY của khung giờ đã xóa (để quay lại đúng tuần đang xem)."""
    try:
        with transaction.atomic():
            lich = lay_khung_gio_cua_nag(nag, ma_lich, khoa=True)
            kiem_tra_duoc_xoa(lich)
            ngay = lich.Ngay
            lich.delete()
            return ngay
    except DatabaseError:       # kể cả ProtectedError: cơ sở dữ liệu vẫn chặn nếu có ai vừa giữ chỗ
        logger.exception('xoa_khung_gio: lỗi xóa (khung giờ %s)', ma_lich)
        raise LichLoi(TB_LOI_LUU)


# ---------------------------------------------------------------------
# Dựng dữ liệu cho màn hình lịch (tuần / tháng)
# ---------------------------------------------------------------------
def phan_tich_ngay(chuoi, hom_nay=None):
    """Đọc ?ngay=YYYY-MM-DD trên thanh địa chỉ. Gõ bậy hoặc quá xa hôm nay -> về hôm nay (không gây lỗi)."""
    hom_nay = hom_nay or bay_gio().date()
    try:
        ngay = date.fromisoformat(chuoi)
    except (TypeError, ValueError):
        return hom_nay
    if abs((ngay - hom_nay).days) > 365 * SO_NAM_TOI_DA:
        return hom_nay
    return ngay


def dau_tuan(ngay):
    """Thứ Hai của tuần chứa ngày này."""
    return ngay - timedelta(days=ngay.weekday())


def nhan_ngay(ngay):
    """'T2 05/10'."""
    return f'{TEN_THU[ngay.weekday()]} {ngay:%d/%m}'


def url_lich(che_do, ngay):
    """Địa chỉ màn hình lịch ở chế độ và ngày cho trước."""
    return reverse('my_calendar') + '?' + urlencode({'che_do': che_do, 'ngay': ngay.isoformat()})


def _lay_lich(nag, tu_ngay, den_ngay):
    """Các khung giờ trong khoảng ngày, kèm số lượt giữ chỗ / Booking đã từng có (để biết xóa được không)."""
    return list(
        LichKhaDung.objects.filter(MaNhiepAnhGia=nag, Ngay__gte=tu_ngay, Ngay__lte=den_ngay)
        .annotate(so_giu_cho=Count('giu_cho', distinct=True), so_booking=Count('booking', distinct=True))
        .order_by('Ngay', 'GioBatDau'))


def _booking_theo_khung_gio(ds_lich):
    """{mã khung giờ: mã Booking còn hiệu lực} cho các khung giờ không còn trống (để dẫn tới chi tiết Booking)."""
    from bookings.models import Booking, TRANG_THAI_HET_HIEU_LUC     # import trong hàm để tránh phụ thuộc vòng giữa các app
    ma_lich = [l.pk for l in ds_lich if l.TrangThai != TrangThaiSlot.TRONG]
    if not ma_lich:
        return {}
    ds = (Booking.objects.filter(MaLich_id__in=ma_lich).exclude(TrangThai__in=TRANG_THAI_HET_HIEU_LUC)
          .order_by('MaBooking'))
    return {b.MaLich_id: b.pk for b in ds}


def _url_booking(ma_booking):
    """Địa chỉ chi tiết Booking của Nhiếp ảnh gia (task T5 của Tuyền). Chưa có tên URL đó thì trả None, trang vẫn chạy."""
    from django.urls import NoReverseMatch
    try:
        return reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': ma_booking})
    except NoReverseMatch:
        return None


def _mo_ta_khung_gio(lich, bg, ma_booking):
    trong = lich.TrangThai == TrangThaiSlot.TRONG
    qua = da_bat_dau(lich, bg)
    da_co_lich_su = (lich.so_giu_cho + lich.so_booking) > 0
    return {
        'lich': lich,
        'mau': tone_of(lich.TrangThai),
        'da_qua': qua,
        'co_the_sua': trong and not qua,
        'co_the_xoa': trong and not qua and not da_co_lich_su,
        'ma_booking': ma_booking,
        'url_booking': _url_booking(ma_booking) if ma_booking else None,
    }


def dung_tuan(nag, ngay_neo):
    """Dữ liệu tuần (thứ Hai - Chủ nhật) chứa ngay_neo."""
    bg = bay_gio()
    dau = dau_tuan(ngay_neo)
    cuoi = dau + timedelta(days=6)
    ds = _lay_lich(nag, dau, cuoi)
    booking = _booking_theo_khung_gio(ds)
    cac_ngay = []
    for i in range(7):
        ngay = dau + timedelta(days=i)
        cac_ngay.append({
            'ngay': ngay,
            'nhan': nhan_ngay(ngay),
            'la_hom_nay': ngay == bg.date(),
            'la_qua_khu': ngay < bg.date(),
            'cac_slot': [_mo_ta_khung_gio(l, bg, booking.get(l.pk)) for l in ds if l.Ngay == ngay],
        })
    return {
        'cac_ngay': cac_ngay,
        'tong_slot': len(ds),
        'nhan_khoang': f'Tuần {dau:%d/%m} – {cuoi:%d/%m/%Y}',
        'truoc': url_lich(CHE_DO_TUAN, dau - timedelta(days=7)),
        'sau': url_lich(CHE_DO_TUAN, dau + timedelta(days=7)),
        'nhan_truoc': 'Tuần trước',
        'nhan_sau': 'Tuần sau',
    }


def dung_thang(nag, ngay_neo):
    """Dữ liệu tháng chứa ngay_neo: lưới các tuần, mỗi ô ngày có số khung giờ theo từng trạng thái."""
    bg = bay_gio()
    dau_thang = ngay_neo.replace(day=1)
    cuoi_thang = ngay_neo.replace(day=calendar.monthrange(ngay_neo.year, ngay_neo.month)[1])
    luoi_dau = dau_tuan(dau_thang)
    luoi_cuoi = dau_tuan(cuoi_thang) + timedelta(days=6)
    ds = _lay_lich(nag, luoi_dau, luoi_cuoi)
    dem = {}
    for l in ds:
        d = dem.setdefault(l.Ngay, {TrangThaiSlot.TRONG: 0, TrangThaiSlot.DANG_GIU: 0, TrangThaiSlot.DA_DAT: 0})
        d[l.TrangThai] += 1
    cac_tuan = []
    ngay = luoi_dau
    while ngay <= luoi_cuoi:
        tuan = []
        for _ in range(7):
            d = dem.get(ngay, {})
            tuan.append({
                'ngay': ngay,
                'trong_thang': ngay.month == ngay_neo.month,
                'la_hom_nay': ngay == bg.date(),
                'dem_trong': d.get(TrangThaiSlot.TRONG, 0),
                'dem_giu': d.get(TrangThaiSlot.DANG_GIU, 0),
                'dem_dat': d.get(TrangThaiSlot.DA_DAT, 0),
                'url': url_lich(CHE_DO_TUAN, ngay),
            })
            ngay += timedelta(days=1)
        cac_tuan.append(tuan)
    return {
        'cac_tuan': cac_tuan,
        'ten_thu': TEN_THU,
        'tong_slot': sum(1 for l in ds if l.Ngay.month == ngay_neo.month),
        'nhan_khoang': f'Tháng {dau_thang:%m/%Y}',
        'truoc': url_lich(CHE_DO_THANG, dau_thang - timedelta(days=1)),
        'sau': url_lich(CHE_DO_THANG, cuoi_thang + timedelta(days=1)),
        'nhan_truoc': 'Tháng trước',
        'nhan_sau': 'Tháng sau',
    }

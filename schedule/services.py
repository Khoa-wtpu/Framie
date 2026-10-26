# =====================================================================
# schedule/services.py  -  K2: hàm dùng chung về khung giờ (Khoa)
# Người dùng hàm này: Tuyền (Booking / giữ chỗ), Khoa (trang quản lý lịch).
#
#   khung_gio_trong(nhiep_anh_gia, so_ngay=None)  -> QuerySet các khung giờ còn trống
#   dem_khung_gio_trong(nhiep_anh_gia, so_ngay=7) -> số khung giờ trống trong N ngày tới
#   doi_trang_thai_khung_gio(ma_lich, trang_thai_moi) -> đổi trạng thái đúng quy trình
#
# Chữ trạng thái luôn lấy từ core/constants.py (TrangThaiSlot), không gõ trực tiếp.
# =====================================================================
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.constants import TrangThaiSlot
from schedule.models import LichKhaDung

# Các chuyển trạng thái được phép (theo quy trình TO-BE của báo cáo):
#   Lịch trống   -> Đang giữ chỗ : Khách chọn slot (giữ 5 phút)
#   Đang giữ chỗ -> Lịch trống   : hết 5 phút / Booking bị từ chối / hết hạn đặt cọc / hủy
#   Đang giữ chỗ -> Đã đặt lịch  : Nhiếp ảnh gia xác nhận đủ cọc (Chốt Booking)
#   Đã đặt lịch  -> Lịch trống   : hủy ở bước Chốt Booking
# Mọi chuyển khác (ví dụ Lịch trống -> Đã đặt lịch) đều bị cấm.
CHUYEN_HOP_LE = {
    TrangThaiSlot.TRONG: {TrangThaiSlot.DANG_GIU},
    TrangThaiSlot.DANG_GIU: {TrangThaiSlot.TRONG, TrangThaiSlot.DA_DAT},
    TrangThaiSlot.DA_DAT: {TrangThaiSlot.TRONG},
}


def _chua_qua_gio_bat_dau():
    # Điều kiện "khung giờ chưa bắt đầu": ngày sau hôm nay, hoặc hôm nay nhưng giờ bắt đầu còn ở phía sau.
    bay_gio = timezone.localtime()
    return Q(Ngay__gt=bay_gio.date()) | Q(Ngay=bay_gio.date(), GioBatDau__gt=bay_gio.time())


def khung_gio_trong(nhiep_anh_gia, so_ngay=None):
    """Các khung giờ 'Lịch trống' CHƯA bắt đầu của một nhiếp ảnh gia, xếp theo ngày/giờ.

    nhiep_anh_gia: đối tượng NhiepAnhGia hoặc mã (MaNhiepAnhGia).
    so_ngay: nếu có (ví dụ 7) thì chỉ lấy trong N ngày tính từ hôm nay (gồm hôm nay).
    Khung giờ đã qua giờ bắt đầu không được tính là trống và không cho chọn.
    """
    ma = getattr(nhiep_anh_gia, 'pk', nhiep_anh_gia)
    ds = LichKhaDung.objects.filter(
        _chua_qua_gio_bat_dau(), MaNhiepAnhGia_id=ma, TrangThai=TrangThaiSlot.TRONG)
    if so_ngay is not None:
        ngay_cuoi = timezone.localdate() + timedelta(days=so_ngay - 1)
        ds = ds.filter(Ngay__lte=ngay_cuoi)
    return ds.order_by('Ngay', 'GioBatDau')


def dem_khung_gio_trong(nhiep_anh_gia, so_ngay=7):
    """Số khung giờ trống trong N ngày tới (mặc định 7 ngày = 'tuần này' ở trang chủ)."""
    return khung_gio_trong(nhiep_anh_gia, so_ngay).count()


def doi_trang_thai_khung_gio(ma_lich, trang_thai_moi):
    """Đổi trạng thái một khung giờ, chỉ cho phép các chuyển hợp lệ (xem CHUYEN_HOP_LE).

    ma_lich: mã khung giờ (MaLich) hoặc đối tượng LichKhaDung.
    Trả về đối tượng LichKhaDung đã cập nhật.
    Báo ValidationError (tiếng Việt) nếu: trạng thái mới không hợp lệ, chuyển không được phép,
    khung giờ đã qua giờ bắt đầu khi định giữ chỗ, hoặc có người khác vừa đổi trạng thái trước.
    """
    ma = getattr(ma_lich, 'pk', ma_lich)
    if trang_thai_moi not in CHUYEN_HOP_LE:
        raise ValidationError('Trạng thái khung giờ không hợp lệ.')

    with transaction.atomic():
        try:
            lich = LichKhaDung.objects.select_for_update().get(pk=ma)
        except LichKhaDung.DoesNotExist:
            raise ValidationError('Khung giờ không tồn tại.')

        cu = lich.TrangThai
        if trang_thai_moi not in CHUYEN_HOP_LE.get(cu, set()):
            raise ValidationError(f'Không thể chuyển khung giờ từ "{cu}" sang "{trang_thai_moi}".')

        # Chỉ được giữ chỗ khung giờ chưa bắt đầu.
        if trang_thai_moi == TrangThaiSlot.DANG_GIU:
            if not LichKhaDung.objects.filter(_chua_qua_gio_bat_dau(), pk=ma).exists():
                raise ValidationError('Khung giờ này đã qua, không thể giữ chỗ.')

        # UPDATE có điều kiện "trạng thái vẫn là cũ": nếu hai người cùng giữ một slot,
        # chỉ một người cập nhật được (số dòng = 1), người còn lại nhận số dòng = 0 và bị báo lỗi.
        so_dong = (LichKhaDung.objects.filter(pk=ma, TrangThai=cu)
                   .update(TrangThai=trang_thai_moi))
        if so_dong != 1:
            raise ValidationError('Khung giờ vừa được người khác thay đổi, vui lòng chọn lại.')

        lich.TrangThai = trang_thai_moi
        return lich
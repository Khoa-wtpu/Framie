# delivery/services_tai_anh.py - N10 / UC5.8: Khách hàng tải về thiết bị ảnh hoàn chỉnh (Nguyên)
# File RIÊNG để không đụng vào delivery/services.py. Dùng lại: kho_anh() (kho ảnh riêng, không công khai).
# Mỗi lượt tải ghi 1 dòng Lịch sử tải ảnh cho TỪNG ảnh (thành công / thất bại). Hết 3 ngày: file bị xóa bởi
# delivery/xoa_anh_het_han.py (T10 của Tuyền), lịch sử vẫn giữ.
import logging
import mimetypes
import tempfile
import zipfile
from pathlib import PurePosixPath

from django.core.exceptions import SuspiciousOperation        # đường dẫn trỏ ra ngoài kho ảnh
from django.db import DatabaseError
from django.utils import timezone

from bookings.models import Booking
from core.constants import KetQuaTaiAnh, LoaiAnh, LuuTruAnh, TrangThaiBooking
from delivery.models import Anh, BanGiao, LichSuTaiAnh
from delivery.services import kho_anh

logger = logging.getLogger(__name__)

SO_DONG_LICH_SU = 10                                           # số dòng lịch sử hiện ở trang


class LoiTaiHoanChinh(Exception):                              # lỗi nghiệp vụ UC5.8: view bắt lại để hiện cho Khách hàng
    pass


def han_tai_anh(booking):                                      # thời hạn tải ảnh (BANGIAO.ThoiHanTaiAnh, 3 ngày sau khi NAG xác nhận 60%); None = chưa mở quyền
    bg = BanGiao.objects.filter(MaBooking=booking).first()
    return bg.ThoiHanTaiAnh if bg else None


def anh_hoan_chinh(booking):                                   # ảnh Hoàn chỉnh (không watermark) còn lưu trên máy chủ
    return Anh.objects.filter(MaBooking=booking, LoaiAnh=LoaiAnh.HOAN_CHINH,
                              TrangThaiLuuTru=LuuTruAnh.CON_LUU).order_by('TenAnh', 'pk')


def ly_do_khong_tai_duoc(booking, bay_gio=None):               # trả về câu báo nếu Khách KHÔNG tải được lúc này, hoặc None nếu được
    if booking.TrangThai != TrangThaiBooking.HOAN_THANH:       # Pre-condition: Nhiếp ảnh gia đã xác nhận thanh toán phần còn lại
        return ('Chỉ Booking đã hoàn thành (Nhiếp ảnh gia đã xác nhận thanh toán phần còn lại) '
                'mới tải được ảnh hoàn chỉnh.')
    han = han_tai_anh(booking)
    if han is None:                                            # chưa có thời hạn = chưa mở quyền tải
        return 'Booking này chưa được mở quyền tải ảnh hoàn chỉnh.'
    con_anh = anh_hoan_chinh(booking).exists()
    da_xoa = Anh.objects.filter(MaBooking=booking, LoaiAnh=LoaiAnh.HOAN_CHINH, TrangThaiLuuTru=LuuTruAnh.DA_XOA).exists()
    if (bay_gio or timezone.now()) > han or (not con_anh and da_xoa):   # ngoại lệ 4a
        return 'Ảnh đã hết thời hạn lưu trữ (3 ngày kể từ khi mở quyền tải) và không còn khả dụng để tải về.'
    if not con_anh:
        return 'Booking này chưa có ảnh hoàn chỉnh để tải.'
    return None


def lich_su_tai(booking, so_dong=SO_DONG_LICH_SU):             # các lượt tải gần nhất của Booking (mới nhất trước)
    return list(LichSuTaiAnh.objects.filter(MaAnh__MaBooking=booking)
                .select_related('MaAnh').order_by('-ThoiDiemTaiAnh', '-pk')[:so_dong])


def _ghi_lich_su(khach, ds_anh, ket_qua):                      # mỗi ảnh một dòng Lịch sử tải ảnh
    bay_gio = timezone.now()
    LichSuTaiAnh.objects.bulk_create([
        LichSuTaiAnh(MaAnh=anh, MaKhachHang=khach, ThoiDiemTaiAnh=bay_gio, KetQuaTaiAnh=ket_qua) for anh in ds_anh])


def _ten_trong_zip(anh, da_dung):                              # tên tệp trong file zip: bỏ thư mục, không để trùng tên
    ten = PurePosixPath(anh.TenAnh.replace('\\', '/')).name or f'anh_{anh.pk}.jpg'
    if ten.lower() in da_dung:
        goc = PurePosixPath(ten)
        ten = f'{goc.stem}_{anh.pk}{goc.suffix}'
    da_dung.add(ten.lower())
    return ten


def chuan_bi_tai(ma_booking, khach, ds_ma_anh=None):           # bước 3-4 của UC5.8
    """ds_ma_anh=None: tải tất cả ảnh hoàn chỉnh. Có danh sách: chỉ tải các ảnh đó.
    Trả về dict {'tep': tệp đang mở, 'ten_tep', 'content_type', 'so_anh'}: 1 ảnh -> trả thẳng ảnh, nhiều ảnh -> 1 file zip.
    Mỗi lần gọi ghi Lịch sử tải ảnh: thành công hoặc thất bại (thất bại thì Khách bấm tải lại được)."""
    try:
        booking = Booking.objects.select_related('MaGoi').get(pk=ma_booking, MaKhachHang=khach)   # chỉ Booking của chính Khách
    except Booking.DoesNotExist:
        raise LoiTaiHoanChinh('Booking không tồn tại hoặc không thuộc về bạn.')
    ly_do = ly_do_khong_tai_duoc(booking)
    if ly_do:
        raise LoiTaiHoanChinh(ly_do)

    ds = anh_hoan_chinh(booking)
    if ds_ma_anh is not None:
        ma_chon = set(ds_ma_anh)
        if not ma_chon:
            raise LoiTaiHoanChinh('Vui lòng chọn ít nhất một ảnh để tải.')
        ds = ds.filter(pk__in=ma_chon)
        if ds.count() != len(ma_chon):                         # ảnh của người khác / chưa hoàn chỉnh / đã xóa
            raise LoiTaiHoanChinh('Có ảnh không hợp lệ hoặc không còn khả dụng để tải.')
    anhs = list(ds)

    kho = kho_anh()
    tep = None
    try:                                                       # đọc file ảnh: lỗi ổ đĩa / thiếu file = ngoại lệ 5a
        if len(anhs) == 1:                                     # 1 ảnh: trả thẳng file ảnh
            anh = anhs[0]
            tep = kho.open(anh.DuongDanAnh, 'rb')
            ten_tep = anh.TenAnh
            content_type = mimetypes.guess_type(anh.TenAnh)[0] or 'application/octet-stream'
        else:                                                  # nhiều ảnh: gói vào 1 file zip (ảnh jpg/png đã nén sẵn nên chỉ lưu, không nén lại)
            tep = tempfile.TemporaryFile()
            da_dung = set()
            with zipfile.ZipFile(tep, 'w', zipfile.ZIP_STORED) as zf:
                for anh in anhs:
                    zf.write(kho.path(anh.DuongDanAnh), _ten_trong_zip(anh, da_dung))
            tep.seek(0)
            ten_tep = f'Framie_Booking_{booking.pk}_anh_hoan_chinh.zip'
            content_type = 'application/zip'
    except (OSError, SuspiciousOperation, zipfile.BadZipFile, ValueError):
        if tep:
            tep.close()
        logger.exception('tai_anh_hoan_chinh: không đọc được ảnh (Booking %s)', booking.pk)
        try:
            _ghi_lich_su(khach, anhs, KetQuaTaiAnh.THAT_BAI)   # ghi nhận lượt tải thất bại
        except DatabaseError:
            logger.exception('tai_anh_hoan_chinh: không ghi được lịch sử thất bại (Booking %s)', booking.pk)
        raise LoiTaiHoanChinh('Không thể tải ảnh về thiết bị do lỗi hệ thống. Vui lòng thử tải lại.')

    try:
        _ghi_lich_su(khach, anhs, KetQuaTaiAnh.THANH_CONG)     # ghi nhận lượt tải thành công
    except DatabaseError:
        tep.close()
        logger.exception('tai_anh_hoan_chinh: không ghi được lịch sử (Booking %s)', booking.pk)
        raise LoiTaiHoanChinh('Không thể tải ảnh về thiết bị do lỗi hệ thống. Vui lòng thử tải lại.')
    return {'tep': tep, 'ten_tep': ten_tep, 'content_type': content_type, 'so_anh': len(anhs)}

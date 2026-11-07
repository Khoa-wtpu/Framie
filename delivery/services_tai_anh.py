# delivery/services_tai_anh.py - N10 / UC5.8: Khách hàng tải về thiết bị ảnh hoàn chỉnh (Nguyên)
# File RIÊNG để không đụng vào delivery/services.py. Dùng lại: kho_anh() (kho ảnh riêng, không công khai).
# Mỗi lượt tải ghi 1 dòng Lịch sử tải ảnh cho TỪNG ảnh (thành công / thất bại). Hết 3 ngày: file bị xóa bởi
# delivery/xoa_anh_het_han.py (T10 của Tuyền), lịch sử vẫn giữ.
# Nạp thư viện/module được sử dụng trong file.
import logging
# Nạp thư viện/module được sử dụng trong file.
import mimetypes
# Nạp thư viện/module được sử dụng trong file.
import tempfile
# Nạp thư viện/module được sử dụng trong file.
import zipfile
# Nạp thành phần từ module pathlib để dùng bên dưới.
from pathlib import PurePosixPath

from django.core.exceptions import SuspiciousOperation        # đường dẫn trỏ ra ngoài kho ảnh
# Nạp thành phần từ module django.db để dùng bên dưới.
from django.db import DatabaseError
# Nạp thành phần từ module django.utils để dùng bên dưới.
from django.utils import timezone

# Nạp thành phần từ module bookings.models để dùng bên dưới.
from bookings.models import Booking
# Nạp thành phần từ module core.constants để dùng bên dưới.
from core.constants import KetQuaTaiAnh, LoaiAnh, LuuTruAnh, TrangThaiBooking
# Nạp thành phần từ module delivery.models để dùng bên dưới.
from delivery.models import Anh, BanGiao, LichSuTaiAnh
# Nạp thành phần từ module delivery.services để dùng bên dưới.
from delivery.services import kho_anh

# Gán giá trị cho logger.
logger = logging.getLogger(__name__)

SO_DONG_LICH_SU = 10                                           # số dòng lịch sử hiện ở trang


class LoiTaiHoanChinh(Exception):                              # lỗi nghiệp vụ UC5.8: view bắt lại để hiện cho Khách hàng
    # Không thực hiện thao tác tại đây; giữ chỗ cho cấu trúc này.
    pass


def han_tai_anh(booking):                                      # thời hạn tải ảnh (BANGIAO.ThoiHanTaiAnh, 3 ngày sau khi NAG xác nhận 60%); None = chưa mở quyền
    # Gán giá trị cho bg.
    bg = BanGiao.objects.filter(MaBooking=booking).first()
    # Trả kết quả của bước xử lý hiện tại.
    return bg.ThoiHanTaiAnh if bg else None


def anh_hoan_chinh(booking):                                   # ảnh Hoàn chỉnh (không watermark) còn lưu trên máy chủ
    # Trả kết quả của bước xử lý hiện tại.
    return Anh.objects.filter(MaBooking=booking, LoaiAnh=LoaiAnh.HOAN_CHINH,
                              TrangThaiLuuTru=LuuTruAnh.CON_LUU).order_by('TenAnh', 'pk')


def ly_do_khong_tai_duoc(booking, bay_gio=None):               # trả về câu báo nếu Khách KHÔNG tải được lúc này, hoặc None nếu được
    if booking.TrangThai != TrangThaiBooking.HOAN_THANH:       # Pre-condition: Nhiếp ảnh gia đã xác nhận thanh toán phần còn lại
        # Trả kết quả của bước xử lý hiện tại.
        return ('Chỉ Booking đã hoàn thành (Nhiếp ảnh gia đã xác nhận thanh toán phần còn lại) '
                'mới tải được ảnh hoàn chỉnh.')
    # Gán giá trị cho han.
    han = han_tai_anh(booking)
    if han is None:                                            # chưa có thời hạn = chưa mở quyền tải
        # Trả kết quả của bước xử lý hiện tại.
        return 'Booking này chưa được mở quyền tải ảnh hoàn chỉnh.'
    # Gán giá trị cho con_anh.
    con_anh = anh_hoan_chinh(booking).exists()
    # Gán giá trị cho da_xoa.
    da_xoa = Anh.objects.filter(MaBooking=booking, LoaiAnh=LoaiAnh.HOAN_CHINH, TrangThaiLuuTru=LuuTruAnh.DA_XOA).exists()
    if (bay_gio or timezone.now()) > han or (not con_anh and da_xoa):   # ngoại lệ 4a
        # Trả kết quả của bước xử lý hiện tại.
        return 'Ảnh đã hết thời hạn lưu trữ (3 ngày kể từ khi mở quyền tải) và không còn khả dụng để tải về.'
    # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
    if not con_anh:
        # Trả kết quả của bước xử lý hiện tại.
        return 'Booking này chưa có ảnh hoàn chỉnh để tải.'
    # Trả kết quả của bước xử lý hiện tại.
    return None


def lich_su_tai(booking, so_dong=SO_DONG_LICH_SU):             # các lượt tải gần nhất của Booking (mới nhất trước)
    # Trả kết quả của bước xử lý hiện tại.
    return list(LichSuTaiAnh.objects.filter(MaAnh__MaBooking=booking)
                .select_related('MaAnh').order_by('-ThoiDiemTaiAnh', '-pk')[:so_dong])


def _ghi_lich_su(khach, ds_anh, ket_qua):                      # mỗi ảnh một dòng Lịch sử tải ảnh
    # Gán giá trị cho bay_gio.
    bay_gio = timezone.now()
    # Thực hiện lời gọi hàm để xử lý bước này.
    LichSuTaiAnh.objects.bulk_create([
        LichSuTaiAnh(MaAnh=anh, MaKhachHang=khach, ThoiDiemTaiAnh=bay_gio, KetQuaTaiAnh=ket_qua) for anh in ds_anh])


def _ten_trong_zip(anh, da_dung):                              # tên tệp trong file zip: bỏ thư mục, không để trùng tên
    # Gán giá trị cho ten.
    ten = PurePosixPath(anh.TenAnh.replace('\\', '/')).name or f'anh_{anh.pk}.jpg'
    # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
    if ten.lower() in da_dung:
        # Gán giá trị cho goc.
        goc = PurePosixPath(ten)
        # Gán giá trị cho ten.
        ten = f'{goc.stem}_{anh.pk}{goc.suffix}'
    # Thực hiện lời gọi hàm để xử lý bước này.
    da_dung.add(ten.lower())
    # Trả kết quả của bước xử lý hiện tại.
    return ten


def chuan_bi_tai(ma_booking, khach, ds_ma_anh=None):           # bước 3-4 của UC5.8
    """ds_ma_anh=None: tải tất cả ảnh hoàn chỉnh. Có danh sách: chỉ tải các ảnh đó.
    Trả về dict {'tep': tệp đang mở, 'ten_tep', 'content_type', 'so_anh'}: 1 ảnh -> trả thẳng ảnh, nhiều ảnh -> 1 file zip.
    Mỗi lần gọi ghi Lịch sử tải ảnh: thành công hoặc thất bại (thất bại thì Khách bấm tải lại được)."""
    # Bắt và xử lý lỗi để tránh làm gián đoạn luồng chính.
    try:
        booking = Booking.objects.select_related('MaGoi').get(pk=ma_booking, MaKhachHang=khach)   # chỉ Booking của chính Khách
    except Booking.DoesNotExist:
        # Phát sinh lỗi để báo trường hợp không hợp lệ.
        raise LoiTaiHoanChinh('Booking không tồn tại hoặc không thuộc về bạn.')
    # Gán giá trị cho ly_do.
    ly_do = ly_do_khong_tai_duoc(booking)
    # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
    if ly_do:
        # Phát sinh lỗi để báo trường hợp không hợp lệ.
        raise LoiTaiHoanChinh(ly_do)

    # Gán giá trị cho ds.
    ds = anh_hoan_chinh(booking)
    # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
    if ds_ma_anh is not None:
        # Gán giá trị cho ma_chon.
        ma_chon = set(ds_ma_anh)
        # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
        if not ma_chon:
            # Phát sinh lỗi để báo trường hợp không hợp lệ.
            raise LoiTaiHoanChinh('Vui lòng chọn ít nhất một ảnh để tải.')
        # Gán giá trị cho ds.
        ds = ds.filter(pk__in=ma_chon)
        if ds.count() != len(ma_chon):                         # ảnh của người khác / chưa hoàn chỉnh / đã xóa
            # Phát sinh lỗi để báo trường hợp không hợp lệ.
            raise LoiTaiHoanChinh('Có ảnh không hợp lệ hoặc không còn khả dụng để tải.')
    # Gán giá trị cho anhs.
    anhs = list(ds)

    # Gán giá trị cho kho.
    kho = kho_anh()
    # Gán giá trị cho tep.
    tep = None
    try:                                                       # đọc file ảnh: lỗi ổ đĩa / thiếu file = ngoại lệ 5a
        if len(anhs) == 1:                                     # 1 ảnh: trả thẳng file ảnh
            # Gán giá trị cho anh.
            anh = anhs[0]
            # Gán giá trị cho tep.
            tep = kho.open(anh.DuongDanAnh, 'rb')
            # Gán giá trị cho ten_tep.
            ten_tep = anh.TenAnh
            # Gán giá trị cho content_type.
            content_type = mimetypes.guess_type(anh.TenAnh)[0] or 'application/octet-stream'
        else:                                                  # nhiều ảnh: gói vào 1 file zip (ảnh jpg/png đã nén sẵn nên chỉ lưu, không nén lại)
            # Gán giá trị cho tep.
            tep = tempfile.TemporaryFile()
            # Gán giá trị cho da_dung.
            da_dung = set()
            # Mở ngữ cảnh xử lý; tài nguyên/transaction được quản lý theo khối này.
            with zipfile.ZipFile(tep, 'w', zipfile.ZIP_STORED) as zf:
                # Lặp qua từng phần tử để thực hiện cùng một thao tác.
                for anh in anhs:
                    # Thực hiện lời gọi hàm để xử lý bước này.
                    zf.write(kho.path(anh.DuongDanAnh), _ten_trong_zip(anh, da_dung))
            # Thực hiện lời gọi hàm để xử lý bước này.
            tep.seek(0)
            # Gán giá trị cho ten_tep.
            ten_tep = f'Framie_Booking_{booking.pk}_anh_hoan_chinh.zip'
            # Gán giá trị cho content_type.
            content_type = 'application/zip'
    except (OSError, SuspiciousOperation, zipfile.BadZipFile, ValueError):
        # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
        if tep:
            # Thực hiện lời gọi hàm để xử lý bước này.
            tep.close()
        # Thực hiện lời gọi hàm để xử lý bước này.
        logger.exception('tai_anh_hoan_chinh: không đọc được ảnh (Booking %s)', booking.pk)
        # Bắt và xử lý lỗi để tránh làm gián đoạn luồng chính.
        try:
            _ghi_lich_su(khach, anhs, KetQuaTaiAnh.THAT_BAI)   # ghi nhận lượt tải thất bại
        except DatabaseError:
            # Thực hiện lời gọi hàm để xử lý bước này.
            logger.exception('tai_anh_hoan_chinh: không ghi được lịch sử thất bại (Booking %s)', booking.pk)
        # Phát sinh lỗi để báo trường hợp không hợp lệ.
        raise LoiTaiHoanChinh('Không thể tải ảnh về thiết bị do lỗi hệ thống. Vui lòng thử tải lại.')

    # Bắt và xử lý lỗi để tránh làm gián đoạn luồng chính.
    try:
        _ghi_lich_su(khach, anhs, KetQuaTaiAnh.THANH_CONG)     # ghi nhận lượt tải thành công
    except DatabaseError:
        # Thực hiện lời gọi hàm để xử lý bước này.
        tep.close()
        # Thực hiện lời gọi hàm để xử lý bước này.
        logger.exception('tai_anh_hoan_chinh: không ghi được lịch sử (Booking %s)', booking.pk)
        # Phát sinh lỗi để báo trường hợp không hợp lệ.
        raise LoiTaiHoanChinh('Không thể tải ảnh về thiết bị do lỗi hệ thống. Vui lòng thử tải lại.')
    # Trả kết quả của bước xử lý hiện tại.
    return {'tep': tep, 'ten_tep': ten_tep, 'content_type': content_type, 'so_anh': len(anhs)}

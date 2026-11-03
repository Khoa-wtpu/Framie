# delivery/services.py - N4 / UC5.3: Nhiếp ảnh gia tải ảnh lên Booking (Nguyên)
import logging                                                 # ghi cảnh báo khi xử lý ảnh quá chậm
from pathlib import Path                                       # tách đuôi và tên tệp
import time                                                    # đo thời gian chèn watermark
import uuid                                                    # tên tệp ngẫu nhiên, không trùng

from django.conf import settings
from django.core.exceptions import ValidationError             # lỗi mà hàm đổi trạng thái của Tuyền ném ra
from django.core.files.base import ContentFile                 # bọc bytes thành "tệp" để lưu
from django.core.files.storage import FileSystemStorage        # lưu tệp xuống ổ đĩa
from django.db import DatabaseError, transaction
from django.utils import timezone
from PIL import Image                                          # chỉ để bắt lỗi DecompressionBombError

from bookings.models import Booking                            # model Booking (của Tuyền)
from bookings.services import chuyen_trang_thai_booking        # HÀM T2: nơi DUY NHẤT được đổi trạng thái Booking
from core.constants import (BenThucHien, LoaiAnh, LoaiHauKy, LuuTruAnh,
                            TrangThaiBooking, VaiTro)
from accounts.permissions import lay_vai_tro
from core.constants import DinhDangTep                         # JPG / JPEG / PNG
from delivery.models import Anh, YeuCauChinhSua
from delivery.watermark import GIOI_HAN_GIAY, chen_watermark   # chèn watermark (bước 6) và mốc 5 giây của N5
from notifications.services import gui_thong_bao               # hàm thông báo dùng chung (của Phanh)

DUOI_CHO_PHEP = ('jpg', 'jpeg', 'png')                         # chỉ nhận 3 đuôi này
DUNG_LUONG_TOI_DA = 20 * 1024 * 1024                           # tối đa 20 MB mỗi ảnh (byte); đặc tả chưa ghi số, đổi ở đây
SO_ANH_TOI_DA = 100                                            # tối đa 100 ảnh mỗi lần tải; đặc tả chưa ghi số, đổi ở đây
SO_PIXEL_TOI_DA = 60_000_000                                   # N5: ảnh tối đa 60 megapixel (khoảng 9000x6700) để chèn watermark kịp 5 giây

logger = logging.getLogger(__name__)


class LoiTaiAnh(Exception):                                    # lỗi nghiệp vụ: view bắt lại để hiện cho Nhiếp ảnh gia
    pass


def kho_anh():                                                 # nơi cất ảnh: thư mục RIÊNG, không công khai (giống ảnh trong dữ liệu mẫu)
    goc = getattr(settings, 'PRIVATE_MEDIA_ROOT', settings.BASE_DIR / 'private_media')
    return FileSystemStorage(location=goc)


def duong_dan_goc(duong_dan_anh):                              # đường dẫn bản GỐC (không watermark) ứng với bản có watermark
    cha, ten = duong_dan_anh.rsplit('/', 1)                    # 'booking_5/abc.jpg' -> 'booking_5', 'abc.jpg'
    return f'{cha}/goc/{ten}'                                  # -> 'booking_5/goc/abc.jpg' (để sau này tạo ảnh Hoàn chỉnh không watermark)


def _xoa_tep(kho, ds_duong_dan):                               # xóa tệp, tệp không tồn tại thì bỏ qua
    for duong_dan in ds_duong_dan:
        try:
            kho.delete(duong_dan)
        except OSError:
            pass


def xac_dinh_giai_doan(booking):                               # Booking đang ở bước tải ảnh nào? (None = chưa/không phải lúc tải)
    if booking.TrangThai == TrangThaiBooking.DA_CHUP:          # sau buổi chụp: tải ảnh gốc
        return {'loai': LoaiAnh.CHUA_HAU_KY, 'tieu_de': 'Tải ảnh gốc (chưa hậu kỳ)'}
    if booking.TrangThai == TrangThaiBooking.DANG_HAU_KY:      # đang hậu kỳ: tải ảnh đã chỉnh sửa
        return {'loai': LoaiAnh.DA_HAU_KY, 'tieu_de': 'Tải ảnh đã hậu kỳ'}
    return None


def anh_can_hau_ky(booking):                                   # các ảnh còn phải tải bản hậu kỳ trong lượt hiện tại
    con_luu = Anh.objects.filter(MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU)
    yeu_cau = YeuCauChinhSua.objects.filter(MaBooking=booking).order_by('-SoLanYeuCau').first()
    if yeu_cau:                                                # Khách đã yêu cầu chỉnh sửa: chỉ các ảnh trong yêu cầu mới nhất,
        return con_luu.filter(yeu_cau_chinh_suas=yeu_cau,      # và chưa được tải lại sau thời điểm yêu cầu
                              NgayTaiLen__lte=yeu_cau.NgayYeuCau)
    ds = con_luu.filter(LoaiAnh=LoaiAnh.CHUA_HAU_KY)           # lượt đầu: các ảnh còn ở dạng chưa hậu kỳ
    if booking.MaGoi.LoaiHauKy == LoaiHauKy.GIOI_HAN:          # gói giới hạn: chỉ các ảnh Khách đã chọn
        ds = ds.filter(DuocChonHauKy=1)
    return ds


def _khoa_ten(ten_tep):                                        # tên không đuôi, viết thường: 'IMG_01.JPG' -> 'img_01'
    return Path(ten_tep).stem.lower()


def _luu_hai_ban(kho, booking, tep, da_luu):                   # lưu bản gốc + bản watermark, trả về (đường dẫn watermark, kích thước, định dạng)
    duoi = Path(tep.name).suffix.lstrip('.').lower()           # jpg / jpeg / png
    dinh_dang = DinhDangTep.PNG if duoi == 'png' else (DinhDangTep.JPEG if duoi == 'jpeg' else DinhDangTep.JPG)
    ten_luu = f'{uuid.uuid4().hex}.{duoi}'                     # tên ngẫu nhiên, không lộ tên gốc
    tep.seek(0)
    bat_dau = time.monotonic()
    ban_wm = chen_watermark(tep, 'PNG' if duoi == 'png' else 'JPEG')   # bước 6: chèn watermark
    mat = time.monotonic() - bat_dau                           # N5: mỗi ảnh tối đa 5 giây
    if mat > GIOI_HAN_GIAY:
        logger.warning('Chèn watermark ảnh %s mất %.1f giây (vượt %s giây)', tep.name, mat, GIOI_HAN_GIAY)
    duong_dan = kho.save(f'booking_{booking.pk}/{ten_luu}', ContentFile(ban_wm))   # lưu bản đã watermark (khách xem bản này)
    da_luu.append(duong_dan)
    tep.seek(0)
    da_luu.append(kho.save(duong_dan_goc(duong_dan), tep))     # lưu thêm bản GỐC nguyên vẹn (chưa watermark) vào thư mục riêng 'goc'
    return duong_dan, len(ban_wm), dinh_dang


def _them_anh_goc(kho, booking, ds_tep, da_luu):               # giai đoạn 1: tải ảnh chưa hậu kỳ
    da_co = {_khoa_ten(t) for t in Anh.objects.filter(
        MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU).values_list('TenAnh', flat=True)}
    trong_lan_nay, trung = set(), []
    for tep in ds_tep:                                         # tên ảnh (không tính đuôi) không được trùng, để sau này ghép ảnh hậu kỳ chính xác
        khoa = _khoa_ten(tep.name)
        if khoa in da_co or khoa in trong_lan_nay:
            trung.append(tep.name)
        trong_lan_nay.add(khoa)
    if trung:
        raise LoiTaiAnh('Tên ảnh bị trùng (trong lần tải này hoặc với ảnh đã tải): ' + ', '.join(trung[:10]))
    for tep in ds_tep:
        duong_dan, kich_thuoc, dinh_dang = _luu_hai_ban(kho, booking, tep, da_luu)
        Anh.objects.create(MaBooking=booking, TenAnh=Path(tep.name).name[:255], DuongDanAnh=duong_dan,
                           DinhDangAnh=dinh_dang, KichThuocAnh=kich_thuoc, LoaiAnh=LoaiAnh.CHUA_HAU_KY,
                           PhienBanAnh=1, CoWatermark=1, DuocChonHauKy=0)
    if booking.MaGoi.LoaiHauKy == LoaiHauKy.GIOI_HAN:          # gói giới hạn: Khách xem và chọn ảnh cần hậu kỳ
        return TrangThaiBooking.CHO_KH_CHON_ANH
    return TrangThaiBooking.CHO_HAU_KY                         # gói hậu kỳ toàn bộ: bỏ qua bước chọn ảnh


def _them_ban_hau_ky(kho, booking, ds_tep, da_luu, xoa_sau):   # giai đoạn 2: tải ảnh đã hậu kỳ (ghi đè ảnh cũ, chỉ giữ bản mới nhất)
    can = {_khoa_ten(a.TenAnh): a for a in anh_can_hau_ky(booking)}
    la, lap, thay = [], set(), []
    for tep in ds_tep:
        khoa = _khoa_ten(tep.name)
        if khoa not in can:
            la.append(tep.name)                                # tên không khớp ảnh nào đang cần hậu kỳ
        elif khoa in lap:
            la.append(tep.name + ' (chọn trùng)')
        lap.add(khoa)
    if la:
        raise LoiTaiAnh('Không có ảnh nào đang cần hậu kỳ khớp tên: ' + ', '.join(la[:10]))
    for tep in ds_tep:
        anh = can[_khoa_ten(tep.name)]
        duong_dan_cu = anh.DuongDanAnh
        duong_dan, kich_thuoc, dinh_dang = _luu_hai_ban(kho, booking, tep, da_luu)
        if anh.LoaiAnh == LoaiAnh.DA_HAU_KY:                   # tải lại sau yêu cầu chỉnh sửa của Khách: tăng phiên bản
            anh.PhienBanAnh += 1
        anh.TenAnh = Path(tep.name).name[:255]
        anh.DuongDanAnh, anh.DinhDangAnh, anh.KichThuocAnh = duong_dan, dinh_dang, kich_thuoc
        anh.LoaiAnh, anh.CoWatermark = LoaiAnh.DA_HAU_KY, 1
        anh.NgayTaiLen = timezone.now()                        # cũng là mốc cho biết ảnh này đã được tải lại
        anh.save()
        xoa_sau.extend([duong_dan_cu, duong_dan_goc(duong_dan_cu)])   # file bản cũ sẽ bị xóa sau khi lưu thành công (chỉ giữ bản mới nhất)
    if anh_can_hau_ky(booking).exists():                       # còn ảnh chưa có bản hậu kỳ: Booking vẫn ở Đang hậu kỳ
        return None
    return TrangThaiBooking.CHO_KH_KIEM_TRA                    # đủ ảnh: gửi Khách kiểm tra


def tai_anh_len(ma_booking, nag_user, ds_tep):                 # bước 5-8 của UC5.3
    kho = kho_anh()
    da_luu, xoa_sau = [], []                                   # da_luu: tệp vừa ghi (xóa nếu lỗi); xoa_sau: tệp cũ (xóa nếu thành công)
    try:
        with transaction.atomic():                             # 1 giao dịch: lỗi ở đâu thì hoàn tác DB
            try:
                booking = (Booking.objects.select_for_update().select_related('MaGoi')
                           .get(pk=ma_booking, MaNhiepAnhGia__MaTaiKhoan=nag_user))   # phải là Booking của chính NAG này
            except Booking.DoesNotExist:
                raise LoiTaiAnh('Booking không tồn tại hoặc không thuộc về bạn.')
            giai_doan = xac_dinh_giai_doan(booking)
            if giai_doan is None:
                raise LoiTaiAnh(f'Booking đang ở trạng thái "{booking.TrangThai}", chưa đến lúc tải ảnh.')
            if giai_doan['loai'] == LoaiAnh.CHUA_HAU_KY:
                trang_thai_moi = _them_anh_goc(kho, booking, ds_tep, da_luu)
            else:
                trang_thai_moi = _them_ban_hau_ky(kho, booking, ds_tep, da_luu, xoa_sau)
            if trang_thai_moi:                                 # HÀM T2: tự kiểm tra, tự ghi Lịch sử trạng thái, tự gán hạn 2 ngày / 3 ngày
                chuyen_trang_thai_booking(booking, trang_thai_moi, BenThucHien.NHIEP_ANH_GIA)
            transaction.on_commit(lambda: _xoa_tep(kho, xoa_sau))   # chỉ xóa file cũ SAU KHI mọi thứ đã lưu thành công
    except LoiTaiAnh:
        _xoa_tep(kho, da_luu)                                  # dọn tệp đã lỡ ghi
        raise
    except ValidationError as loi:                             # hàm của Tuyền từ chối bước chuyển
        _xoa_tep(kho, da_luu)
        raise LoiTaiAnh(' '.join(loi.messages))
    except (OSError, DatabaseError, ValueError, Image.DecompressionBombError):   # lỗi ghi tệp, lỗi DB, ảnh quá lớn/hỏng (ngoại lệ 7a)
        _xoa_tep(kho, da_luu)
        raise LoiTaiAnh('Không thể lưu ảnh sau khi xử lý, vui lòng thực hiện tải ảnh lại.')
    except Exception as loi:                                  # Pillow/decoder có thể ném SyntaxError hoặc lỗi ngoài dự kiến
        _xoa_tep(kho, da_luu)
        raise LoiTaiAnh('Không thể lưu ảnh sau khi xử lý, vui lòng thực hiện tải ảnh lại.') from loi

    khach = booking.MaKhachHang                                # bước 8: báo Khách hàng
    if trang_thai_moi == TrangThaiBooking.CHO_KH_CHON_ANH:
        thong_bao = f'Booking #{booking.pk}: ảnh đã được tải lên, vui lòng xem và chọn ảnh cần hậu kỳ.'
    elif trang_thai_moi == TrangThaiBooking.CHO_HAU_KY:
        thong_bao = f'Booking #{booking.pk}: Nhiếp ảnh gia đã tải ảnh lên, đang chờ hậu kỳ.'
    elif trang_thai_moi == TrangThaiBooking.CHO_KH_KIEM_TRA:
        thong_bao = f'Booking #{booking.pk}: ảnh đã hậu kỳ, vui lòng kiểm tra.'
    else:
        thong_bao = None                                       # mới tải một phần ảnh hậu kỳ, chưa báo Khách
    if thong_bao:
        gui_thong_bao(khach, 'Nhiếp ảnh gia đã tải ảnh lên', thong_bao, booking=booking)
    con_thieu = anh_can_hau_ky(booking).count() if giai_doan['loai'] == LoaiAnh.DA_HAU_KY else 0
    return {'so_anh': len(ds_tep), 'trang_thai_moi': trang_thai_moi, 'con_thieu': con_thieu}


def mo_anh(user, ma_anh):                                      # dùng cho trang xem ảnh (có kiểm tra quyền); chỉ bao giờ trả về BẢN CÓ WATERMARK
    try:
        anh = Anh.objects.select_related('MaBooking__MaNhiepAnhGia').get(pk=ma_anh)
    except Anh.DoesNotExist:
        return None, None
    bk = anh.MaBooking
    duoc_xem = (user.pk in (bk.MaKhachHang_id, bk.MaNhiepAnhGia.MaTaiKhoan_id)
                or lay_vai_tro(user) == VaiTro.QUAN_TRI_VIEN)  # Quản trị viên được xem bản watermark để xử lý tranh chấp
    if not duoc_xem or anh.LoaiAnh == LoaiAnh.HOAN_CHINH:      # ảnh Hoàn chỉnh (không watermark) do chức năng tải ảnh của Khách xử lý, không phục vụ ở đây
        return False, None
    if anh.TrangThaiLuuTru != LuuTruAnh.CON_LUU:
        return None, None
    return anh, kho_anh()


def chuyen_thanh_anh_hoan_chinh(booking):                      # N5: ảnh Hoàn chỉnh KHÔNG có watermark
    """Gọi khi Nhiếp ảnh gia xác nhận đủ 60% (UC5.7), trong cùng giao dịch với bước đó.
    Ảnh 'Đã hậu kỳ' -> 'Hoàn chỉnh': đổi sang BẢN GỐC (không watermark), xóa bản có watermark.
    Trả về số ảnh đã chuyển."""
    kho = kho_anh()
    xoa_sau = []
    try:
        with transaction.atomic():
            ds = list(Anh.objects.select_for_update().filter(
                MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU, LoaiAnh=LoaiAnh.DA_HAU_KY))
            for anh in ds:
                goc = duong_dan_goc(anh.DuongDanAnh)            # bản không watermark do UC5.3 đã lưu sẵn
                if not kho.exists(goc):
                    raise LoiTaiAnh(f'Không tìm thấy bản gốc của ảnh {anh.TenAnh}.')
                xoa_sau.append(anh.DuongDanAnh)                 # bản có watermark sẽ bị xóa sau khi lưu thành công
                anh.DuongDanAnh, anh.KichThuocAnh = goc, kho.size(goc)
                anh.LoaiAnh, anh.CoWatermark = LoaiAnh.HOAN_CHINH, 0   # CHECK của bảng: Hoàn chỉnh <=> không watermark
                anh.save()
            transaction.on_commit(lambda: _xoa_tep(kho, xoa_sau))
    except (OSError, DatabaseError):
        raise LoiTaiAnh('Không thể chuyển ảnh sang bản hoàn chỉnh, vui lòng thực hiện lại.')
    return len(ds)

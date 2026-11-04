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
from delivery.models import Anh, BanGiao, YeuCauChinhSua, YeuCauChinhSua_Anh   # N7: bảng yêu cầu chỉnh sửa; N8: thêm bảng Bàn giao
from core.constants import LoaiThanhToan, TrangThaiThanhToan   # N8: loại và trạng thái của khoản thanh toán 60%
from payments.models import ThanhToan, tinh_so_tien            # N8: bảng Thanh toán và hàm tính số tiền (cọc 40%, còn lại 60%)
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
    # Gói hậu kỳ toàn bộ đi thẳng từ "Đang hậu kỳ" mà chưa có bước tải ảnh gốc.
    # Vì vậy lượt tải đầu tiên của gói này tạo bản ghi ảnh mới, không ghép theo tên ảnh gốc.
    if (booking.MaGoi.LoaiHauKy == LoaiHauKy.TOAN_BO
            and not Anh.objects.filter(MaBooking=booking).exists()):
        da_co_trong_luot, trung = set(), []
        for tep in ds_tep:
            khoa = _khoa_ten(tep.name)
            if khoa in da_co_trong_luot:
                trung.append(tep.name)
            da_co_trong_luot.add(khoa)
        if trung:
            raise LoiTaiAnh('Tên ảnh bị trùng trong lần tải này: ' + ', '.join(trung[:10]))
        for tep in ds_tep:
            duong_dan, kich_thuoc, dinh_dang = _luu_hai_ban(kho, booking, tep, da_luu)
            Anh.objects.create(
                MaBooking=booking, TenAnh=Path(tep.name).name[:255], DuongDanAnh=duong_dan,
                DinhDangAnh=dinh_dang, KichThuocAnh=kich_thuoc, LoaiAnh=LoaiAnh.DA_HAU_KY,
                PhienBanAnh=1, CoWatermark=1, DuocChonHauKy=0, NgayTaiLen=timezone.now())
        return TrangThaiBooking.CHO_KH_KIEM_TRA

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
        logger.exception('Lỗi bất ngờ khi tải ảnh lên Booking #%s', ma_booking)
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


# =====================================================================
# N6 / UC5.4: Khách hàng lựa chọn ảnh cần hậu kỳ  +  Nhiếp ảnh gia bấm "Bắt đầu hậu kỳ"
# =====================================================================
TRANG_THAI_DA_GUI_DANH_SACH = (                                # các trạng thái SAU bước chọn ảnh: danh sách đã được gửi đi rồi
    TrangThaiBooking.CHO_HAU_KY, TrangThaiBooking.DANG_HAU_KY, TrangThaiBooking.CHO_KH_KIEM_TRA,  # các trạng thái sau bước chọn ảnh (tiếp theo)
    TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN, TrangThaiBooking.HOAN_THANH)  # các trạng thái cuối quy trình


class LoiChonAnh(Exception):                                   # lỗi nghiệp vụ của UC5.4: view bắt lại để hiện cho Khách hàng
    pass                                                       # không cần thêm gì, chỉ dùng làm "nhãn" cho lỗi


class LoiBatDauHauKy(Exception):                               # lỗi khi Nhiếp ảnh gia bấm "Bắt đầu hậu kỳ"
    pass                                                       # không cần thêm gì, chỉ dùng làm "nhãn" cho lỗi


def so_anh_toi_da_cua_goi(booking):                            # số ảnh được hậu kỳ tối đa theo gói dịch vụ của Booking
    return booking.MaGoi.SoAnhHauKyToiDa or 0                  # gói giới hạn luôn có số này (CHECK của DB); phòng khi None thì coi là 0


def anh_de_chon(booking):                                      # các ảnh Khách được xem và chọn: ảnh gốc có watermark, còn lưu
    return Anh.objects.filter(                                 # lấy từ bảng ANH
        MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU,  # đúng Booking này và file ảnh còn tồn tại
        LoaiAnh=LoaiAnh.CHUA_HAU_KY).order_by('TenAnh')        # chỉ ảnh "Chưa hậu kỳ", xếp theo tên cho dễ tìm


def ly_do_khong_chon_duoc(booking):                            # trả về câu báo lỗi nếu Khách KHÔNG được chọn ảnh lúc này, hoặc None nếu được
    if booking.MaGoi.LoaiHauKy != LoaiHauKy.GIOI_HAN:          # Pre-condition: gói phải có quy định số ảnh được hậu kỳ
        return 'Gói dịch vụ của Booking này hậu kỳ toàn bộ ảnh nên không cần lựa chọn ảnh.'   # gói toàn bộ: không có bước chọn
    if booking.TrangThai in TRANG_THAI_DA_GUI_DANH_SACH:       # đã gửi danh sách cho Nhiếp ảnh gia rồi
        return 'Danh sách ảnh cần hậu kỳ đã được gửi cho Nhiếp ảnh gia, bạn không thể chọn lại.'  # báo: danh sách đã gửi rồi
    if booking.TrangThai != TrangThaiBooking.CHO_KH_CHON_ANH:  # chưa đến bước chọn ảnh (hoặc Booking đã hủy...)
        return f'Booking đang ở trạng thái "{booking.TrangThai}", chưa đến lúc lựa chọn ảnh.'  # báo: chưa đến bước chọn ảnh
    if booking.HanChonAnh and timezone.now() > booking.HanChonAnh:   # N6: chỉ được chọn trong hạn 2 ngày
        return 'Đã quá hạn lựa chọn ảnh (2 ngày kể từ khi ảnh được tải lên), không thể chọn thêm.'  # báo: đã quá hạn 2 ngày
    return None                                                # mọi điều kiện đều ổn: được chọn


def _lay_booking_de_chon(ma_booking, khach):                   # khóa Booking của Khách và kiểm tra được chọn ảnh; PHẢI gọi trong transaction.atomic
    try:                                                       # thử lấy Booking
        booking = (Booking.objects.select_for_update().select_related('MaGoi')   # khóa dòng để 2 lần bấm cùng lúc không đè nhau
                   .get(pk=ma_booking, MaKhachHang=khach))     # phải là Booking của chính Khách này
    except Booking.DoesNotExist:                               # không có hoặc của người khác
        raise LoiChonAnh('Booking không tồn tại hoặc không thuộc về bạn.')  # báo: Booking không tồn tại hoặc của người khác
    ly_do = ly_do_khong_chon_duoc(booking)                     # kiểm tra trạng thái, gói, hạn chót
    if ly_do:                                                  # có lý do cấm
        raise LoiChonAnh(ly_do)                                # báo lỗi và dừng
    return booking                                             # hợp lệ: trả Booking đã khóa


def _ghi_lua_chon(booking, ds_ma_anh):                         # bước 4: ghi danh sách ảnh được chọn vào cột DuocChonHauKy; trả về số ảnh đã chọn
    ds = set(ds_ma_anh)                                        # bỏ mã trùng (nếu có)
    toi_da = so_anh_toi_da_cua_goi(booking)                    # giới hạn của gói
    if len(ds) > toi_da:                                       # ngoại lệ 4b: chọn vượt quá số ảnh được phép
        raise LoiChonAnh(f'Bạn đã chọn {len(ds)} ảnh, vượt quá giới hạn {toi_da} ảnh của gói dịch vụ. '  # ngoại lệ 4b: báo chọn vượt giới hạn
                         f'Vui lòng bỏ bớt {len(ds) - toi_da} ảnh.')  # nối tiếp câu báo: số ảnh cần bỏ bớt
    hop_le = set(anh_de_chon(booking).filter(pk__in=ds).values_list('pk', flat=True))   # những mã thật sự là ảnh của Booking này
    if hop_le != ds:                                           # có mã lạ (ảnh Booking khác, ảnh đã hậu kỳ...) -> không tin dữ liệu gửi lên
        raise LoiChonAnh('Có ảnh được chọn không thuộc Booking này hoặc không còn để chọn, vui lòng tải lại trang.')  # báo: có mã ảnh không hợp lệ
    anh_de_chon(booking).filter(pk__in=ds).update(DuocChonHauKy=1)       # các ảnh được chọn -> đánh dấu 1
    anh_de_chon(booking).exclude(pk__in=ds).update(DuocChonHauKy=0)      # các ảnh còn lại -> bỏ đánh dấu (để lưu lại nhiều lần được)
    return len(ds)                                             # số ảnh đã chọn


def luu_lua_chon(ma_booking, khach, ds_ma_anh):                # bước 3-4: lưu lựa chọn (chưa gửi cho Nhiếp ảnh gia); trả về số ảnh đã chọn
    try:                                                       # bắt lỗi hệ thống để báo cho Khách
        with transaction.atomic():                             # 1 giao dịch: lỗi ở đâu thì hoàn tác hết
            booking = _lay_booking_de_chon(ma_booking, khach)  # khóa Booking và kiểm tra quyền, trạng thái, hạn
            return _ghi_lua_chon(booking, ds_ma_anh)           # ghi lựa chọn và trả số ảnh
    except DatabaseError:                                      # lỗi database
        raise LoiChonAnh('Không thể lưu danh sách ảnh được lựa chọn, vui lòng thực hiện lại thao tác.')   # ngoại lệ 6a


def gui_danh_sach_hau_ky(ma_booking, khach):                   # bước 5-6: Khách xác nhận, gửi danh sách ĐÃ LƯU cho Nhiếp ảnh gia
    try:                                                       # bắt lỗi hệ thống để báo cho Khách
        with transaction.atomic():                             # 1 giao dịch: đổi trạng thái + ghi lịch sử cùng thành công hoặc cùng hủy
            booking = _lay_booking_de_chon(ma_booking, khach)  # khóa Booking và kiểm tra quyền, trạng thái, hạn
            so_chon = anh_de_chon(booking).filter(DuocChonHauKy=1).count()   # đếm ảnh đã lưu là "được chọn"
            if so_chon == 0:                                   # chưa chọn ảnh nào
                raise LoiChonAnh('Vui lòng chọn ít nhất một ảnh cần hậu kỳ.')  # báo: chưa chọn ảnh nào
            if so_chon > so_anh_toi_da_cua_goi(booking):       # phòng dữ liệu cũ vượt giới hạn
                raise LoiChonAnh('Số ảnh đã chọn vượt quá giới hạn của gói dịch vụ, vui lòng bỏ bớt ảnh.')  # báo: vượt giới hạn (dữ liệu cũ)
            chuyen_trang_thai_booking(booking, TrangThaiBooking.CHO_HAU_KY, BenThucHien.KHACH_HANG)   # HÀM T2: Chờ KH chọn ảnh -> Chờ hậu kỳ, tự ghi lịch sử
    except ValidationError as loi:                             # hàm của Tuyền từ chối bước chuyển
        raise LoiChonAnh(' '.join(loi.messages))               # đổi thành lỗi của UC5.4 để view hiển thị
    except DatabaseError:                                      # lỗi database
        raise LoiChonAnh('Không thể lưu danh sách ảnh được lựa chọn, vui lòng thực hiện lại thao tác.')   # ngoại lệ 6a
    gui_thong_bao(booking.MaNhiepAnhGia.MaTaiKhoan, 'Khách hàng đã chọn ảnh cần hậu kỳ',   # bước 6: báo Nhiếp ảnh gia
                  f'Booking #{booking.pk}: Khách hàng đã gửi danh sách {so_chon} ảnh cần hậu kỳ, vui lòng bắt đầu hậu kỳ.',
                  booking=booking)                             # gắn thông báo vào Booking
    return {'so_anh': so_chon}                                 # trả số ảnh đã gửi để view hiện thông báo


def bat_dau_hau_ky(ma_booking, nag_user):                      # Nhiếp ảnh gia bấm "Bắt đầu hậu kỳ": Chờ hậu kỳ -> Đang hậu kỳ (hạn 3 ngày)
    try:                                                       # bắt lỗi để báo cho Nhiếp ảnh gia
        with transaction.atomic():                             # 1 giao dịch
            try:                                               # lấy Booking của chính Nhiếp ảnh gia này
                booking = Booking.objects.select_for_update().get(pk=ma_booking, MaNhiepAnhGia__MaTaiKhoan=nag_user)  # khóa Booking của Nhiếp ảnh gia này
            except Booking.DoesNotExist:                       # không có hoặc của người khác
                raise LoiBatDauHauKy('Booking không tồn tại hoặc không thuộc về bạn.')  # báo: Booking không tồn tại hoặc của người khác
            return chuyen_trang_thai_booking(booking, TrangThaiBooking.DANG_HAU_KY, BenThucHien.NHIEP_ANH_GIA)   # HÀM T2: tự gán HanHauKy = 3 ngày và ghi lịch sử
    except ValidationError as loi:                             # hàm của Tuyền từ chối (sai trạng thái, sai bên thực hiện...)
        raise LoiBatDauHauKy(' '.join(loi.messages))           # đổi thành lỗi để view hiển thị
    except DatabaseError:                                      # lỗi database
        raise LoiBatDauHauKy('Không thể bắt đầu hậu kỳ, vui lòng thử lại.')  # báo: lỗi hệ thống


# =====================================================================
# N7 / UC5.5: Khách hàng yêu cầu chỉnh sửa ảnh (tối đa 3 lần cho mỗi Booking)
# =====================================================================
SO_LAN_CHINH_SUA_TOI_DA = 3                                    # BR5.5-1: tối đa 03 lần yêu cầu chỉnh sửa cho mỗi Booking
DO_DAI_NHAN_XET_TOI_DA = 1000                                  # nhận xét tổng quát tối đa 1000 ký tự (cột NoiDung của YEUCAUCHINHSUA)
DO_DAI_NOI_DUNG_ANH_TOI_DA = 500                               # nội dung sửa của mỗi ảnh tối đa 500 ký tự (cột NoiDungChinhSua)


class LoiYeuCauChinhSua(Exception):                            # lỗi nghiệp vụ của UC5.5: view bắt lại để hiện cho Khách hàng
    pass                                                       # không cần thêm gì, chỉ dùng làm "nhãn" cho lỗi


def so_lan_chinh_sua_da_dung(booking):                         # bước 2: Booking này đã gửi bao nhiêu lần yêu cầu chỉnh sửa
    return YeuCauChinhSua.objects.filter(MaBooking=booking).count()   # đếm số dòng yêu cầu của Booking


def so_lan_chinh_sua_con_lai(booking):                         # bước 2: còn bao nhiêu lần được yêu cầu
    return max(0, SO_LAN_CHINH_SUA_TOI_DA - so_lan_chinh_sua_da_dung(booking))   # không để số âm


def anh_de_chinh_sua(booking):                                 # các ảnh Khách được xem và chọn sửa: ảnh đã hậu kỳ (có watermark), còn lưu
    return Anh.objects.filter(                                 # lấy từ bảng ANH
        MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU,  # đúng Booking này và file ảnh còn tồn tại
        LoaiAnh=LoaiAnh.DA_HAU_KY).order_by('TenAnh')          # chỉ ảnh "Đã hậu kỳ", xếp theo tên


def ly_do_khong_yeu_cau_duoc(booking):                         # trả về câu báo nếu Khách KHÔNG được yêu cầu chỉnh sửa lúc này, hoặc None nếu được
    if booking.TrangThai == TrangThaiBooking.DANG_HAU_KY:      # Nhiếp ảnh gia đang hậu kỳ (lần đầu hoặc đang sửa theo yêu cầu)
        return 'Nhiếp ảnh gia đang hậu kỳ ảnh, chưa đến lúc kiểm tra và yêu cầu chỉnh sửa.'
    if booking.TrangThai in (TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN, TrangThaiBooking.HOAN_THANH):   # Khách đã xác nhận bàn giao
        return 'Bạn đã xác nhận bàn giao ảnh nên không thể yêu cầu chỉnh sửa nữa.'
    if booking.TrangThai != TrangThaiBooking.CHO_KH_KIEM_TRA:  # Pre-condition: Nhiếp ảnh gia đã tải ảnh hậu kỳ lên (Chờ Khách hàng kiểm tra)
        return f'Booking đang ở trạng thái "{booking.TrangThai}", chưa đến lúc kiểm tra ảnh.'
    if so_lan_chinh_sua_con_lai(booking) == 0:                 # luồng 2a: đã dùng đủ 3 lần
        return (f'Bạn đã sử dụng tối đa {SO_LAN_CHINH_SUA_TOI_DA:02d} lần yêu cầu chỉnh sửa cho Booking này '
                'nên không thể gửi thêm yêu cầu chỉnh sửa.')
    return None                                                # mọi điều kiện đều ổn: được yêu cầu


def _lay_booking_de_yeu_cau(ma_booking, khach):                # khóa Booking của Khách và kiểm tra được yêu cầu; PHẢI gọi trong transaction.atomic
    try:                                                       # thử lấy Booking
        booking = (Booking.objects.select_for_update().select_related('MaGoi')   # khóa dòng để hai lần bấm cùng lúc không tạo trùng
                   .get(pk=ma_booking, MaKhachHang=khach))     # phải là Booking của chính Khách này
    except Booking.DoesNotExist:                               # không có hoặc của người khác
        raise LoiYeuCauChinhSua('Booking không tồn tại hoặc không thuộc về bạn.')   # báo lỗi và dừng
    ly_do = ly_do_khong_yeu_cau_duoc(booking)                  # kiểm tra trạng thái và số lần
    if ly_do:                                                  # có lý do cấm
        raise LoiYeuCauChinhSua(ly_do)                         # báo lỗi và dừng
    return booking                                             # hợp lệ: trả Booking đã khóa


def gui_yeu_cau_chinh_sua(ma_booking, khach, nhan_xet, ds_anh):   # bước 4-6 của UC5.5; ds_anh = {mã ảnh: nội dung cần sửa}
    nhan_xet = (nhan_xet or '').strip()                        # bỏ khoảng trắng 2 đầu của nhận xét tổng quát
    chuan = {int(ma): (nd or '').strip() for ma, nd in (ds_anh or {}).items()}   # chuẩn hóa: mã ảnh là số, nội dung bỏ khoảng trắng 2 đầu
    try:                                                       # bắt lỗi hệ thống để báo cho Khách
        with transaction.atomic():                             # 1 giao dịch: lưu yêu cầu + đổi trạng thái + ghi lịch sử cùng thành công hoặc cùng hủy
            booking = _lay_booking_de_yeu_cau(ma_booking, khach)   # khóa Booking và kiểm tra quyền, trạng thái, số lần
            if not chuan:                                      # ngoại lệ 4a: chưa chọn ảnh nào
                raise LoiYeuCauChinhSua('Vui lòng chọn ít nhất một ảnh cần chỉnh sửa.')
            if not nhan_xet:                                   # ngoại lệ 4b: nhận xét tổng quát trống
                raise LoiYeuCauChinhSua('Nội dung yêu cầu không hợp lệ: vui lòng nhập nhận xét tổng quát.')
            if len(nhan_xet) > DO_DAI_NHAN_XET_TOI_DA:         # ngoại lệ 4b: nhận xét quá dài
                raise LoiYeuCauChinhSua(f'Nội dung yêu cầu không hợp lệ: nhận xét tổng quát tối đa {DO_DAI_NHAN_XET_TOI_DA} ký tự.')
            ten_anh = dict(anh_de_chinh_sua(booking).filter(pk__in=chuan).values_list('pk', 'TenAnh'))   # {mã: tên} của các ảnh hợp lệ
            if set(ten_anh) != set(chuan):                      # có mã lạ (ảnh Booking khác, ảnh chưa hậu kỳ...) -> không tin dữ liệu gửi lên
                raise LoiYeuCauChinhSua('Có ảnh được chọn không thuộc Booking này hoặc chưa được hậu kỳ, vui lòng tải lại trang.')
            thieu = [ten_anh[ma] for ma, nd in chuan.items() if not nd]   # các ảnh đã chọn nhưng chưa nhập nội dung
            if thieu:                                          # ngoại lệ 4b: thiếu nội dung chỉnh sửa
                raise LoiYeuCauChinhSua('Nội dung yêu cầu không hợp lệ: vui lòng nhập nội dung chỉnh sửa cho ảnh ' + ', '.join(sorted(thieu)[:10]) + '.')
            dai = [ten_anh[ma] for ma, nd in chuan.items() if len(nd) > DO_DAI_NOI_DUNG_ANH_TOI_DA]   # các ảnh có nội dung quá dài
            if dai:                                            # ngoại lệ 4b: nội dung quá dài
                raise LoiYeuCauChinhSua(f'Nội dung yêu cầu không hợp lệ: nội dung chỉnh sửa tối đa {DO_DAI_NOI_DUNG_ANH_TOI_DA} ký tự (ảnh ' + ', '.join(sorted(dai)[:10]) + ').')
            so_lan = so_lan_chinh_sua_da_dung(booking) + 1     # bước 5: đây là lần yêu cầu thứ mấy
            yeu_cau = YeuCauChinhSua.objects.create(MaBooking=booking, NoiDung=nhan_xet, SoLanYeuCau=so_lan)   # lưu yêu cầu (nhận xét tổng quát) và số lần đã dùng
            YeuCauChinhSua_Anh.objects.bulk_create([           # lưu nội dung chỉnh sửa của từng ảnh
                YeuCauChinhSua_Anh(MaYeuCauChinhSua=yeu_cau, MaAnh_id=ma, NoiDungChinhSua=nd) for ma, nd in chuan.items()])
            chuyen_trang_thai_booking(booking, TrangThaiBooking.DANG_HAU_KY, BenThucHien.KHACH_HANG)   # HÀM T2: Chờ KH kiểm tra -> Đang hậu kỳ, tự tính lại hạn 3 ngày và ghi lịch sử
    except ValidationError as loi:                             # hàm của Tuyền từ chối bước chuyển
        raise LoiYeuCauChinhSua(' '.join(loi.messages))        # đổi thành lỗi của UC5.5 để view hiển thị
    except DatabaseError:                                      # ngoại lệ 5a: lỗi lưu yêu cầu (kể cả trùng số lần do hai lần bấm cùng lúc)
        raise LoiYeuCauChinhSua('Không thể lưu yêu cầu chỉnh sửa, vui lòng thực hiện lại thao tác.')
    thong_bao = gui_thong_bao(booking.MaNhiepAnhGia.MaTaiKhoan, 'Khách hàng yêu cầu chỉnh sửa ảnh',   # bước 6: báo Nhiếp ảnh gia
                              f'Booking #{booking.pk}: Khách hàng gửi yêu cầu chỉnh sửa lần {so_lan}/{SO_LAN_CHINH_SUA_TOI_DA} '
                              f'cho {len(chuan)} ảnh, vui lòng chỉnh sửa và tải phiên bản mới.', booking=booking)
    da_bao_nag = thong_bao is not None                         # gui_thong_bao trả None nếu lỗi
    if not da_bao_nag:                                         # ngoại lệ 6a: không gửi được thông báo
        logger.error('UC5.5: không gửi được thông báo yêu cầu chỉnh sửa lần %s của Booking %s (MaYeuCauChinhSua=%s), cần gửi lại',
                     so_lan, booking.pk, yeu_cau.pk)           # ghi nhận để xử lý lại (đặc tả chưa có cột lưu trạng thái này)
    return {'so_lan': so_lan, 'so_anh': len(chuan), 'da_bao_nag': da_bao_nag}   # trả kết quả cho view


# =====================================================================
# N8 / UC5.6: Khách hàng xác nhận hoàn tất bàn giao
# =====================================================================
class LoiBanGiao(Exception):                                   # lỗi nghiệp vụ của UC5.6: view bắt lại để hiện cho Khách hàng
    pass                                                       # không cần thêm gì, chỉ dùng làm "nhãn" cho lỗi


def so_tien_con_lai(booking):                                  # số tiền khoản thanh toán 60% còn lại (hàm tính của payments)
    return tinh_so_tien(booking.TongGiaTri, LoaiThanhToan.PHAN_CON_LAI)   # Tổng giá trị - tiền cọc 40% (làm tròn)


def dinh_dang_tien(so_tien):                                   # 600000 -> "600.000 VNĐ" để hiện cho Khách
    return f'{int(so_tien):,}'.replace(',', '.') + ' VNĐ'      # đổi dấu phẩy ngăn cách nghìn thành dấu chấm


def ly_do_khong_xac_nhan_duoc(booking):                        # trả về câu báo nếu Khách KHÔNG xác nhận bàn giao được lúc này, hoặc None nếu được
    if booking.TrangThai in (TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN, TrangThaiBooking.HOAN_THANH):   # đã xác nhận rồi
        return 'Bạn đã xác nhận hoàn tất bàn giao cho Booking này.'  # báo: đã xác nhận rồi
    if booking.TrangThai == TrangThaiBooking.DANG_HAU_KY:      # Nhiếp ảnh gia đang hậu kỳ
        return 'Nhiếp ảnh gia đang hậu kỳ ảnh, chưa đến lúc kiểm tra và xác nhận bàn giao.'  # báo: đang hậu kỳ
    if booking.TrangThai != TrangThaiBooking.CHO_KH_KIEM_TRA:  # Pre-condition: Nhiếp ảnh gia đã tải ảnh hậu kỳ lên (Chờ Khách hàng kiểm tra)
        return f'Booking đang ở trạng thái "{booking.TrangThai}", chưa đến lúc xác nhận bàn giao.'  # báo: chưa đến lúc xác nhận
    return None                                                # mọi điều kiện đều ổn: được xác nhận


def xac_nhan_hoan_tat_ban_giao(ma_booking, khach):             # bước 4-7 của UC5.6
    buoc = 'ban_giao'                                          # đang làm bước nào, để báo đúng lỗi 5a hay 6a
    try:                                                       # bắt lỗi hệ thống để báo cho Khách
        with transaction.atomic():                             # 1 giao dịch: Bàn giao + Thanh toán 60% + đổi trạng thái cùng thành công hoặc cùng hủy
            try:                                               # lấy Booking của chính Khách này
                booking = (Booking.objects.select_for_update().select_related('MaGoi')   # khóa dòng để hai lần bấm cùng lúc không tạo trùng
                           .get(pk=ma_booking, MaKhachHang=khach))  # phải là Booking của chính Khách này
            except Booking.DoesNotExist:                       # không có hoặc của người khác
                raise LoiBanGiao('Booking không tồn tại hoặc không thuộc về bạn.')  # báo: Booking không tồn tại hoặc của người khác
            ly_do = ly_do_khong_xac_nhan_duoc(booking)         # kiểm tra trạng thái
            if ly_do:                                          # có lý do cấm
                raise LoiBanGiao(ly_do)                        # báo lỗi và dừng
            bay_gio = timezone.now()                           # mốc giờ xác nhận
            BanGiao.objects.create(MaBooking=booking, NgayXacNhan=bay_gio)   # bước 5: tạo bản ghi Bàn giao, trạng thái mặc định "Hoàn tất bàn giao"
            ThanhToan.objects.create(                          # tạo khoản thanh toán 60% còn lại
                MaBooking=booking, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI,   # loại: phần còn lại
                SoTien=so_tien_con_lai(booking), TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_60)   # số tiền 60%, trạng thái chờ xác nhận
            buoc = 'booking'                                   # từ đây là bước 6: đổi trạng thái Booking
            booking = chuyen_trang_thai_booking(booking, TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN, BenThucHien.KHACH_HANG)   # HÀM T2: tự gán hạn thanh toán 2 ngày và ghi lịch sử
    except ValidationError as loi:                             # hàm của Tuyền từ chối bước chuyển
        raise LoiBanGiao(' '.join(loi.messages))               # đổi thành lỗi của UC5.6 để view hiển thị
    except DatabaseError:                                      # lỗi database: hoàn tác cả giao dịch
        if buoc == 'ban_giao':                                 # ngoại lệ 5a: lỗi khi tạo Bàn giao / khoản thanh toán
            raise LoiBanGiao('Không thể cập nhật trạng thái bàn giao, vui lòng thực hiện lại thao tác.')  # ngoại lệ 5a: báo lỗi tạo Bàn giao
        raise LoiBanGiao('Không thể cập nhật Booking sang trạng thái chờ thanh toán phần còn lại, vui lòng thử lại.')   # ngoại lệ 6a
    so_tien = so_tien_con_lai(booking)                         # số tiền phải thanh toán
    han_text = timezone.localtime(booking.HanThanhToanConLai).strftime('%d/%m/%Y %H:%M')   # hạn thanh toán (2 ngày) dạng chữ
    gui_thong_bao(khach, 'Vui lòng thanh toán phần còn lại',   # bước 6: báo Khách hàng thanh toán 60%
                  f'Booking #{booking.pk}: bạn đã xác nhận hoàn tất bàn giao. Vui lòng thanh toán {dinh_dang_tien(so_tien)} '
                  f'(phần còn lại) trước {han_text}.', booking=booking)  # nối tiếp câu báo thành công
    gui_thong_bao(booking.MaNhiepAnhGia.MaTaiKhoan, 'Khách hàng đã xác nhận hoàn tất bàn giao',   # bước 7: báo Nhiếp ảnh gia
                  f'Booking #{booking.pk}: Khách hàng đã xác nhận hoàn tất bàn giao. '
                  f'Đang chờ Khách hàng thanh toán phần còn lại ({dinh_dang_tien(so_tien)}).', booking=booking)  # nối tiếp nội dung thông báo
    return {'so_tien': so_tien, 'han': booking.HanThanhToanConLai}   # trả kết quả cho view

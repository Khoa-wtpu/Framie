# payments/services.py - N2 / UC5.1 (Khách hàng tải minh chứng) và N3 / UC5.2 (Nhiếp ảnh gia xác nhận cọc) (Nguyên)
import uuid                                                  # tạo tên tệp ngẫu nhiên, không trùng, không lộ tên gốc
from pathlib import Path                                     # tách phần đuôi (.png) khỏi tên tệp

from django.conf import settings                             # đọc BASE_DIR và (nếu có) MINH_CHUNG_ROOT
from django.core.files.storage import FileSystemStorage      # lưu tệp xuống ổ đĩa
from django.core.exceptions import ValidationError           # lỗi mà hàm đổi trạng thái của Tuyền ném ra (N3)
from django.db import DatabaseError, transaction             # DatabaseError: lỗi DB; transaction: lỗi thì hoàn tác
from django.utils import timezone                            # giờ hiện tại có múi giờ

from accounts.permissions import lay_vai_tro                 # vai trò của User (đã có sẵn của Phanh)
from bookings.models import Booking                          # model Booking của Tuyền
from bookings.services import chuyen_trang_thai_booking      # (N3) HÀM T2 của Tuyền: nơi DUY NHẤT được đổi trạng thái Booking
from core.constants import (BenThucHien, LoaiThanhToan,      # hằng số, KHÔNG gõ chữ tiếng Việt trực tiếp
                            TrangThaiBooking, TrangThaiThanhToan, VaiTro)
from notifications.services import gui_thong_bao            # hàm gửi thông báo dùng chung của Phanh
from payments.models import MinhChungThanhToan, ThanhToan, tinh_so_tien  # model + hàm tính 40%/60% của chính app

DUOI_CHO_PHEP = ('jpg', 'jpeg', 'png')                       # chỉ nhận 3 đuôi này
DUNG_LUONG_TOI_DA = 5 * 1024 * 1024                          # tối đa 5 MB (tính bằng byte), muốn đổi thì sửa số 5


class LoiTaiMinhChung(Exception):                            # lỗi nghiệp vụ: view bắt lại để hiện cho Khách hàng
    pass


def kho_minh_chung():                                        # nơi cất minh chứng: KHÔNG nằm trong media/ công khai
    goc = getattr(settings, 'MINH_CHUNG_ROOT', settings.BASE_DIR / 'private_media')  # mặc định D:\FRAMIE\private_media
    return FileSystemStorage(location=goc)                   # tạo kho lưu tệp trỏ vào thư mục đó


def xac_dinh_khoan(booking):                                 # Booking đang cần thanh toán khoản nào? (None = không cần)
    if booking.TrangThai == TrangThaiBooking.CHO_DAT_COC:    # Chờ đặt cọc -> khoản cọc 40%
        loai, han, cho = (LoaiThanhToan.TIEN_COC, booking.HanDatCoc,
                          TrangThaiThanhToan.CHO_XAC_NHAN_COC)
    elif booking.TrangThai == TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN:  # Chờ xác nhận thanh toán -> khoản 60%
        loai, han, cho = (LoaiThanhToan.PHAN_CON_LAI, booking.HanThanhToanConLai,
                          TrangThaiThanhToan.CHO_XAC_NHAN_60)
    else:                                                    # các trạng thái khác không có thanh toán để nộp
        return None
    return {'loai': loai,                                    # 'Tiền cọc' hoặc 'Phần còn lại'
            'so_tien': tinh_so_tien(booking.TongGiaTri, loai),  # hàm của chính payments/models.py (cọc = 40% làm tròn)
            'han': han,                                      # hạn chót thanh toán khoản này
            'trang_thai_cho': cho}                           # trạng thái khoản thanh toán khi đang chờ NAG xác nhận


def ly_do_khong_gui_duoc(khoan, thanh_toan):                 # trả về câu báo lỗi nếu KHÔNG được gửi, hoặc None nếu được gửi
    # NAG đã yêu cầu bổ sung thì Khách được gửi lại trong lúc Booking vẫn chờ khoản thanh toán,
    # kể cả khi hạn ban đầu đã qua. Tác vụ tự chuyển Booking hết hạn sẽ xử lý riêng sau.
    dang_cho_bo_sung = thanh_toan is not None and bool(thanh_toan.LyDoTuChoi)
    if khoan['han'] and timezone.now() > khoan['han'] and not dang_cho_bo_sung:
        return 'Đã quá hạn thanh toán, không thể tải minh chứng.'
    if thanh_toan is not None and thanh_toan.TrangThai != khoan['trang_thai_cho']:  # đã xác nhận hoặc quá hạn
        return 'Khoản thanh toán này không còn nhận thêm minh chứng.'
    return None


def tai_len_minh_chung(ma_booking, khach_hang, tep):         # bước 4-7 của UC5.1
    kho = kho_minh_chung()                                   # kho lưu tệp riêng
    duong_dan = None                                         # đường dẫn tệp đã lưu (để xóa nếu sau đó DB báo lỗi)
    try:
        with transaction.atomic():                           # cả khối là 1 giao dịch: lỗi thì hoàn tác DB
            try:
                booking = (Booking.objects.select_for_update()   # khóa dòng Booking, tránh bấm 2 lần cùng lúc
                           .get(pk=ma_booking, MaKhachHang=khach_hang))  # và phải là Booking của chính khách này
            except Booking.DoesNotExist:
                raise LoiTaiMinhChung('Booking không tồn tại.')
            khoan = xac_dinh_khoan(booking)
            if khoan is None:
                raise LoiTaiMinhChung('Booking hiện không ở giai đoạn thanh toán.')

            thanh_toan = ThanhToan.objects.filter(MaBooking=booking, LoaiThanhToan=khoan['loai']).first()  # khoản đã có chưa
            loi = ly_do_khong_gui_duoc(khoan, thanh_toan)
            if loi:
                raise LoiTaiMinhChung(loi)
            if thanh_toan is None:                           # lần tải đầu của khoản cọc: tạo khoản thanh toán
                thanh_toan = ThanhToan.objects.create(
                    MaBooking=booking, LoaiThanhToan=khoan['loai'], SoTien=khoan['so_tien'],
                    TrangThai=khoan['trang_thai_cho'])       # 'Chờ xác nhận thanh toán cọc'

            duoi = Path(tep.name).suffix.lstrip('.').lower()  # đuôi tệp: png / jpg / jpeg
            duong_dan = kho.save(f'minh_chung/{thanh_toan.pk}/{uuid.uuid4().hex}.{duoi}', tep)  # ghi tệp xuống ổ đĩa
            MinhChungThanhToan.objects.create(               # mỗi lần gửi = 1 dòng mới (gửi lại nhiều lần được)
                MaThanhToan=thanh_toan, TenTep=Path(tep.name).name[:255], DuongDanTep=duong_dan,
                DinhDangTep=duoi.upper(), KichThuocTep=tep.size)  # JPG / JPEG / PNG đúng DinhDangTep trong constants
            thanh_toan.NgayThanhToan = timezone.now()        # lúc Khách hàng nộp minh chứng
            thanh_toan.LyDoTuChoi = None                     # xóa yêu cầu bổ sung cũ (nếu NAG từng yêu cầu)
            thanh_toan.save(update_fields=['NgayThanhToan', 'LyDoTuChoi'])
    except (OSError, DatabaseError):                         # lỗi ghi tệp hoặc lỗi DB (ngoại lệ 6a)
        if duong_dan:                                        # tệp đã lỡ lưu thì xóa đi, tránh tệp mồ côi
            try:
                kho.delete(duong_dan)
            except OSError:
                pass
        raise LoiTaiMinhChung('Không thể lưu minh chứng thanh toán, vui lòng thử lại.')

    gui_thong_bao(booking.MaNhiepAnhGia.MaTaiKhoan,          # báo nhiếp ảnh gia (hàm của Phanh, không ném lỗi ra ngoài)
                  'Khách hàng đã tải minh chứng thanh toán',
                  f'Booking #{booking.pk}: Khách hàng đã gửi minh chứng {khoan["loai"].lower()}. '
                  'Vui lòng kiểm tra và xác nhận.',
                  booking=booking)
    return thanh_toan


def mo_minh_chung(user, ma_minh_chung):                      # dùng cho trang xem ảnh minh chứng (có kiểm tra quyền)
    try:
        mc = (MinhChungThanhToan.objects
              .select_related('MaThanhToan__MaBooking__MaNhiepAnhGia')
              .get(pk=ma_minh_chung))
    except MinhChungThanhToan.DoesNotExist:
        return None, None
    bk = mc.MaThanhToan.MaBooking
    duoc_xem = (user.pk == bk.MaKhachHang_id                 # chính Khách hàng của Booking
                or user.pk == bk.MaNhiepAnhGia.MaTaiKhoan_id  # hoặc Nhiếp ảnh gia nhận Booking
                or lay_vai_tro(user) == VaiTro.QUAN_TRI_VIEN)  # hoặc Quản trị viên
    return (mc if duoc_xem else False), kho_minh_chung()     # False = có tệp nhưng không được xem


# =====================================================================
# N3 / UC5.2: Nhiếp ảnh gia xác nhận thanh toán tiền cọc
# =====================================================================
class LoiXacNhanCoc(Exception):                              # lỗi nghiệp vụ UC5.2: view bắt lại để hiện cho Nhiếp ảnh gia
    pass


def ly_do_khong_xu_ly_duoc(booking, thanh_toan):             # trả về câu báo lỗi nếu NAG chưa xử lý được, hoặc None nếu xử lý được
    if booking.TrangThai != TrangThaiBooking.CHO_DAT_COC:    # Booking đã chốt, hủy, hết hạn...
        return f'Booking đang ở trạng thái "{booking.TrangThai}", không thể xử lý tiền cọc.'
    if thanh_toan is None or not thanh_toan.minh_chungs.exists():  # khách chưa nộp gì để kiểm tra
        return 'Khách hàng chưa tải minh chứng thanh toán tiền cọc.'
    if thanh_toan.TrangThai != TrangThaiThanhToan.CHO_XAC_NHAN_COC:  # khoản cọc đã xử lý rồi
        return 'Khoản tiền cọc này đã được xử lý.'
    if thanh_toan.LyDoTuChoi:                                # đã yêu cầu bổ sung, đang chờ khách nộp lại
        return 'Đang chờ Khách hàng bổ sung minh chứng theo yêu cầu trước đó.'
    return None


def _lay_booking_va_khoan_coc(ma_booking, nag_user):         # hàm phụ: khóa Booking, lấy khoản cọc, kiểm tra điều kiện chung
    try:
        booking = (Booking.objects.select_for_update()       # khóa dòng, tránh 2 lần bấm cùng lúc (gọi trong transaction)
                   .get(pk=ma_booking, MaNhiepAnhGia__MaTaiKhoan=nag_user))  # và phải là Booking của chính NAG này
    except Booking.DoesNotExist:
        raise LoiXacNhanCoc('Booking không tồn tại hoặc không thuộc về bạn.')
    thanh_toan = ThanhToan.objects.filter(MaBooking=booking, LoaiThanhToan=LoaiThanhToan.TIEN_COC).first()
    loi = ly_do_khong_xu_ly_duoc(booking, thanh_toan)
    if loi:
        raise LoiXacNhanCoc(loi)
    return booking, thanh_toan


def xac_nhan_thanh_toan_coc(ma_booking, nag_user):           # bước 4-5 của UC5.2
    try:
        with transaction.atomic():                           # 1 giao dịch: lỗi ở đâu thì hoàn tác hết (ngoại lệ 5a)
            booking, thanh_toan = _lay_booking_va_khoan_coc(ma_booking, nag_user)
            thanh_toan.TrangThai = TrangThaiThanhToan.DA_DAT_COC   # khoản cọc -> 'Đã đặt cọc'
            thanh_toan.NgayXacNhan = timezone.now()          # CHECK của bảng bắt buộc có giá trị này khi 'Đã đặt cọc'
            thanh_toan.save(update_fields=['TrangThai', 'NgayXacNhan'])
            chuyen_trang_thai_booking(                       # HÀM T2: Booking -> Chốt Booking, tự ghi Lịch sử, tự đổi slot -> Đã đặt lịch
                booking, TrangThaiBooking.CHOT_BOOKING, BenThucHien.NHIEP_ANH_GIA)
    except ValidationError as loi:                           # hàm của Tuyền từ chối bước chuyển (sai trạng thái, có người đổi trước...)
        raise LoiXacNhanCoc(' '.join(loi.messages))
    except DatabaseError:                                    # lỗi hệ thống khi ghi dữ liệu
        raise LoiXacNhanCoc('Không thể cập nhật trạng thái thanh toán, vui lòng thực hiện lại.')

    gui_thong_bao(booking.MaKhachHang,                       # báo Khách hàng (hàm của Phanh, không ném lỗi ra ngoài)
                  'Nhiếp ảnh gia đã xác nhận tiền cọc',
                  f'Booking #{booking.pk} đã được chốt. Hẹn gặp bạn ở buổi chụp.',
                  booking=booking)
    return thanh_toan


def yeu_cau_bo_sung_minh_chung(ma_booking, nag_user, ly_do):  # nhánh 4a: minh chứng không hợp lệ / không khớp
    ly_do = (ly_do or '').strip()
    if not ly_do:
        raise LoiXacNhanCoc('Vui lòng nhập lý do yêu cầu bổ sung minh chứng.')
    if len(ly_do) > 255:                                     # cột LyDoTuChoi dài tối đa 255
        raise LoiXacNhanCoc('Lý do tối đa 255 ký tự.')
    try:
        with transaction.atomic():
            booking, thanh_toan = _lay_booking_va_khoan_coc(ma_booking, nag_user)
            thanh_toan.LyDoTuChoi = ly_do                    # có giá trị = đang chờ khách nộp lại; TrangThai GIỮ NGUYÊN
            thanh_toan.save(update_fields=['LyDoTuChoi'])
    except DatabaseError:
        raise LoiXacNhanCoc('Không thể cập nhật trạng thái thanh toán, vui lòng thực hiện lại.')

    gui_thong_bao(booking.MaKhachHang,                       # báo Khách hàng tải lại / bổ sung
                  'Nhiếp ảnh gia yêu cầu bổ sung minh chứng',
                  f'Booking #{booking.pk}: {ly_do}',
                  booking=booking)
    return thanh_toan

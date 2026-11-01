# payments/services.py - N2 / UC5.1: Khách hàng tải lên minh chứng thanh toán (Nguyên)
import uuid                                                  # tạo tên tệp ngẫu nhiên, không trùng, không lộ tên gốc
from pathlib import Path                                     # tách phần đuôi (.png) khỏi tên tệp

from django.conf import settings                             # đọc BASE_DIR và (nếu có) MINH_CHUNG_ROOT
from django.core.files.storage import FileSystemStorage      # lưu tệp xuống ổ đĩa
from django.db import DatabaseError, transaction             # DatabaseError: lỗi DB; transaction: lỗi thì hoàn tác
from django.utils import timezone                            # giờ hiện tại có múi giờ

from accounts.permissions import lay_vai_tro                 # vai trò của User (đã có sẵn của Phanh)
from bookings.models import Booking                          # model Booking của Tuyền
from core.constants import (LoaiThanhToan, TrangThaiBooking,  # hằng số, KHÔNG gõ chữ tiếng Việt trực tiếp
                            TrangThaiThanhToan, VaiTro)
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
    if khoan['han'] and timezone.now() > khoan['han']:       # quá hạn chót
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
                    TrangThai=khoan['trang_thai_cho'])       # 'Chờ xác nhận thanh toán cọc (40%)'

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

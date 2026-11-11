# payments/services_con_lai.py - N9 / UC5.7: Nhiếp ảnh gia xác nhận thanh toán phần còn lại (60%) (Nguyên)
# Viết riêng một file để không đụng vào payments/services.py (N2, N3). Cách làm giống hệt UC5.2.
import logging
from datetime import timedelta                                 # hạn tải ảnh 3 ngày

from django.core.exceptions import ValidationError             # lỗi mà hàm đổi trạng thái của Tuyền ném ra
from django.db import DatabaseError, transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.services import chuyen_trang_thai_booking        # HÀM T2 của Tuyền: nơi DUY NHẤT được đổi trạng thái Booking
from core.constants import BenThucHien, LoaiThanhToan, TrangThaiBooking, TrangThaiThanhToan
from delivery.models import BanGiao                            # bản ghi Bàn giao (N8) chứa ThoiHanTaiAnh
from delivery.services import LoiTaiAnh, chuyen_thanh_anh_hoan_chinh   # N5: ảnh Đã hậu kỳ -> Hoàn chỉnh (không watermark)
from notifications.services import gui_thong_bao               # hàm gửi thông báo dùng chung của Phanh
from payments.models import ThanhToan

logger = logging.getLogger(__name__)

SO_NGAY_TAI_ANH = 3                                            # khách được tải ảnh hoàn chỉnh trong 3 ngày (BANGIAO.ThoiHanTaiAnh)
DO_DAI_LY_DO_TOI_DA = 255                                      # THANHTOAN.LyDoTuChoi VARCHAR(255)


class LoiXacNhanConLai(Exception):                             # lỗi nghiệp vụ UC5.7: view bắt lại để hiện cho Nhiếp ảnh gia
    pass


def lay_khoan_con_lai(booking):                                # khoản thanh toán 60% của Booking (None nếu chưa có)
    return ThanhToan.objects.filter(MaBooking=booking, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI).first()


def la_qua_han(thanh_toan):                                    # luồng 1b: khoản đang ở "Quá hạn thanh toán"
    return thanh_toan is not None and thanh_toan.TrangThai == TrangThaiThanhToan.QUA_HAN


def ly_do_khong_xu_ly_duoc(booking, thanh_toan):               # trả về câu báo lỗi nếu NAG chưa xử lý được, hoặc None nếu xử lý được
    if booking.TrangThai == TrangThaiBooking.HOAN_THANH:       # đã xác nhận xong rồi
        return 'Booking đã hoàn thành, khoản thanh toán phần còn lại đã được xác nhận.'
    if booking.TrangThai != TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN:   # Pre-condition: Khách đã xác nhận hoàn tất bàn giao
        return f'Booking đang ở trạng thái "{booking.TrangThai}", không thể xác nhận thanh toán phần còn lại.'
    if thanh_toan is None:
        return 'Booking này chưa có khoản thanh toán phần còn lại.'
    if thanh_toan.TrangThai == TrangThaiThanhToan.DA_THANH_TOAN:
        return 'Khoản thanh toán phần còn lại này đã được xử lý.'
    if la_qua_han(thanh_toan):                                 # luồng 1b: quá hạn vẫn xác nhận thủ công được, không cần minh chứng
        return None
    if not thanh_toan.minh_chungs.exists():                    # thông thường: phải có minh chứng để kiểm tra
        return 'Khách hàng chưa tải minh chứng thanh toán phần còn lại.'
    if thanh_toan.LyDoTuChoi:                                  # đã yêu cầu bổ sung, đang chờ khách nộp lại
        return 'Đang chờ Khách hàng bổ sung minh chứng theo yêu cầu trước đó.'
    return None


def _lay_booking_va_khoan_con_lai(ma_booking, nag_user):       # khóa Booking, lấy khoản 60%, kiểm tra điều kiện chung (gọi trong transaction)
    try:
        booking = (Booking.objects.select_for_update().select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan')
                   .get(pk=ma_booking, MaNhiepAnhGia__MaTaiKhoan=nag_user))   # phải là Booking của chính NAG này
    except Booking.DoesNotExist:
        raise LoiXacNhanConLai('Booking không tồn tại hoặc không thuộc về bạn.')
    thanh_toan = lay_khoan_con_lai(booking)
    loi = ly_do_khong_xu_ly_duoc(booking, thanh_toan)
    if loi:
        raise LoiXacNhanConLai(loi)
    return booking, thanh_toan


def xac_nhan_thanh_toan_con_lai(ma_booking, nag_user):         # bước 4-7 của UC5.7 (và luồng 1b)
    buoc = 'thanh_toan'                                        # đang làm bước nào, để báo đúng lỗi 5a / 6a
    try:
        with transaction.atomic():                             # 1 giao dịch: thanh toán + Booking + ảnh + bàn giao cùng thành công hoặc cùng hủy
            booking, thanh_toan = _lay_booking_va_khoan_con_lai(ma_booking, nag_user)
            bay_gio = timezone.now()
            thanh_toan.TrangThai = TrangThaiThanhToan.DA_THANH_TOAN   # bước 5: khoản 60% -> 'Đã thanh toán'
            thanh_toan.NgayXacNhan = bay_gio                   # CHECK của bảng bắt buộc có giá trị này khi 'Đã thanh toán'
            thanh_toan.LyDoTuChoi = None                       # xóa yêu cầu bổ sung cũ (nếu có)
            thanh_toan.save(update_fields=['TrangThai', 'NgayXacNhan', 'LyDoTuChoi'])
            buoc = 'booking'                                   # từ đây là bước 6
            booking = chuyen_trang_thai_booking(booking, TrangThaiBooking.HOAN_THANH, BenThucHien.NHIEP_ANH_GIA)   # HÀM T2: ghi Lịch sử
            buoc = 'sau_hoan_thanh'                            # mở quyền tải ảnh hoàn chỉnh
            chuyen_thanh_anh_hoan_chinh(booking)               # N5: ảnh Đã hậu kỳ -> Hoàn chỉnh, không watermark (cùng giao dịch, đúng ghi chú của N5)
            han_tai = bay_gio + timedelta(days=SO_NGAY_TAI_ANH)
            BanGiao.objects.filter(MaBooking=booking).update(ThoiHanTaiAnh=han_tai)   # 3 ngày sau khi xác nhận đủ 60%
    except ValidationError as loi:                             # hàm của Tuyền từ chối bước chuyển (sai trạng thái, có người đổi trước...)
        raise LoiXacNhanConLai(' '.join(loi.messages))
    except LoiTaiAnh as loi:                                   # không chuyển được ảnh sang bản hoàn chỉnh: hoàn tác cả giao dịch
        raise LoiXacNhanConLai(str(loi))
    except DatabaseError:
        if buoc == 'thanh_toan':                               # ngoại lệ 5a
            raise LoiXacNhanConLai('Không thể cập nhật trạng thái thanh toán, vui lòng thực hiện lại thao tác.')
        if buoc == 'booking':                                  # ngoại lệ 6a
            raise LoiXacNhanConLai('Không thể cập nhật Booking sang trạng thái "Hoàn thành", vui lòng thử lại.')
        raise LoiXacNhanConLai('Không thể hoàn tất xác nhận thanh toán, vui lòng thử lại.')

    han_text = timezone.localtime(han_tai).strftime('%d/%m/%Y %H:%M')
    gui_thong_bao(booking.MaKhachHang, 'Thanh toán phần còn lại đã được xác nhận',   # bước 7: báo Khách hàng có thể tải ảnh
                  f'Booking #{booking.pk} đã hoàn thành. Nhiếp ảnh gia đã xác nhận thanh toán phần còn lại, '
                  f'bạn có thể tải ảnh hoàn chỉnh (không watermark) trước {han_text}.', booking=booking)
    try:                                                       # N11: nhắc Khách đánh giá nhiếp ảnh gia (không bao giờ làm hỏng việc xác nhận)
        from reviews.services import gui_nhac_danh_gia
        gui_nhac_danh_gia(booking)
    except Exception:  # noqa: BLE001
        logger.exception('payments: không gửi được thông báo nhắc đánh giá (Booking %s)', booking.pk)
    return thanh_toan


def yeu_cau_bo_sung_con_lai(ma_booking, nag_user, ly_do):      # nhánh 4a: minh chứng không hợp lệ / số tiền chưa đủ
    ly_do = (ly_do or '').strip()
    if not ly_do:
        raise LoiXacNhanConLai('Vui lòng nhập lý do yêu cầu bổ sung minh chứng.')
    if len(ly_do) > DO_DAI_LY_DO_TOI_DA:                       # cột LyDoTuChoi dài tối đa 255
        raise LoiXacNhanConLai(f'Lý do tối đa {DO_DAI_LY_DO_TOI_DA} ký tự.')
    try:
        with transaction.atomic():
            booking, thanh_toan = _lay_booking_va_khoan_con_lai(ma_booking, nag_user)
            if la_qua_han(thanh_toan):                         # quá hạn: khách không tải lại được nữa, hai bên tự thỏa thuận
                raise LoiXacNhanConLai('Khoản thanh toán đã quá hạn nên không yêu cầu bổ sung minh chứng được. '
                                       'Hãy xác nhận khi bạn đã nhận đủ tiền từ Khách hàng.')
            thanh_toan.LyDoTuChoi = ly_do                      # có giá trị = đang chờ khách nộp lại; TrangThai GIỮ NGUYÊN
            thanh_toan.save(update_fields=['LyDoTuChoi'])
    except DatabaseError:
        raise LoiXacNhanConLai('Không thể cập nhật trạng thái thanh toán, vui lòng thực hiện lại.')

    gui_thong_bao(booking.MaKhachHang, 'Nhiếp ảnh gia yêu cầu bổ sung minh chứng',   # báo Khách hàng tải lại / bổ sung
                  f'Booking #{booking.pk}: {ly_do}', booking=booking)
    return thanh_toan

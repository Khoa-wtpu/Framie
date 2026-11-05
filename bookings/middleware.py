# bookings/middleware.py - T10: "Kiểm tra mỗi khi mở trang liên quan".
# Trước khi chạy view, nếu địa chỉ thuộc các trang liên quan thì quét xử lý quá hạn (bookings/qua_han.py).
# Không bao giờ làm hỏng trang: mọi lỗi chỉ ghi log.
import logging

from bookings.qua_han import xu_ly_qua_han

logger = logging.getLogger(__name__)

# Trang liên quan: Booking (giữ chỗ, theo dõi, hủy...), Tổng quan, Thanh toán, Bàn giao ảnh, Tìm kiếm (hiện lịch trống).
TIEN_TO_LIEN_QUAN = ('/bookings/', '/tong-quan/', '/payments/', '/delivery/', '/tim-kiem/')


class XuLyQuaHanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(TIEN_TO_LIEN_QUAN):
            try:
                xu_ly_qua_han()
            except Exception:  # noqa: BLE001
                logger.exception('XuLyQuaHanMiddleware: lỗi khi xử lý quá hạn')
        return self.get_response(request)

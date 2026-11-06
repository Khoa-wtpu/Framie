# bookings/middleware.py - T10: "Kiểm tra mỗi khi mở trang liên quan".
# Trước khi chạy view, nếu địa chỉ thuộc các trang liên quan thì quét xử lý quá hạn (bookings/qua_han.py).
# Không bao giờ làm hỏng trang: mọi lỗi chỉ ghi log.
import logging

from bookings.qua_han import xu_ly_qua_han

logger = logging.getLogger(__name__)

# Trang liên quan, theo ĐÚNG đường dẫn thật trong config/urls.py (payments, delivery, reviews, search đều include ở gốc ''):
#   /bookings/...                          Booking: giữ chỗ, gửi, theo dõi, hủy... (bookings.*)
#   /tong-quan/                            Tổng quan (core)
#   /booking/<id>/minh-chung/, xac-nhan-coc/, xac-nhan-thanh-toan-con-lai/   Thanh toán (payments)
#   /booking/<id>/tai-anh/, chon-anh/, xac-nhan-ban-giao/, tai-anh-hoan-chinh/ ...   Bàn giao ảnh (delivery)
#   /minh-chung/<id>/xem/                  Xem minh chứng thanh toán (payments)
#   /anh/<id>/xem/                         Xem ảnh bàn giao (delivery)
#   /tim-kiem/                             Tìm kiếm, hiện lịch trống (search)
# Lưu ý: '/booking/' (số ít, thanh toán + bàn giao + đánh giá) khác '/bookings/' (số nhiều). Cần giữ cả hai.
TIEN_TO_LIEN_QUAN = ('/bookings/', '/booking/', '/minh-chung/', '/anh/', '/tong-quan/', '/tim-kiem/')


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

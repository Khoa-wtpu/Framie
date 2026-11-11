# bookings/middleware.py - T10: "Kiểm tra mỗi khi mở trang liên quan".
# Trước khi chạy view, nếu địa chỉ thuộc các trang liên quan thì quét xử lý quá hạn (bookings/qua_han.py).
# Không bao giờ làm hỏng trang: mọi lỗi chỉ ghi log.
# Giới hạn tần suất: quét quá hạn tối đa 1 lần mỗi XU_LY_QUA_HAN_KHOANG_CACH_GIAY giây (mặc định 45, xem config/settings.py),
# tính theo từng tiến trình web. Việc quá hạn theo NGÀY không cần chính xác từng giây; muốn đúng giờ thì chạy thêm lệnh
#   python manage.py xu_ly_qua_han --lap 60     (xem README.md, mục "Xử lý quá hạn tự động").
import logging
import threading
import time

from django.conf import settings

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


KHOANG_CACH_MAC_DINH_GIAY = 45        # dùng khi settings không khai báo XU_LY_QUA_HAN_KHOANG_CACH_GIAY

_khoa = threading.Lock()              # nhiều luồng của cùng một tiến trình có thể vào middleware cùng lúc
_lan_quet_cuoi = None                 # mốc time.monotonic() của lần quét gần nhất (None = chưa quét lần nào)


def dat_lai_gioi_han_tan_suat():
    """Xóa mốc 'lần quét gần nhất' để request kế tiếp chắc chắn được quét (dùng trong test)."""
    global _lan_quet_cuoi
    with _khoa:
        _lan_quet_cuoi = None


def _den_luc_quet():
    """True nếu đã qua đủ khoảng cách kể từ lần quét trước; đồng thời ghi mốc mới (chỉ một request thắng khi đua nhau).
    Ghi mốc TRƯỚC khi quét: nếu việc quét lỗi thì cũng không bị thử lại dồn dập ở mỗi request."""
    global _lan_quet_cuoi
    khoang_cach = getattr(settings, 'XU_LY_QUA_HAN_KHOANG_CACH_GIAY', KHOANG_CACH_MAC_DINH_GIAY)
    bay_gio = time.monotonic()
    with _khoa:
        if _lan_quet_cuoi is not None and bay_gio - _lan_quet_cuoi < khoang_cach:
            return False
        _lan_quet_cuoi = bay_gio
        return True


class XuLyQuaHanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(TIEN_TO_LIEN_QUAN) and _den_luc_quet():
            try:
                xu_ly_qua_han()
            except Exception:  # noqa: BLE001
                logger.exception('XuLyQuaHanMiddleware: lỗi khi xử lý quá hạn')
        return self.get_response(request)

# bookings/middleware.py - T10: "Kiểm tra mỗi khi mở trang liên quan".
# Trước khi chạy view, nếu địa chỉ thuộc các trang liên quan thì quét xử lý quá hạn (bookings/qua_han.py).
# Không bao giờ làm hỏng trang: mọi lỗi chỉ ghi log.
# Giới hạn tần suất: quét quá hạn tối đa 1 lần mỗi XU_LY_QUA_HAN_KHOANG_CACH_GIAY giây (mặc định 45, xem config/settings.py),
# tính theo từng tiến trình web. Đây là lớp phụ: việc nhả đúng giờ do luồng nền bookings/nen_qua_han.py (mỗi 60 giây khi web chạy)
# và/hoặc lệnh  python manage.py xu_ly_qua_han --lap 60  đảm nhiệm (xem README.md, mục "Xử lý quá hạn tự động").
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
#1 Dạ, trong lớp XuLyQuaHanMiddleware, hàm __call__() kiểm tra đường dẫn người dùng
# đang truy cập có thuộc các trang liên quan hay không, đồng thời gọi hàm _den_luc_quet()
# để kiểm tra đã đủ khoảng cách mặc định 45 giây kể từ lần quét trước chưa.
# Nếu thỏa mãn cả hai điều kiện, hệ thống gọi hàm xu_ly_qua_han() trong
# file bookings/qua_han.py để xử lý 5 trường hợp quá hạn.
# Mục đích là để hệ thống tự động xử lý các trường hợp quá hạn mà không cần ai bấm nút.
# Ví dụ lượt giữ chỗ quá 5 phút thì nhả slot,
    # hoặc booking quá hạn đặt cọc thì chuyển sang "Hết thời hạn đặt cọc".
    def __call__(self, request):
        # Trong hàm __call__(), hệ thống kiểm tra đường dẫn người dùng đang truy
        # cập có thuộc các trang liên quan hay không để xử lý giữ chỗ hết hạn,
        # quá hạn đặt cọc, quá hạn chờ xác nhận, quá hạn thanh toán 60% và xóa ảnh hết hạn),
        # đồng thời gọi hàm _den_luc_quet() để kiểm tra đã đủ khoảng cách 45 giây
        # kể từ lần quét trước chưa.
        # Nếu thỏa mãn cả hai điều kiện, hệ thống gọi hàm xu_ly_qua_han()
        # trong file bookings/qua_han.py để xử lý các trường hợp quá hạn.
        if request.path.startswith(TIEN_TO_LIEN_QUAN) and _den_luc_quet():
            try:
                xu_ly_qua_han()
            except Exception:  # noqa: BLE001
                logger.exception('XuLyQuaHanMiddleware: lỗi khi xử lý quá hạn')
        return self.get_response(request)


# ---------------------------------------------------------------------------------------------------------
# UC4.1 / UC4.2 luồng 6b: Khách rời khỏi luồng đặt lịch thì MẤT lượt giữ chỗ ngay (không treo đồng hồ ở trang khác).
# Lớp CHẮC CHẮN ở phía server, đi kèm nha_giu_cho.js (sendBeacon). Beacon có thể tới trễ hơn request của trang kế tiếp
# hoặc bị mất; nên khi Khách mở một TRANG khác (không thuộc luồng đặt lịch) mà vẫn còn lượt 'Đang giữ chỗ' thì nhả luôn.
# ---------------------------------------------------------------------------------------------------------
# Các trang thuộc luồng đặt lịch: ở các trang này KHÔNG nhả. (huy_giu_cho / trang_thai_giu_cho là request nền của chính luồng.)
TRANG_TRONG_LUONG_DAT_LICH = {
    'lich_chon_slot', 'chon_slot', 'man_hinh_giu_cho', 'gui_booking', 'huy_giu_cho', 'trang_thai_giu_cho',
}


class NhaGiuChoKhiRoiLuongMiddleware:


#Sau đó, hệ thống gọi hàm huy_giu_cho() trong file bookings/giu_cho.py
# để giải phóng lượt giữ chỗ ngay mà không cần đợi hết 5 phút.
#Cả hai lớp middleware đều sử dụng try...except để bắt lỗi.
# Nếu xảy ra lỗi trong quá trình xử lý, hệ thống gọi logger.exception()
# để ghi lại thông tin lỗi và vẫn cho phép người dùng tiếp tục truy cập trang.

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
#2 Trong hàm process_view(), hệ thống kiểm tra người dùng đã đăng nhập chưa và
# trang đang truy cập có thuộc luồng đặt lịch hay không. (112-116)
    def process_view(self, request, view_func, view_args, view_kwargs):
        try:
            user = getattr(request, 'user', None)
            if user is None or not user.is_authenticated or request.method not in ('GET', 'HEAD'):
                return None
            #3 Hệ thống kiểm tra khách hàng có thực sự mở một trang mới hay không,
            # tránh nhả giữ chỗ nhầm khi có request chạy nền (116-125)
            if 'text/html' not in request.headers.get('Accept', '') or request.headers.get('X-Requested-With'):
                return None
            # Trình duyệt tải trước trang (prefetch/prerender khi rê chuột, gõ URL...) hoặc không phải điều hướng thật
            # (iframe, ảnh...) thì KHÔNG phải Khách đã rời luồng: bỏ qua. Test client không gửi các header này nên không ảnh hưởng.
            muc_dich = (request.headers.get('Sec-Purpose', '') + request.headers.get('Purpose', '')).lower()
            if 'prefetch' in muc_dich or 'prerender' in muc_dich:
                return None
            che_do = request.headers.get('Sec-Fetch-Mode')
            if che_do and che_do != 'navigate':
                return None
            #4 Sau đó, hệ thống kiểm tra trang đang truy cập có thuộc luồng đặt lịch hay không.
            # 128-130
            khop = request.resolver_match
            if khop is None or khop.url_name in TRANG_TRONG_LUONG_DAT_LICH:
                return None
            from bookings.giu_cho import huy_giu_cho
            from bookings.models import GiuCho
            from core.constants import TrangThaiGiuCho
            #5 Nếu khách hàng thực sự mở một trang ngoài luồng đặt lịch, hệ thống sử dụng
            # GiuCho.objects.filter() để tìm các lượt giữ chỗ của khách hàng đang có
            # trạng thái “Đang giữ chỗ”
            for ma in list(GiuCho.objects.filter(MaKhachHang=user, TrangThai=TrangThaiGiuCho.DANG_GIU)
                           .values_list('pk', flat=True)):
                logger.warning('NhaGiuCho: %s mở %s nên nhả lượt %s', user.pk, request.path, ma)   # để truy vết ai nhả
                #6 Sau đó, hệ thống gọi hàm huy_giu_cho()
                # trong file bookings/giu_cho.py để giải phóng lượt giữ chỗ ngay
                # mà không cần đợi hết 5 phút.
                huy_giu_cho(user, ma)      # chỉ nhả lượt 'Đang giữ chỗ' của chính Khách; lượt đã gửi Booking không bị đụng
        #7 Nếu xảy ra lỗi trong quá trình xử lý, hệ thống gọi
        # logger.exception() để ghi lại thông tin lỗi.
        except Exception:  # noqa: BLE001
            logger.exception('NhaGiuChoKhiRoiLuongMiddleware: lỗi khi nhả giữ chỗ')
        return None #8 Hệ thống vẫn cho phép người dùng tiếp tục truy cập trang.
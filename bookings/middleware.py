
# bookings/middleware.py
# T10: Tự động kiểm tra và xử lý quá hạn khi mở trang liên quan.
# UC4.1 / UC4.2: Nhả giữ chỗ khi khách rời khỏi luồng đặt lịch.


import logging  # Thư viện ghi nhật ký hoạt động và lỗi.

import threading  # Thư viện hỗ trợ xử lý nhiều luồng.

import time  # Thư viện hỗ trợ xử lý thời gian.

from django.conf import settings  # Lấy cấu hình từ settings.py.

from bookings.qua_han import xu_ly_qua_han  # Import hàm xử lý 5 công việc quá hạn.


logger = logging.getLogger(__name__)
# Tạo đối tượng ghi log theo tên module hiện tại (bookings.middleware).


# ============================================================
# PHẦN 1: KHAI BÁO CÁC BIẾN VÀ HẰNG SỐ
# ============================================================

TIEN_TO_LIEN_QUAN = (
    '/bookings/',     # Các trang quản lý Booking, giữ chỗ, hủy Booking.
    '/booking/',      # Các trang thanh toán, bàn giao ảnh, đánh giá.
    '/minh-chung/',   # Trang xem minh chứng thanh toán.
    '/anh/',          # Trang xem ảnh bàn giao.
    '/tong-quan/',    # Trang tổng quan sau khi đăng nhập.
    '/tim-kiem/'      # Trang tìm kiếm nhiếp ảnh gia và lịch trống.
)
# Tuple chứa các tiền tố URL cần kiểm tra quá hạn.
# Chỉ những Request có đường dẫn bắt đầu bằng các tiền tố này
# mới được Middleware xem xét xử lý quá hạn.


KHOANG_CACH_MAC_DINH_GIAY = 45
# Khoảng cách mặc định giữa hai lần quét là 45 giây.
# Sử dụng khi settings.py không khai báo giá trị tương ứng.


_khoa = threading.Lock()
# Tạo khóa để tránh nhiều luồng trong cùng một tiến trình
# đồng thời kiểm tra và cập nhật mốc thời gian quét.


_lan_quet_cuoi = None
# Biến lưu mốc thời gian quét gần nhất.
# None nghĩa là hệ thống chưa thực hiện lần quét nào.


# ============================================================
# PHẦN 2: HÀM ĐẶT LẠI GIỚI HẠN TẦN SUẤT
# ============================================================

def dat_lai_gioi_han_tan_suat():
    """Xóa mốc lần quét gần nhất, chủ yếu dùng trong test."""

    global _lan_quet_cuoi
    # Cho phép thay đổi biến _lan_quet_cuoi
    # được khai báo bên ngoài hàm.

    with _khoa:
        # Giữ khóa trong lúc cập nhật biến.
        # Các luồng khác phải chờ đến khi khóa được giải phóng.

        _lan_quet_cuoi = None
        # Đặt lại trạng thái thành chưa từng quét.
        # Request liên quan tiếp theo sẽ được phép quét.


# ============================================================
# PHẦN 3: KIỂM TRA ĐÃ ĐẾN LÚC QUÉT HAY CHƯA
# ============================================================

def _den_luc_quet():
    """Trả True nếu đã đủ khoảng cách giữa hai lần quét."""

    global _lan_quet_cuoi
    # Cho phép cập nhật biến toàn cục _lan_quet_cuoi.

    khoang_cach = getattr(
        settings,
        'XU_LY_QUA_HAN_KHOANG_CACH_GIAY',
        KHOANG_CACH_MAC_DINH_GIAY
    )
    # getattr(đối tượng, tên thuộc tính, giá trị mặc định).
    # Lấy khoảng cách quét được khai báo trong settings.py.
    # Nếu không có cấu hình thì sử dụng mặc định 45 giây.

    bay_gio = time.monotonic()
    # Lấy mốc thời gian hiện tại để tính thời gian đã trôi qua.
    # Không bị ảnh hưởng khi đồng hồ hệ thống được chỉnh lại.

    with _khoa:
        # Khóa đoạn code kiểm tra và cập nhật mốc thời gian.
        # Tại một thời điểm chỉ một luồng được vào đoạn này.

        if _lan_quet_cuoi is not None and bay_gio - _lan_quet_cuoi < khoang_cach:
            # Điều kiện 1: Hệ thống đã từng thực hiện quét.
            # Điều kiện 2: Thời gian từ lần quét trước
            # đến hiện tại chưa đủ khoảng cách quy định.
            #
            # Ví dụ: 30 giây < 45 giây.

            return False
            # Chưa đến lúc quét nên không cho phép quét.

        _lan_quet_cuoi = bay_gio
        # Cập nhật mốc quét gần nhất thành thời điểm hiện tại.
        # Ghi mốc trước khi thực sự quét để tránh nhiều Request
        # cùng được phép quét hoặc liên tục thử lại khi có lỗi.

        return True
        # Cho phép thực hiện xử lý quá hạn.


# ============================================================
# PHẦN 4: MIDDLEWARE TỰ ĐỘNG XỬ LÝ QUÁ HẠN
# ============================================================

class XuLyQuaHanMiddleware:
    # Khai báo class Middleware xử lý quá hạn.

    def __init__(self, get_response):
        # Hàm khởi tạo khi Django tạo đối tượng Middleware.
        # get_response là hàm xử lý tiếp theo trong chuỗi.

        self.get_response = get_response
        # Lưu get_response vào thuộc tính của đối tượng
        # để sử dụng trong hàm __call__.

    def __call__(self, request):
        # Hàm được gọi mỗi khi Request đi qua Middleware.
        # request chứa thông tin yêu cầu của người dùng.

        if request.path.startswith(TIEN_TO_LIEN_QUAN) and _den_luc_quet():
            # request.path: Lấy đường dẫn đang được truy cập.
            #
            # startswith(): Kiểm tra đường dẫn có bắt đầu
            # bằng một trong các tiền tố liên quan hay không.
            #
            # _den_luc_quet(): Kiểm tra đã đủ thời gian
            # kể từ lần quét trước hay chưa.
            #
            # Cả hai điều kiện phải đúng mới thực hiện quét.

            try:
                # Thử thực hiện công việc xử lý quá hạn.

                xu_ly_qua_han()
                # Gọi hàm chính trong bookings/qua_han.py.
                #
                # Hàm này thực hiện 5 công việc:
                # 1. Giải phóng giữ chỗ hết hạn.
                # 2. Xử lý Booking quá hạn đặt cọc.
                # 3. Xử lý Booking quá hạn xác nhận.
                # 4. Xử lý quá hạn thanh toán 60%.
                # 5. Xóa ảnh hết hạn tải.

            except Exception:  # noqa: BLE001
                # Bắt ngoại lệ nếu quá trình xử lý quá hạn gặp lỗi.
                # noqa: BLE001 yêu cầu công cụ kiểm tra code
                # bỏ qua cảnh báo bắt ngoại lệ quá rộng.

                logger.exception(
                    'XuLyQuaHanMiddleware: lỗi khi xử lý quá hạn'
                )
                # Ghi thông báo lỗi và dấu vết lỗi vào log.
                # Không để lỗi xử lý quá hạn làm gián đoạn trang.

        return self.get_response(request)
        # Chuyển Request đến bước xử lý tiếp theo.
        # Cuối cùng nhận và trả về Response.
        # Dù có quét hay không, Request vẫn được đi tiếp.


# ============================================================
# PHẦN 5: CÁC TRANG THUỘC LUỒNG ĐẶT LỊCH
# ============================================================

# UC4.1 / UC4.2 - Luồng 6b:
# Khi khách hàng rời khỏi luồng đặt lịch,
# hệ thống giải phóng lượt giữ chỗ ngay.
#
# Middleware hoạt động ở phía server, kết hợp với
# nha_giu_cho.js sử dụng sendBeacon ở phía trình duyệt.
#
# Nếu Beacon bị mất hoặc đến trễ, Middleware vẫn có thể
# giải phóng lượt giữ chỗ khi khách mở trang khác.


TRANG_TRONG_LUONG_DAT_LICH = {
    'lich_chon_slot',       # Trang hiển thị lịch khả dụng.
    'chon_slot',            # Chức năng chọn slot.
    'man_hinh_giu_cho',     # Màn hình giữ chỗ.
    'gui_booking',         # Chức năng gửi yêu cầu Booking.
    'huy_giu_cho',          # Chức năng hủy lượt giữ chỗ.
    'trang_thai_giu_cho',   # Chức năng kiểm tra trạng thái giữ chỗ.
}
# Set chứa tên URL thuộc luồng đặt lịch.
# Nếu người dùng vẫn đang truy cập các chức năng này,
# Middleware không tự động giải phóng lượt giữ chỗ.


# ============================================================
# PHẦN 6: MIDDLEWARE NHẢ GIỮ CHỖ KHI RỜI LUỒNG ĐẶT LỊCH
# ============================================================

class NhaGiuChoKhiRoiLuongMiddleware:
    # Khai báo Middleware giải phóng lượt giữ chỗ
    # khi khách hàng chuyển sang trang ngoài luồng đặt lịch.

    def __init__(self, get_response):
        # Hàm khởi tạo Middleware.

        self.get_response = get_response
        # Lưu hàm xử lý tiếp theo trong chuỗi Middleware.

    def __call__(self, request):
        # Được gọi khi Request đi qua Middleware.

        return self.get_response(request)
        # Chuyển Request đi tiếp và trả về Response.
        # Logic giải phóng giữ chỗ nằm trong process_view().


    def process_view(self, request, view_func, view_args, view_kwargs):
        # Hàm đặc biệt của Middleware trong Django.
        # Được gọi trước khi View thực thi.
        #
        # self: Đối tượng Middleware hiện tại.
        # request: Yêu cầu của người dùng.
        # view_func: Hàm View sắp được thực thi.
        # view_args: Các tham số vị trí truyền vào View.
        # view_kwargs: Các tham số có tên truyền vào View.

        try:
            # Thử thực hiện logic giải phóng giữ chỗ.

            user = getattr(request, 'user', None)
            # Lấy thông tin người dùng từ Request.
            # Nếu Request không có thuộc tính user thì trả None.

            if user is None or not user.is_authenticated or request.method not in ('GET', 'HEAD'):
                # Bỏ qua nếu xảy ra một trong ba trường hợp:
                #
                # 1. user is None:
                #    Không có thông tin người dùng.
                #
                # 2. not user.is_authenticated:
                #    Người dùng chưa đăng nhập.
                #
                # 3. request.method not in ('GET', 'HEAD'):
                #    Request không sử dụng phương thức GET hoặc HEAD.
                #    Ví dụ: POST sẽ bị bỏ qua.

                return None
                # Không thực hiện giải phóng giữ chỗ.
                # Cho phép View tiếp tục chạy.


            # ------------------------------------------------
            # KIỂM TRA REQUEST CÓ PHẢI YÊU CẦU MỞ TRANG KHÔNG
            # ------------------------------------------------

            if 'text/html' not in request.headers.get('Accept', '') or request.headers.get('X-Requested-With'):
                # request.headers: Lấy các Header của Request.
                #
                # .get('Accept', ''):
                # Lấy loại dữ liệu mà trình duyệt muốn nhận.
                # Nếu không có Header Accept thì trả chuỗi rỗng.
                #
                # 'text/html' not in ...:
                # Kiểm tra Request không yêu cầu nội dung HTML.
                #
                # .get('X-Requested-With'):
                # Kiểm tra Header thường dùng để nhận biết
                # một số Request AJAX.
                #
                # Mục đích: Phân biệt Request mở trang
                # với các Request chạy nền như đồng hồ đếm ngược.

                return None
                # Bỏ qua Request không thỏa mãn điều kiện mở trang.
                # Không giải phóng lượt giữ chỗ.


            # ------------------------------------------------
            # KIỂM TRA KHÁCH CÓ RỜI LUỒNG ĐẶT LỊCH KHÔNG
            # ------------------------------------------------

            khop = request.resolver_match
            # Lấy thông tin URL mà Django đã xác định.
            # Bao gồm tên URL, View và các tham số liên quan.

            if khop is None or khop.url_name in TRANG_TRONG_LUONG_DAT_LICH:
                # Điều kiện 1: Không xác định được thông tin URL.
                #
                # Điều kiện 2: Tên URL vẫn thuộc luồng đặt lịch.
                #
                # Ví dụ: Khách chuyển từ trang chọn slot
                # sang trang gửi yêu cầu Booking.

                return None
                # Không giải phóng giữ chỗ vì khách
                # chưa rời khỏi luồng đặt lịch.


            # ------------------------------------------------
            # IMPORT CÁC HÀM, MODEL VÀ HẰNG SỐ CẦN THIẾT
            # ------------------------------------------------

            from bookings.giu_cho import huy_giu_cho
            # Import hàm hủy lượt giữ chỗ.

            from bookings.models import GiuCho
            # Import Model GiuCho để truy vấn database.

            from core.constants import TrangThaiGiuCho
            # Import các hằng số trạng thái giữ chỗ.


            # ------------------------------------------------
            # TÌM VÀ GIẢI PHÓNG CÁC LƯỢT ĐANG GIỮ CHỖ
            # ------------------------------------------------

            for ma in list(
                GiuCho.objects.filter(
                    MaKhachHang=user,
                    TrangThai=TrangThaiGiuCho.DANG_GIU
                ).values_list('pk', flat=True)
            ):
                # GiuCho.objects:
                # Truy cập dữ liệu của Model GiuCho.
                #
                # filter():
                # Lọc dữ liệu theo các điều kiện.
                #
                # MaKhachHang=user:
                # Chỉ lấy lượt giữ chỗ của người dùng hiện tại.
                #
                # TrangThai=TrangThaiGiuCho.DANG_GIU:
                # Chỉ lấy những lượt có trạng thái Đang giữ chỗ.
                #
                # values_list('pk', flat=True):
                # Chỉ lấy khóa chính của các lượt giữ chỗ.
                # Ví dụ: [12, 15, 18].
                #
                # list():
                # Thực hiện truy vấn và chuyển kết quả
                # thành danh sách Python.
                #
                # for ma in ...:
                # Duyệt lần lượt từng mã giữ chỗ trong danh sách.

                huy_giu_cho(user, ma)
                # Gọi hàm hủy lượt giữ chỗ tương ứng.
                #
                # user: Người dùng thực hiện hủy.
                # ma: Mã lượt giữ chỗ cần hủy.
                #
                # Chỉ nhả lượt Đang giữ chỗ của chính khách.
                # Không tác động đến lượt đã gửi Booking.


        # ----------------------------------------------------
        # XỬ LÝ NGOẠI LỆ
        # ----------------------------------------------------

        except Exception:  # noqa: BLE001
            # Bắt ngoại lệ phát sinh trong quá trình
            # kiểm tra và giải phóng lượt giữ chỗ.

            logger.exception(
                'NhaGiuChoKhiRoiLuongMiddleware: lỗi khi nhả giữ chỗ'
            )
            # Ghi thông báo lỗi và dấu vết lỗi vào log.
            # Tránh để lỗi nhả giữ chỗ làm gián đoạn trang.

        return None
        # Trong process_view(), return None nghĩa là
        # Middleware không chặn Request.
        # Django tiếp tục thực thi View bình thường.

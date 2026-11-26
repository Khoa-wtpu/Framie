
# =====================================================================
# bookings/nen_qua_han.py - Luồng nền tự động xử lý các lượt đặt chỗ quá hạn.
# Luồng này hoạt động độc lập, không cần người dùng mở website và không cần chạy lệnh thủ công.
#
# Vấn đề cũ: Slot "Đang giữ chỗ" chỉ được giải phóng khi có người truy cập trang liên quan
# (thông qua bookings/middleware.py) hoặc khi chạy thủ công lệnh xu_ly_qua_han.
# Nếu không có ai truy cập website, slot có thể bị giữ quá thời gian quy định 5 phút.
#
# Cách sửa: Khi web server khởi động (config/wsgi.py hoặc config/asgi.py gọi bat_dau()),
# chương trình tạo một luồng nền (daemon thread).
# Luồng này gọi hàm bookings.qua_han.xu_ly_qua_han() định kỳ theo số giây được cấu hình.
# Mặc định là 60 giây, giúp slot được giải phóng chậm nhất khoảng 1 phút sau khi hết hạn.
# BR4.1-1 (UC4.1): Xử lý định kỳ 60 giây một lần + mỗi khi có truy cập liên quan.
# Keyword tra cứu: chu kỳ 60 giây | giải phóng slot quá hạn định kỳ | NEN_MAC_DINH_GIAY = 60
#
# Middleware và lệnh xu_ly_qua_han vẫn được giữ nguyên.
# Các cơ chế này có thể chạy song song vì đều kiểm tra lại trạng thái trước khi cập nhật.
#
# Lưu ý khi triển khai:
# - Mỗi tiến trình web sẽ có một luồng nền riêng.
#   Nếu chạy nhiều worker (gunicorn -w 4), có thể xuất hiện nhiều luồng cùng xử lý.
#   Điều này vẫn đảm bảo tính đúng đắn nhưng có thể lặp lại công việc.
#   Khi đó có thể đặt XU_LY_QUA_HAN_NEN_GIAY = 0 ở worker thừa
#   hoặc dùng lệnh xu_ly_qua_han --lap 60 riêng.
# - Khi web server tắt, luồng nền cũng dừng theo.
#   Nếu muốn xử lý ngay cả khi web server đã tắt, cần sử dụng Task Scheduler hoặc cron.
# - XU_LY_QUA_HAN_NEN_GIAY = 0 sẽ tắt luồng nền.
#   Mặc định luồng cũng không chạy khi thực hiện lệnh manage.py test.
# =====================================================================

import logging       # Thư viện ghi lại thông tin hoạt động và lỗi của chương trình.
import threading     # Thư viện hỗ trợ tạo và quản lý các luồng chạy song song.

from django.conf import settings  # Truy cập các cấu hình được khai báo trong settings.py.
from django.db import connection  # Quản lý kết nối database của Django.

logger = logging.getLogger(__name__)  # Tạo logger để ghi log với tên module hiện tại.


NEN_MAC_DINH_GIAY = 60  # Thời gian mặc định giữa hai lần xử lý quá hạn, tính bằng giây.
                        # Nếu không khai báo cấu hình trong settings.py thì sử dụng 60 giây.


_khoa = threading.Lock()  # Tạo khóa đồng bộ để tránh nhiều nơi khởi động luồng cùng lúc.
                          # Ví dụ: cả WSGI và ASGI cùng gọi bat_dau().

_luong = None  # Biến lưu đối tượng luồng nền đang chạy.
               # Giá trị None nghĩa là chưa có luồng nền nào được khởi tạo.

_dung = threading.Event()  # Tạo sự kiện dùng để thông báo cho luồng nền dừng hoạt động.
                           # Khi sự kiện được bật (set), vòng lặp sẽ dừng.


def _chay_mot_vong():
    """Thực hiện một lần kiểm tra và xử lý các lượt đặt chỗ quá hạn."""

    # Import hàm xử lý quá hạn tại thời điểm cần sử dụng.
    # Import muộn giúp tránh nạp model quá sớm trong quá trình khởi động Django.
    from bookings.qua_han import xu_ly_qua_han

    try:
        xu_ly_qua_han()  # Gọi hàm xử lý quá hạn để kiểm tra và giải phóng các slot hết hạn.

    except Exception:  # Bắt mọi ngoại lệ phát sinh trong quá trình xử lý.
        logger.exception('nen_qua_han: lỗi khi xử lý quá hạn')
        # Ghi lại thông tin lỗi và vị trí xảy ra lỗi vào log.
        # Không để lỗi làm dừng hoạt động của luồng nền.

    finally:
        connection.close()  # Đóng kết nối database sau mỗi lần xử lý.
                             # Luồng nền có kết nối riêng nên cần đóng để tránh giữ kết nối
                             # hoặc khóa SQLite không cần thiết.


def _vong_lap(khoang_cach):
    # Vòng lặp chạy liên tục trong suốt thời gian luồng nền hoạt động.
    while not _dung.wait(khoang_cach):
        # Chờ trong khoảng thời gian khoang_cach (ví dụ 60 giây).
        # Nếu sự kiện _dung được bật trong thời gian chờ, wait() trả về True
        # và vòng lặp kết thúc.
        # Nếu hết thời gian chờ mà chưa có yêu cầu dừng, wait() trả về False.

        _chay_mot_vong()  # Thực hiện một lần xử lý các lượt đặt chỗ quá hạn.


def bat_dau():
    """Khởi động luồng nền nếu chưa chạy và cấu hình cho phép."""

    global _luong  # Cho phép hàm truy cập và thay đổi biến _luong ở phạm vi toàn module.

    # Lấy khoảng thời gian xử lý từ settings.py.
    # Nếu không tìm thấy cấu hình XU_LY_QUA_HAN_NEN_GIAY,
    # sử dụng giá trị mặc định NEN_MAC_DINH_GIAY = 60.
    khoang_cach = getattr(settings, 'XU_LY_QUA_HAN_NEN_GIAY', NEN_MAC_DINH_GIAY)

    # Kiểm tra cấu hình có cho phép chạy luồng nền hay không.
    # Nếu giá trị bằng 0, None hoặc nhỏ hơn 0 thì không khởi động.
    if not khoang_cach or khoang_cach <= 0:
        return False  # Trả về False để thông báo luồng nền không được khởi động.

    # Sử dụng khóa để đảm bảo chỉ một luồng được khởi động tại một thời điểm.
    with _khoa:

        # Kiểm tra xem đã có luồng nền nào đang hoạt động hay chưa.
        if _luong is not None and _luong.is_alive():
            return True  # Nếu luồng đã chạy thì không tạo thêm luồng mới.

        _dung.clear()  # Xóa trạng thái dừng để cho phép luồng nền hoạt động trở lại.

        # Tạo một luồng nền mới.
        _luong = threading.Thread(
            target=_vong_lap,  # Hàm sẽ được thực thi khi luồng bắt đầu chạy.
            args=(khoang_cach,),  # Truyền khoảng thời gian chờ vào hàm _vong_lap.
            name='framie-xu-ly-qua-han',  # Đặt tên để dễ nhận diện luồng khi kiểm tra.
            daemon=True  # Đánh dấu là luồng daemon: tự kết thúc khi chương trình chính tắt.
        )

        _luong.start()  # Khởi chạy luồng nền, bắt đầu thực hiện hàm _vong_lap.

        # Ghi log thông báo luồng nền đã được khởi động thành công.
        logger.info('nen_qua_han: bật xử lý quá hạn nền mỗi %s giây', khoang_cach)

        return True  # Trả về True để thông báo luồng nền đang hoạt động.


def dung():
    """Dừng luồng nền khi cần thiết, ví dụ trong quá trình kiểm thử."""

    global _luong  # Cho phép hàm thay đổi biến _luong ở phạm vi toàn module.

    # Sử dụng khóa để tránh xung đột khi có thao tác khởi động hoặc dừng luồng.
    with _khoa:

        _dung.set()  # Bật sự kiện dừng để thông báo cho vòng lặp kết thúc.

        # Lưu lại luồng hiện tại vào biến luong và đặt _luong về None.
        # Điều này cho phép chương trình có thể khởi động lại luồng sau đó.
        luong, _luong = _luong, None

    # Kiểm tra xem có luồng nào cần dừng hay không.
    if luong is not None:

        # Chờ luồng kết thúc tối đa 5 giây.
        # Nếu luồng kết thúc sớm, chương trình tiếp tục ngay.
        # Nếu quá 5 giây, chương trình không chờ thêm.
        luong.join(timeout=5)

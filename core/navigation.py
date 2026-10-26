"""Cấu hình menu theo vai trò. Muốn đổi menu chỉ sửa file này."""
from django.urls import NoReverseMatch, reverse

from .constants import VaiTro

GUEST = "Khách"
CUSTOMER = VaiTro.KHACH_HANG
PHOTOGRAPHER = VaiTro.NHIEP_ANH_GIA
ADMIN = VaiTro.QUAN_TRI_VIEN

# Chỉ dùng khi DEBUG: ?xem_voi_vai_tro=<khóa> để xem thử menu mà không cần đăng nhập
PREVIEW_KEYS = {"khach": GUEST, "khach_hang": CUSTOMER, "nhiep_anh_gia": PHOTOGRAPHER, "quan_tri_vien": ADMIN}

# Tên URL dùng ở khung chung -> đổi tên ở đây nếu urls.py của nhóm đặt khác.
# Tên nào chưa có trong urls.py thì link tạm thành "#" (không gây lỗi).
URL_NAMES = {
    "home": "home",
    "login": "login",
    "register": "register",
    "notifications": "notifications",
    "logout_confirm": "logout_confirm",  # SC7.5 Xác nhận đăng xuất
}

# (nhãn, tên URL)
MENUS = {
    GUEST: [("Trang chủ", "home"), ("Tìm nhiếp ảnh gia", "search"), ("Giới thiệu", "about")],
    CUSTOMER: [("Tìm kiếm", "search"), ("Booking của tôi", "my_bookings"), ("Tin nhắn", "inbox")],
    PHOTOGRAPHER: [
        ("Hồ sơ của tôi", "photographer_profile"),
        ("Portfolio", "portfolio"),
        ("Gói dịch vụ", "service_packages"),
        ("Lịch của tôi", "my_calendar"),
        ("Quản lý Booking", "manage_bookings"),
        ("Booking của tôi", "my_bookings"),
        ("Tin nhắn", "inbox"),
    ],
    # Menu Quản trị viên: chỉnh lại cho đúng danh sách màn hình admin của nhóm
    ADMIN: [
        ("Tài khoản & vai trò", "admin_accounts"),
        ("Duyệt hồ sơ", "admin_profile_review"),
        ("Booking", "admin_bookings"),
        ("Thanh toán", "admin_payments"),
    ],
}

# Menu thả xuống của "Tài khoản" (chuông thông báo nằm riêng trên header)
_ACCOUNT = [("Hồ sơ cá nhân", "account_profile"), ("Đổi mật khẩu", "change_password")]
ACCOUNT_MENUS = {CUSTOMER: _ACCOUNT, PHOTOGRAPHER: _ACCOUNT, ADMIN: _ACCOUNT}


def resolve(url_name):
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def is_active(path, url):
    if url == "#":
        return False
    return path == url if url == "/" else path.startswith(url)


def get_role(user):
    """Vai trò = tên Group của Django (VaiTro trong core/constants.py); superuser luôn là Quản trị viên."""
    if not user.is_authenticated:
        return GUEST
    if user.is_superuser:
        return ADMIN
    groups = set(user.groups.values_list("name", flat=True))
    for role in (ADMIN, PHOTOGRAPHER, CUSTOMER):
        if role in groups:
            return role
    return CUSTOMER


def count_unread(user):
    """Số thông báo chưa đọc của người dùng (hiện trên chuông ở header)."""
    from notifications.services import dem_chua_doc  # import trong hàm để tránh import vòng giữa core và notifications
    return dem_chua_doc(user)

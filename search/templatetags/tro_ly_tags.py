# =====================================================================
# search/templatetags/tro_ly_tags.py  -  E5: bộ lọc cho nút "Trợ lý chọn Nhiếp ảnh gia" ở trang Tìm kiếm (Phanh)
# Dùng trong template:  {% load tro_ly_tags %}  rồi  {% if user|la_khach_hang %} ... {% endif %}
# =====================================================================
from django import template  # công cụ đăng ký bộ lọc cho template

from core.constants import VaiTro  # tên vai trò (không tự gõ chữ "Khách hàng")

register = template.Library()  # nơi đăng ký bộ lọc; tên biến này bắt buộc phải là register


@register.filter  # đăng ký hàm bên dưới thành bộ lọc dùng trong template
def la_khach_hang(user):  # True nếu là Khách hàng đã đăng nhập
    if not getattr(user, 'is_authenticated', False):  # chưa đăng nhập (hoặc không phải user)
        return False  # không hiện nút
    return user.groups.filter(name=VaiTro.KHACH_HANG).exists()  # cùng quy tắc với khach_hang_required: phải thuộc nhóm Khách hàng, tránh hiện nút rồi bị 403

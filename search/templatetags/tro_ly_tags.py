# =====================================================================
# search/templatetags/tro_ly_tags.py  -  E5: bộ lọc cho nút "Trợ lý chọn Nhiếp ảnh gia" ở trang Tìm kiếm (Phanh)
# Dùng trong template:  {% load tro_ly_tags %}  rồi  {% if user|la_khach_hang %} ... {% endif %}
# =====================================================================
from django import template  # công cụ đăng ký bộ lọc cho template

from core.constants import VaiTro  # tên vai trò (không tự gõ chữ "Khách hàng")

register = template.Library()  # nơi đăng ký bộ lọc; tên biến này bắt buộc phải là register


@register.filter  # decorator đăng ký hàm bên dưới thành bộ lọc dùng trong template
def la_khach_hang(user):  # True nếu là Khách hàng đã đăng nhập
    if not getattr(user, 'is_authenticated', False):  # is Kiểm tra đăng nhập; kh,mặc định False
        return False  # không hiện nút
    return user.groups.filter(name=VaiTro.KHACH_HANG).exists()  # cùng quy tắc với khach_hang_required: phải thuộc nhóm Khách hàng, tránh hiện nút rồi bị 403
#exami? thuộc nhóm KHACH_HANG, lọc các nhóm theo tên vai trò; exist true false


@register.filter  # đăng ký bộ lọc thứ hai
def hien_tro_ly(user):  # True nếu nên hiện khối "Chưa biết chọn ai?": khách chưa đăng nhập HOẶC Khách hàng
    if not getattr(user, 'is_authenticated', False):  # chưa đăng nhập đk đúng: vẫn hiện (nút sẽ dẫn sang trang đăng nhập)
        return True  # hiện khối
    return la_khach_hang(user)  # đã đăng nhập, call lại: chỉ Khách hàng thấy; Nhiếp ảnh gia và Quản trị viên thì không

#la_khach_hang: kiểm tra vai trò; hien_tro_ly: sd kq quyết định hiển thị.
#h3, acc, views.py, 2 giai đoạn
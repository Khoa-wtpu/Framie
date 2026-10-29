# =====================================================================
# accounts/templatetags/quan_tri.py  -  B7: thẻ {% admin_menu %} vẽ menu bên trái
# Nhờ thẻ này, view của module khác KHÔNG phải tự gửi menu vào template.
# =====================================================================
from django import template  # thư viện thẻ template của Django

from accounts.quan_tri import tao_menu  # hàm tạo danh sách mục menu

register = template.Library()  # nơi đăng ký thẻ


@register.inclusion_tag('accounts/quan_tri/_menu.html', takes_context=True)  # thẻ vẽ file _menu.html, được đọc request
def admin_menu(context):  # dùng trong template: {% admin_menu %}
    duong_dan = context['request'].path  # đường dẫn trang đang mở, ví dụ /quan-tri/booking/
    return {'muc_menu': tao_menu(duong_dan)}  # gửi danh sách mục sang _menu.html

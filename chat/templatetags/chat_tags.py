# chat/templatetags/chat_tags.py - P10: thẻ {% nut_nhan_tin %} để Khoa gắn vào trang hồ sơ Nhiếp ảnh gia.
from django import template  # thư viện thẻ template
from django.contrib.auth.views import redirect_to_login  # tạo đường dẫn đăng nhập kèm ?next=

from chat.services import la_khach_hang  # kiểm tra vai trò Khách hàng

register = template.Library()  # nơi đăng ký thẻ


@register.inclusion_tag('chat/nut_nhan_tin.html', takes_context=True)  # thẻ dựng từ template nut_nhan_tin.html
def nut_nhan_tin(context, ma_nhiep_anh_gia):  # cách dùng: {% nut_nhan_tin nag.pk %}
    request = context['request']  # lấy request hiện tại
    kieu = ''  # mặc định không hiện gì (Nhiếp ảnh gia và Quản trị viên không thấy nút)
    url_dang_nhap = ''  # đường dẫn đăng nhập (chỉ dùng cho người chưa đăng nhập)
    if not request.user.is_authenticated:  # khách vãng lai
        kieu = 'dang_nhap'  # hiện nút dẫn sang đăng nhập
        url_dang_nhap = redirect_to_login(request.get_full_path()).url  # đăng nhập xong quay lại đúng trang này
    elif la_khach_hang(request.user):  # Khách hàng đã đăng nhập
        kieu = 'form'  # hiện nút gửi POST
    return {'kieu': kieu, 'ma_nhiep_anh_gia': ma_nhiep_anh_gia, 'url_dang_nhap': url_dang_nhap}  # dữ liệu cho template
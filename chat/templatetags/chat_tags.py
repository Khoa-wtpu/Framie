# chat/templatetags/chat_tags.py - P10: thẻ {% nut_nhan_tin %} để Khoa gắn vào trang hồ sơ Nhiếp ảnh gia.
import datetime  # so sánh ngày

from django import template  # thư viện thẻ template
from django.utils import timezone  # đổi giờ UTC sang giờ địa phương (Asia/Ho_Chi_Minh)
from django.contrib.auth.views import redirect_to_login  # tạo đường dẫn đăng nhập kèm ?next=

from chat.services import anh_het_han as _anh_het_han, la_khach_hang  # kiểm tra vai trò Khách hàng; kiểm ảnh đã quá 6 tháng chưa

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


THU = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật']  # tên thứ, weekday() 0 = thứ Hai


@register.filter  # cách dùng: {{ c.luc|gio_ds }} - giờ hiện ở danh sách bên trái (đúng wireframe: 12:30 / Hôm qua / Thứ Hai)
def gio_ds(gia_tri):
    if not gia_tri:  # không có giờ
        return ''
    luc = timezone.localtime(gia_tri) if timezone.is_aware(gia_tri) else gia_tri  # về giờ địa phương
    hom_nay = timezone.localtime().date()  # ngày hôm nay
    chenh = (hom_nay - luc.date()).days  # cách hôm nay mấy ngày
    if chenh <= 0:  # hôm nay (hoặc giờ lệch nhẹ)
        return luc.strftime('%H:%M')  # chỉ giờ
    if chenh == 1:  # hôm qua
        return 'Hôm qua'
    if chenh < 7:  # trong tuần qua: hiện thứ
        return THU[luc.weekday()]
    return luc.strftime('%d/%m/%Y')  # xa hơn: ngày đầy đủ


@register.filter  # cách dùng: {% if tin|anh_het_han %} - ảnh của tin đã quá 6 tháng lưu trữ
def anh_het_han(tin):
    return _anh_het_han(tin)  # True nếu tin gửi cách đây hơn 6 tháng

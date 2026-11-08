# core/templatetags/buoc_ke.py - đọc nút "sang bước kế" gắn trong message (xem core/buoc_ke.py)
from django import template

from core.buoc_ke import NGAN_CACH, TIEN_TO, url_booking

register = template.Library()


@register.filter
def nut_buoc_ke(message):
    """{% with nut=message|nut_buoc_ke %} -> {'nhan': ..., 'url': ...} hoặc None nếu message không có nút."""
    extra = getattr(message, 'extra_tags', '') or ''
    if not extra.startswith(TIEN_TO + NGAN_CACH):
        return None
    phan = extra.split(NGAN_CACH, 2)
    if len(phan) != 3:
        return None
    _, nhan, url = phan
    if not url.startswith('/') or url.startswith('//'):    # chỉ nhận đường dẫn nội bộ của web
        return None
    return {'nhan': nhan, 'url': url}


@register.simple_tag(name='url_quay_lai_booking')
def url_quay_lai_booking(booking, la_nag=False):
    """{% url_quay_lai_booking booking la_nag %} -> địa chỉ trang Booking theo vai trò (xem core/buoc_ke.url_booking)."""
    return url_booking(booking, bool(la_nag))

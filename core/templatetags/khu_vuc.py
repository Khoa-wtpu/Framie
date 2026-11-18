# core/templatetags/khu_vuc.py   (task F3)
from django import template

from core.du_lieu_khu_vuc import nhom_theo_mien as _nhom

register = template.Library()


@register.filter
def nhom_theo_mien(field):
    """{% for mien, ds in form.khu_vuc|nhom_theo_mien %} - chia các lựa chọn của một ô chọn Khu vực
    (hộp tích hoặc nút radio) thành nhóm Miền Bắc / Miền Trung / Miền Nam. Mỗi phần tử của ds
    dùng như khi lặp trực tiếp qua field: {{ c.tag }}, {{ c.choice_label }}."""
    return _nhom(list(field), lay_ten=lambda c: str(c.choice_label))

# reviews/templatetags/danh_gia.py - N11: hiện số sao dạng ★★★★☆
from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def sao(diem):
    """{% sao danh_gia.Diem %} hoặc {% sao thong_ke.diem_tb %} (số thập phân thì làm tròn gần nhất để tô sao)."""
    try:
        day = max(0, min(5, int(float(diem) + 0.5)))   # 4.5 -> 5 (làm tròn lên, không dùng round() vì round(4.5) = 4)
    except (TypeError, ValueError):
        day = 0
    return format_html('<span class="sao" role="img" aria-label="{} trên 5 sao">'
                       '<span class="sao__day">{}</span><span class="sao__trong">{}</span></span>',
                       diem, '★' * day, '★' * (5 - day))

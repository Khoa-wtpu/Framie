from django import template
from django.utils.html import format_html

from core.status_tones import tone_of

register = template.Library()


@register.simple_tag
def status_badge(value, label=None):
    """{% status_badge booking.trang_thai %} - value là chữ trạng thái lưu trong DB (core/constants.py)."""
    return format_html('<span class="badge badge--{}">{}</span>', tone_of(value), label or value or "")


@register.filter
def add_class(field, css):
    """{{ form.email|add_class:"input" }} - thêm class và aria-invalid cho widget."""
    attrs = {"class": f'{field.field.widget.attrs.get("class", "")} {css}'.strip()}
    if field.errors:
        attrs["aria-invalid"] = "true"
    return field.as_widget(attrs=attrs)


@register.simple_tag
def page_range(page_obj, on_each_side=1, on_ends=1):
    paginator = page_obj.paginator
    return [
        {"number": p, "ellipsis": p == paginator.ELLIPSIS}
        for p in paginator.get_elided_page_range(page_obj.number, on_each_side=on_each_side, on_ends=on_ends)
    ]


@register.simple_tag(takes_context=True)
def page_url(context, number):
    """Giữ nguyên các tham số lọc/tìm kiếm trên URL, chỉ đổi ?page="""
    query = context["request"].GET.copy()
    query["page"] = number
    return "?" + query.urlencode()


@register.filter
def vnd(value):
    """{{ so_tien|vnd }} - 600000 -> 600.000, 1200000 -> 1.200.000 (bỏ số lẻ, dấu chấm ngăn mỗi 3 số)."""
    try:
        so = int(round(float(value)))
    except (TypeError, ValueError):
        return value if value is not None else ""
    return f"{so:,}".replace(",", ".")

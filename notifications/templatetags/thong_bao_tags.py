# notifications/templatetags/thong_bao_tags.py - P8: bộ lọc nhỏ cho template thông báo
from datetime import datetime  # lấy giờ hiện tại khi dữ liệu không có múi giờ

from django import template  # công cụ tạo bộ lọc template
from django.utils import timezone  # đổi giờ về múi giờ địa phương

from core.constants import DanhDauSao, TrangThaiDoc  # hằng số trạng thái (template không tự gõ chữ tiếng Việt)

register = template.Library()  # nơi đăng ký các bộ lọc

TEN_THU = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật']  # weekday(): 0 là Thứ Hai


@register.filter  # dùng: {% if tb|chua_doc %}
def chua_doc(thong_bao):  # True nếu thông báo đang Chưa đọc
    return thong_bao.TrangThaiDoc == TrangThaiDoc.CHUA_DOC  # so sánh với hằng số chung


@register.filter  # dùng: {% if tb|co_sao %}
def co_sao(thong_bao):  # True nếu thông báo đã đánh dấu sao
    return thong_bao.DanhDauSao == DanhDauSao.DA_DANH_DAU  # so sánh với hằng số chung


def _ve_gio_dia_phuong(gia_tri):  # trả về (giờ của thông báo, giờ hiện tại) cùng một kiểu múi giờ
    if timezone.is_naive(gia_tri):  # dữ liệu không có múi giờ (USE_TZ = False)
        return gia_tri, datetime.now()  # so sánh trực tiếp với giờ máy
    return timezone.localtime(gia_tri), timezone.localtime()  # đổi cả hai về múi giờ của project


@register.filter  # dùng: {{ tb.NgayTao|thoi_gian_ngan }}
def thoi_gian_ngan(gia_tri):  # giờ ngắn trên danh sách: 10:30, Hôm qua, Thứ Hai, 04/10/2026
    if not gia_tri:  # không có giá trị
        return ''  # hiện rỗng
    luc, bay_gio = _ve_gio_dia_phuong(gia_tri)  # đưa về cùng múi giờ
    so_ngay = (bay_gio.date() - luc.date()).days  # cách hôm nay bao nhiêu ngày
    if so_ngay <= 0:  # hôm nay
        return luc.strftime('%H:%M')  # chỉ hiện giờ phút
    if so_ngay == 1:  # hôm qua
        return 'Hôm qua'  # đúng wireframe
    if so_ngay < 7:  # trong vòng một tuần
        return TEN_THU[luc.weekday()]  # tên thứ, ví dụ "Thứ Hai"
    return luc.strftime('%d/%m/%Y')  # xa hơn thì hiện ngày đầy đủ


@register.filter  # dùng: {{ tb.NgayTao|thoi_gian_day_du }}
def thoi_gian_day_du(gia_tri):  # giờ đầy đủ trên trang chi tiết: 10:30, 04/10/2026
    if not gia_tri:  # không có giá trị
        return ''  # hiện rỗng
    luc, _ = _ve_gio_dia_phuong(gia_tri)  # chỉ cần giờ của thông báo
    return luc.strftime('%H:%M, %d/%m/%Y')  # đúng định dạng wireframe

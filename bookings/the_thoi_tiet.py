# =====================================================================
# bookings/the_thoi_tiet.py  -  E8
#   Thẻ "Dự báo thời tiết buổi chụp" ở trang chi tiết Booking (bookings/theo_doi.py -> theo_doi_chi_tiet.html)
#
# Yêu cầu (task E8):
#   - Hiện cho Khách hàng và Nhiếp ảnh gia (Quản trị viên không thấy), CHỈ khi Booking còn hiệu lực
#     (không phải Đã từ chối / Hết thời hạn đặt cọc / Đã hủy) VÀ buổi chụp chưa diễn ra.
#   - Có dự báo: hiện nhiệt độ, khả năng mưa, mô tả. Không có dự báo (E7 trả {}): ghi "Chưa có dự báo".
#   - Khả năng mưa cao (>= NGUONG_MUA_CAO %): nhắc hai bên trao đổi đổi lịch, kèm nút sang trò chuyện.
#   - Khu vực tra dự báo = khu vực Khách đã chọn khi đặt (phần đầu của DiaDiem); không khớp thì dùng khu vực của Nhiếp ảnh gia.
#   - Dự báo lấy từ bookings.thoi_tiet.lay_du_bao_thoi_tiet (E7, của Nguyên); file này KHÔNG tự gọi mạng.
# =====================================================================
from django.contrib import messages  # hộp thông báo ngắn trên đầu trang
from django.core.exceptions import ValidationError  # lỗi dữ liệu không hợp lệ khi tạo cuộc trò chuyện
from django.db import DatabaseError  # lỗi cơ sở dữ liệu bất ngờ
from django.shortcuts import redirect  # chuyển trang
from django.urls import NoReverseMatch, reverse  # reverse: từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # giờ hiện tại có múi giờ
from django.views.decorators.http import require_POST  # chỉ nhận POST (tránh trình duyệt tải trước làm tạo cuộc trò chuyện)

from accounts.permissions import vai_tro_required  # nhãn chặn sai vai trò
from core.constants import VaiTro  # tên vai trò dùng chung
from profiles.models import KhuVuc  # bảng khu vực

from bookings.models import TRANG_THAI_HET_HIEU_LUC  # 3 trạng thái hết hiệu lực của Booking
from bookings.thoi_tiet import lay_du_bao_thoi_tiet  # E7: trả {'nhiet_do', 'xac_suat_mua', 'mo_ta'} hoặc {}

NGUONG_MUA_CAO = 60  # khả năng mưa từ mức này (%) trở lên thì nhắc trao đổi đổi lịch
TB_CHUA_CO_DU_BAO = 'Chưa có dự báo'  # câu hiện khi E7 không trả được dự báo
TB_NHAC_DOI_LICH = ('Khả năng mưa cao vào giờ chụp. Khách hàng và Nhiếp ảnh gia nên trao đổi '
                    'để cân nhắc đổi lịch chụp.')  # câu nhắc hai bên khi mưa cao


def _khu_vuc_can_tra(booking):  # danh sách khu vực dùng để tra dự báo, theo thứ tự ưu tiên
    """Form gửi Booking (gui_booking.py) lưu DiaDiem = "<Khu vực>" hoặc "<Khu vực> - <Địa chỉ cụ thể>", nên khu vực Khách
    ĐÃ CHỌN là phần đầu của DiaDiem: khớp tên KhuVuc (chọn tên dài nhất nếu nhiều tên cùng khớp).
    Không khớp (Booking cũ / DiaDiem gõ tay) thì dùng các khu vực Nhiếp ảnh gia đã khai."""
    dia_diem = (booking.DiaDiem or '').strip()  # chữ địa điểm Khách đã lưu
    khop = [k for k in KhuVuc.objects.all()  # mọi khu vực của hệ thống (vài dòng)
            if dia_diem == k.TenKhuVuc or dia_diem.startswith(k.TenKhuVuc + ' - ')]
    if khop:  # tìm được khu vực Khách đã chọn
        return [max(khop, key=lambda k: len(k.TenKhuVuc))]
    return list(booking.MaNhiepAnhGia.khu_vuc.all())  # dự phòng: khu vực Nhiếp ảnh gia nhận chụp


def _lay_du_bao_theo_khu_vuc(booking):  # lấy dự báo đầu tiên có theo thứ tự ưu tiên của _khu_vuc_can_tra
    for khu_vuc in _khu_vuc_can_tra(booking):
        du_bao = lay_du_bao_thoi_tiet(khu_vuc, booking.NgayGioChup)  # E7: không bao giờ ném lỗi
        if du_bao:  # có dự báo
            return du_bao
    return {}  # không khu vực nào có dự báo


def _nut_tro_chuyen(booking, la_khach, la_nag):  # địa chỉ nút "Trao đổi qua trò chuyện" (nút luôn là form POST) hoặc None
    """Khách: dùng thẳng UC8.1 của app chat (mở cuộc cũ hoặc tạo mới).
    Nhiếp ảnh gia: app chat không cho Nhiếp ảnh gia khởi tạo, nên dùng view mo_tro_chuyen bên dưới (cùng cặp Khách - Nhiếp ảnh gia
    của Booking, chat.services.mo_hoac_tao_cuoc_tro_chuyen vẫn đảm bảo mỗi cặp chỉ có MỘT cuộc)."""
    try:  # tên url do app chat / bookings khai báo
        if la_khach:  # Khách hàng
            return reverse('khoi_tao_cuoc_tro_chuyen', kwargs={'ma_nhiep_anh_gia': booking.MaNhiepAnhGia_id})
        if la_nag:  # Nhiếp ảnh gia
            return reverse('mo_tro_chuyen_booking', kwargs={'ma_booking': booking.pk})
    except NoReverseMatch:  # url chưa được nối -> ẩn nút, không làm hỏng trang
        pass
    return None


def lay_the_thoi_tiet(booking, la_khach, la_nag):  # dữ liệu cho thẻ; None = không hiện thẻ
    """Trả dict {du_bao, mua_cao, url_chat, TB_...} hoặc None khi không được hiện thẻ."""
    if not (la_khach or la_nag):  # Quản trị viên và vai trò khác không thấy thẻ
        return None
    if booking.TrangThai in TRANG_THAI_HET_HIEU_LUC:  # Booking đã hết hiệu lực
        return None
    if booking.NgayGioChup <= timezone.now():  # buổi chụp đã diễn ra (hoặc đang diễn ra)
        return None
    du_bao = _lay_du_bao_theo_khu_vuc(booking)  # {} nếu không có dự báo
    mua_cao = bool(du_bao) and du_bao['xac_suat_mua'] >= NGUONG_MUA_CAO  # chỉ nhắc khi có dự báo và mưa cao
    url_chat = _nut_tro_chuyen(booking, la_khach, la_nag) if mua_cao else None  # nút chỉ cần khi nhắc
    return {'du_bao': du_bao, 'mua_cao': mua_cao, 'url_chat': url_chat,
            'TB_CHUA_CO_DU_BAO': TB_CHUA_CO_DU_BAO, 'TB_NHAC_DOI_LICH': TB_NHAC_DOI_LICH}


@vai_tro_required(VaiTro.NHIEP_ANH_GIA)  # chỉ Nhiếp ảnh gia (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
@require_POST  # chỉ POST
def mo_tro_chuyen(request, ma_booking):  # nút "Trao đổi qua trò chuyện" của Nhiếp ảnh gia: mở / tạo cuộc với Khách của Booking
    """Nhiếp ảnh gia chỉ mở được cuộc với Khách của chính Booking gửi đến mình (Booking người khác -> 404)."""
    from bookings.theo_doi import lay_chi_tiet_booking  # import trong hàm để tránh vòng import (theo_doi nạp file này)
    from chat import services as chat_services  # logic chat của nhóm
    booking = lay_chi_tiet_booking(request.user, VaiTro.NHIEP_ANH_GIA, ma_booking)  # phạm vi BR4.7-1
    try:
        cuoc, _ = chat_services.mo_hoac_tao_cuoc_tro_chuyen(booking.MaKhachHang, booking.MaNhiepAnhGia)  # mở cuộc cũ hoặc tạo mới
    except (ValidationError, DatabaseError):  # lỗi bất ngờ: ở lại trang Booking và báo
        messages.error(request, 'Không mở được cuộc trò chuyện, vui lòng thử lại.')
        return redirect('chi_tiet_booking', ma_booking=booking.pk)
    return redirect(chat_services.duong_dan_cuoc_tro_chuyen(cuoc.pk) or reverse('inbox'))  # vào thẳng cuộc trò chuyện

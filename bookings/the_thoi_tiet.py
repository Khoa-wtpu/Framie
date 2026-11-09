# =====================================================================
# bookings/the_thoi_tiet.py  -  E8
#   Thẻ "Dự báo thời tiết buổi chụp" ở trang chi tiết Booking (bookings/theo_doi.py -> theo_doi_chi_tiet.html)
#
# Yêu cầu (task E8):
#   - Hiện cho Khách hàng và Nhiếp ảnh gia (Quản trị viên không thấy), CHỈ khi Booking còn hiệu lực
#     (không phải Đã từ chối / Hết thời hạn đặt cọc / Đã hủy) VÀ buổi chụp chưa diễn ra.
#   - Có dự báo: hiện nhiệt độ, khả năng mưa, mô tả. Không có dự báo (E7 trả {}): ghi "Chưa có dự báo".
#   - Khả năng mưa cao (>= NGUONG_MUA_CAO %): nhắc hai bên trao đổi đổi lịch, kèm nút sang trò chuyện.
#   - Dự báo lấy từ bookings.thoi_tiet.lay_du_bao_thoi_tiet (E7, của Nguyên); file này KHÔNG tự gọi mạng.
# =====================================================================
from django.urls import NoReverseMatch, reverse  # reverse: từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # giờ hiện tại có múi giờ

from bookings.models import TRANG_THAI_HET_HIEU_LUC  # 3 trạng thái hết hiệu lực của Booking
from bookings.thoi_tiet import lay_du_bao_thoi_tiet  # E7: trả {'nhiet_do', 'xac_suat_mua', 'mo_ta'} hoặc {}

NGUONG_MUA_CAO = 60  # khả năng mưa từ mức này (%) trở lên thì nhắc trao đổi đổi lịch
TB_CHUA_CO_DU_BAO = 'Chưa có dự báo'  # câu hiện khi E7 không trả được dự báo
TB_NHAC_DOI_LICH = ('Khả năng mưa cao vào giờ chụp. Khách hàng và Nhiếp ảnh gia nên trao đổi '
                    'để cân nhắc đổi lịch chụp.')  # câu nhắc hai bên khi mưa cao


def _lay_du_bao_theo_khu_vuc(booking):  # thử lần lượt các khu vực của Nhiếp ảnh gia, lấy dự báo đầu tiên có
    """Booking không lưu khu vực, nên dùng các KHU VỰC Nhiếp ảnh gia đã khai (theo yêu cầu E7: tọa độ theo khu vực).
    Khu vực nào chưa có trong bảng tọa độ thì E7 trả {} và ta thử khu vực kế tiếp. Không có khu vực nào -> {}."""
    for khu_vuc in booking.MaNhiepAnhGia.khu_vuc.all():  # từng khu vực của Nhiếp ảnh gia (A-Z)
        du_bao = lay_du_bao_thoi_tiet(khu_vuc, booking.NgayGioChup)  # E7: không bao giờ ném lỗi
        if du_bao:  # có dự báo
            return du_bao
    return {}  # không khu vực nào có dự báo


def _nut_tro_chuyen(booking, la_khach, la_nag):  # nút sang trò chuyện: (kiểu, địa chỉ) hoặc (None, None)
    """Khách: nút POST tới UC8.1 (mở cuộc cũ hoặc tạo mới). Nhiếp ảnh gia không được khởi tạo cuộc trò chuyện
    nên chỉ có nút khi cuộc của hai bên đã tồn tại (link GET). Kiểu: 'post' / 'get'."""
    try:  # tên url do app chat khai báo
        if la_khach:  # Khách hàng
            return 'post', reverse('khoi_tao_cuoc_tro_chuyen', kwargs={'ma_nhiep_anh_gia': booking.MaNhiepAnhGia_id})
        if la_nag:  # Nhiếp ảnh gia
            from chat.models import CuocTroChuyen  # import trong hàm để tránh vòng import
            cuoc = CuocTroChuyen.objects.filter(MaKhachHang=booking.MaKhachHang_id,
                                                MaNhiepAnhGia=booking.MaNhiepAnhGia_id).first()
            if cuoc:  # hai bên đã có cuộc trò chuyện
                return 'get', reverse('chi_tiet_cuoc_tro_chuyen', kwargs={'ma_cuoc': cuoc.pk})
    except NoReverseMatch:  # app chat chưa được nối url -> ẩn nút, không làm hỏng trang
        pass
    return None, None


def lay_the_thoi_tiet(booking, la_khach, la_nag):  # dữ liệu cho thẻ; None = không hiện thẻ
    """Trả dict {du_bao, mua_cao, nhac_doi_lich, kieu_chat, url_chat, TB_CHUA_CO_DU_BAO} hoặc None khi không được hiện thẻ."""
    if not (la_khach or la_nag):  # Quản trị viên và vai trò khác không thấy thẻ
        return None
    if booking.TrangThai in TRANG_THAI_HET_HIEU_LUC:  # Booking đã hết hiệu lực
        return None
    if booking.NgayGioChup <= timezone.now():  # buổi chụp đã diễn ra (hoặc đang diễn ra)
        return None
    du_bao = _lay_du_bao_theo_khu_vuc(booking)  # {} nếu không có dự báo
    mua_cao = bool(du_bao) and du_bao['xac_suat_mua'] >= NGUONG_MUA_CAO  # chỉ nhắc khi có dự báo và mưa cao
    kieu_chat, url_chat = _nut_tro_chuyen(booking, la_khach, la_nag) if mua_cao else (None, None)  # nút chỉ cần khi nhắc
    return {'du_bao': du_bao, 'mua_cao': mua_cao, 'kieu_chat': kieu_chat, 'url_chat': url_chat,
            'TB_CHUA_CO_DU_BAO': TB_CHUA_CO_DU_BAO, 'TB_NHAC_DOI_LICH': TB_NHAC_DOI_LICH}

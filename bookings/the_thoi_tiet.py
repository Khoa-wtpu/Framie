# =====================================================================
# bookings/the_thoi_tiet.py  -  E8
#   Thẻ "Dự báo thời tiết buổi chụp" ở trang chi tiết Booking (bookings/theo_doi.py -> theo_doi_chi_tiet.html)
#
# Yêu cầu (task E8):
#   - Hiện cho Khách hàng và Nhiếp ảnh gia (Quản trị viên không thấy), CHỈ khi Booking còn hiệu lực
#     (không phải Đã từ chối / Hết thời hạn đặt cọc / Đã hủy) VÀ buổi chụp chưa diễn ra.
#   - Có dự báo: hiện nhiệt độ, khả năng mưa, mô tả. Không có dự báo (E7 trả {}): ghi "Chưa có dự báo".
#   - Khả năng mưa cao (>= NGUONG_MUA_CAO %): nhắc hai bên trao đổi đổi lịch, kèm nút sang trò chuyện.
#   - Khu vực tra dự báo = nơi Khách chụp: (1) khu vực Khách chọn trong form (phần đầu của DiaDiem); (2) tỉnh thành đọc được trong
#     DiaDiem gõ tay ("Hồ Gươm, Hà Nội" -> Hà Nội); (3) chỉ khi không đọc được mới dùng khu vực Nhiếp ảnh gia khai, và CHỈ khi
#     Nhiếp ảnh gia khai đúng 1 khu vực (khai nhiều khu vực thì không đoán, ghi "Chưa có dự báo" thay vì hiện nhầm thành phố).
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
from core.du_lieu_khu_vuc import TEN_34, TEN_CU_SANG_MOI  # F1: danh mục 34 tỉnh thành + tên cũ
from profiles.models import KhuVuc  # bảng khu vực

from bookings.models import TRANG_THAI_HET_HIEU_LUC  # 3 trạng thái hết hiệu lực của Booking
from bookings.thoi_tiet import lay_du_bao_thoi_tiet  # E7: trả {'nhiet_do', 'xac_suat_mua', 'mo_ta'} hoặc {}
import unicodedata  # bỏ dấu tiếng Việt để so tên địa điểm
import re  # tách chữ theo dấu câu

# BR4.7-4 (UC4.7): Ngưỡng nhắc đổi lịch là khả năng mưa từ 60%; lời nhắc chỉ mang tính gợi ý trao đổi,
# hệ thống không tự đổi hay hủy lịch.
# Keyword tra cứu: ngưỡng mưa 60% | NGUONG_MUA_CAO | khả năng mưa cao | nhắc đổi lịch
NGUONG_MUA_CAO = 60  # khả năng mưa từ mức này (%) trở lên thì nhắc trao đổi đổi lịch
TB_CHUA_CO_DU_BAO = 'Chưa có dự báo'  # câu hiện khi E7 không trả được dự báo
TB_NHAC_DOI_LICH = ('Khả năng mưa cao vào giờ chụp. Khách hàng và Nhiếp ảnh gia nên trao đổi '
                    'để cân nhắc đổi lịch chụp.')  # câu nhắc hai bên khi mưa cao


# Tên gọi quen thuộc (thành phố, địa danh, viết tắt) -> tỉnh thành hiện hành, để đọc được DiaDiem gõ tay như "Phố cổ Hội An".
BI_DANH_DIA_DANH = dict(TEN_CU_SANG_MOI)
BI_DANH_DIA_DANH.update({'Sài Gòn': 'Hồ Chí Minh', 'Saigon': 'Hồ Chí Minh', 'HCM': 'Hồ Chí Minh', 'Hội An': 'Đà Nẵng',\
                         'Vũng Tàu': 'Hồ Chí Minh', 'Hạ Long': 'Quảng Ninh', 'Sa Pa': 'Lào Cai', 'Phú Quốc': 'An Giang'})
TIEN_TO_BO = ('tinh ', 'thanh pho ', 'tp ')  # chữ đứng đầu tên tỉnh thành cần bỏ khi so sánh


def _tu(chu):  # 'TP. Hồ Chí Minh' -> 'tp ho chi minh' (bỏ dấu, chỉ giữ chữ/số, cách nhau một dấu cách)
    chu = unicodedata.normalize('NFD', str(chu).lower().replace('đ', 'd'))
    chu = ''.join(c for c in chu if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', chu).split())


def _bo_tien_to(chu):  # 'thanh pho da nang' -> 'da nang'
    for tt in TIEN_TO_BO:
        if (chu + ' ').startswith(tt):
            return chu[len(tt):].strip()
    return chu


# dạng so sánh (đã bỏ dấu, cách chữ) -> tên tỉnh thành trong danh mục 34
_TEN_THEO_DANG = {_tu(t): t for t in TEN_34}
_TEN_THEO_DANG.update({_tu(bd): tinh for bd, tinh in BI_DANH_DIA_DANH.items()})
_TEN_THEO_DANG_LIEN = {k.replace(' ', ''): v for k, v in _TEN_THEO_DANG.items()}  # viết liền không dấu: 'hanoi', 'danang'


def doc_tinh_thanh_tu_dia_diem(dia_diem):  # đọc tỉnh thành trong DiaDiem gõ tay; không đọc được -> None
    """'Hồ Gươm, Hà Nội' -> 'Hà Nội'; 'Phố đi bộ Nguyễn Huệ, TP.HCM' -> 'Hồ Chí Minh'; 'Hồ Gươm Hà Nội' -> 'Hà Nội'.
    Cách đọc (đi từ cuối địa chỉ ngược lên, vì người Việt ghi tỉnh thành ở cuối):
      1) một đoạn (ngăn bằng dấu phẩy hoặc ' - ') trùng hẳn tên tỉnh thành / tên gọi quen thuộc;
      2) đoạn cuối KẾT THÚC bằng tên có từ 2 chữ trở lên (tên 1 chữ như 'Huế' không xét kiểu này, tránh nhầm 'Nguyễn Huệ').
    Không đoán bừa: không khớp thì trả None."""
    doan = [_bo_tien_to(_tu(d)) for d in re.split(r'[,;]|\s-\s', dia_diem or '') if _tu(d)]
    for d in reversed(doan):  # 1) khớp trọn một đoạn, từ đoạn cuối trở lên
        if d in _TEN_THEO_DANG:
            return _TEN_THEO_DANG[d]
        if d.replace(' ', '') in _TEN_THEO_DANG_LIEN:  # gõ liền như 'Hanoi'
            return _TEN_THEO_DANG_LIEN[d.replace(' ', '')]
    if doan:  # 2) đoạn cuối kết thúc bằng tên tỉnh thành (tên dài nhất thắng)
        for dang in sorted(_TEN_THEO_DANG, key=len, reverse=True):
            if ' ' in dang and (' ' + doan[-1]).endswith(' ' + dang):
                return _TEN_THEO_DANG[dang]
    return None


def _khu_vuc_can_tra(booking):  # danh sách khu vực dùng để tra dự báo, theo thứ tự ưu tiên
    """1) Form gửi Booking (gui_booking.py) lưu DiaDiem = "<Khu vực>" hoặc "<Khu vực> - <Địa chỉ cụ thể>": khớp tên KhuVuc
    (chọn tên dài nhất nếu nhiều tên cùng khớp).
    2) DiaDiem gõ tay / Booking cũ ("Hồ Gươm, Hà Nội"): đọc tỉnh thành trong chữ địa điểm (doc_tinh_thanh_tu_dia_diem).
    3) Vẫn không đọc được: dùng khu vực Nhiếp ảnh gia đã khai, nhưng CHỈ khi khai đúng 1 khu vực. Khai nhiều khu vực thì không
       biết Khách chụp ở đâu, nên trả rỗng (thẻ ghi "Chưa có dự báo") thay vì hiện nhầm thời tiết thành phố khác."""
    dia_diem = (booking.DiaDiem or '').strip()  # chữ địa điểm Khách đã lưu
    khop = [k for k in KhuVuc.objects.all()  # mọi khu vực của hệ thống (vài dòng)
            if dia_diem == k.TenKhuVuc or dia_diem.startswith(k.TenKhuVuc + ' - ')]
    if khop:  # 1) khu vực Khách đã chọn trong form
        return [max(khop, key=lambda k: len(k.TenKhuVuc))]
    tinh = doc_tinh_thanh_tu_dia_diem(dia_diem)  # 2) đọc từ chữ gõ tay
    if tinh:
        return [tinh]
    khu_vuc_nag = list(booking.MaNhiepAnhGia.khu_vuc.all())  # 3) dự phòng
    return khu_vuc_nag if len(khu_vuc_nag) == 1 else []


def _lay_du_bao_theo_khu_vuc(booking):
    #3 sử dụng _khu_vuc_can_tra để xác định khu vực chụp
    # -> gọi lay_du_bao_thoi_tiet trong file thoi_tiet.py.
    for khu_vuc in _khu_vuc_can_tra(booking):
        du_bao = lay_du_bao_thoi_tiet(khu_vuc, booking.NgayGioChup, booking.MaGoi.ThoiLuongChup)   # E7: không bao giờ ném lỗi
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

#1 Đầu tiên, khi người dùng mở trang chi tiết Booking,
# hàm _trang_chi_tiet trong file theo_doi.py gọi
# hàm lay_the_thoi_tiet để kiểm tra điều kiện hiển thị thẻ thời tiết. (129->137)
def lay_the_thoi_tiet(booking, la_khach, la_nag):  # dữ liệu cho thẻ; None = không hiện thẻ
    """Trả dict {du_bao, mua_cao, url_chat, TB_...} hoặc None khi không được hiện thẻ."""
    if not (la_khach or la_nag):
        # Quản trị viên và vai trò khác không thấy thẻ
        return None
    if booking.TrangThai in TRANG_THAI_HET_HIEU_LUC:
        # Booking đã hết hiệu lực
        return None
    if booking.NgayGioChup <= timezone.now():
        # buổi chụp đã diễn ra (hoặc đang diễn ra)
        return None
    #2 Nếu đủ điều kiện, hàm này gọi _lay_du_bao_theo_khu_vuc,
    # trong đó sử dụng _khu_vuc_can_tra để xác định khu vực chụp,
    # sau đó gọi lay_du_bao_thoi_tiet trong file thoi_tiet.py.
    du_bao = _lay_du_bao_theo_khu_vuc(booking)  # {} nếu không có dự báo
    # Nếu xác suất mưa từ 60% trở lên, hệ thống gọi _nut_tro_chuyen để lấy đường dẫn trò chuyện
    # và hiển thị cảnh báo khuyến khích hai bên trao đổi đổi lịch.
    #4 Nếu xác suất mưa từ 60% trở lên, hệ thống gọi _nut_tro_chuyen để lấy đường
    # dẫn trò chuyện và hiển thị cảnh báo khuyến khích hai bên trao đổi đổi lịch.
    mua_cao = bool(du_bao) and du_bao['xac_suat_mua'] >= NGUONG_MUA_CAO  # chỉ nhắc khi có dự báo và mưa cao
    url_chat = _nut_tro_chuyen(booking, la_khach, la_nag) if mua_cao else None
    # nút chỉ cần khi nhắc đổi đổi lịch
    return {'du_bao': du_bao, 'mua_cao': mua_cao, 'url_chat': url_chat,
            'TB_CHUA_CO_DU_BAO': TB_CHUA_CO_DU_BAO, 'TB_NHAC_DOI_LICH': TB_NHAC_DOI_LICH}
#5 Cuối cùng, dữ liệu được hiển thị thông qua template bookings/includes/the_thoi_tiet.html.

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
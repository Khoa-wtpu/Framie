# bookings/templatetags/thoi_tiet_tags.py  -  bộ lọc cho thẻ "Dự báo thời tiết buổi chụp"
# Dùng trong bookings/templates/bookings/includes/the_thoi_tiet.html:
#     {% load thoi_tiet_tags %}   ...   {{ du_bao.mo_ta|nhom_thoi_tiet }}
# Đổi câu mô tả tiếng Việt của E7 (bookings/thoi_tiet.py, bảng MO_TA_THEO_MA) thành một "nhóm" để chọn biểu tượng và màu nhấn.
# Làm ở đây (không sửa E7) để hợp đồng của E7 giữ nguyên: E7 vẫn chỉ trả nhiet_do, xac_suat_mua, mo_ta.
import unicodedata

from django import template

register = template.Library()

# Các nhóm trả về: 'dong' (dông) | 'phun' (mưa phùn) | 'mua' (mưa, mưa rào) | 'suong' (sương mù)
#                  'may' (nhiều mây) | 'it-may' (ít mây, có mây) | 'nang' (trời quang)
NHOM_MAC_DINH = 'may'     # mô tả lạ (ví dụ "Chưa rõ thời tiết") thì dùng biểu tượng đám mây chung


@register.filter
def nhom_thoi_tiet(mo_ta):
    """'Mưa rào nhẹ' -> 'mua'; 'Dông kèm mưa đá nhẹ' -> 'dong'; 'Trời quang' -> 'nang'."""
    ten = unicodedata.normalize('NFC', str(mo_ta or '')).lower()
    # Thứ tự kiểm tra quan trọng: "Dông kèm mưa đá" chứa chữ "mưa" nên phải xét "dông" trước; "Mưa phùn" xét "phùn" trước "mưa".
    for tu_khoa, nhom in (('dông', 'dong'), ('phùn', 'phun'), ('mưa', 'mua'), ('sương', 'suong'),
                          ('nhiều mây', 'may'), ('có mây', 'it-may'), ('ít mây', 'it-may'), ('quang', 'nang')):
        if tu_khoa in ten:
            return nhom
    return NHOM_MAC_DINH

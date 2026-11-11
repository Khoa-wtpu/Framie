# core/buoc_ke.py - thông báo thành công kèm nút "sang bước kế" (dùng chung cho delivery, payments, reviews)
# Cách dùng trong view:
#     from core.buoc_ke import thanh_cong_co_nut
#     thanh_cong_co_nut(request, 'Đã gửi minh chứng.', reverse('chi_tiet_booking', args=[booking.pk]), 'Xem Booking')
# includes/messages.html đọc lại nút này qua bộ lọc nut_buoc_ke (core/templatetags/buoc_ke.py) và đưa vào hộp thông báo.
from django.contrib import messages
from django.urls import reverse

TIEN_TO = 'buoc-ke'    # đánh dấu trong extra_tags của message
NGAN_CACH = '::'       # ngăn cách: buoc-ke::<nhãn nút>::<đường dẫn>


def thanh_cong_co_nut(request, noi_dung, url, nhan):
    """Gửi messages.success kèm nút dẫn tới `url` với chữ `nhan` (đường dẫn nội bộ, bắt đầu bằng /)."""
    messages.success(request, noi_dung, extra_tags=f'{TIEN_TO}{NGAN_CACH}{nhan}{NGAN_CACH}{url}')


def url_booking(booking, la_nag=False):
    """Trang Booking để quay lại: Khách hàng -> chi_tiet_booking; Nhiếp ảnh gia -> chi_tiet_yeu_cau_booking.
    MỘT chỗ duy nhất quy định đích quay lại (nút quay lại ở templates/includes/quay_lai_booking.html cũng gọi hàm này)."""
    return reverse('chi_tiet_yeu_cau_booking' if la_nag else 'chi_tiet_booking', kwargs={'ma_booking': booking.pk})

# payments/views_con_lai.py - N9 / UC5.7: Nhiếp ảnh gia xác nhận thanh toán phần còn lại
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from bookings.models import Booking
from core.constants import TrangThaiBooking
from payments import services_con_lai as services
from payments.forms import YeuCauBoSungForm                    # dùng lại ô nhập lý do của N3 (tối đa 255 ký tự)
from profiles.decorators import nhiep_anh_gia_da_duyet         # chỉ Nhiếp ảnh gia hồ sơ Đã duyệt; decorator truyền thêm tham số nag


@nhiep_anh_gia_da_duyet
def xac_nhan_thanh_toan_con_lai(request, nag, ma_booking):     # trang UC5.7
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaKhachHang', 'MaGoi'), pk=ma_booking, MaNhiepAnhGia=nag)
    form = YeuCauBoSungForm()

    if request.method == 'POST':                               # NAG bấm một trong hai nút
        hanh_dong = request.POST.get('hanh_dong')
        try:
            if hanh_dong == 'xac_nhan':                        # bước 4 (và luồng 1b)
                services.xac_nhan_thanh_toan_con_lai(booking.pk, request.user)   # bước 5-7
                messages.success(request, 'Đã xác nhận thanh toán phần còn lại. Booking đã hoàn thành.')
                return redirect('chi_tiet_booking', ma_booking=booking.pk)   # tránh gửi lại khi F5
            elif hanh_dong == 'bo_sung':                       # nhánh 4a
                form = YeuCauBoSungForm(request.POST)
                if form.is_valid():
                    services.yeu_cau_bo_sung_con_lai(booking.pk, request.user, form.cleaned_data['ly_do'])
                    messages.success(request, 'Đã gửi yêu cầu bổ sung minh chứng cho Khách hàng.')
                    return redirect('chi_tiet_booking', ma_booking=booking.pk)
            else:
                messages.error(request, 'Thao tác không hợp lệ.')
        except services.LoiXacNhanConLai as loi:               # lỗi nghiệp vụ hoặc lỗi hệ thống (5a, 6a)
            messages.error(request, str(loi))

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    thanh_toan = services.lay_khoan_con_lai(booking)
    return render(request, 'payments/xac_nhan_thanh_toan_con_lai.html', {
        'booking': booking, 'thanh_toan': thanh_toan,
        'minh_chungs': thanh_toan.minh_chungs.order_by('-NgayTaiLen') if thanh_toan else [],
        'khong_xu_ly_duoc': services.ly_do_khong_xu_ly_duoc(booking, thanh_toan),
        'qua_han': services.la_qua_han(thanh_toan), 'form': form,
        'da_hoan_thanh': booking.TrangThai == TrangThaiBooking.HOAN_THANH})

# payments/views.py - N2 / UC5.1
import mimetypes                                              # đoán loại tệp (image/png...) khi trả ảnh về trình duyệt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import chi_khach_hang               # chỉ vai trò Khách hàng (đã có sẵn của Phanh)
from bookings.models import Booking
from payments import services
from payments.forms import MinhChungForm
from payments.models import ThanhToan


@chi_khach_hang                                               # chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403
def tai_len_minh_chung(request, ma_booking):
    booking = get_object_or_404(                              # chỉ xem được Booking của chính mình
        Booking.objects.select_related('MaNhiepAnhGia', 'MaGoi'), pk=ma_booking, MaKhachHang=request.user)

    if request.method == 'POST':                              # bước 5: Khách hàng bấm gửi
        form = MinhChungForm(request.POST, request.FILES)
        if form.is_valid():                                   # bước 4: kiểm tra định dạng, dung lượng
            try:
                services.tai_len_minh_chung(booking.pk, request.user, form.cleaned_data['tep'])  # bước 6-7
            except services.LoiTaiMinhChung as loi:           # lỗi nghiệp vụ hoặc lỗi lưu (6a)
                form.add_error(None, str(loi))
            else:
                messages.success(request, 'Đã gửi minh chứng. Vui lòng chờ Nhiếp ảnh gia xác nhận.')
                return redirect('tai_len_minh_chung', ma_booking=booking.pk)  # tránh gửi lại khi F5
    else:
        form = MinhChungForm()                                # bước 2: biểu mẫu trống

    booking.refresh_from_db()                                 # đọc lại trạng thái mới nhất
    khoan = services.xac_dinh_khoan(booking)
    thanh_toan = (ThanhToan.objects.filter(MaBooking=booking, LoaiThanhToan=khoan['loai']).first()
                  if khoan else None)
    return render(request, 'payments/tai_len_minh_chung.html', {
        'booking': booking, 'khoan': khoan, 'nag': booking.MaNhiepAnhGia, 'thanh_toan': thanh_toan,
        'minh_chungs': thanh_toan.minh_chungs.order_by('-NgayTaiLen') if thanh_toan else [],
        'khong_gui_duoc': services.ly_do_khong_gui_duoc(khoan, thanh_toan) if khoan else None,
        'form': form})


@login_required
def xem_minh_chung(request, ma_minh_chung):                   # trả ảnh minh chứng về trình duyệt (chỉ người có quyền)
    mc, kho = services.mo_minh_chung(request.user, ma_minh_chung)
    if mc is None:
        raise Http404
    if mc is False:
        raise PermissionDenied
    try:
        tep = kho.open(mc.DuongDanTep, 'rb')
    except OSError:
        raise Http404
    return FileResponse(tep, content_type=mimetypes.guess_type(mc.DuongDanTep)[0] or 'application/octet-stream')

# payments/views.py - N2 / UC5.1 và N3 / UC5.2
import mimetypes                                              # đoán loại tệp (image/png...) khi trả ảnh về trình duyệt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import chi_khach_hang               # chỉ vai trò Khách hàng (đã có sẵn của Phanh)
from bookings.models import Booking
from profiles.decorators import nhiep_anh_gia_da_duyet      # (N3) chỉ Nhiếp ảnh gia hồ sơ Đã duyệt (decorator chung của leader)
from core.constants import LoaiThanhToan, TrangThaiBooking  # (N3) loại khoản thanh toán và trạng thái Booking
from payments import services
from payments.forms import MinhChungForm, YeuCauBoSungForm
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
    phan_hoi = FileResponse(tep, content_type=mimetypes.guess_type(mc.DuongDanTep)[0] or 'application/octet-stream')
    phan_hoi['X-Content-Type-Options'] = 'nosniff'             # trình duyệt không tự đoán lại loại tệp
    return phan_hoi


@nhiep_anh_gia_da_duyet                                       # N3: chỉ NAG hồ sơ Đã duyệt; decorator truyền thêm tham số nag
def xac_nhan_thanh_toan_coc(request, nag, ma_booking):        # trang UC5.2
    booking = get_object_or_404(                              # chỉ xem được Booking của chính mình
        Booking.objects.select_related('MaKhachHang', 'MaGoi'), pk=ma_booking, MaNhiepAnhGia=nag)
    form = YeuCauBoSungForm()

    if request.method == 'POST':                              # NAG bấm một trong hai nút
        hanh_dong = request.POST.get('hanh_dong')
        try:
            if hanh_dong == 'xac_nhan':                       # bước 4
                services.xac_nhan_thanh_toan_coc(booking.pk, request.user)    # bước 5
                messages.success(request, 'Đã xác nhận tiền cọc. Booking được chốt.')
                return redirect('xac_nhan_thanh_toan_coc', ma_booking=booking.pk)
            elif hanh_dong == 'bo_sung':                      # nhánh 4a
                form = YeuCauBoSungForm(request.POST)
                if form.is_valid():
                    services.yeu_cau_bo_sung_minh_chung(booking.pk, request.user, form.cleaned_data['ly_do'])
                    messages.success(request, 'Đã gửi yêu cầu bổ sung minh chứng cho Khách hàng.')
                    return redirect('xac_nhan_thanh_toan_coc', ma_booking=booking.pk)
            else:
                messages.error(request, 'Thao tác không hợp lệ.')
        except services.LoiXacNhanCoc as loi:                 # lỗi nghiệp vụ hoặc lỗi hệ thống (5a)
            messages.error(request, str(loi))

    booking.refresh_from_db()                                 # đọc lại trạng thái mới nhất
    thanh_toan = ThanhToan.objects.filter(MaBooking=booking, LoaiThanhToan=LoaiThanhToan.TIEN_COC).first()
    khong_xu_ly_duoc = services.ly_do_khong_xu_ly_duoc(booking, thanh_toan)
    return render(request, 'payments/xac_nhan_thanh_toan_coc.html', {
        'booking': booking, 'thanh_toan': thanh_toan,
        'minh_chungs': thanh_toan.minh_chungs.order_by('-NgayTaiLen') if thanh_toan else [],
        'khong_xu_ly_duoc': khong_xu_ly_duoc, 'form': form,
        'da_chot': booking.TrangThai == TrangThaiBooking.CHOT_BOOKING})   # để template hiện dòng "Booking đã được chốt"

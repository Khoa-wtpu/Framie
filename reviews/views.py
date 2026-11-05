# reviews/views.py - N11 / UC6.1: Khách hàng đánh giá nhiếp ảnh gia + hiển thị công khai đánh giá
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import chi_khach_hang
from bookings.models import Booking
from reviews import services
from reviews.forms import DanhGiaForm
from reviews.models import DanhGia
from search.services import nhiep_anh_gia_cong_khai


def _ten(user, mac_dinh):                                      # tên hiển thị (không bao giờ hiện email/username)
    return user.get_full_name() or mac_dinh


@chi_khach_hang                                                # chỉ Khách hàng (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
def danh_gia_booking(request, ma_booking):                     # trang UC6.1
    booking = get_object_or_404(                               # chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaNhiepAnhGia__MaTaiKhoan'), pk=ma_booking, MaKhachHang=request.user)
    form = DanhGiaForm()

    if request.method == 'POST':
        form = DanhGiaForm(request.POST)
        if form.is_valid():
            try:
                services.tao_danh_gia(booking.pk, request.user, form.cleaned_data['diem'], form.cleaned_data['nhan_xet'])
            except services.LoiDanhGia as loi:
                messages.error(request, str(loi))
            else:
                messages.success(request, 'Cảm ơn bạn! Đánh giá đã được gửi và hiển thị công khai trên hồ sơ nhiếp ảnh gia.')
                return redirect('danh_gia_booking', ma_booking=booking.pk)   # tránh gửi lại khi F5

    booking.refresh_from_db()
    danh_gia = DanhGia.objects.filter(MaBooking=booking).first()   # đã đánh giá thì chỉ xem lại
    ly_do = None if danh_gia else services.ly_do_khong_danh_gia_duoc(booking)
    nag_user = booking.MaNhiepAnhGia.MaTaiKhoan
    diem_chon = form['diem'].value() if form.is_bound else None
    return render(request, 'reviews/danh_gia_booking.html', {
        'booking': booking, 'form': form, 'danh_gia': danh_gia, 'ly_do': ly_do,
        'ten_nag': _ten(nag_user, nag_user.username),
        'diem_chon': int(diem_chon) if str(diem_chon).isdigit() else 0,   # giữ lại số sao đã chọn khi báo lỗi
        'nhan_xet_nhap': form['nhan_xet'].value() or '' if form.is_bound else '',
        'toi_da': services.DO_DAI_NHAN_XET_TOI_DA,
        'cho_danh_gia': ly_do is None and danh_gia is None})


def danh_gia_cong_khai(request, ma_nag):                       # đánh giá + điểm trung bình hiển thị công khai (không cần đăng nhập)
    nag = get_object_or_404(nhiep_anh_gia_cong_khai().select_related('MaTaiKhoan'), pk=ma_nag)   # chỉ hồ sơ công khai (Đã duyệt, còn hoạt động)
    thong_ke, trang = services.lay_trang_danh_gia(nag, request.GET.get('page'))
    return render(request, 'reviews/danh_gia_nhiep_anh_gia.html', {
        'nag': nag, 'ten_nag': _ten(nag.MaTaiKhoan, nag.MaTaiKhoan.username),
        'thong_ke': thong_ke, 'page_obj': trang})

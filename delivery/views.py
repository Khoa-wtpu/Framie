# delivery/views.py - N4 / UC5.3: Nhiếp ảnh gia tải ảnh lên Booking
import mimetypes                                               # đoán loại tệp (image/jpeg...) khi trả ảnh về trình duyệt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from bookings.models import Booking
from core.constants import LoaiAnh, LoaiHauKy, LuuTruAnh, TrangThaiBooking
from delivery import services
from delivery.forms import TaiAnhForm
from delivery.models import Anh
from profiles.decorators import nhiep_anh_gia_da_duyet         # chỉ Nhiếp ảnh gia hồ sơ Đã duyệt (decorator chung của leader)


@nhiep_anh_gia_da_duyet                                        # decorator truyền thêm tham số nag (hồ sơ của người đang đăng nhập)
def tai_anh_len(request, nag, ma_booking):
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaKhachHang'), pk=ma_booking, MaNhiepAnhGia=nag)
    la_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'   # JavaScript gửi để hiện thanh tiến trình
    form = TaiAnhForm()

    if request.method == 'POST':                               # bước 5: Nhiếp ảnh gia bấm tải
        form = TaiAnhForm(request.POST, request.FILES)
        if form.is_valid():                                    # bước 4: kiểm tra định dạng, dung lượng, số lượng
            try:
                ket_qua = services.tai_anh_len(booking.pk, request.user, form.cleaned_data['anh'])   # bước 6-8
            except services.LoiTaiAnh as loi:                  # lỗi nghiệp vụ hoặc lỗi lưu (7a)
                form.add_error(None, str(loi))
            else:
                if ket_qua['trang_thai_moi']:
                    messages.success(request, f'Đã tải {ket_qua["so_anh"]} ảnh. Booking chuyển sang "{ket_qua["trang_thai_moi"]}".')
                else:
                    messages.success(request, f'Đã tải {ket_qua["so_anh"]} ảnh hậu kỳ. Còn {ket_qua["con_thieu"]} ảnh cần tải.')
                url = reverse('tai_anh_len', args=[booking.pk])
                return JsonResponse({'ok': True, 'url': url}) if la_ajax else redirect(url)
        if la_ajax:                                            # trả lỗi cho JavaScript hiển thị
            loi = [str(e) for ds in form.errors.values() for e in ds]
            return JsonResponse({'ok': False, 'loi': loi}, status=400)

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    giai_doan = services.xac_dinh_giai_doan(booking)
    cho_hau_ky = list(services.anh_can_hau_ky(booking)) if giai_doan and giai_doan['loai'] == LoaiAnh.DA_HAU_KY else []
    return render(request, 'delivery/tai_anh_len.html', {
        'booking': booking, 'giai_doan': giai_doan, 'form': form,
        'anhs': Anh.objects.filter(MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU).order_by('TenAnh'),
        'cho_hau_ky': cho_hau_ky, 'so_anh_toi_da': services.SO_ANH_TOI_DA,
        'gioi_han': booking.MaGoi.LoaiHauKy == LoaiHauKy.GIOI_HAN,
        'dang_o_buoc_goc': booking.TrangThai == TrangThaiBooking.DA_CHUP})


@login_required
def xem_anh(request, ma_anh):                                  # bước 7: hiển thị ảnh đã chèn watermark (chỉ người có quyền)
    anh, kho = services.mo_anh(request.user, ma_anh)
    if anh is None:
        raise Http404
    if anh is False:
        raise PermissionDenied
    try:
        tep = kho.open(anh.DuongDanAnh, 'rb')
    except OSError:
        raise Http404
    return FileResponse(tep, content_type=mimetypes.guess_type(anh.DuongDanAnh)[0] or 'application/octet-stream')

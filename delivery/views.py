# delivery/views.py - N4 / UC5.3: Nhiếp ảnh gia tải ảnh lên Booking
import io
import mimetypes                                               # đoán loại tệp (image/jpeg...) khi trả ảnh về trình duyệt

from PIL import Image

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST          # N6: chỉ nhận phương thức POST (bấm nút), gõ địa chỉ trực tiếp thì báo 405

from accounts.permissions import chi_khach_hang                # N6: chỉ vai trò Khách hàng (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
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
    page_obj = Paginator(
        Anh.objects.filter(MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU).order_by('TenAnh'), 24
    ).get_page(request.GET.get('page'))
    cho_bat_dau = booking.TrangThai == TrangThaiBooking.CHO_HAU_KY    # N6: Khách đã gửi danh sách -> Nhiếp ảnh gia bấm "Bắt đầu hậu kỳ"
    anh_da_chon = (list(Anh.objects.filter(MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU, DuocChonHauKy=1).order_by('TenAnh'))
                   if cho_bat_dau and booking.MaGoi.LoaiHauKy == LoaiHauKy.GIOI_HAN else [])   # N6: danh sách ảnh Khách đã chọn (chỉ gói giới hạn)
    return render(request, 'delivery/tai_anh_len.html', {
        'booking': booking, 'giai_doan': giai_doan, 'form': form,
        'cho_bat_dau_hau_ky': cho_bat_dau, 'anh_da_chon': anh_da_chon,   # N6: dữ liệu cho khung "Bắt đầu hậu kỳ"

        'anhs': page_obj.object_list, 'page_obj': page_obj,
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
    if request.GET.get('nho') == '1':
        try:
            with Image.open(tep) as hinh:
                hinh.thumbnail((400, 400))
                hinh = hinh.convert('RGB')
                dem = io.BytesIO()
                hinh.save(dem, format='JPEG', quality=82, optimize=True)
        except Exception:
            tep.close()
            raise Http404
        tep.close()
        phan_hoi = HttpResponse(dem.getvalue(), content_type='image/jpeg')
    else:
        phan_hoi = FileResponse(tep, content_type=mimetypes.guess_type(anh.DuongDanAnh)[0] or 'application/octet-stream')
    phan_hoi['Content-Disposition'] = 'inline'                 # N5: chỉ cho XEM trên trang, trình duyệt không tự tải xuống
    phan_hoi['Cache-Control'] = 'private, no-store, max-age=0'  # không cho lưu bản sao vào bộ nhớ đệm / proxy
    phan_hoi['X-Content-Type-Options'] = 'nosniff'             # trình duyệt không đoán lại loại tệp
    return phan_hoi


# =====================================================================
# N6 / UC5.4: Khách hàng lựa chọn ảnh cần hậu kỳ
# =====================================================================
def _doc_ds_ma_anh(request):                                   # lấy danh sách mã ảnh Khách tick từ form (các ô name="anh")
    return [int(giatri) for giatri in request.POST.getlist('anh') if giatri.isdigit()]   # chỉ nhận chuỗi số, bỏ giá trị lạ


@chi_khach_hang                                                # chỉ Khách hàng mới vào được trang này
def chon_anh_hau_ky(request, ma_booking):                      # trang UC5.4
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaNhiepAnhGia'), pk=ma_booking, MaKhachHang=request.user)  # lấy kèm Gói và Nhiếp ảnh gia trong 1 truy vấn
    toi_da = services.so_anh_toi_da_cua_goi(booking)           # số ảnh tối đa theo gói
    hoi_chon_them = False                                      # True = hiện hộp hỏi "chọn thêm hay gửi" (luồng 4a)
    ds_tick = None                                             # danh sách mã ảnh hiển thị là đã tick (None = lấy từ database)

    if request.method == 'POST':                               # Khách bấm một trong các nút
        hanh_dong = request.POST.get('hanh_dong')              # nút nào: luu / gui / gui_xac_nhan
        ds_ma_anh = _doc_ds_ma_anh(request)                    # các ảnh Khách đang tick
        try:                                                   # bắt lỗi nghiệp vụ
            if hanh_dong == 'luu':                             # bước 3-4: chỉ lưu lựa chọn
                so_chon = services.luu_lua_chon(booking.pk, request.user, ds_ma_anh)   # ghi vào database
                messages.success(request, f'Đã lưu {so_chon} ảnh được chọn (tối đa {toi_da} ảnh).')  # báo đã lưu lựa chọn
                return redirect('chon_anh_hau_ky', ma_booking=booking.pk)   # tránh gửi lại khi F5
            elif hanh_dong == 'gui':                           # bước 5: Khách bấm xác nhận lựa chọn
                so_chon = services.luu_lua_chon(booking.pk, request.user, ds_ma_anh)   # ghi lựa chọn trước (ném lỗi 4b nếu vượt giới hạn)
                if so_chon == 0:                               # chưa tick ảnh nào
                    raise services.LoiChonAnh('Vui lòng chọn ít nhất một ảnh cần hậu kỳ.')  # báo: chưa chọn ảnh nào
                if so_chon < toi_da:                           # luồng 4a: chưa đạt số lượng tối đa
                    hoi_chon_them = True                       # hiện hộp hỏi, CHƯA gửi (lựa chọn đã được lưu)
                else:                                          # đã đủ số lượng: gửi luôn
                    services.gui_danh_sach_hau_ky(booking.pk, request.user)   # bước 6
                    messages.success(request, f'Đã gửi danh sách {so_chon} ảnh cho Nhiếp ảnh gia để hậu kỳ.')  # báo đã gửi danh sách cho Nhiếp ảnh gia
                    return redirect('chon_anh_hau_ky', ma_booking=booking.pk)  # chuyển về trang chọn ảnh để tránh gửi lại khi F5
            elif hanh_dong == 'gui_xac_nhan':                  # luồng 4a-2: Khách chọn "Không, gửi danh sách ảnh đã chọn"
                kq = services.gui_danh_sach_hau_ky(booking.pk, request.user)   # gửi danh sách đã lưu
                messages.success(request, f'Đã gửi danh sách {kq["so_anh"]} ảnh cho Nhiếp ảnh gia để hậu kỳ.')  # báo đã gửi danh sách cho Nhiếp ảnh gia
                return redirect('chon_anh_hau_ky', ma_booking=booking.pk)  # chuyển về trang chọn ảnh để tránh gửi lại khi F5
            else:                                              # nút lạ
                messages.error(request, 'Thao tác không hợp lệ.')  # báo thao tác lạ
        except services.LoiChonAnh as loi:                     # lỗi nghiệp vụ: vượt giới hạn (4b), lỗi lưu (6a)...
            messages.error(request, str(loi))                  # hiện lỗi cho Khách
            ds_tick = ds_ma_anh                                # giữ nguyên các ô Khách vừa tick để Khách bỏ bớt

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    ly_do = services.ly_do_khong_chon_duoc(booking)            # None = được chọn; có chữ = không được chọn
    anhs = list(services.anh_de_chon(booking))                 # các ảnh có watermark của Booking
    if ds_tick is None:                                        # không phải trường hợp lỗi vừa rồi
        ds_tick = [a.pk for a in anhs if a.DuocChonHauKy == 1]   # lấy các ảnh đã lưu là "được chọn"
    if ly_do:                                                  # không được chọn nữa: chỉ cho xem các ảnh đã chọn
        anhs = [a for a in anhs if a.DuocChonHauKy == 1]  # chỉ giữ các ảnh đã chọn
    return render(request, 'delivery/chon_anh_hau_ky.html', {  # hiển thị trang chọn ảnh
        'booking': booking, 'ly_do': ly_do, 'anhs': anhs, 'ds_tick': ds_tick,  # dữ liệu gửi sang template (1)
        'so_da_chon': len(ds_tick), 'so_toi_da': toi_da, 'hoi_chon_them': hoi_chon_them})  # dữ liệu gửi sang template (2)


@nhiep_anh_gia_da_duyet                                        # chỉ Nhiếp ảnh gia hồ sơ Đã duyệt (tự truyền thêm tham số nag)
@require_POST                                                  # chỉ nhận khi bấm nút (POST)
def bat_dau_hau_ky(request, nag, ma_booking):                  # Nhiếp ảnh gia bấm "Bắt đầu hậu kỳ"
    booking = get_object_or_404(Booking, pk=ma_booking, MaNhiepAnhGia=nag)   # chỉ Booking của chính mình
    try:                                                       # bắt lỗi nghiệp vụ
        services.bat_dau_hau_ky(booking.pk, request.user)      # Chờ hậu kỳ -> Đang hậu kỳ (hạn 3 ngày)
        messages.success(request, 'Đã bắt đầu hậu kỳ. Booking chuyển sang "Đang hậu kỳ", hạn 3 ngày.')  # báo đã bắt đầu hậu kỳ
    except services.LoiBatDauHauKy as loi:                     # sai trạng thái...
        messages.error(request, str(loi))                      # hiện lỗi
    return redirect('tai_anh_len', ma_booking=booking.pk)      # quay lại trang tải ảnh của Booking

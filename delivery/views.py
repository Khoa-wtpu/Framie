# delivery/views.py - N4 / UC5.3: Nhiếp ảnh gia tải ảnh lên Booking
import io
import mimetypes                                               # đoán loại tệp (image/jpeg...) khi trả ảnh về trình duyệt

from PIL import Image

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError                            # N8: bắt lỗi database khi tải ảnh (ngoại lệ 2a)
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone                              # N8: đổi hạn thanh toán sang giờ địa phương để hiện cho Khách
from django.views.decorators.http import require_POST          # N6: chỉ nhận phương thức POST (bấm nút), gõ địa chỉ trực tiếp thì báo 405

from accounts.permissions import chi_khach_hang                # N6: chỉ vai trò Khách hàng (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
from bookings.models import Booking
from core.constants import LoaiAnh, LoaiHauKy, LuuTruAnh, TrangThaiBooking
from delivery import services
from delivery.forms import TaiAnhForm
from delivery.models import Anh, YeuCauChinhSua, YeuCauChinhSua_Anh   # N7: bảng yêu cầu chỉnh sửa và chi tiết từng ảnh
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
                url = reverse('chi_tiet_booking', args=[booking.pk]) if ket_qua['trang_thai_moi'] else reverse('tai_anh_len', args=[booking.pk])
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
    yeu_cau_moi = (YeuCauChinhSua.objects.filter(MaBooking=booking).order_by('-SoLanYeuCau').first()   # N7: yêu cầu chỉnh sửa gần nhất của Khách
                   if booking.TrangThai == TrangThaiBooking.DANG_HAU_KY else None)   # N7: chỉ hiện khi đang hậu kỳ
    yeu_cau_anhs = (list(YeuCauChinhSua_Anh.objects.filter(MaYeuCauChinhSua=yeu_cau_moi).select_related('MaAnh').order_by('MaAnh__TenAnh'))
                    if yeu_cau_moi else [])   # N7: nội dung cần sửa của từng ảnh để Nhiếp ảnh gia đọc
    return render(request, 'delivery/tai_anh_len.html', {
        'booking': booking, 'giai_doan': giai_doan, 'form': form,
        'yeu_cau_moi': yeu_cau_moi, 'yeu_cau_anhs': yeu_cau_anhs,   # N7: dữ liệu cho khung "Khách hàng yêu cầu chỉnh sửa"
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
                    return redirect('chi_tiet_booking', ma_booking=booking.pk)  # đã gửi lựa chọn, quay về chi tiết Booking
            elif hanh_dong == 'gui_xac_nhan':                  # luồng 4a-2: Khách chọn "Không, gửi danh sách ảnh đã chọn"
                kq = services.gui_danh_sach_hau_ky(booking.pk, request.user)   # gửi danh sách đã lưu
                messages.success(request, f'Đã gửi danh sách {kq["so_anh"]} ảnh cho Nhiếp ảnh gia để hậu kỳ.')  # báo đã gửi danh sách cho Nhiếp ảnh gia
                return redirect('chi_tiet_booking', ma_booking=booking.pk)  # đã gửi lựa chọn, quay về chi tiết Booking
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
    return redirect('chi_tiet_booking', ma_booking=booking.pk)  # hậu kỳ bắt đầu: quay về chi tiết Booking


# =====================================================================
# N7 / UC5.5: Khách hàng yêu cầu chỉnh sửa ảnh
# =====================================================================
@chi_khach_hang                                                # chỉ Khách hàng mới vào được trang này
def yeu_cau_chinh_sua(request, ma_booking):                    # trang UC5.5
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaNhiepAnhGia'), pk=ma_booking, MaKhachHang=request.user)  # lấy kèm Gói và Nhiếp ảnh gia trong 1 truy vấn
    nhan_xet = ''                                              # nhận xét tổng quát đang hiển thị trong ô nhập
    ds_tick = set()                                            # các mã ảnh đang được tick
    noi_dung_nhap = {}                                         # {mã ảnh: nội dung đã nhập} để giữ lại khi báo lỗi

    if request.method == 'POST':                               # Khách bấm "Gửi yêu cầu chỉnh sửa"
        nhan_xet = request.POST.get('nhan_xet', '')            # nhận xét tổng quát
        ds_tick = {int(g) for g in request.POST.getlist('anh') if g.isdigit()}   # các ảnh Khách tick (chỉ nhận chuỗi số)
        noi_dung_nhap = {ma: request.POST.get(f'noi_dung_{ma}', '') for ma in ds_tick}   # nội dung sửa của từng ảnh đã tick
        try:                                                   # bắt lỗi nghiệp vụ
            kq = services.gui_yeu_cau_chinh_sua(booking.pk, request.user, nhan_xet, noi_dung_nhap)   # bước 5-6: lưu và báo Nhiếp ảnh gia
            messages.success(request, f'Đã gửi yêu cầu chỉnh sửa lần {kq["so_lan"]}/{services.SO_LAN_CHINH_SUA_TOI_DA} '  # báo thành công: lần thứ mấy, bao nhiêu ảnh
                                      f'cho {kq["so_anh"]} ảnh. Nhiếp ảnh gia sẽ chỉnh sửa và tải phiên bản mới.')   # báo thành công
            if not kq['da_bao_nag']:                           # ngoại lệ 6a: yêu cầu đã lưu nhưng thông báo bị lỗi
                messages.warning(request, 'Yêu cầu đã được lưu nhưng hệ thống chưa gửi được thông báo đến Nhiếp ảnh gia. '  # báo yêu cầu đã lưu nhưng thông báo bị lỗi
                                          'Hệ thống đã ghi nhận để xử lý lại.')   # báo cho Khách biết
            return redirect('chi_tiet_booking', ma_booking=booking.pk)   # đã gửi yêu cầu chỉnh sửa
        except services.LoiYeuCauChinhSua as loi:              # lỗi nghiệp vụ: 2a, 4a, 4b, 5a
            messages.error(request, str(loi))                  # hiện lỗi cho Khách (giữ nguyên dữ liệu đã nhập)

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    ly_do = services.ly_do_khong_yeu_cau_duoc(booking)         # None = được yêu cầu; có chữ = không được (gồm luồng 2a)
    anhs = list(services.anh_de_chinh_sua(booking))            # các ảnh đã hậu kỳ (có watermark) của Booking
    for a in anhs:                                             # gắn thêm dữ liệu hiển thị cho từng ảnh
        a.da_tick = a.pk in ds_tick                            # ảnh này đang được tick không
        a.noi_dung_nhap = noi_dung_nhap.get(a.pk, '')          # nội dung đã nhập (nếu có)
    con_lai = services.so_lan_chinh_sua_con_lai(booking)       # bước 2: số lần còn lại
    return render(request, 'delivery/yeu_cau_chinh_sua.html', {  # hiển thị trang yêu cầu chỉnh sửa
        'booking': booking, 'ly_do': ly_do, 'anhs': anhs, 'nhan_xet': nhan_xet,  # dữ liệu gửi sang template (1)
        'so_lan_toi_da': services.SO_LAN_CHINH_SUA_TOI_DA, 'so_lan_con_lai': con_lai,  # dữ liệu gửi sang template (2)
        'so_lan_da_dung': services.SO_LAN_CHINH_SUA_TOI_DA - con_lai,  # dữ liệu gửi sang template (3)
        'lich_su': YeuCauChinhSua.objects.filter(MaBooking=booking).order_by('SoLanYeuCau')})   # lịch sử các lần đã yêu cầu


# =====================================================================
# N8 / UC5.6: Khách hàng xác nhận hoàn tất bàn giao
# =====================================================================
@chi_khach_hang                                                # chỉ Khách hàng mới vào được trang này
def xac_nhan_ban_giao(request, ma_booking):                    # trang UC5.6
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaNhiepAnhGia'), pk=ma_booking, MaKhachHang=request.user)  # lấy kèm Gói và Nhiếp ảnh gia
    hoi_xac_nhan = False                                       # True = hiện hộp "Bạn có chắc chắn xác nhận?" (bước xác nhận)

    if request.method == 'POST':                               # Khách bấm một trong các nút
        hanh_dong = request.POST.get('hanh_dong')              # nút nào: hoi / xac_nhan
        try:                                                   # bắt lỗi nghiệp vụ
            if hanh_dong == 'hoi':                             # bước 4: Khách bấm "Xác nhận hoàn tất bàn giao" -> hỏi lại cho chắc
                ly_do = services.ly_do_khong_xac_nhan_duoc(booking)   # kiểm tra có được xác nhận không
                if ly_do:                                      # không được
                    raise services.LoiBanGiao(ly_do)           # báo lỗi
                hoi_xac_nhan = True                            # hiện hộp xác nhận, CHƯA ghi gì
            elif hanh_dong == 'xac_nhan':                      # Khách bấm "Có, xác nhận hoàn tất bàn giao"
                kq = services.xac_nhan_hoan_tat_ban_giao(booking.pk, request.user)   # bước 5-7: tạo Bàn giao, khoản 60%, đổi trạng thái, thông báo
                messages.success(request, f'Đã xác nhận hoàn tất bàn giao. Vui lòng thanh toán {services.dinh_dang_tien(kq["so_tien"])} '  # báo thành công kèm số tiền
                                          f'(phần còn lại) trước {timezone.localtime(kq["han"]).strftime("%d/%m/%Y %H:%M")}.')   # báo thành công kèm số tiền và hạn
                return redirect('chi_tiet_booking', ma_booking=booking.pk)   # đã xác nhận bàn giao
            else:                                              # nút lạ
                messages.error(request, 'Thao tác không hợp lệ.')   # báo thao tác lạ
        except services.LoiBanGiao as loi:                     # lỗi nghiệp vụ: 5a, 6a, sai trạng thái...
            messages.error(request, str(loi))                  # hiện lỗi cho Khách

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    ly_do = services.ly_do_khong_xac_nhan_duoc(booking)        # None = được xác nhận; có chữ = không được
    try:                                                       # bước 2: tải các ảnh đã hậu kỳ có watermark
        anhs = list(services.anh_de_chinh_sua(booking))        # danh sách ảnh
    except DatabaseError:                                      # ngoại lệ 2a: không tải được ảnh
        anhs = []                                              # không có ảnh để hiện
        messages.error(request, 'Không thể tải ảnh hậu kỳ, vui lòng thử lại.')   # báo cho Khách
    return render(request, 'delivery/xac_nhan_ban_giao.html', {  # hiển thị trang xác nhận bàn giao
        'booking': booking, 'ly_do': ly_do, 'anhs': anhs, 'hoi_xac_nhan': hoi_xac_nhan,  # dữ liệu gửi sang template (1)
        'so_tien_con_lai': services.dinh_dang_tien(services.so_tien_con_lai(booking)),   # số tiền 60% để báo trước cho Khách
        'so_lan_chinh_sua_con_lai': services.so_lan_chinh_sua_con_lai(booking),   # còn mấy lần yêu cầu chỉnh sửa (nhánh 4a)
        'da_xac_nhan': booking.TrangThai == TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN})   # đã xác nhận, đang chờ thanh toán

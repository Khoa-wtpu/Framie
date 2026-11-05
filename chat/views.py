# chat/views.py - P10 (UC8.1) khởi tạo cuộc trò chuyện; P11 (UC8.2, UC8.3) hộp thư, gửi tin, xem lịch sử, polling.
from django.conf import settings  # đọc LOGIN_URL
from django.contrib import messages  # hộp thông báo ngắn trên đầu trang
from django.contrib.auth.decorators import login_required  # bắt buộc đăng nhập cho các trang HTML
from django.contrib.auth.views import redirect_to_login  # chuyển người chưa đăng nhập sang trang đăng nhập, kèm ?next=
from django.core.exceptions import PermissionDenied, ValidationError  # 403: không đủ quyền; ValidationError: dữ liệu không hợp lệ
from django.db import DatabaseError  # lỗi cơ sở dữ liệu bất ngờ
from django.http import JsonResponse  # trả dữ liệu JSON cho JavaScript
from django.shortcuts import get_object_or_404, redirect, render, resolve_url  # tìm đối tượng; chuyển trang; dựng trang; đổi tên URL thành đường dẫn
from django.template.loader import render_to_string  # dựng một đoạn HTML (một bong bóng tin nhắn) thành chuỗi
from django.views.decorators.cache import never_cache  # không cho trình duyệt lưu đệm kết quả polling
from django.views.decorators.http import require_POST, require_safe  # chỉ nhận POST; chỉ nhận GET/HEAD

from chat import services  # logic nghiệp vụ nằm ở services.py
from profiles.models import NhiepAnhGia  # hồ sơ Nhiếp ảnh gia (app của Khoa)


@require_POST  # GET vào đường dẫn này trả lỗi 405, tránh trình duyệt tải trước làm tạo cuộc trò chuyện
def khoi_tao_cuoc_tro_chuyen(request, ma_nhiep_anh_gia):  # UC8.1
    nag = get_object_or_404(NhiepAnhGia.objects.select_related('MaTaiKhoan'), pk=ma_nhiep_anh_gia)  # không có hồ sơ thì 404
    ho_so = services.duong_dan_ho_so(nag.pk)  # trang hồ sơ để quay lại
    if not request.user.is_authenticated:  # chưa đăng nhập
        return redirect_to_login(ho_so)  # sang trang đăng nhập, đăng nhập xong quay lại hồ sơ
    if not services.la_khach_hang(request.user):  # đã đăng nhập nhưng không phải Khách hàng
        raise PermissionDenied('Chỉ Khách hàng mới được khởi tạo cuộc trò chuyện.')  # 403
    try:  # luồng ngoại lệ 2a của UC8.1: lỗi bất ngờ khi khởi tạo
        cuoc, da_tao = services.mo_hoac_tao_cuoc_tro_chuyen(request.user, nag)  # mở cuộc cũ hoặc tạo mới
    except (ValidationError, DatabaseError):  # Http404 (chưa duyệt) và 403 không bị bắt ở đây, vẫn giữ nguyên
        messages.error(request, 'Không thể khởi tạo cuộc trò chuyện. Vui lòng thực hiện lại.')  # hộp đỏ theo đặc tả
        return redirect(ho_so)  # quay về hồ sơ để bấm lại
    dich = services.duong_dan_cuoc_tro_chuyen(cuoc.pk)  # màn hình trò chuyện (UC8.2)
    if dich:  # có đường dẫn
        return redirect(dich)  # vào thẳng cuộc trò chuyện
    ten = nag.MaTaiKhoan.get_full_name() or nag.MaTaiKhoan.username  # tên hiển thị của Nhiếp ảnh gia
    messages.success(request, f'Đã tạo cuộc trò chuyện với {ten}.' if da_tao else f'Đã mở lại cuộc trò chuyện với {ten}.')  # dự phòng
    return redirect(ho_so)  # quay lại hồ sơ


# ---------------------------------------------------------------------------------------------
# P11
# ---------------------------------------------------------------------------------------------

def _la_yeu_cau_ngam(request):  # True nếu yêu cầu do chat.js gửi ngầm (fetch) chứ không phải form thường
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'  # chat.js luôn gắn tiêu đề này


def _het_phien_json():  # phản hồi cho yêu cầu ngầm khi phiên đăng nhập đã hết hạn
    return JsonResponse({'ok': False, 'loi': 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'}, status=401)  # 401 để chat.js dừng polling


def _dong_goi_tin(danh_sach, nguoi_xem):  # đổi danh sách TinNhan thành [{id, html}] để chat.js chèn thẳng vào trang
    return [  # mỗi tin một phần tử
        {'id': tin.pk, 'html': render_to_string('chat/_tin_nhan.html', {'tin': tin, 'nguoi_xem_id': nguoi_xem.pk})}  # HTML đã được Django tự escape
        for tin in danh_sach  # duyệt từng tin
    ]  # hết danh sách


@login_required  # chưa đăng nhập thì sang trang đăng nhập, kèm ?next=
@require_safe  # chỉ GET/HEAD
def hop_thu(request):  # màn hình danh sách cuộc trò chuyện, menu "Tin nhắn" (url name='inbox')
    if not services.duoc_dung_tro_chuyen(request.user):  # Quản trị viên hoặc Nhiếp ảnh gia chưa được duyệt
        raise PermissionDenied('Bạn không có quyền dùng mục Tin nhắn.')  # 403
    loi = ''  # thông báo lỗi nếu không tải được danh sách
    try:  # truy vấn danh sách
        cac_cuoc = services.danh_sach_cuoc(request.user)  # các cuộc trò chuyện của người dùng
    except DatabaseError:  # lỗi bất ngờ
        cac_cuoc = []  # danh sách rỗng
        loi = services.LOI_TAI_LICH_SU  # báo lỗi
    return render(request, 'chat/hop_thu.html', {  # dựng trang
        'cac_cuoc': cac_cuoc,  # danh sách cuộc trò chuyện
        'la_khach': services.la_khach_hang(request.user),  # để chọn câu hướng dẫn khi danh sách trống
        'loi': loi,  # thông báo lỗi (nếu có)
    })  # hết render


@login_required  # chưa đăng nhập thì sang trang đăng nhập
@require_safe  # chỉ GET/HEAD
def chi_tiet_cuoc_tro_chuyen(request, ma_cuoc):  # SC8.2 + UC8.3: mở cuộc trò chuyện và xem lịch sử
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # người ngoài cuộc bị 404
    tin_nhan, con_cu, loi_tai = [], False, ''  # mặc định: chưa có tin, không còn tin cũ, không lỗi
    try:  # luồng ngoại lệ 2a của UC8.3: không truy xuất được lịch sử
        tin_nhan, con_cu = services.lay_tin_gan_nhat(cuoc)  # các tin gần nhất
    except DatabaseError:  # lỗi bất ngờ
        loi_tai = services.LOI_TAI_LICH_SU  # báo lỗi, trang vẫn hiện để người dùng bấm tải lại
    return render(request, 'chat/chi_tiet_cuoc_tro_chuyen.html', {  # dựng trang
        'cuoc': cuoc,  # cuộc trò chuyện
        'doi_phuong': services.thong_tin_doi_phuong(cuoc, request.user),  # người ở phía bên kia
        'tin_nhan': tin_nhan,  # các tin gần nhất (cũ trước, mới sau)
        'con_cu': con_cu,  # còn tin cũ hơn để tải thêm không
        'id_dau': tin_nhan[0].pk if tin_nhan else 0,  # mã tin đầu danh sách (mốc để tải tin cũ)
        'id_cuoi': tin_nhan[-1].pk if tin_nhan else 0,  # mã tin cuối danh sách (mốc để polling)
        'nguoi_xem_id': request.user.pk,  # để template biết tin nào là của mình
        'loi_tai': loi_tai,  # thông báo lỗi 2a (nếu có)
        'gioi_han': services.GIOI_HAN_NOI_DUNG,  # số ký tự tối đa mỗi tin
        'url_dang_nhap': resolve_url(settings.LOGIN_URL),  # chat.js dùng khi phiên hết hạn
    })  # hết render


@require_POST  # chỉ nhận POST (form có CSRF)
def gui_tin_nhan(request, ma_cuoc):  # UC8.2: gửi một tin nhắn
    ngam = _la_yeu_cau_ngam(request)  # do chat.js gửi ngầm hay form thường
    if not request.user.is_authenticated:  # phiên đã hết hạn
        if ngam:  # yêu cầu ngầm
            return _het_phien_json()  # trả 401 JSON
        return redirect_to_login(services.duong_dan_cuoc_tro_chuyen(ma_cuoc) or '/')  # form thường: sang đăng nhập
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # người ngoài cuộc bị 404, không ghi được gì
    loi, ma_loi = '', 0  # nội dung lỗi và mã HTTP (0 = không lỗi)
    tin = None  # tin vừa lưu
    try:  # thử lưu tin
        tin = services.gui_tin_nhan(cuoc, request.user, request.POST.get('noi_dung', ''))  # lưu vào lịch sử trao đổi
    except ValidationError as e:  # tin rỗng, quá dài hoặc sai người gửi
        loi, ma_loi = ' '.join(e.messages), 400  # lấy nội dung lỗi đầu tiên cho người dùng đọc
    except DatabaseError:  # luồng ngoại lệ 5a: không lưu được
        loi, ma_loi = services.LOI_GUI_TIN, 500  # thông báo theo đặc tả
    if ngam:  # chat.js gửi ngầm
        if loi:  # có lỗi
            return JsonResponse({'ok': False, 'loi': loi}, status=ma_loi)  # báo lỗi cho chat.js hiện ngay dưới khung nhập
        return JsonResponse({'ok': True, 'id': tin.pk})  # thành công; chat.js sẽ lấy tin về bằng lần polling ngay sau đó
    if loi:  # form thường (không có JavaScript) bị lỗi
        messages.error(request, loi)  # hộp đỏ trên đầu trang
    return redirect('chi_tiet_cuoc_tro_chuyen', ma_cuoc=cuoc.pk)  # quay lại cuộc trò chuyện (đổi trang sau POST, tránh gửi lại khi F5)


@never_cache  # kết quả polling không được lưu đệm
@require_safe  # chỉ GET/HEAD
def tin_nhan_moi(request, ma_cuoc):  # JSON: tin mới (?sau=<id>) hoặc tin cũ hơn (?truoc=<id>)
    if not request.user.is_authenticated:  # phiên đã hết hạn
        return _het_phien_json()  # 401 để chat.js dừng polling
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # chỉ hai người trong cuộc được xem, người ngoài 404
    try:  # đọc tham số trên URL
        sau = int(request.GET['sau']) if 'sau' in request.GET else None  # mã tin cuối trình duyệt đang có
        truoc = int(request.GET['truoc']) if 'truoc' in request.GET else None  # mã tin đầu trình duyệt đang có
    except ValueError:  # không phải số nguyên
        return JsonResponse({'ok': False, 'loi': 'Tham số không hợp lệ.'}, status=400)  # 400
    if (sau is None) == (truoc is None):  # phải có đúng MỘT trong hai tham số
        return JsonResponse({'ok': False, 'loi': 'Tham số không hợp lệ.'}, status=400)  # 400
    try:  # truy vấn tin nhắn
        if sau is not None:  # polling tin mới
            danh_sach, con_cu = services.lay_tin_moi_hon(cuoc, sau), False  # tin mới hơn mốc
        else:  # tải tin cũ khi kéo lên đầu
            danh_sach, con_cu = services.lay_tin_cu_hon(cuoc, truoc)  # tin cũ hơn mốc
    except DatabaseError:  # lỗi bất ngờ (luồng 2a khi đang tải lịch sử)
        return JsonResponse({'ok': False, 'loi': services.LOI_TAI_LICH_SU}, status=500)  # chat.js hiện thông báo
    return JsonResponse({  # trả kết quả
        'ok': True,  # thành công
        'tin_nhan': _dong_goi_tin(danh_sach, request.user),  # các tin, cũ trước mới sau
        'con_cu': con_cu,  # còn tin cũ hơn nữa không (chỉ có nghĩa với ?truoc=)
    })  # hết JsonResponse

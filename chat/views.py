# chat/views.py - P10 (UC8.1) khởi tạo; P11 (UC8.2, UC8.3) hộp thư, gửi tin, lịch sử, polling; nâng cấp bước 1 đến 6: đã xem, chưa đọc, đồng bộ cột trái, ghim, ẩn, xóa cuộc trò chuyện, gửi và xem ảnh, thu hồi và trả lời tin.
import hashlib  # băm nội dung cột trái để biết có thay đổi hay không
import io  # bộ đệm trong bộ nhớ để lưu ảnh thu nhỏ
import os  # lấy đuôi file ảnh
from django.conf import settings  # đọc LOGIN_URL
from django.contrib import messages  # hộp thông báo ngắn trên đầu trang
from django.contrib.auth.decorators import login_required  # bắt buộc đăng nhập cho các trang HTML
from django.contrib.auth.views import redirect_to_login  # chuyển người chưa đăng nhập sang trang đăng nhập, kèm ?next=
from django.core.exceptions import PermissionDenied, ValidationError  # 403: không đủ quyền; ValidationError: dữ liệu không hợp lệ
from django.db import DatabaseError  # lỗi cơ sở dữ liệu bất ngờ
from django.http import FileResponse, Http404, HttpResponse, JsonResponse  # JSON cho JavaScript; trả file ảnh; trả ảnh thu nhỏ
from django.shortcuts import get_object_or_404, redirect, render, resolve_url  # tìm đối tượng; chuyển trang; dựng trang; đổi tên URL thành đường dẫn
from django.template.loader import render_to_string  # dựng một đoạn HTML (một bong bóng tin nhắn) thành chuỗi
from django.urls import reverse  # đổi tên URL thành đường dẫn (địa chỉ xem ảnh)
from PIL import Image, ImageOps  # Pillow: tạo ảnh thu nhỏ, xoay đúng chiều theo EXIF
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
        if services.duoc_dung_tro_chuyen(request.user):  # Nhiếp ảnh gia đã duyệt: chặn nhẹ nhàng, đưa về hộp thư
            messages.error(request, 'Chỉ Khách hàng mới được khởi tạo cuộc trò chuyện.')  # hộp đỏ
            return redirect('inbox')  # về hộp thư của chính mình
        raise PermissionDenied('Chỉ Khách hàng mới được khởi tạo cuộc trò chuyện.')  # Quản trị viên, Nhiếp ảnh gia chưa duyệt: 403
    try:  # luồng ngoại lệ 2a của UC8.1: lỗi bất ngờ khi khởi tạo
        cuoc, da_tao = services.mo_hoac_tao_cuoc_tro_chuyen(request.user, nag)  # mở cuộc cũ hoặc tạo mới
    except (ValidationError, DatabaseError):  # Http404 (chưa duyệt) và 403 không bị bắt ở đây, vẫn giữ nguyên
        ngu_canh = services.ngu_canh_danh_sach(request.user)  # cột trái vẫn hiện đủ danh sách
        ngu_canh.update({'nag': nag, 'doi_phuong': services.thong_tin_nag(nag), 'ho_so': ho_so, 'ma_dang_mo': 0, 'loi_khoi_tao': services.LOI_KHOI_TAO})  # đối phương = Nhiếp ảnh gia vừa bấm
        return render(request, 'chat/loi_khoi_tao.html', ngu_canh, status=500)  # màn hình lỗi theo wireframe, có Thử lại và Quay lại hồ sơ
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


def _dong_goi_tin(danh_sach, nguoi_xem, cuoc):  # đổi danh sách TinNhan thành [{id, html}] để chat.js chèn thẳng vào trang
    doi_phuong = services.thong_tin_doi_phuong(cuoc, nguoi_xem)  # để tin của đối phương có ảnh/chữ cái đầu như khi tải trang
    xoa_den = services.lay_tham_gia(cuoc, nguoi_xem).XoaDenMaTin  # mốc đã xóa phía mình: trích dẫn "trả lời" không được lộ tin đã xóa
    return [  # mỗi tin một phần tử
        {'id': tin.pk, 'html': render_to_string('chat/_tin_nhan.html', {'tin': tin, 'nguoi_xem_id': nguoi_xem.pk, 'doi_phuong': doi_phuong, 'xoa_den': xoa_den}),  # HTML đã được Django tự escape; tin đã thu hồi chỉ có câu thay thế
         'anh': [] if tin.DaThuHoi or services.anh_het_han(tin) else [{'ma': dk.pk, 'url': reverse('xem_anh_chat', args=[dk.pk])} for dk in tin.dinh_kem.all()]}  # ảnh của tin (đã nạp sẵn) cho panel "File phương tiện"; tin đã thu hồi hoặc ảnh quá 6 tháng thì KHÔNG đưa ảnh ra
        for tin in danh_sach  # duyệt từng tin
    ]  # hết danh sách


@login_required  # chưa đăng nhập thì sang trang đăng nhập, kèm ?next=
@require_safe  # chỉ GET/HEAD
def hop_thu(request):  # màn hình danh sách cuộc trò chuyện, menu "Tin nhắn" (url name='inbox')
    if not services.duoc_dung_tro_chuyen(request.user):  # Quản trị viên hoặc Nhiếp ảnh gia chưa được duyệt
        raise PermissionDenied('Bạn không có quyền dùng mục Tin nhắn.')  # 403
    return render(request, 'chat/hop_thu.html', services.ngu_canh_danh_sach(request.user))  # cột trái dùng chung với trang chi tiết


@login_required  # chưa đăng nhập thì sang trang đăng nhập
@require_safe  # chỉ GET/HEAD
def chi_tiet_cuoc_tro_chuyen(request, ma_cuoc):  # SC8.2 + UC8.3: mở cuộc trò chuyện và xem lịch sử
    try:  # người ngoài cuộc và cuộc không tồn tại đều cho CÙNG một kết quả, không lộ cuộc có tồn tại hay không
        cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # người ngoài cuộc bị 404
    except Http404:  # trang 404 riêng của chat
        return render(request, 'chat/khong_tim_thay.html', status=404)  # "Không tìm thấy cuộc trò chuyện" + nút về hộp thư
    tin_nhan, con_cu, loi_tai, anh_chia_se, xoa_den = [], False, '', [], 0  # mặc định: chưa có tin, không còn tin cũ, không lỗi, chưa có ảnh chia sẻ, chưa xóa gì
    try:  # luồng ngoại lệ 2a của UC8.3: không truy xuất được lịch sử
        tham_gia = services.lay_tham_gia(cuoc, request.user)  # trạng thái riêng của mình (đã xóa tới tin nào...)
        tin_nhan, con_cu = services.lay_tin_gan_nhat(cuoc, sau_ma=tham_gia.XoaDenMaTin)  # các tin gần nhất, bỏ phần đã xóa phía mình
        xoa_den = tham_gia.XoaDenMaTin  # mốc đã xóa phía mình, template dùng để che trích dẫn của tin đã xóa
        anh_chia_se = services.lay_anh_chia_se(cuoc, tham_gia.XoaDenMaTin)  # ảnh hiện ở cột phải (bỏ ảnh tin đã thu hồi và phần đã xóa phía mình)
        services.danh_dau_da_xem(cuoc, request.user, tin_nhan[-1].pk if tin_nhan else 0, mo_trang=True)  # mở cuộc = đã xem hết, bỏ dấu "chưa đọc" tự đánh
    except DatabaseError:  # lỗi bất ngờ
        loi_tai = services.LOI_TAI_LICH_SU  # báo lỗi, trang vẫn hiện để người dùng bấm tải lại
    ngu_canh = services.ngu_canh_danh_sach(request.user)  # BẮT BUỘC: cột trái (cac_cuoc, loi, la_khach) giống hộp thư
    ngu_canh.update({  # thêm dữ liệu riêng của trang chi tiết
        'ma_dang_mo': cuoc.pk,  # cuộc đang mở được làm nổi bật ở cột trái
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
        'doi_da_xem': services.doi_phuong_da_xem_toi(cuoc, request.user),  # mốc đối phương đã xem, chat.js hiện "Đã xem"
        'anh_theo_thang': services.nhom_anh_theo_thang(anh_chia_se),  # panel "File phương tiện" ở cột phải: ảnh chia theo tháng, mới nhất trước
        'thoi_han_anh_thang': services.THOI_HAN_ANH_THANG,  # ghi chú "Ảnh được lưu 6 tháng" ở panel

        'xoa_den': xoa_den,  # mốc đã xóa phía mình
        'so_anh_toi_da': services.SO_ANH_TOI_DA,  # chat.js kiểm số ảnh trước khi gửi
    })  # hết cập nhật
    return render(request, 'chat/chi_tiet_cuoc_tro_chuyen.html', ngu_canh)  # dựng trang


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
        tin = services.gui_tin_nhan(cuoc, request.user, request.POST.get('noi_dung', ''), ds_anh=request.FILES.getlist('anh'),
                                  ma_tra_loi=int(request.POST['tra_loi']) if request.POST.get('tra_loi', '').isdigit() else None)  # lưu vào lịch sử trao đổi, kèm ảnh (nếu có) và tin đang trả lời (nếu có)
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
            sau_ma = services.lay_tham_gia(cuoc, request.user).XoaDenMaTin  # phần đã xóa phía mình không tải lại
            danh_sach, con_cu = services.lay_tin_cu_hon(cuoc, truoc, sau_ma=sau_ma)  # tin cũ hơn mốc
        xem = request.GET.get('xem', '')  # chat.js gửi ?xem=<mã tin cuối đang hiện> khi người dùng đang nhìn tab này
        if xem.isdigit():  # chỉ nhận số
            services.danh_dau_da_xem(cuoc, request.user, xem)  # ghi nhận đã xem (chỉ gọi từ chat.js, không phải link người dùng bấm)
        doi_da_xem = services.doi_phuong_da_xem_toi(cuoc, request.user)  # mốc đối phương đã xem
        tu = request.GET.get('tu', '')  # chat.js gửi ?tu=<mã tin đầu đang hiện> để biết tin nào trong khung đã bị thu hồi
        thu_hoi = services.tin_da_thu_hoi(cuoc, int(tu)) if sau is not None and tu.isdigit() else []  # chỉ trả MÃ tin, không trả nội dung
    except DatabaseError:  # lỗi bất ngờ (luồng 2a khi đang tải lịch sử)
        return JsonResponse({'ok': False, 'loi': services.LOI_TAI_LICH_SU}, status=500)  # chat.js hiện thông báo
    return JsonResponse({  # trả kết quả
        'ok': True,  # thành công
        'tin_nhan': _dong_goi_tin(danh_sach, request.user, cuoc),  # các tin, cũ trước mới sau
        'con_cu': con_cu,  # còn tin cũ hơn nữa không (chỉ có nghĩa với ?truoc=)
        'doi_da_xem': doi_da_xem,  # mã tin lớn nhất đối phương đã xem
        'thu_hoi': thu_hoi,  # mã các tin đã thu hồi, chat.js đổi bong bóng tương ứng thành "Tin nhắn đã bị thu hồi"
    })  # hết JsonResponse



@never_cache  # kết quả tìm không được lưu đệm
@require_safe  # chỉ GET/HEAD
def tim_trong_cuoc(request, ma_cuoc):  # bước 7: JSON kết quả tìm từ khóa (?q=) trong cuộc trò chuyện
    if not request.user.is_authenticated:  # phiên đã hết hạn
        return _het_phien_json()  # 401 để chat.js báo hết phiên
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # chỉ hai người trong cuộc được tìm, người ngoài 404
    try:  # truy vấn tìm kiếm
        ket_qua, bi_cat = services.tim_trong_cuoc(cuoc, request.user, request.GET.get('q', ''))  # tin đã thu hồi và phần đã xóa phía mình không bị tìm ra
    except DatabaseError:  # lỗi bất ngờ
        return JsonResponse({'ok': False, 'loi': services.LOI_TIM}, status=500)  # chat.js báo không tìm được
    return JsonResponse({'ok': True, 'ket_qua': ket_qua, 'bi_cat': bi_cat})  # kết quả mới nhất trước, không có nội dung tin ngoài đoạn trích


@never_cache  # kết quả không được lưu đệm
@require_safe  # chỉ GET/HEAD
def tin_nhan_den_tin(request, ma_cuoc):  # bước 7: JSON các tin từ gần tin ?tin= tới trước tin đầu đang hiện ?truoc= (để nhảy tới kết quả tìm ở phần chưa tải)
    if not request.user.is_authenticated:  # phiên đã hết hạn
        return _het_phien_json()  # 401
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # chỉ hai người trong cuộc, người ngoài 404
    try:  # đọc tham số trên URL
        ma_tin = int(request.GET['tin'])  # tin cần tới
        truoc = int(request.GET['truoc'])  # mã tin đầu trình duyệt đang có
    except (KeyError, ValueError):  # thiếu hoặc không phải số
        return JsonResponse({'ok': False, 'loi': 'Tham số không hợp lệ.'}, status=400)  # 400
    if ma_tin >= truoc:  # tin này đã nằm trong phần đang hiện, không cần tải
        return JsonResponse({'ok': False, 'loi': 'Tham số không hợp lệ.'}, status=400)  # 400
    try:  # truy vấn tin
        sau_ma = services.lay_tham_gia(cuoc, request.user).XoaDenMaTin  # phần đã xóa phía mình không tải lại
        danh_sach, con_cu = services.lay_tin_den_tin(cuoc, ma_tin, truoc, sau_ma)  # đoạn liền mạch từ trước tin cần tới
    except DatabaseError:  # lỗi bất ngờ
        return JsonResponse({'ok': False, 'loi': services.LOI_TAI_LICH_SU}, status=500)  # chat.js hiện thông báo
    if danh_sach is None:  # tin nằm quá xa
        return JsonResponse({'ok': False, 'loi': 'Tin nhắn này nằm quá xa. Hãy kéo lên để tải dần các tin cũ hơn.'}, status=422)  # báo cách khác
    return JsonResponse({'ok': True, 'tin_nhan': _dong_goi_tin(danh_sach, request.user, cuoc), 'con_cu': con_cu})  # các tin cũ trước mới sau


KIEU_ANH = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}  # loại nội dung theo đuôi file đã lưu (đuôi do server tự đặt theo định dạng thật)


def _anh_nho(tep):  # đọc ảnh, thu nhỏ còn tối đa 400px, trả về bytes JPEG (cùng cách với xem_anh của delivery)
    with Image.open(tep) as hinh:  # mở ảnh
        hinh = ImageOps.exif_transpose(hinh)  # xoay đúng chiều ảnh chụp bằng điện thoại
        hinh.thumbnail((400, 400))  # thu nhỏ, giữ tỉ lệ
        if hinh.mode in ('RGBA', 'LA') or (hinh.mode == 'P' and 'transparency' in hinh.info):  # PNG/WEBP có nền trong suốt
            hinh = hinh.convert('RGBA')  # đưa về RGBA để lấy kênh trong suốt
            nen = Image.new('RGB', hinh.size, (255, 255, 255))  # nền trắng (JPEG không có trong suốt)
            nen.paste(hinh, mask=hinh.split()[-1])  # dán ảnh lên nền trắng
            hinh = nen
        else:  # ảnh thường
            hinh = hinh.convert('RGB')  # JPEG chỉ nhận RGB
        dem = io.BytesIO()  # bộ đệm
        hinh.save(dem, format='JPEG', quality=82, optimize=True)  # lưu JPEG nhẹ
        return dem.getvalue()  # bytes


@login_required  # chưa đăng nhập thì sang trang đăng nhập
@require_safe  # chỉ GET/HEAD
def xem_anh_chat(request, ma_dinh_kem):  # trả ảnh đính kèm; ?nho=1 là bản 400px. Ảnh nằm ở thư mục riêng nên CHỈ đi qua view này
    dinh_kem, kho = services.mo_anh_chat(request.user, ma_dinh_kem)  # người ngoài cuộc, ảnh đã thu hồi hoặc đã xóa phía mình: 404
    try:  # mở file thật
        tep = kho.open(dinh_kem.DuongDanFile, 'rb')  # file mất thì báo 404
    except OSError:
        raise Http404('Không tìm thấy ảnh.')
    if request.GET.get('nho') == '1':  # bản thu nhỏ cho bong bóng chat và panel
        try:
            noi_dung = _anh_nho(tep)  # tạo ảnh nhỏ tức thời
        except Exception:  # file hỏng
            raise Http404('Không tìm thấy ảnh.')
        finally:
            tep.close()  # đóng file
        phan_hoi = HttpResponse(noi_dung, content_type='image/jpeg')  # ảnh nhỏ luôn là JPEG
    else:  # ảnh đầy đủ (cho trang xem ảnh)
        loai = KIEU_ANH.get(os.path.splitext(dinh_kem.DuongDanFile)[1].lower(), 'application/octet-stream')  # loại theo đuôi file
        phan_hoi = FileResponse(tep, content_type=loai)  # trả file theo luồng
    phan_hoi['Content-Disposition'] = 'inline'  # chỉ xem trên trang, không tự tải xuống
    phan_hoi['Cache-Control'] = 'private, max-age=300'  # chỉ bộ nhớ đệm của riêng trình duyệt, tối đa 5 phút (tải lại trang không phải tạo lại ảnh nhỏ)
    phan_hoi['X-Content-Type-Options'] = 'nosniff'  # trình duyệt không đoán lại loại tệp
    return phan_hoi


@never_cache  # kết quả đồng bộ không được lưu đệm
@require_safe  # chỉ GET/HEAD
def dong_bo_danh_sach(request):  # JSON: HTML mới của cột trái; chat.js gọi vài giây một lần để cột trái tự cập nhật (tin mới, số chưa đọc)
    if not request.user.is_authenticated:  # phiên hết hạn
        return _het_phien_json()  # 401 để chat.js dừng
    if not services.duoc_dung_tro_chuyen(request.user):  # không có quyền dùng Tin nhắn
        return JsonResponse({'ok': False, 'loi': 'Không có quyền.'}, status=403)  # 403
    ma_mo = request.GET.get('mo', '0')  # mã cuộc đang mở (để làm nổi bật)
    chi_an = request.GET.get('an') == '1'  # tab "Đã ẩn": chỉ lấy các cuộc đang bị ẩn
    ngu_canh = services.ngu_canh_danh_sach(request.user, chi_an)  # dữ liệu cột trái, giống lúc tải trang (chi_an=True: danh sách đã ẩn)
    ngu_canh.update({'ma_dang_mo': int(ma_mo) if ma_mo.isdigit() else 0, 'hien_o_giua': request.GET.get('o_giua') == '1'})  # cuộc đang mở và kiểu hiển thị khi danh sách trống
    if ngu_canh['loi']:  # không tải được danh sách: để nguyên cột trái hiện tại, chat.js thử lại lần sau
        return JsonResponse({'ok': False, 'loi': ngu_canh['loi']}, status=500)  # 500
    html = render_to_string('chat/_vung_danh_sach.html', ngu_canh, request=request)  # dựng lại phần danh sách
    dau_van_tay = hashlib.md5(html.encode('utf-8')).hexdigest()  # băm HTML: đổi thì mới cần thay
    if request.GET.get('vt') == dau_van_tay:  # trình duyệt đã có đúng bản này
        return JsonResponse({'ok': True, 'doi': False, 'vt': dau_van_tay})  # khỏi gửi lại HTML
    return JsonResponse({'ok': True, 'doi': True, 'vt': dau_van_tay, 'html': html})  # gửi HTML mới


@require_POST  # chỉ nhận POST (có CSRF)
def doi_chua_doc(request, ma_cuoc):  # nút ba chấm: đánh dấu chưa đọc / đã đọc
    if not request.user.is_authenticated:  # phiên hết hạn
        return _het_phien_json()  # 401
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # người ngoài cuộc bị 404
    try:  # ghi trạng thái
        chua_doc = services.chuyen_danh_dau_chua_doc(cuoc, request.user)  # đổi trạng thái
    except DatabaseError:  # lỗi bất ngờ
        return JsonResponse({'ok': False, 'loi': 'Không thể cập nhật. Vui lòng thử lại.'}, status=500)  # 500
    return JsonResponse({'ok': True, 'chua_doc': chua_doc})  # trạng thái mới


@require_POST  # chỉ nhận POST (có CSRF)
def thu_hoi_tin(request, ma_cuoc, ma_tin):  # thu hồi một tin: chỉ NGƯỜI GỬI, nội dung vẫn giữ trong DB (Quản trị viên xem khi có tranh chấp), trình duyệt không nhận nữa
    if not request.user.is_authenticated:  # phiên hết hạn
        return _het_phien_json()  # 401
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # người ngoài cuộc bị 404
    try:  # đánh dấu thu hồi
        tin = services.thu_hoi_tin(cuoc, request.user, ma_tin)  # kiểm tin thuộc cuộc và do chính mình gửi
    except PermissionDenied:  # tin của người kia
        return JsonResponse({'ok': False, 'loi': 'Chỉ người gửi mới thu hồi được tin nhắn.'}, status=403)  # 403
    except Http404:  # không có tin này trong cuộc
        return JsonResponse({'ok': False, 'loi': 'Không tìm thấy tin nhắn.'}, status=404)  # 404
    except DatabaseError:  # lỗi bất ngờ
        return JsonResponse({'ok': False, 'loi': 'Không thể thu hồi tin nhắn. Vui lòng thử lại.'}, status=500)  # 500
    return JsonResponse({'ok': True, 'id': tin.pk})  # thành công


def _doi_trang_thai_cuoc(request, ma_cuoc, ham):  # khung chung cho Ghim, Ẩn, Xóa: kiểm đăng nhập, lấy cuộc của mình, gọi hàm ở services, trả JSON
    if not request.user.is_authenticated:  # phiên hết hạn
        return _het_phien_json()  # 401
    cuoc = services.lay_cuoc_cua_nguoi_dung(request.user, ma_cuoc)  # người ngoài cuộc bị 404, không đổi được gì
    try:  # ghi trạng thái
        trang_thai = ham(cuoc, request.user)  # chuyen_ghim / chuyen_an / xoa_cuoc_phia_minh, chỉ đổi hàng THAMGIA của CHÍNH MÌNH
    except DatabaseError:  # lỗi bất ngờ
        return JsonResponse({'ok': False, 'loi': 'Không thể cập nhật. Vui lòng thử lại.'}, status=500)  # 500, chat.js hiện thông báo
    return JsonResponse({'ok': True, 'ma': cuoc.pk, 'trang_thai': trang_thai})  # trạng thái mới (ghim: True = đang ghim; ẩn: True = đang ẩn)


@require_POST  # chỉ nhận POST (có CSRF)
def doi_ghim(request, ma_cuoc):  # ba chấm: Ghim lên đầu / Bỏ ghim
    return _doi_trang_thai_cuoc(request, ma_cuoc, services.chuyen_ghim)  # đổi DaGhim, GhimLuc


@require_POST  # chỉ nhận POST (có CSRF)
def doi_an(request, ma_cuoc):  # ba chấm: Ẩn / Bỏ ẩn cuộc trò chuyện
    return _doi_trang_thai_cuoc(request, ma_cuoc, services.chuyen_an)  # đổi DaAn (có tin mới thì tự hiện lại, xem gui_tin_nhan)


@require_POST  # chỉ nhận POST (có CSRF)
def xoa_cuoc(request, ma_cuoc):  # ba chấm: Xóa cuộc trò chuyện, chỉ xóa PHÍA MÌNH
    return _doi_trang_thai_cuoc(request, ma_cuoc, services.xoa_cuoc_phia_minh)  # đặt XoaDenMaTin, người kia vẫn thấy đủ tin

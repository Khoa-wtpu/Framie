# notifications/views.py - P8: UC9.1 Xem thông báo, UC9.2 Đánh dấu thông báo (Phanh)
import logging  # ghi log lỗi ra Terminal thay vì làm sập trang

from django.contrib import messages  # hộp thông báo ngắn trên đầu trang (lỗi hiện màu đỏ nhờ MESSAGE_TAGS)
from django.contrib.auth.decorators import login_required  # bắt buộc đăng nhập
from django.core.paginator import Paginator  # chia danh sách thành từng trang
from django.db import DatabaseError  # lỗi cơ sở dữ liệu
from django.http import HttpResponse, QueryDict  # phản hồi trống kèm mã lỗi (cho khung chuông); QueryDict dựng tham số địa chỉ
from django.shortcuts import get_object_or_404, redirect, render  # tìm 1 dòng hoặc 404; chuyển trang; dựng HTML
from django.urls import reverse  # đổi tên URL thành địa chỉ
from django.utils.http import url_has_allowed_host_and_scheme  # kiểm tra địa chỉ quay lại có an toàn không
from django.views.decorators.cache import never_cache  # không cho trình duyệt lưu khung chuông (luôn lấy bản mới)
from django.views.decorators.http import require_GET, require_POST  # giới hạn cách gọi: chỉ GET hoặc chỉ POST

from notifications import services  # toàn bộ luật nghiệp vụ nằm ở services.py

logger = logging.getLogger(__name__)  # bộ ghi log riêng của file này

dang_nhap_bat_buoc = login_required(login_url='login')  # chưa đăng nhập thì chuyển tới trang có tên URL 'login'

TB_LOI_TAI = 'Không thể tải danh sách thông báo. Vui lòng thử lại.'  # câu cho màn hình Lỗi tải (SC9.1)
TB_LOI_DANH_DAU = 'Không thể cập nhật trạng thái thông báo. Vui lòng thực hiện lại.'  # câu cho Lỗi đánh dấu (SC9.1, SC9.2)
TB_LOI_DA_DOC = 'Không thể cập nhật trạng thái Đã đọc cho thông báo này.'  # câu cho Lỗi cập nhật đã đọc (SC9.2)


def _dia_chi_giu_trang_thai(duong_dan, tham_so=None):  # thêm ?giu=1 vào địa chỉ trang chi tiết để trang KHÔNG tự đánh dấu Đã đọc
    """Dùng khi quay về trang chi tiết sau khi người dùng chủ động đổi trạng thái (lỗi 1 người kiểm tra nêu)."""  # mô tả hàm
    tham_so = tham_so.copy() if tham_so is not None else QueryDict(mutable=True)  # sao chép các tham số đang có (nếu có)
    tham_so['giu'] = '1'  # đánh dấu "giữ nguyên trạng thái, đừng tự đọc"
    return f'{duong_dan}?{tham_so.urlencode()}'  # ví dụ /thong-bao/5/?giu=1


def _trang_quay_lai(request, mac_dinh):  # quyết định sau khi bấm nút POST thì quay về đâu
    """Chỉ nhận địa chỉ cùng website (chặn chuyển hướng sang trang lạ)."""  # mô tả hàm
    dich = request.POST.get('next', '')  # địa chỉ trang đang xem, form gửi kèm
    if dich and url_has_allowed_host_and_scheme(  # kiểm tra địa chỉ có thuộc cùng website không
            dich, allowed_hosts={request.get_host()}, require_https=request.is_secure()):  # chỉ cho phép đúng tên miền hiện tại
        return dich  # an toàn thì quay về đúng trang cũ (giữ nguyên bộ lọc, số trang)
    return mac_dinh  # không hợp lệ thì dùng địa chỉ mặc định


@dang_nhap_bat_buoc  # phải đăng nhập
@require_GET  # trang xem chỉ nhận GET
def danh_sach(request):  # SC9.1 Danh sách thông báo
    """UC9.1 bước 1 đến 3: danh sách của người đang đăng nhập, có nhóm lọc, tìm kiếm, phân trang."""  # mô tả hàm
    loc = services.chuan_hoa_loc(request.GET.get('loc'))  # nhóm đang chọn (Tất cả / Chưa đọc / Đã đánh dấu sao)
    tu_khoa = (request.GET.get('q') or '').strip()[:services.DO_DAI_TU_KHOA_TOI_DA]  # từ khóa tìm kiếm đã làm sạch
    ngu_canh = {  # dữ liệu chung gửi sang template
        'loc': loc,  # nhóm đang chọn
        'q': tu_khoa,  # từ khóa đang tìm
        'ten_nhom': services.NHAN_NHOM[loc],  # tên nhóm hiện ở tiêu đề, ví dụ "Chưa đọc"
        'loi_tai': False,  # mặc định: tải thành công
        'khong_co_gi': False,  # mặc định: người dùng có thông báo
        'cac_nhom': [],  # danh sách nhóm cho menu "Lọc thông báo"
        'page_obj': None,  # trang hiện tại (điền bên dưới)
    }  # hết ngữ cảnh gốc
    try:  # thử truy xuất; lỗi DB thì hiện màn hình Lỗi tải
        so_nhom = services.dem_theo_nhom(request.user)  # đếm 3 nhóm (1 câu truy vấn)
        trang = Paginator(services.lay_danh_sach(request.user, loc, tu_khoa), services.SO_DONG_MOI_TRANG)  # chia 10 dòng một trang
        page_obj = trang.get_page(request.GET.get('page'))  # lấy trang ?page=..., số lạ thì tự về trang hợp lệ
        page_obj.object_list = list(page_obj.object_list)  # chạy truy vấn ngay trong try để bắt lỗi DB tại đây
    except DatabaseError:  # lỗi cơ sở dữ liệu
        logger.exception('thong_bao: tải danh sách thất bại')  # ghi log
        ngu_canh['loi_tai'] = True  # bật màn hình Lỗi tải
        messages.error(request, TB_LOI_TAI)  # hộp đỏ trên đầu trang (đúng wireframe Lỗi tải)
        return render(request, 'notifications/danh_sach.html', ngu_canh)  # dựng trang lỗi, vẫn mã 200 để có nút "Thử lại"
    ngu_canh['cac_nhom'] = [  # dựng menu lọc: mỗi nhóm gồm khóa, nhãn, số lượng
        {'khoa': khoa, 'nhan': nhan, 'so': so_nhom[khoa]} for khoa, nhan in services.NHAN_NHOM.items()  # theo đúng thứ tự trong NHAN_NHOM
    ]  # hết danh sách nhóm
    ngu_canh['khong_co_gi'] = so_nhom[services.LOC_TAT_CA] == 0  # người dùng chưa từng có thông báo nào (màn hình Rỗng)
    ngu_canh['page_obj'] = page_obj  # trang hiện tại
    ngu_canh['so_trong_nhom'] = page_obj.paginator.count  # số thông báo khớp bộ lọc, hiện cạnh tiêu đề nhóm
    ngu_canh['quay_lai'] = request.get_full_path()  # địa chỉ trang này, để các nút POST quay về đúng chỗ
    return render(request, 'notifications/danh_sach.html', ngu_canh)  # dựng trang


@dang_nhap_bat_buoc  # phải đăng nhập
@require_GET  # trang xem chỉ nhận GET
def chi_tiet(request, ma_thong_bao):  # SC9.2 Chi tiết thông báo
    """UC9.1 bước 4 đến 5 và UC9.2 bước 6: xem chi tiết, tự chuyển Chưa đọc sang Đã đọc."""  # mô tả hàm
    thong_bao = get_object_or_404(services.queryset_chi_tiet(request.user), pk=ma_thong_bao)  # của người khác hoặc không có thì 404
    if request.GET.get('giu'):  # người dùng vừa chủ động đổi trạng thái (nút ở trang này) nên KHÔNG tự đánh dấu Đã đọc
        da_cap_nhat = True  # không có gì cần cập nhật, nên không hiện hộp lỗi
    else:  # mở từ danh sách hoặc từ chuông
        da_cap_nhat = services.tu_dong_danh_dau_da_doc(request.user, thong_bao)  # tự chuyển sang Đã đọc
    return render(request, 'notifications/chi_tiet.html', {  # dựng trang chi tiết
        'tb': thong_bao,  # thông báo đang xem
        'booking': thong_bao.MaBooking,  # Booking liên quan (None nếu không gắn)
        'url_booking': services.url_booking(thong_bao, request.user),  # link nút "Xem Booking" (None, '#' hoặc địa chỉ thật)
        'loi_cap_nhat_doc': not da_cap_nhat,  # True thì hiện hộp "Lỗi cập nhật đã đọc"
        'TB_LOI_DA_DOC': TB_LOI_DA_DOC,  # câu hiển thị trong hộp lỗi đó
        'quay_lai': _dia_chi_giu_trang_thai(request.path, request.GET),  # các nút POST quay về lại trang này, kèm giu=1
    })  # hết render


def _ket_qua_doi_trang_thai(request, thanh_cong, mac_dinh):  # phần kết thúc chung của 2 view POST bên dưới
    if not thanh_cong:  # cập nhật không thành công
        messages.error(request, TB_LOI_DANH_DAU)  # hộp đỏ "Cập nhật không thành công" ở trang quay về
    return redirect(_trang_quay_lai(request, mac_dinh))  # quay về trang cũ (hoặc trang mặc định)


@dang_nhap_bat_buoc  # phải đăng nhập
@require_POST  # CHỈ nhận POST (kèm csrf_token) nên không đổi trạng thái được bằng cách mở link
def doi_trang_thai_doc(request, ma_thong_bao):  # nút "Đánh dấu đã đọc" / "Đánh dấu chưa đọc"
    """UC9.2: nhận gia_tri = 'da_doc' hoặc 'chua_doc'."""  # mô tả hàm
    thong_bao = get_object_or_404(services.thong_bao_cua(request.user), pk=ma_thong_bao)  # thông báo của người khác thì 404
    gia_tri = request.POST.get('gia_tri')  # giá trị đích do form gửi
    mac_dinh = _dia_chi_giu_trang_thai(reverse('chi_tiet_thong_bao', args=[thong_bao.pk]))  # không có địa chỉ quay lại thì về trang chi tiết (kèm giu=1)
    if gia_tri not in ('da_doc', 'chua_doc'):  # giá trị lạ (bị sửa tay)
        return _ket_qua_doi_trang_thai(request, False, mac_dinh)  # coi như thất bại
    thanh_cong = services.dat_trang_thai_doc(request.user, thong_bao.pk, gia_tri == 'da_doc')  # ghi vào DB
    return _ket_qua_doi_trang_thai(request, thanh_cong, mac_dinh)  # báo lỗi nếu có rồi quay lại


@dang_nhap_bat_buoc  # phải đăng nhập
@require_POST  # chỉ nhận POST
def doi_dau_sao(request, ma_thong_bao):  # nút ★ và mục "Đánh dấu sao" / "Bỏ đánh dấu sao"
    """UC9.2: nhận gia_tri = 'co' (gắn sao) hoặc 'khong' (bỏ sao)."""  # mô tả hàm
    thong_bao = get_object_or_404(services.thong_bao_cua(request.user), pk=ma_thong_bao)  # thông báo của người khác thì 404
    gia_tri = request.POST.get('gia_tri')  # giá trị đích do form gửi
    mac_dinh = _dia_chi_giu_trang_thai(reverse('chi_tiet_thong_bao', args=[thong_bao.pk]))  # không có địa chỉ quay lại thì về trang chi tiết (kèm giu=1)
    if gia_tri not in ('co', 'khong'):  # giá trị lạ
        return _ket_qua_doi_trang_thai(request, False, mac_dinh)  # coi như thất bại
    thanh_cong = services.dat_dau_sao(request.user, thong_bao.pk, gia_tri == 'co')  # ghi vào DB
    return _ket_qua_doi_trang_thai(request, thanh_cong, mac_dinh)  # báo lỗi nếu có rồi quay lại


@never_cache  # luôn lấy bản mới nhất, không dùng bản lưu của trình duyệt
@require_GET  # chỉ nhận GET
def khung_thong_bao(request):  # mảnh HTML cho khung chuông thả xuống (chỉ tải khi bấm chuông)
    """Trả 401 nếu chưa đăng nhập (không chuyển sang trang đăng nhập, vì mảnh này do JS gọi)."""  # mô tả hàm
    if not request.user.is_authenticated:  # chưa đăng nhập
        return HttpResponse(status=401)  # báo 401 để JS hiện lỗi gọn
    try:  # thử lấy dữ liệu
        ds = services.lay_moi_nhat(request.user)  # 4 thông báo mới nhất
        so_chua_doc = services.dem_chua_doc(request.user)  # số chưa đọc cho nhãn "N chưa đọc"
    except DatabaseError:  # lỗi cơ sở dữ liệu
        logger.exception('thong_bao: tải khung chuông thất bại')  # ghi log
        return HttpResponse(status=500)  # JS sẽ hiện "Không thể tải thông báo" kèm nút Thử lại
    return render(request, 'notifications/_khung_chuong.html', {'ds': ds, 'so_chua_doc': so_chua_doc})  # dựng mảnh HTML

# =====================================================================
# accounts/views_quan_tri.py  -  B7: trang tổng quan khu Quản trị; P7: quản lý tài khoản và vai trò
# =====================================================================
from django.contrib import messages  # thông báo ngắn hiện ở đầu trang (includes/messages.html)
from django.contrib.auth import get_user_model  # lấy class User của dự án
from django.core.paginator import Paginator  # chia danh sách thành nhiều trang
from django.shortcuts import get_object_or_404, redirect, render  # tìm 1 dòng hoặc báo 404; chuyển trang; hiện template
from django.urls import reverse  # đổi tên URL thành đường dẫn
from django.utils.http import url_has_allowed_host_and_scheme  # kiểm tra đường dẫn quay lại có an toàn không
from django.views.decorators.http import require_POST  # chỉ nhận phương thức POST (GET trả lỗi 405)

from core.constants import VaiTro  # tên 3 vai trò
from core.navigation import resolve  # đổi tên URL thành đường dẫn (chưa có thì "#")

from . import quan_ly_tai_khoan as ql  # P7: luật nghiệp vụ đổi vai trò, khóa/mở
from .permissions import chi_quan_tri_vien  # decorator: chỉ Quản trị viên được vào (người khác bị 403)
from .quan_tri import thong_ke_tong_quan  # hàm tính số liệu

User = get_user_model()  # class User của dự án
SO_DONG_MOI_TRANG = 20  # mỗi trang hiện tối đa 20 tài khoản


@chi_quan_tri_vien  # chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403
def tong_quan(request):  # trang tổng quan /quan-tri/
    boi_canh = {  # dữ liệu gửi sang template
        'thong_ke': thong_ke_tong_quan(),  # các con số
        'url_duyet_ho_so': resolve('admin_profile_review'),  # link nút "Duyệt hồ sơ" (có thể là "#")
        'url_tai_khoan': reverse('admin_accounts'),  # link nút "Xem tài khoản" ở thẻ Tổng tài khoản
        'url_booking': resolve('admin_bookings'),  # link nút "Xem Booking" (có thể là "#")
    }  # hết dict
    return render(request, 'accounts/quan_tri/tong_quan.html', boi_canh)  # hiện trang


@chi_quan_tri_vien  # chỉ Quản trị viên xem được danh sách tài khoản
def danh_sach_tai_khoan(request):  # P7: trang /quan-tri/tai-khoan/
    tim = request.GET.get('q', '').strip()  # từ khóa tìm kiếm (tên, email, số điện thoại)
    vai_tro = request.GET.get('vai_tro', '')  # bộ lọc vai trò ('' = tất cả)
    trang_thai = request.GET.get('trang_thai', '')  # bộ lọc trạng thái ('' = tất cả)
    ds = ql.danh_sach_tai_khoan(tim, vai_tro, trang_thai)  # QuerySet đã lọc
    page_obj = Paginator(ds, SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))  # trang hiện tại; tên page_obj và tham số page khớp includes/pagination.html; get_page tự xử lý số trang sai
    boi_canh = {  # dữ liệu gửi sang template
        'hang': [ql.mo_ta_tai_khoan(request.user, u) for u in page_obj],  # mỗi tài khoản kèm thông tin được phép làm gì
        'page_obj': page_obj,  # đối tượng trang, includes/pagination.html đọc biến này để vẽ thanh chuyển trang
        'tim': tim, 'vai_tro_loc': vai_tro, 'trang_thai_loc': trang_thai,  # giữ lại giá trị trên các ô lọc
        'cac_vai_tro': (VaiTro.KHACH_HANG, VaiTro.NHIEP_ANH_GIA, VaiTro.QUAN_TRI_VIEN),  # lựa chọn của ô lọc vai trò
        'vai_tro_cho_doi': ql.VAI_TRO_CHO_DOI,  # lựa chọn của ô đổi vai trò từng dòng
        'quay_lai': request.get_full_path(),  # sau khi đổi/khóa thì quay lại đúng trang và bộ lọc này
    }  # hết dict
    return render(request, 'accounts/quan_tri/tai_khoan.html', boi_canh)  # hiện trang


def _trang_quay_lai(request):  # đường dẫn quay lại sau khi xử lý POST
    dich = request.POST.get('quay_lai', '')  # đường dẫn do form gửi lên
    if dich and url_has_allowed_host_and_scheme(dich, allowed_hosts={request.get_host()}):  # chỉ chấp nhận đường dẫn cùng website (chống chuyển hướng ra trang lạ)
        return dich  # an toàn thì dùng
    return reverse('admin_accounts')  # không thì về danh sách


@chi_quan_tri_vien  # lớp 1: chỉ Quản trị viên (người khác bị 403 kể cả khi tự gửi POST)
@require_POST  # lớp 2: chỉ nhận POST (đổi dữ liệu không được làm bằng link GET)
def doi_vai_tro(request, pk):  # P7: đổi vai trò của tài khoản có khóa chính pk
    user = get_object_or_404(User, pk=pk)  # không có tài khoản này thì trả 404
    try:  # bọc lại để bắt lỗi nghiệp vụ
        ql.doi_vai_tro(request.user, user, request.POST.get('vai_tro', ''))  # gọi luật nghiệp vụ
    except ql.LoiQuanLyTaiKhoan as loi:  # sai luật
        messages.error(request, str(loi))  # hiện câu lỗi tiếng Việt ở đầu trang
    else:  # đổi thành công
        messages.success(request, f'Đã đổi vai trò của {user.email} thành {request.POST.get("vai_tro")}.')  # báo thành công
    return redirect(_trang_quay_lai(request))  # quay lại danh sách (kiểu POST-redirect-GET, F5 không gửi lại form)


@chi_quan_tri_vien  # lớp 1: chỉ Quản trị viên
@require_POST  # lớp 2: chỉ nhận POST
def khoa_mo_tai_khoan(request, pk):  # P7: khóa hoặc mở tài khoản có khóa chính pk
    user = get_object_or_404(User, pk=pk)  # không có thì 404
    hanh_dong = request.POST.get('hanh_dong', '')  # form gửi hanh_dong=khoa hoặc hanh_dong=mo
    if hanh_dong not in ('khoa', 'mo'):  # thiếu, rỗng, gõ sai hoặc form bị sửa: không đoán là mở khóa
        messages.error(request, 'Thao tác không hợp lệ.')  # báo lỗi
        return redirect(_trang_quay_lai(request))  # quay lại, không gọi hàm nghiệp vụ
    khoa = hanh_dong == 'khoa'  # đến đây chắc chắn là khoa hoặc mo
    try:  # bọc lại để bắt lỗi nghiệp vụ
        ql.khoa_mo_tai_khoan(request.user, user, khoa)  # gọi luật nghiệp vụ
    except ql.LoiQuanLyTaiKhoan as loi:  # sai luật
        messages.error(request, str(loi))  # hiện câu lỗi
    else:  # thành công
        messages.success(request, f'Đã {"khóa" if khoa else "mở"} tài khoản {user.email}.')  # báo thành công
    return redirect(_trang_quay_lai(request))  # quay lại danh sách

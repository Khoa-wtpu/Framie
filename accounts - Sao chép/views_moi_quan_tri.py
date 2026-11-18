# =====================================================================
# accounts/views_moi_quan_tri.py  -  Quản trị viên mời Quản trị viên mới bằng link có chữ ký
#   moi_quan_tri_vien: admin nhập email  ->  gửi mail chứa link
#   dang_ky_quan_tri : người được mời mở link  ->  form đăng ký (email bị khóa)
# =====================================================================
from django.contrib import messages  # thông báo ngắn hiện ở đầu trang kế tiếp
from django.contrib.auth import get_user_model  # lấy class User của dự án
from django.db import IntegrityError  # lỗi trùng email/SĐT do hai người đăng ký cùng lúc
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template
from django.urls import reverse  # đổi tên URL thành đường dẫn
from django.db.models import Q  # ghép điều kiện "hoặc" khi kiểm tra link đã dùng

from core.constants import VaiTro  # tên vai trò, không tự gõ chữ

from .forms import DangKyQuanTriForm, MoiQuanTriForm  # form mời (admin) và form đăng ký (người được mời)
from .permissions import chi_quan_tri_vien, url_trang_chu  # chỉ Quản trị viên được mời; đã đăng nhập thì chuyển đi
from .services import (  # hàm token + gửi mail + tạo tài khoản
    HIEU_LUC_LOI_MOI_QTV, LoiMoiQuanTriKhongHopLe, doc_token_loi_moi_qtv,
    gui_email_loi_moi_qtv, tao_token_loi_moi_qtv, tao_tai_khoan,
)

User = get_user_model()  # class User của dự án


@chi_quan_tri_vien  # chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403 (kể cả khi tự gõ đường dẫn)
def moi_quan_tri_vien(request):  # trang /quan-tri/tai-khoan/moi-quan-tri/
    form = MoiQuanTriForm(request.POST) if request.method == 'POST' else MoiQuanTriForm()  # POST: form có dữ liệu; GET: form trống
    link_gui_tay = None  # chỉ có giá trị khi gửi mail lỗi: admin copy link này gửi tay
    if request.method == 'POST' and form.is_valid():  # bấm Gửi lời mời và email hợp lệ
        email = form.cleaned_data['email']  # email đã làm sạch (chữ thường, chưa có tài khoản)
        link = request.build_absolute_uri(reverse('register_admin', args=[tao_token_loi_moi_qtv(email)]))  # link tuyệt đối để dán vào email
        if gui_email_loi_moi_qtv(email, link, request.user):  # gửi được
            messages.success(request, f'Đã gửi lời mời làm Quản trị viên tới {email}.')  # báo ở trang kế tiếp
            return redirect('admin_accounts')  # về danh sách tài khoản (POST-redirect-GET)
        link_gui_tay = link  # gửi lỗi: giữ link để hiện ra
        messages.warning(request, 'Chưa gửi được email. Bạn có thể copy link bên dưới và gửi trực tiếp cho người được mời.')  # báo nhẹ
    return render(request, 'accounts/quan_tri/moi_quan_tri.html', {  # hiện trang
        'form': form,  # form mời
        'link_gui_tay': link_gui_tay,  # None nếu không cần
        'gio_hieu_luc': int(HIEU_LUC_LOI_MOI_QTV.total_seconds() // 3600),  # số giờ hiệu lực hiển thị cạnh link
    })  # hết dict


def dang_ky_quan_tri(request, token):  # trang /dang-ky/quan-tri/<token>/ (công khai, an toàn nhờ chữ ký)
    if request.user.is_authenticated:  # đã đăng nhập rồi thì không cần đăng ký
        return redirect(url_trang_chu(request.user))  # chuyển theo vai trò
    try:  # kiểm tra chữ ký và hạn
        email = doc_token_loi_moi_qtv(token)  # email người được mời
    except LoiMoiQuanTriKhongHopLe as loi:  # link sai hoặc hết hạn
        return render(request, 'accounts/dang_ky_quan_tri.html', {'loi_link': str(loi)}, status=400)  # báo lỗi rõ ràng, không hiện form
    if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():  # email đã có tài khoản = lời mời đã dùng (link chỉ dùng một lần)
        return render(request, 'accounts/dang_ky_quan_tri.html', {'loi_link': 'Link mời này đã được sử dụng. Vui lòng đăng nhập bằng email được mời.'}, status=400)  # báo đã dùng

    form = DangKyQuanTriForm(request.POST, email=email) if request.method == 'POST' else DangKyQuanTriForm(email=email)  # email lấy từ token, KHÔNG lấy từ dữ liệu gửi lên
    if request.method == 'POST' and form.is_valid():  # bấm Đăng ký và mọi ô hợp lệ
        d = form.cleaned_data  # dữ liệu đã kiểm tra
        try:  # thử tạo tài khoản
            tao_tai_khoan(d['ho_ten'], email, d['so_dien_thoai'], d['mat_khau'], vai_tro=VaiTro.QUAN_TRI_VIEN)  # dùng lại hàm chung: băm mật khẩu, gán nhóm Quản trị viên
        except IntegrityError:  # hiếm: giữa lúc kiểm tra và lưu, người khác vừa đăng ký trùng
            form.add_error(None, 'Email hoặc số điện thoại vừa được đăng ký bởi người khác. Vui lòng kiểm tra lại.')  # báo lỗi chung
        else:  # tạo thành công
            messages.success(request, 'Tạo tài khoản Quản trị viên thành công. Vui lòng đăng nhập để tiếp tục.')  # báo ở trang đăng nhập
            return redirect('login')  # sang trang đăng nhập
    return render(request, 'accounts/dang_ky_quan_tri.html', {'form': form})  # GET hoặc form còn lỗi

from django.contrib import messages  # gửi thông báo ngắn hiện ở đầu trang (includes/messages.html)
from django.contrib.auth import logout  # hàm đăng xuất: xóa phiên làm việc
from django.contrib.auth.decorators import login_required  # chặn người chưa đăng nhập
from django.contrib.auth.views import LoginView  # view đăng nhập mẫu của Django
from django.db import IntegrityError  # lỗi khi hai người đăng ký trùng email/số điện thoại cùng một lúc
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template
from django.urls import reverse  # đổi tên URL thành đường dẫn

from core.constants import VaiTro  # tên 3 vai trò

from .forms import DangKyForm, DangNhapForm  # form đăng ký (P4) và form đăng nhập (P3)
from .permissions import lay_vai_tro, url_trang_chu, vai_tro_required  # công cụ kiểm tra quyền
from .services import gui_email_dang_ky_thanh_cong, tao_tai_khoan  # tạo tài khoản và gửi email (P4)


class DangNhapView(LoginView):  # trang đăng nhập (UC7.2)
    template_name = 'accounts/dang_nhap.html'  # file giao diện
    authentication_form = DangNhapForm  # dùng form email + mật khẩu của ta
    redirect_authenticated_user = True  # đã đăng nhập rồi mà vào /dang-nhap/ thì chuyển đi luôn

    def get_default_redirect_url(self):  # trang đến khi URL không có ?next=
        return url_trang_chu(self.request.user)  # chuyển theo vai trò

    def form_valid(self, form):  # chạy khi email và mật khẩu đúng
        response = super().form_valid(form)  # Django thực hiện đăng nhập và tạo phản hồi chuyển trang
        user = form.get_user()  # tài khoản vừa đăng nhập
        messages.success(self.request, f'Xin chào, {user.get_full_name() or user.email}.')  # lời chào ở đầu trang kế tiếp
        return response  # trả phản hồi chuyển trang


def dang_ky(request):  # P4: trang đăng ký Khách hàng (UC7.1a)
    if request.user.is_authenticated:  # đã đăng nhập rồi thì không cần đăng ký nữa
        return redirect(url_trang_chu(request.user))  # chuyển về trang theo vai trò, giống trang đăng nhập
    form = DangKyForm(request.POST) if request.method == 'POST' else DangKyForm()  # POST: form có dữ liệu người dùng; GET: form trống
    if request.method == 'POST' and form.is_valid():  # người dùng bấm Đăng ký và mọi ô hợp lệ
        d = form.cleaned_data  # dữ liệu đã kiểm tra và làm sạch
        try:  # thử tạo tài khoản
            user = tao_tai_khoan(d['ho_ten'], d['email'], d['so_dien_thoai'], d['mat_khau'])  # vai trò mặc định là Khách hàng, nhóm được gán ngay
        except IntegrityError:  # hiếm: giữa lúc kiểm tra và lưu, người khác vừa đăng ký trùng
            form.add_error(None, 'Email hoặc số điện thoại vừa được đăng ký bởi người khác. Vui lòng kiểm tra lại.')  # báo lỗi chung ở đầu form
        else:  # tạo thành công
            da_gui = gui_email_dang_ky_thanh_cong(user, request.build_absolute_uri(reverse('login')))  # True nếu gửi được, False nếu lỗi
            messages.success(request, 'Đăng ký thành công. Vui lòng đăng nhập để tiếp tục.')  # tài khoản đã tạo xong dù email có gửi được hay không
            if not da_gui:  # email gửi lỗi (mất mạng, sai mật khẩu SMTP...)
                messages.warning(request, 'Tài khoản đã được tạo nhưng chưa gửi được email xác nhận.')  # báo nhẹ, không làm hỏng đăng ký
            return redirect('login')  # chuyển sang trang đăng nhập
    return render(request, 'accounts/dang_ky.html', {'form': form})  # GET hoặc form còn lỗi: hiện lại trang kèm thông báo lỗi


@login_required  # phải đăng nhập mới được xác nhận đăng xuất
def xac_nhan_dang_xuat(request):  # SC7.5: trang hỏi trước khi đăng xuất (UC7.4)
    if request.method == 'POST':  # người dùng đã bấm nút xác nhận
        logout(request)  # xóa phiên đăng nhập
        messages.success(request, 'Bạn đã đăng xuất.')  # báo cho người dùng biết
        return redirect('login')  # về trang đăng nhập
    return render(request, 'accounts/dang_xuat.html')  # GET: chỉ hiện câu hỏi xác nhận, chưa đăng xuất


@login_required  # trang tạm cho tài khoản chưa có trang riêng
def trang_tam(request):  # TẠM: xóa khi các trang theo vai trò đã có đủ
    return render(request, 'accounts/trang_tam.html', {'vai_tro': lay_vai_tro(request.user)})  # hiện vai trò hiện tại


# ---- 3 trang THỬ QUYỀN: chỉ để test P3, xóa khi gộp bản cuối ----
@vai_tro_required(VaiTro.KHACH_HANG)  # chỉ Khách hàng được vào
def thu_khach_hang(request):  # trang thử 1
    return render(request, 'accounts/trang_tam.html', {'vai_tro': 'TRANG THỬ: dành cho Khách hàng'})  # hiện nhãn


@vai_tro_required(VaiTro.NHIEP_ANH_GIA)  # chỉ Nhiếp ảnh gia được vào
def thu_nhiep_anh_gia(request):  # trang thử 2
    return render(request, 'accounts/trang_tam.html', {'vai_tro': 'TRANG THỬ: dành cho Nhiếp ảnh gia'})  # hiện nhãn


@vai_tro_required(VaiTro.QUAN_TRI_VIEN)  # chỉ Quản trị viên được vào
def thu_quan_tri(request):  # trang thử 3
    return render(request, 'accounts/trang_tam.html', {'vai_tro': 'TRANG THỬ: dành cho Quản trị viên'})  # hiện nhãn

from django.contrib import messages  # gửi thông báo ngắn hiện ở đầu trang (includes/messages.html)
from django.contrib.auth import logout  # hàm đăng xuất: xóa phiên làm việc
from django.contrib.auth.decorators import login_required  # chặn người chưa đăng nhập
from django.contrib.auth.views import LoginView  # view đăng nhập mẫu của Django
from django.db import IntegrityError, transaction  # SỬA: thêm transaction để gom nhiều thao tác DB thành một khối, lỗi thì hoàn tác hết
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template
from django.urls import reverse  # đổi tên URL thành đường dẫn

from core.constants import TrangThaiHoSo, VaiTro  # SỬA: thêm TrangThaiHoSo để dùng trạng thái "Chờ duyệt"

from .forms import DangKyForm, DangNhapForm  # form đăng ký (P4) và form đăng nhập (P3)
from .permissions import lay_vai_tro, url_trang_chu, vai_tro_required  # công cụ kiểm tra quyền
from .services import gui_email_dang_ky_thanh_cong, tao_tai_khoan  # tạo tài khoản và gửi email (P4)
from profiles.forms import NhiepAnhGiaForm  # MỚI: form hồ sơ Nhiếp ảnh gia của Khoa (P5)

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

class HoSoKhongHopLe(Exception):  # lỗi tự đặt, chỉ để "ném" ra khỏi khối atomic nhằm hoàn tác việc tạo User
    pass  # không cần thêm gì, chỉ cần có tên


def dang_ky_nhiep_anh_gia(request):  # P5: trang đăng ký Nhiếp ảnh gia (UC7.1b)
    if request.user.is_authenticated:  # đã đăng nhập rồi thì không cần đăng ký nữa
        return redirect(url_trang_chu(request.user))  # chuyển về trang theo vai trò, giống dang_ky của Khách hàng

    if request.method != 'POST':  # lần đầu mở trang (GET): chỉ hiện form trống
        return render(request, 'accounts/dang_ky_nhiep_anh_gia.html', {  # hiện template
            'form_tai_khoan': DangKyForm(),  # form tài khoản (họ tên, email, SĐT, mật khẩu) của Phanh, trống
            'form': NhiepAnhGiaForm(user=None),  # form hồ sơ của Khoa, trống; PHẢI tên "form" vì 2 file include của Khoa đọc biến này
        })  # hết dict

    form_tai_khoan = DangKyForm(request.POST)  # form tài khoản chứa dữ liệu người dùng vừa gửi
    form = None  # form hồ sơ: chưa tạo được vì nó cần User, nên tạm để trống

    if form_tai_khoan.is_valid():  # bước 1: phần tài khoản hợp lệ thì mới tạo User
        d = form_tai_khoan.cleaned_data  # dữ liệu tài khoản đã kiểm tra và làm sạch
        try:  # bọc lại để bắt 2 loại lỗi bên dưới
            with transaction.atomic():  # từ dòng này, lỗi ở đâu thì hoàn tác TẤT CẢ (kể cả User vừa tạo)
                user = tao_tai_khoan(  # dùng lại đúng hàm của P4 (đã tự gán nhóm)
                    d['ho_ten'], d['email'], d['so_dien_thoai'], d['mat_khau'],  # 4 thông tin tài khoản
                    vai_tro=VaiTro.NHIEP_ANH_GIA,  # gán nhóm Nhiếp ảnh gia TRƯỚC khi tạo form hồ sơ (theo dặn của Khoa)
                    trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET,  # cột trang_thai_ho_so của User = "Chờ duyệt"
                )  # hết tạo User
                form = NhiepAnhGiaForm(request.POST, request.FILES, user=user)  # nhận cả chữ (POST) lẫn file (FILES: ảnh đại diện, QR)
                if not form.is_valid():  # hồ sơ sai (thiếu loại hình, sai số tài khoản...)
                    raise HoSoKhongHopLe  # ném lỗi để atomic hoàn tác: không sót tài khoản mồ côi
                form.save()  # form tự lưu hồ sơ, 3 nhóm, lượt duyệt và gửi thông báo Quản trị viên (KHÔNG gọi thêm gì nữa)
        except HoSoKhongHopLe:  # hồ sơ lỗi: User đã bị hoàn tác, form giữ nguyên các lỗi
            pass  # rơi xuống dòng render ở cuối hàm để hiện lỗi
        except IntegrityError:  # hiếm: có người đăng ký trùng email/SĐT đúng lúc này
            form_tai_khoan.add_error(None, 'Email hoặc số điện thoại vừa được đăng ký bởi người khác. Vui lòng kiểm tra lại.')  # báo lỗi chung ở đầu form
        else:  # không có lỗi nào: User và hồ sơ đã lưu xong
            messages.success(request, 'Đăng ký thành công. Hồ sơ của bạn đang chờ Quản trị viên duyệt. Vui lòng đăng nhập để theo dõi hồ sơ.')  # lời báo ở trang kế tiếp
            return redirect('login')  # chuyển sang trang đăng nhập, giống luồng Khách hàng

    if form is None:  # chưa tạo được form hồ sơ (do form tài khoản lỗi, hoặc lỗi trùng ở bước tạo User)
        form = NhiepAnhGiaForm(request.POST, request.FILES, user=None)  # dựng lại từ dữ liệu đã gửi để người dùng không phải gõ lại chữ
    return render(request, 'accounts/dang_ky_nhiep_anh_gia.html', {  # hiện lại trang kèm thông báo lỗi
        'form_tai_khoan': form_tai_khoan,  # form tài khoản (có lỗi nếu có)
        'form': form,  # form hồ sơ (có lỗi nếu có)
    })  # hết dict

from django.contrib import messages  # gửi thông báo ngắn hiện ở đầu trang (includes/messages.html)
from django.contrib.auth import logout  # hàm đăng xuất: xóa phiên làm việc
from django.contrib.auth.decorators import login_required  # chặn người chưa đăng nhập
from django.contrib.auth.views import LoginView  # view đăng nhập mẫu của Django
from django.core.exceptions import NON_FIELD_ERRORS  # tên khóa chứa lỗi chung (không thuộc ô nào) trong form.errors
from django.db import IntegrityError, transaction  # transaction: gom nhiều thao tác DB thành một khối, lỗi thì hoàn tác hết
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template
from django.urls import reverse  # đổi tên URL thành đường dẫn

from core.constants import TrangThaiHoSo, VaiTro  # TrangThaiHoSo: trạng thái "Chờ duyệt"

from .forms import DangKyForm, DangNhapForm  # form đăng ký (P4) và form đăng nhập (P3)
from .permissions import lay_vai_tro, url_trang_chu, vai_tro_required  # công cụ kiểm tra quyền
from .services import gui_email_dang_ky_thanh_cong, tao_tai_khoan  # tạo tài khoản và gửi email (P4)
from profiles.forms import NhiepAnhGiaForm  # form hồ sơ Nhiếp ảnh gia của Khoa (P5)

KHOA_CO_TRO_LY = 'tro_ly_sau_dang_ky'  # khóa cờ trong session: vừa đăng ký Khách hàng xong (E5)

class HoSoKhongHopLe(Exception):  # lỗi tự đặt, chỉ để "ném" ra khỏi khối atomic nhằm hoàn tác việc tạo User
    pass  # không cần thêm gì, chỉ cần có tên


class TaiKhoanTrung(Exception):  # lỗi tự đặt: lúc tạo User thì email/SĐT vừa bị người khác đăng ký (tranh chấp hiếm gặp)
    pass  # không cần thêm gì, chỉ cần có tên

class DangNhapView(LoginView):  # trang đăng nhập (UC7.2)
    template_name = 'accounts/dang_nhap.html'  # file giao diện
    authentication_form = DangNhapForm  # dùng form email + mật khẩu của ta
    redirect_authenticated_user = True  # đã đăng nhập rồi mà vào /dang-nhap/ thì chuyển đi luôn
    chuyen_tro_ly = False  # E5: True khi lần đăng nhập này phải chuyển sang Trợ lý (đặt trong form_valid)

    def get_default_redirect_url(self):  # trang đến khi URL không có ?next=
        if self.chuyen_tro_ly:  # Khách hàng vừa đăng ký xong
            return reverse('assistant')  # sang Trợ lý chọn Nhiếp ảnh gia
        return url_trang_chu(self.request.user)  # còn lại chuyển theo vai trò như cũ

    def form_valid(self, form):  # chạy khi email và mật khẩu đúng
        co_co = self.request.session.pop(KHOA_CO_TRO_LY, False)  # đọc và XÓA cờ ngay, kể cả khi URL có ?next= (cờ chỉ dùng một lần)
        user = form.get_user()  # tài khoản sắp đăng nhập
        self.chuyen_tro_ly = bool(co_co) and user.groups.filter(name=VaiTro.KHACH_HANG).exists()  # chỉ Khách hàng, cùng quy tắc khach_hang_required
        response = super().form_valid(form)  # Django thực hiện đăng nhập và tạo phản hồi chuyển trang
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
            request.session[KHOA_CO_TRO_LY] = True  # E5: đánh dấu để lần đăng nhập đầu tiên chuyển sang Trợ lý
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

def _co_loi_o_nhap(form):  # True nếu form có lỗi ở một ô cụ thể (bỏ qua lỗi chung "__all__")
    return any(ten != NON_FIELD_ERRORS for ten in form.errors)  # form.errors: {tên ô: lỗi}; lỗi chung nằm ở khóa "__all__"


def dang_ky_nhiep_anh_gia(request):  # P5: trang đăng ký Nhiếp ảnh gia (UC7.1b)
    if request.user.is_authenticated:  # đã đăng nhập rồi thì không cần đăng ký nữa
        return redirect(url_trang_chu(request.user))  # chuyển về trang theo vai trò, giống dang_ky của Khách hàng

    if request.method != 'POST':  # lần đầu mở trang (GET): chỉ hiện form trống
        return render(request, 'accounts/dang_ky_nhiep_anh_gia.html', {  # hiện template
            'form_tai_khoan': DangKyForm(),  # form tài khoản (họ tên, email, SĐT, mật khẩu) của Phanh, trống
            'form': NhiepAnhGiaForm(user=None),  # form hồ sơ của Khoa, trống; PHẢI tên "form" vì 2 file include của Khoa đọc biến này
        })  # hết dict

    form_tai_khoan = DangKyForm(request.POST)  # form tài khoản chứa dữ liệu người dùng vừa gửi
    form = NhiepAnhGiaForm(request.POST, request.FILES, user=None)  # form hồ sơ kiểm tra thử khi CHƯA có User, để hiện hết lỗi của cả hai form một lần
    form.is_valid()  # chạy kiểm tra để form.errors có dữ liệu (kết quả True/False dùng bên dưới qua _co_loi_o_nhap)
    tai_khoan_ok = form_tai_khoan.is_valid()  # phần tài khoản hợp lệ chưa
    ho_so_ok = not _co_loi_o_nhap(form)  # phần hồ sơ không có ô nào lỗi; lỗi chung (ví dụ "thiếu tài khoản" do chưa có User) được bỏ qua ở bước thử này
    form_co_user = False  # đánh dấu form hiện tại đã gắn User thật hay chưa (để biết có cần ẩn lỗi chung giả hay không)

    if tai_khoan_ok and ho_so_ok:  # cả hai phần đều qua bước thử thì mới tạo User
        d = form_tai_khoan.cleaned_data  # dữ liệu tài khoản đã kiểm tra và làm sạch
        try:  # bọc lại để bắt các lỗi tự đặt bên dưới
            with transaction.atomic():  # từ dòng này, lỗi ở đâu thì hoàn tác TẤT CẢ (kể cả User vừa tạo)
                try:  # CHỈ bọc bước tạo User, để IntegrityError từ bước khác không bị báo nhầm là trùng email/SĐT
                    user = tao_tai_khoan(  # dùng lại đúng hàm của P4 (đã tự gán nhóm)
                        d['ho_ten'], d['email'], d['so_dien_thoai'], d['mat_khau'],  # 4 thông tin tài khoản
                        vai_tro=VaiTro.NHIEP_ANH_GIA,  # gán nhóm Nhiếp ảnh gia TRƯỚC khi tạo form hồ sơ (theo dặn của Khoa)
                        trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET,  # cột trang_thai_ho_so của User = "Chờ duyệt"
                    )  # hết tạo User
                except IntegrityError:  # giữa lúc kiểm tra và lưu, người khác vừa đăng ký trùng email/SĐT
                    raise TaiKhoanTrung  # đổi thành lỗi tự đặt để thoát khối atomic (hoàn tác) mà vẫn biết nguyên nhân
                form = NhiepAnhGiaForm(request.POST, request.FILES, user=user)  # form hồ sơ lần này có User thật; nhận cả chữ (POST) lẫn file (FILES)
                form_co_user = True  # từ đây lỗi chung (nếu có) là lỗi thật, không phải do thiếu User
                if not form.is_valid():  # hiếm: hồ sơ vẫn sai khi đã có User (lỗi chung của form Khoa)
                    raise HoSoKhongHopLe  # ném lỗi để atomic hoàn tác: không sót tài khoản mồ côi
                form.save()  # form tự lưu hồ sơ, 3 nhóm, lượt duyệt và gửi thông báo Quản trị viên (KHÔNG gọi thêm gì nữa)
        except HoSoKhongHopLe:  # User đã bị hoàn tác, form giữ nguyên các lỗi
            pass  # rơi xuống dòng render ở cuối hàm để hiện lỗi
        except TaiKhoanTrung:  # User chưa tạo được vì trùng
            form_tai_khoan.add_error(None, 'Email hoặc số điện thoại vừa được đăng ký bởi người khác. Vui lòng kiểm tra lại.')  # báo lỗi chung ở đầu form tài khoản
        else:  # không có lỗi nào: User và hồ sơ đã lưu xong
            messages.success(request, 'Đăng ký thành công. Hồ sơ của bạn đang chờ Quản trị viên duyệt. Vui lòng đăng nhập để theo dõi hồ sơ.')  # lời báo ở trang kế tiếp
            return redirect('login')  # chuyển sang trang đăng nhập, giống luồng Khách hàng

    if not form_co_user:  # form hồ sơ là bản kiểm tra thử (user=None)
        form.errors.pop(NON_FIELD_ERRORS, None)  # bỏ lỗi chung do thiếu User (nếu form của Khoa có báo), tránh hiện câu lỗi vô lý cho người dùng; lỗi ở từng ô vẫn giữ
    return render(request, 'accounts/dang_ky_nhiep_anh_gia.html', {  # hiện lại trang kèm thông báo lỗi
        'form_tai_khoan': form_tai_khoan,  # form tài khoản (có lỗi nếu có)
        'form': form,  # form hồ sơ (có lỗi nếu có)
    })  # hết dict

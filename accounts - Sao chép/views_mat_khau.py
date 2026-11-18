# =====================================================================
# accounts/views_mat_khau.py  -  P6 (UC7.5 Quên mật khẩu): 3 bước (Phanh)
# Bước 1 nhập email, bước 2 nhập mã 6 chữ số, bước 3 nhập mật khẩu mới.
# =====================================================================
from django.contrib import messages  # thông báo ngắn hiện ở đầu trang kế tiếp
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template

from core.constants import TrangThaiDatLaiMatKhau as TT  # 4 trạng thái lượt yêu cầu

from .forms import DatLaiMatKhauForm, NhapMaForm, QuenMatKhauForm  # 3 form của P6
from .models import YeuCauDatLaiMatKhau  # model lượt yêu cầu
from .permissions import url_trang_chu  # trang chủ theo vai trò (dùng khi người đã đăng nhập lỡ vào đây)
from .services import (  # các hàm xử lý đã viết trong services.py
    KQ_DUNG, KQ_SAI, con_hieu_luc, danh_dau_het_han, dat_lai_mat_khau,
    gui_email_ma_dat_lai, tao_yeu_cau_dat_lai, xac_thuc_ma,
)

TEMPLATE = 'accounts/dat_lai_mat_khau_buoc.html'  # cả 3 bước dùng chung một giao diện
SO_LAN_SAI_TOI_DA = 5  # nhập sai mã quá số lần này thì lượt bị hủy, phải xin mã mới
KHOA_YEU_CAU = 'dat_lai_ma_yeu_cau'  # tên khóa trong session lưu mã lượt yêu cầu đang xử lý
KHOA_SO_LAN_SAI = 'dat_lai_so_lan_sai'  # tên khóa trong session đếm số lần nhập sai mã


def _lay_yeu_cau(request):  # lấy lượt yêu cầu đang xử lý của trình duyệt này, None nếu không có
    ma = request.session.get(KHOA_YEU_CAU)  # mã lượt đã lưu ở bước 1
    if not ma:  # chưa qua bước 1
        return None  # không có lượt nào
    return YeuCauDatLaiMatKhau.objects.filter(pk=ma).select_related('MaTaiKhoan').first()  # tìm trong CSDL kèm luôn User; None nếu không còn


def _xoa_phien(request):  # xóa thông tin lượt khỏi session
    request.session.pop(KHOA_YEU_CAU, None)  # bỏ mã lượt, không lỗi nếu chưa có
    request.session.pop(KHOA_SO_LAN_SAI, None)  # bỏ bộ đếm số lần sai


def quen_mat_khau(request):  # bước 1: nhập email, hệ thống gửi mã
    if request.user.is_authenticated:  # đã đăng nhập thì không cần quên mật khẩu
        return redirect(url_trang_chu(request.user))  # chuyển về trang theo vai trò
    form = QuenMatKhauForm(request.POST) if request.method == 'POST' else QuenMatKhauForm()  # POST: có dữ liệu; GET: form trống
    if request.method == 'POST' and form.is_valid():  # email đúng dạng và đã đăng ký
        yeu_cau = tao_yeu_cau_dat_lai(form.user)  # tạo lượt mới kèm mã 6 chữ số, các lượt cũ hết hạn
        if gui_email_ma_dat_lai(form.user, yeu_cau.OtpXacThuc):  # gửi mã tới email
            request.session[KHOA_YEU_CAU] = yeu_cau.pk  # nhớ lượt này cho bước 2 và 3
            request.session[KHOA_SO_LAN_SAI] = 0  # bắt đầu đếm số lần sai từ 0
            messages.success(request, f'Đã gửi mã xác thực đến {form.cleaned_data["email"]}. Mã có hiệu lực trong 10 phút.')  # báo cho người dùng
            return redirect('verify_reset_code')  # sang bước 2
        danh_dau_het_han(yeu_cau)  # gửi lỗi thì hủy lượt, vì không ai nhận được mã
        form.add_error(None, 'Không gửi được email lúc này. Vui lòng thử lại sau.')  # báo lỗi chung, KHÔNG cho sang bước 2
    return render(request, TEMPLATE, {  # GET hoặc form còn lỗi
        'form': form, 'tieu_de': 'Quên mật khẩu', 'ten_nut': 'Gửi mã xác thực',  # tiêu đề và chữ trên nút
        'mo_ta': 'Nhập email đã đăng ký. Chúng tôi sẽ gửi mã 6 chữ số để bạn đặt lại mật khẩu.',  # câu giải thích
    })  # hết dict


def nhap_ma_xac_thuc(request):  # bước 2: nhập mã 6 chữ số
    if request.user.is_authenticated:  # đã đăng nhập
        return redirect(url_trang_chu(request.user))  # chuyển về trang theo vai trò
    yeu_cau = _lay_yeu_cau(request)  # lượt đang xử lý
    if yeu_cau is None:  # mở thẳng bước 2 mà chưa qua bước 1
        messages.error(request, 'Vui lòng nhập email để nhận mã xác thực.')  # hướng dẫn quay lại
        return redirect('forgot_password')  # về bước 1
    if yeu_cau.TrangThai == TT.DA_XAC_THUC and con_hieu_luc(yeu_cau):  # đã nhập đúng mã rồi mà bấm Back
        return redirect('reset_password')  # đi tiếp bước 3, không bắt nhập lại
    form = NhapMaForm(request.POST) if request.method == 'POST' else NhapMaForm()  # POST: có dữ liệu; GET: form trống
    if request.method == 'POST' and form.is_valid():  # mã đúng 6 chữ số
        ket_qua = xac_thuc_ma(yeu_cau, form.cleaned_data['ma'])  # kiểm tra mã và cập nhật trạng thái
        if ket_qua == KQ_DUNG:  # mã đúng
            return redirect('reset_password')  # sang bước 3
        if ket_qua == KQ_SAI:  # mã sai
            so_lan = request.session.get(KHOA_SO_LAN_SAI, 0) + 1  # tăng bộ đếm
            request.session[KHOA_SO_LAN_SAI] = so_lan  # lưu lại
            if so_lan >= SO_LAN_SAI_TOI_DA:  # sai quá số lần cho phép
                danh_dau_het_han(yeu_cau)  # hủy lượt để không dò mã được
                _xoa_phien(request)  # xóa khỏi session
                messages.error(request, 'Bạn đã nhập sai mã quá 5 lần. Vui lòng yêu cầu mã mới.')  # báo lý do
                return redirect('forgot_password')  # về bước 1
            form.add_error('ma', f'Mã xác thực không đúng. Bạn còn {SO_LAN_SAI_TOI_DA - so_lan} lần thử.')  # báo sai kèm số lần còn lại
        else:  # quá 10 phút, hoặc lượt không còn ở trạng thái Chờ xác thực
            _xoa_phien(request)  # xóa khỏi session
            messages.error(request, 'Mã xác thực đã hết hạn. Vui lòng yêu cầu mã mới.')  # báo hết hạn
            return redirect('forgot_password')  # về bước 1
    return render(request, TEMPLATE, {  # GET hoặc form còn lỗi
        'form': form, 'tieu_de': 'Nhập mã xác thực', 'ten_nut': 'Xác thực',  # tiêu đề và chữ trên nút
        'mo_ta': f'Mã đã được gửi đến {yeu_cau.MaTaiKhoan.email}.',  # nhắc người dùng kiểm tra đúng hộp thư
    })  # hết dict


def dat_lai_mat_khau_moi(request):  # bước 3: nhập mật khẩu mới
    if request.user.is_authenticated:  # đã đăng nhập
        return redirect(url_trang_chu(request.user))  # chuyển về trang theo vai trò
    yeu_cau = _lay_yeu_cau(request)  # lượt đang xử lý
    if yeu_cau is None or yeu_cau.TrangThai != TT.DA_XAC_THUC or not con_hieu_luc(yeu_cau):  # chưa xác thực mã, hoặc xác thực xong nhưng quá hạn
        if yeu_cau is not None and yeu_cau.TrangThai == TT.DA_XAC_THUC:  # trường hợp quá hạn
            danh_dau_het_han(yeu_cau)  # ghi trạng thái Hết hạn
        _xoa_phien(request)  # xóa khỏi session
        messages.error(request, 'Phiên đặt lại mật khẩu đã hết hạn hoặc chưa xác thực mã. Vui lòng thực hiện lại từ đầu.')  # báo lý do
        return redirect('forgot_password')  # về bước 1, KHÔNG cho đặt mật khẩu khi chưa nhập đúng mã
    user = yeu_cau.MaTaiKhoan  # tài khoản đang đặt lại mật khẩu
    form = DatLaiMatKhauForm(request.POST, user=user) if request.method == 'POST' else DatLaiMatKhauForm(user=user)  # POST: có dữ liệu; GET: form trống
    if request.method == 'POST' and form.is_valid():  # mật khẩu mới qua mọi luật
        if dat_lai_mat_khau(yeu_cau, form.cleaned_data['mat_khau_moi']):  # đổi mật khẩu và ghi trạng thái Đã đặt lại mật khẩu
            _xoa_phien(request)  # xong rồi, xóa khỏi session
            messages.success(request, 'Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.')  # báo thành công
            return redirect('login')  # sang trang đăng nhập
        _xoa_phien(request)  # lượt không còn hợp lệ (quá hạn trong lúc nhập)
        messages.error(request, 'Phiên đặt lại mật khẩu đã hết hạn. Vui lòng thực hiện lại từ đầu.')  # báo lý do
        return redirect('forgot_password')  # về bước 1
    return render(request, TEMPLATE, {  # GET hoặc form còn lỗi
        'form': form, 'tieu_de': 'Đặt mật khẩu mới', 'ten_nut': 'Đặt lại mật khẩu',  # tiêu đề và chữ trên nút
        'mo_ta': 'Mã đã được xác thực. Nhập mật khẩu mới cho tài khoản của bạn.',  # câu giải thích
    })  # hết dict

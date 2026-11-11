# accounts/views_khach_hang.py - Hồ sơ của tôi (Khách hàng), Cập nhật hồ sơ và Đổi mật khẩu (Phanh)
from django.contrib import messages  # thông báo ngắn hiện ở đầu trang kế tiếp
from django.contrib.auth import update_session_auth_hash  # giữ phiên đăng nhập sau khi đổi mật khẩu
from django.contrib.auth.decorators import login_required  # chặn người chưa đăng nhập
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template
from django.urls import NoReverseMatch, reverse  # đổi tên URL thành đường dẫn

from core.constants import VaiTro  # tên vai trò, không tự gõ chữ

from .forms import CapNhatKhachHangForm, DoiMatKhauForm  # form sửa hồ sơ và form đổi mật khẩu
from .permissions import lay_vai_tro, url_trang_chu, vai_tro_required  # công cụ kiểm tra quyền


@vai_tro_required(VaiTro.KHACH_HANG)  # chỉ Khách hàng; vai trò khác -> 403, chưa đăng nhập -> trang đăng nhập
def ho_so_khach_hang(request):  # trang "Hồ sơ của tôi" của Khách hàng
    user = request.user  # tài khoản đang đăng nhập
    return render(request, 'accounts/ho_so_khach_hang.html', {
        'user_kh': user,  # để template đọc email, số điện thoại
        'ten': user.get_full_name() or user.email,  # họ và tên (chưa có thì dùng email)
        'ma': f'KH-{user.pk:04d}',  # mã hiển thị cùng kiểu NAG-0022 của Nhiếp ảnh gia
    })


@vai_tro_required(VaiTro.KHACH_HANG)  # chỉ Khách hàng
def cap_nhat_ho_so_khach_hang(request):  # trang "Cập nhật hồ sơ" của Khách hàng
    form = CapNhatKhachHangForm(request.POST or None, user=request.user)  # POST: có dữ liệu người dùng; GET: điền sẵn dữ liệu hiện tại
    if request.method == 'POST' and form.is_valid():  # bấm Lưu và mọi ô hợp lệ
        form.save()  # ghi vào User
        messages.success(request, 'Đã cập nhật hồ sơ thành công.')  # báo ở trang kế tiếp
        return redirect('customer_profile')  # về Hồ sơ của tôi
    return render(request, 'accounts/cap_nhat_ho_so_khach_hang.html', {'form': form})  # GET hoặc còn lỗi: hiện form


def _ve_ho_so(user):  # đích quay về sau khi đổi mật khẩu hoặc bấm Hủy: trang hồ sơ của đúng vai trò
    ten_url = {VaiTro.KHACH_HANG: 'customer_profile', VaiTro.NHIEP_ANH_GIA: 'photographer_profile', VaiTro.QUAN_TRI_VIEN: 'account_profile'}.get(lay_vai_tro(user))  # cả 3 vai trò đều có trang hồ sơ riêng
    if ten_url:  # vai trò có trang hồ sơ
        try:  # URL có thể chưa nối
            return reverse(ten_url)  # đường dẫn trang hồ sơ
        except NoReverseMatch:  # chưa có thì dùng trang đích mặc định
            pass  # rơi xuống dòng cuối
    return url_trang_chu(user)  # Quản trị viên hoặc dự phòng


@login_required  # mọi vai trò đã đăng nhập đều được đổi mật khẩu
def doi_mat_khau(request):  # trang "Đổi mật khẩu"
    form = DoiMatKhauForm(request.POST or None, user=request.user)  # POST: có dữ liệu; GET: form trống
    if request.method == 'POST' and form.is_valid():  # mật khẩu cũ đúng, mật khẩu mới hợp lệ
        user = form.save()  # băm và lưu mật khẩu mới
        update_session_auth_hash(request, user)  # giữ phiên hiện tại, không bị đăng xuất
        messages.success(request, 'Đổi mật khẩu thành công.')  # báo ở trang kế tiếp
        return redirect(_ve_ho_so(user))  # về trang hồ sơ
    return render(request, 'accounts/doi_mat_khau.html', {'form': form, 'huy_url': _ve_ho_so(request.user)})  # hiện form kèm lỗi (nếu có)

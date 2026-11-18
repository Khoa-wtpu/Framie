# accounts/views_ho_so_quan_tri.py - Hồ sơ của tôi và Cập nhật hồ sơ của Quản trị viên (Phanh)
# Cùng cách làm với views_khach_hang.py: dùng lại CapNhatKhachHangForm (không phụ thuộc vai trò) và trang Đổi mật khẩu chung.
from django.contrib import messages  # thông báo ngắn hiện ở đầu trang kế tiếp
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template

from .forms import CapNhatKhachHangForm  # form sửa họ tên, số điện thoại, email (bỏ qua chính mình khi kiểm tra trùng)
from .permissions import chi_quan_tri_vien  # chỉ Quản trị viên; vai trò khác -> 403, chưa đăng nhập -> trang đăng nhập


@chi_quan_tri_vien  # chặn Khách hàng và Nhiếp ảnh gia kể cả khi tự gõ đường dẫn
def ho_so_quan_tri(request):  # trang "Hồ sơ của tôi" của Quản trị viên
    user = request.user  # tài khoản đang đăng nhập
    return render(request, 'accounts/ho_so_quan_tri.html', {
        'user_qt': user,  # để template đọc email, số điện thoại
        'ten': user.get_full_name() or user.email,  # họ và tên (chưa có thì dùng email)
        'ma': f'QTV-{user.pk:04d}',  # mã hiển thị cùng kiểu KH-0001 và NAG-0022
    })


@chi_quan_tri_vien  # chỉ Quản trị viên
def cap_nhat_ho_so_quan_tri(request):  # trang "Cập nhật hồ sơ" của Quản trị viên
    form = CapNhatKhachHangForm(request.POST or None, user=request.user)  # POST: dữ liệu người dùng; GET: điền sẵn dữ liệu hiện tại
    if request.method == 'POST' and form.is_valid():  # bấm Lưu và mọi ô hợp lệ
        form.save()  # ghi vào User
        messages.success(request, 'Đã cập nhật hồ sơ thành công.')  # báo ở trang kế tiếp
        return redirect('account_profile')  # về Hồ sơ của tôi
    return render(request, 'accounts/cap_nhat_ho_so_quan_tri.html', {'form': form})  # GET hoặc còn lỗi: hiện form

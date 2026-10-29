# profiles/views.py - K3 (Khoa)
# Trang thử form hồ sơ. Trang đăng ký thật nằm ở accounts (P5 của Phanh) và dùng chính form này.
from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.permissions import vai_tro_required
from core.constants import VaiTro
from profiles.forms import NhiepAnhGiaForm
from profiles.models import NhiepAnhGia


@vai_tro_required(VaiTro.NHIEP_ANH_GIA)       # chỉ Nhiếp ảnh gia; sai vai trò -> 403, chưa đăng nhập -> trang đăng nhập
def tao_ho_so_thu(request):                   # TRANG THỬ K3: xóa khi gộp bản cuối
    if NhiepAnhGia.objects.filter(MaTaiKhoan=request.user).exists():
        messages.info(request, 'Bạn đã có hồ sơ rồi.')
        return redirect('trang_tam')
    form = NhiepAnhGiaForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()                           # lưu hồ sơ + 3 danh mục + lượt duyệt 'Chờ duyệt' + báo Quản trị viên
        messages.success(request, 'Đã gửi hồ sơ. Hồ sơ đang chờ Quản trị viên duyệt.')
        return redirect('trang_tam')
    return render(request, 'profiles/tao_ho_so_thu.html', {'form': form})

# profiles/decorators.py - dùng chung cho các trang quản lý của nhiếp ảnh gia (K5 Portfolio, K6 Gói dịch vụ, sau này K10 Lịch)
from functools import wraps

from django.contrib import messages

from accounts.permissions import vai_tro_required
from core.constants import TrangThaiHoSo, VaiTro
from profiles.models import NhiepAnhGia
from profiles.views import _ve_ho_so_cua_toi


def nhiep_anh_gia_da_duyet(view):
    """Đúng vai trò + hồ sơ 'Đã duyệt' mới vào được; nếu không thì về trang hồ sơ kèm thông báo.
    View nhận thêm tham số thứ hai: nag (hồ sơ của người đang đăng nhập)."""
    @wraps(view)
    @vai_tro_required(VaiTro.NHIEP_ANH_GIA)
    def boc(request, *args, **kwargs):
        nag = NhiepAnhGia.objects.filter(MaTaiKhoan=request.user).first()
        if nag is None:
            messages.info(request, 'Bạn chưa có hồ sơ nên chưa thể sử dụng chức năng này.')
            return _ve_ho_so_cua_toi()
        if request.user.trang_thai_ho_so != TrangThaiHoSo.DA_DUYET:
            messages.info(request, 'Hồ sơ của bạn chưa được duyệt nên chưa thể sử dụng chức năng này.')
            return _ve_ho_so_cua_toi()
        return view(request, nag, *args, **kwargs)
    return boc

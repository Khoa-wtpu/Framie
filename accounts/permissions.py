from functools import wraps  # giữ nguyên tên và mô tả của view khi bọc decorator

from django.contrib.auth.mixins import AccessMixin  # lớp có sẵn xử lý "chưa đăng nhập" / "không đủ quyền"
from django.contrib.auth.views import redirect_to_login  # hàm chuyển người dùng về trang đăng nhập kèm ?next=
from django.core.exceptions import PermissionDenied  # ném lỗi này để Django trả HTTP 403
from django.urls import NoReverseMatch, reverse  # reverse: đổi tên URL thành đường dẫn

from core.constants import VaiTro  # tên 3 vai trò, không tự gõ chữ tiếng Việt (README)

# Trang đầu tiên của mỗi vai trò sau khi đăng nhập: thử lần lượt từng tên URL, tên nào tồn tại thì dùng.
TRANG_CHU_THEO_VAI_TRO = {  # từ điển: vai trò -> danh sách tên URL ưu tiên
    VaiTro.QUAN_TRI_VIEN: ['admin_dashboard', 'admin_accounts'],  # TODO: đổi cho đúng tên URL trang tổng quan khi làm B7
    VaiTro.NHIEP_ANH_GIA: ['photographer_profile'],  # "Hồ sơ của tôi" (cả NAG chưa duyệt cũng chỉ thấy trang này)
    VaiTro.KHACH_HANG: ['search', 'home'],  # Khách hàng vào trang tìm kiếm, chưa có thì về trang chủ
}  # hết từ điển


def lay_vai_tro(user):  # trả về vai trò chính của một User
    if not user.is_authenticated:  # chưa đăng nhập
        return None  # không có vai trò
    if user.is_superuser:  # tài khoản tạo bằng createsuperuser
        return VaiTro.QUAN_TRI_VIEN  # luôn coi là Quản trị viên (giống core/navigation.py)
    ten_nhom = set(user.groups.values_list('name', flat=True))  # lấy tên các nhóm quyền của User
    for vai_tro in (VaiTro.QUAN_TRI_VIEN, VaiTro.NHIEP_ANH_GIA, VaiTro.KHACH_HANG):  # duyệt theo thứ tự ưu tiên
        if vai_tro in ten_nhom:  # User thuộc nhóm này
            return vai_tro  # trả vai trò tìm được
    return None  # tài khoản chưa gán nhóm nào: coi như không có quyền gì


def url_trang_chu(user):  # đường dẫn trang đích sau khi đăng nhập
    for ten_url in TRANG_CHU_THEO_VAI_TRO.get(lay_vai_tro(user), []):  # duyệt các tên URL của vai trò
        try:  # thử đổi tên URL thành đường dẫn
            return reverse(ten_url)  # URL tồn tại thì dùng ngay
        except NoReverseMatch:  # URL này của bạn khác chưa làm xong
            continue  # thử tên tiếp theo
    return reverse('trang_tam')  # chưa có trang nào thì về trang tạm của accounts (không bị lỗi)


def vai_tro_required(*vai_tro_cho_phep):  # decorator cho view dạng hàm: @vai_tro_required(VaiTro.KHACH_HANG)
    def decorator(view_func):  # nhận hàm view cần bảo vệ
        @wraps(view_func)  # giữ tên hàm gốc
        def wrapper(request, *args, **kwargs):  # hàm thay thế, chạy trước view thật
            if not request.user.is_authenticated:  # chưa đăng nhập
                return redirect_to_login(request.get_full_path())  # chuyển về đăng nhập, đăng nhập xong quay lại đúng trang này
            if lay_vai_tro(request.user) not in vai_tro_cho_phep:  # vai trò không nằm trong danh sách được vào
                raise PermissionDenied  # trả lỗi 403 (kể cả khi người dùng tự gõ đường dẫn)
            return view_func(request, *args, **kwargs)  # hợp lệ thì chạy view thật
        return wrapper  # trả hàm đã bọc
    return decorator  # trả decorator


chi_khach_hang = vai_tro_required(VaiTro.KHACH_HANG)  # dạng viết tắt: chỉ Khách hàng
chi_nhiep_anh_gia = vai_tro_required(VaiTro.NHIEP_ANH_GIA)  # dạng viết tắt: chỉ Nhiếp ảnh gia
chi_quan_tri_vien = vai_tro_required(VaiTro.QUAN_TRI_VIEN)  # dạng viết tắt: chỉ Quản trị viên


class VaiTroRequiredMixin(AccessMixin):  # dùng cho view dạng class: class X(VaiTroRequiredMixin, View)
    vai_tro_cho_phep = ()  # lớp con khai báo, ví dụ (VaiTro.QUAN_TRI_VIEN,)

    def dispatch(self, request, *args, **kwargs):  # Django gọi hàm này trước mọi phương thức GET/POST
        if lay_vai_tro(request.user) not in self.vai_tro_cho_phep:  # chưa đăng nhập hoặc sai vai trò
            return self.handle_no_permission()  # chưa đăng nhập -> trang đăng nhập; đã đăng nhập mà sai quyền -> 403
        return super().dispatch(request, *args, **kwargs)  # hợp lệ thì chạy tiếp view
# chat/views.py - P10 (UC8.1): khởi tạo cuộc trò chuyện từ nút "Nhắn tin" ở hồ sơ Nhiếp ảnh gia.
from django.contrib import messages  # hộp thông báo ngắn trên đầu trang
from django.contrib.auth.views import redirect_to_login  # chuyển người chưa đăng nhập sang trang đăng nhập, kèm ?next=
from django.core.exceptions import PermissionDenied, ValidationError  # 403: không đủ quyền; ValidationError: dữ liệu không hợp lệ
from django.db import DatabaseError  # lỗi cơ sở dữ liệu bất ngờ
from django.shortcuts import get_object_or_404, redirect  # tìm đối tượng hoặc báo 404; chuyển trang
from django.views.decorators.http import require_POST  # chỉ nhận POST (nút Nhắn tin là form POST, có CSRF)

from chat import services  # logic nghiệp vụ nằm ở services.py
from profiles.models import NhiepAnhGia  # hồ sơ Nhiếp ảnh gia (app của Khoa)


@require_POST  # GET vào đường dẫn này trả lỗi 405, tránh trình duyệt tải trước làm tạo cuộc trò chuyện
def khoi_tao_cuoc_tro_chuyen(request, ma_nhiep_anh_gia):  # UC8.1
    nag = get_object_or_404(NhiepAnhGia.objects.select_related('MaTaiKhoan'), pk=ma_nhiep_anh_gia)  # không có hồ sơ thì 404
    ho_so = services.duong_dan_ho_so(nag.pk)  # trang hồ sơ để quay lại
    if not request.user.is_authenticated:  # chưa đăng nhập
        return redirect_to_login(ho_so)  # sang trang đăng nhập, đăng nhập xong quay lại hồ sơ
    if not services.la_khach_hang(request.user):  # đã đăng nhập nhưng không phải Khách hàng
        raise PermissionDenied('Chỉ Khách hàng mới được khởi tạo cuộc trò chuyện.')  # 403
    try:  # luồng ngoại lệ 2a của UC8.1: lỗi bất ngờ khi khởi tạo
        cuoc, da_tao = services.mo_hoac_tao_cuoc_tro_chuyen(request.user, nag)  # mở cuộc cũ hoặc tạo mới
    except (ValidationError, DatabaseError):  # Http404 (chưa duyệt) và 403 không bị bắt ở đây, vẫn giữ nguyên
        messages.error(request, 'Không thể khởi tạo cuộc trò chuyện. Vui lòng thực hiện lại.')  # hộp đỏ theo đặc tả
        return redirect(ho_so)  # quay về hồ sơ để bấm lại
    dich = services.duong_dan_cuoc_tro_chuyen(cuoc.pk)  # màn hình trò chuyện (UC8.2)
    if dich:  # UC8.2 đã có
        return redirect(dich)  # vào thẳng cuộc trò chuyện
    ten = nag.MaTaiKhoan.get_full_name() or nag.MaTaiKhoan.username  # tên hiển thị của Nhiếp ảnh gia
    messages.success(request, f'Đã tạo cuộc trò chuyện với {ten}.' if da_tao else f'Đã mở lại cuộc trò chuyện với {ten}.')  # tạm thời, tới khi có UC8.2
    return redirect(ho_so)  # quay lại hồ sơ

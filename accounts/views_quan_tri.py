# =====================================================================
# accounts/views_quan_tri.py  -  B7: view trang tổng quan khu Quản trị
# =====================================================================
from django.shortcuts import render  # hàm hiện template

from core.navigation import resolve  # đổi tên URL thành đường dẫn (chưa có thì "#")

from .permissions import chi_quan_tri_vien  # decorator: chỉ Quản trị viên được vào (người khác bị 403)
from .quan_tri import thong_ke_tong_quan  # hàm tính số liệu


@chi_quan_tri_vien  # chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403
def tong_quan(request):  # trang tổng quan /quan-tri/
    boi_canh = {  # dữ liệu gửi sang template
        'thong_ke': thong_ke_tong_quan(),  # các con số
        'url_duyet_ho_so': resolve('admin_profile_review'),  # link nút "Duyệt hồ sơ" (có thể là "#")
        'url_booking': resolve('admin_bookings'),  # link nút "Xem Booking" (có thể là "#")
    }  # hết dict
    return render(request, 'accounts/quan_tri/tong_quan.html', boi_canh)  # hiện trang

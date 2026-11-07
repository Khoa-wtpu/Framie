from django.urls import path  # hàm khai báo một đường dẫn

from . import views  # các view vừa viết
from . import views_mat_khau  # P6: 3 bước quên mật khẩu
from . import views_quan_tri  # B7: view trang tổng quan khu Quản trị
from . import views_khach_hang  # Hồ sơ của tôi (Khách hàng) và Đổi mật khẩu

urlpatterns = [  # danh sách đường dẫn của app accounts
    path('dang-nhap/', views.DangNhapView.as_view(), name='login'),  # name='login' khớp core/navigation.py và header
    path('dang-xuat/', views.xac_nhan_dang_xuat, name='logout_confirm'),  # name khớp header ("Đăng xuất" trỏ về đây)
    path('tai-khoan/trang-tam/', views.trang_tam, name='trang_tam'),  # trang tạm sau đăng nhập
    path('thu-quyen/khach-hang/', views.thu_khach_hang, name='thu_khach_hang'),  # trang thử quyền 1 (xóa sau)
    path('thu-quyen/nhiep-anh-gia/', views.thu_nhiep_anh_gia, name='thu_nhiep_anh_gia'),  # trang thử quyền 2 (xóa sau)
    path('thu-quyen/quan-tri/', views.thu_quan_tri, name='thu_quan_tri'),  # trang thử quyền 3 (xóa sau)
    path('dang-ky/', views.dang_ky, name='register'), # P4: name='register' khớp core/navigation.py, nút Đăng ký ở header và link Tạo tài khoản
    path('quan-tri/', views_quan_tri.tong_quan, name='admin_dashboard'),  # B7: trang tổng quan Quản trị; name khớp permissions.py và menu
    path('dang-ky/nhiep-anh-gia/', views.dang_ky_nhiep_anh_gia, name='register_photographer'),
    # P5: đăng ký Nhiếp ảnh gia
    path('quen-mat-khau/', views_mat_khau.quen_mat_khau, name='forgot_password'),  # P6 bước 1: nhập email
    path('quen-mat-khau/xac-thuc/', views_mat_khau.nhap_ma_xac_thuc, name='verify_reset_code'),  # P6 bước 2: nhập mã 6 chữ số
    path('quen-mat-khau/dat-lai/', views_mat_khau.dat_lai_mat_khau_moi, name='reset_password'),  # P6 bước 3: nhập mật khẩu mới
    path('quan-tri/tai-khoan/', views_quan_tri.danh_sach_tai_khoan, name='admin_accounts'),
    # P7: danh sách tài khoản; name khớp permissions.py và menu header
    path('quan-tri/tai-khoan/<int:pk>/doi-vai-tro/', views_quan_tri.doi_vai_tro, name='admin_account_role'),
    # P7: đổi vai trò (chỉ POST)
    path('quan-tri/tai-khoan/<int:pk>/khoa-mo/', views_quan_tri.khoa_mo_tai_khoan, name='admin_account_toggle'),
    # P7: khóa/mở (chỉ POST)
    path('ho-so/khach-hang/', views_khach_hang.ho_so_khach_hang, name='customer_profile'),  # Hồ sơ của tôi (Khách hàng); name khớp core/navigation.py
    path('ho-so/khach-hang/cap-nhat/', views_khach_hang.cap_nhat_ho_so_khach_hang, name='customer_profile_update'),  # Cập nhật hồ sơ (Khách hàng)
    path('tai-khoan/doi-mat-khau/', views_khach_hang.doi_mat_khau, name='change_password'),  # Đổi mật khẩu (mọi vai trò đã đăng nhập); name khớp menu avatar
]  # hết danh sách

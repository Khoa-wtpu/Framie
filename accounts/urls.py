from django.urls import path  # hàm khai báo một đường dẫn

from . import views  # các view vừa viết

urlpatterns = [  # danh sách đường dẫn của app accounts
    path('dang-nhap/', views.DangNhapView.as_view(), name='login'),  # name='login' khớp core/navigation.py và header
    path('dang-xuat/', views.xac_nhan_dang_xuat, name='logout_confirm'),  # name khớp header ("Đăng xuất" trỏ về đây)
    path('tai-khoan/trang-tam/', views.trang_tam, name='trang_tam'),  # trang tạm sau đăng nhập
    path('thu-quyen/khach-hang/', views.thu_khach_hang, name='thu_khach_hang'),  # trang thử quyền 1 (xóa sau)
    path('thu-quyen/nhiep-anh-gia/', views.thu_nhiep_anh_gia, name='thu_nhiep_anh_gia'),  # trang thử quyền 2 (xóa sau)
    path('thu-quyen/quan-tri/', views.thu_quan_tri, name='thu_quan_tri'),  # trang thử quyền 3 (xóa sau)
]  # hết danh sách

# notifications/urls.py - P8: địa chỉ các trang thông báo (nối vào config/urls.py bằng path('', include('notifications.urls')))
from django.urls import path  # hàm khai báo "địa chỉ nào chạy view nào"

from . import views  # các view trong notifications/views.py

urlpatterns = [  # bảng chỉ đường của app thông báo (không dùng app_name vì header gọi tên 'notifications' trực tiếp)
    path('thong-bao/', views.danh_sach, name='notifications'),  # SC9.1: tên 'notifications' khớp URL_NAMES trong core/navigation.py
    path('thong-bao/khung/', views.khung_thong_bao, name='khung_thong_bao'),  # mảnh HTML cho khung chuông thả xuống
    path('thong-bao/<int:ma_thong_bao>/', views.chi_tiet, name='chi_tiet_thong_bao'),  # SC9.2: chi tiết một thông báo
    path('thong-bao/<int:ma_thong_bao>/doc/', views.doi_trang_thai_doc, name='doi_trang_thai_doc'),  # POST: đổi Đã đọc / Chưa đọc
    path('thong-bao/<int:ma_thong_bao>/sao/', views.doi_dau_sao, name='doi_dau_sao'),  # POST: gắn hoặc bỏ sao
    path('thong-bao/<int:ma_thong_bao>/xoa/', views.xoa, name='xoa_thong_bao'),  # POST: xóa một thông báo
]  # hết bảng chỉ đường

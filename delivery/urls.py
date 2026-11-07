# delivery/urls.py - N4 / UC5.3, N6 / UC5.4, N7 / UC5.5, N8 / UC5.6, N10 / UC5.8
from django.urls import path

from . import views, views_tai_anh

urlpatterns = [
    path('booking/<int:ma_booking>/tai-anh/', views.tai_anh_len, name='tai_anh_len'),   # trang Nhiếp ảnh gia tải ảnh
    path('anh/<int:ma_anh>/xem/', views.xem_anh, name='xem_anh'),
    path('booking/<int:ma_booking>/chon-anh/', views.chon_anh_hau_ky, name='chon_anh_hau_ky'),   # N6: Khách hàng chọn ảnh cần hậu kỳ
    path('booking/<int:ma_booking>/bat-dau-hau-ky/', views.bat_dau_hau_ky, name='bat_dau_hau_ky'),   # N6: Nhiếp ảnh gia bấm bắt đầu hậu kỳ
    path('booking/<int:ma_booking>/yeu-cau-chinh-sua/', views.yeu_cau_chinh_sua, name='yeu_cau_chinh_sua'),   # N7: Khách hàng yêu cầu chỉnh sửa ảnh
    path('booking/<int:ma_booking>/xac-nhan-ban-giao/', views.xac_nhan_ban_giao, name='xac_nhan_ban_giao'),   # N8: Khách hàng xác nhận hoàn tất bàn giao
    path('booking/<int:ma_booking>/tai-anh-hoan-chinh/', views_tai_anh.tai_anh_hoan_chinh, name='tai_anh_hoan_chinh'),   # N10: Khách hàng tải ảnh hoàn chỉnh
    path('booking/<int:ma_booking>/tai-anh-hoan-chinh/<int:ma_anh>/xem-truoc/', views_tai_anh.xem_truoc_anh_hoan_chinh, name='xem_truoc_anh_hoan_chinh'),   # N10: ảnh thu nhỏ xem trước
]
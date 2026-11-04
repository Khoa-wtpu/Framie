# delivery/urls.py - N4 / UC5.3, N6 / UC5.4, N7 / UC5.5
from django.urls import path

from . import views

urlpatterns = [
    path('booking/<int:ma_booking>/tai-anh/', views.tai_anh_len, name='tai_anh_len'),   # trang Nhiếp ảnh gia tải ảnh
    path('anh/<int:ma_anh>/xem/', views.xem_anh, name='xem_anh'),
    path('booking/<int:ma_booking>/chon-anh/', views.chon_anh_hau_ky, name='chon_anh_hau_ky'),   # N6: Khách hàng chọn ảnh cần hậu kỳ
    path('booking/<int:ma_booking>/bat-dau-hau-ky/', views.bat_dau_hau_ky, name='bat_dau_hau_ky'),   # N6: Nhiếp ảnh gia bấm bắt đầu hậu kỳ
    path('booking/<int:ma_booking>/yeu-cau-chinh-sua/', views.yeu_cau_chinh_sua, name='yeu_cau_chinh_sua'),   # N7: Khách hàng yêu cầu chỉnh sửa ảnh
]

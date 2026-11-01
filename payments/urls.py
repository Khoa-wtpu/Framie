# payments/urls.py
from django.urls import path

from . import views

urlpatterns = [
    path('booking/<int:ma_booking>/minh-chung/', views.tai_len_minh_chung, name='tai_len_minh_chung'),
    path('minh-chung/<int:ma_minh_chung>/xem/', views.xem_minh_chung, name='xem_minh_chung'),
    path('booking/<int:ma_booking>/xac-nhan-coc/', views.xac_nhan_thanh_toan_coc, name='xac_nhan_thanh_toan_coc'),  # N3: NAG xác nhận cọc
]

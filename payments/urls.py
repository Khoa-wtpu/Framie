# payments/urls.py
from django.urls import path

from . import views, views_con_lai, admin_views

urlpatterns = [
    path('thanh-toan/quan-ly/', admin_views.quan_ly_thanh_toan, name='admin_payments'),
    path('booking/<int:ma_booking>/minh-chung/', views.tai_len_minh_chung, name='tai_len_minh_chung'),
    path('minh-chung/<int:ma_minh_chung>/xem/', views.xem_minh_chung, name='xem_minh_chung'),
    path('booking/<int:ma_booking>/xac-nhan-coc/', views.xac_nhan_thanh_toan_coc, name='xac_nhan_thanh_toan_coc'),  # N3: NAG xác nhận cọc
    path('booking/<int:ma_booking>/xac-nhan-thanh-toan-con-lai/', views_con_lai.xac_nhan_thanh_toan_con_lai, name='xac_nhan_thanh_toan_con_lai'),  # N9: NAG xác nhận 60%
]

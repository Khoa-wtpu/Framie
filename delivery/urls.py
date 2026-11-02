# delivery/urls.py - N4 / UC5.3
from django.urls import path

from . import views

urlpatterns = [
    path('booking/<int:ma_booking>/tai-anh/', views.tai_anh_len, name='tai_anh_len'),   # trang Nhiếp ảnh gia tải ảnh
    path('anh/<int:ma_anh>/xem/', views.xem_anh, name='xem_anh'),
]

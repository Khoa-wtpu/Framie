# reviews/urls.py - N11 / UC6.1
from django.urls import path

from . import views

urlpatterns = [
    path('booking/<int:ma_booking>/danh-gia/', views.danh_gia_booking, name='danh_gia_booking'),   # Khách hàng đánh giá Booking Hoàn thành
    path('nhiep-anh-gia/<int:ma_nag>/danh-gia/', views.danh_gia_cong_khai, name='photographer_reviews'),   # công khai: đánh giá + điểm trung bình
]

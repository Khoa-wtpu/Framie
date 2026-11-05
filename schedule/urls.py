from django.urls import path

from . import views_lich

urlpatterns = [
    # K10: quản lý lịch khả dụng (name='my_calendar' khớp menu Nhiếp ảnh gia trong core/navigation.py)
    path('lich/', views_lich.quan_ly_lich, name='my_calendar'),
    path('lich/them/', views_lich.lich_them, name='lich_them'),
    path('lich/<int:pk>/sua/', views_lich.lich_sua, name='lich_sua'),
    path('lich/<int:pk>/xoa/', views_lich.lich_xoa, name='lich_xoa'),
]

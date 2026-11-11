# profiles/urls_cong_khai.py - K9. Nối vào config/urls.py:  path('', include('profiles.urls_cong_khai')),
from django.urls import path

from . import views_cong_khai

urlpatterns = [
    # name='photographer_detail' là tên mà trang Tìm kiếm (search/views.py) đã chờ sẵn
    path('nhiep-anh-gia/<int:ma_nhiep_anh_gia>/', views_cong_khai.photographer_detail, name='photographer_detail'),
    path('nhiep-anh-gia/<int:ma_nhiep_anh_gia>/du-an/<int:ma_project>/', views_cong_khai.photographer_project,
         name='photographer_project'),
]

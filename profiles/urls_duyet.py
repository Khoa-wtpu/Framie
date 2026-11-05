# profiles/urls_duyet.py - K7: Duyệt hồ sơ (UC1.5). config/urls.py thêm: path('', include('profiles.urls_duyet'))
from django.urls import path

from . import views_duyet

urlpatterns = [
    # name='admin_profile_review' khớp menu Quản trị viên trong core/navigation.py ("Duyệt hồ sơ")
    path('quan-tri/duyet-ho-so/', views_duyet.danh_sach, name='admin_profile_review'),
    path('quan-tri/duyet-ho-so/<int:ma_duyet>/', views_duyet.chi_tiet, name='duyet_ho_so_chi_tiet'),
]

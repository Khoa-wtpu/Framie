# profiles/urls_cua_toi.py - K3b: "Hồ sơ của tôi" (SC1.2). Nối vào config/urls.py:  path('', include('profiles.urls_cua_toi')),
from django.urls import path

from . import views_cua_toi

urlpatterns = [
    # name='photographer_profile' khớp menu Nhiếp ảnh gia trong core/navigation.py ("Hồ sơ của tôi") và đích quay về của K4
    path('ho-so/cua-toi/', views_cua_toi.ho_so_cua_toi, name='photographer_profile'),
]

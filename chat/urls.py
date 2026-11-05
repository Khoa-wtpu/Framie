# chat/urls.py - P10. Nối vào config/urls.py bằng: path('', include('chat.urls'))
from django.urls import path  # hàm khai báo đường dẫn

from chat import views  # các view của app chat

urlpatterns = [  # danh sách đường dẫn của app chat
    path('tin-nhan/bat-dau/<int:ma_nhiep_anh_gia>/', views.khoi_tao_cuoc_tro_chuyen, name='khoi_tao_cuoc_tro_chuyen'),  # UC8.1, chỉ POST
]  # hết danh sách

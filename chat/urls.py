# chat/urls.py - P10, P11. Nối vào config/urls.py bằng: path('', include('chat.urls')) (Khoa đã nối sẵn)
from django.urls import path  # hàm khai báo đường dẫn

from chat import views  # các view của app chat

urlpatterns = [  # danh sách đường dẫn của app chat
    path('tin-nhan/', views.hop_thu, name='inbox'),  # P11: danh sách cuộc trò chuyện, menu "Tin nhắn" (core/navigation.py dùng name này)
    path('tin-nhan/bat-dau/<int:ma_nhiep_anh_gia>/', views.khoi_tao_cuoc_tro_chuyen, name='khoi_tao_cuoc_tro_chuyen'),  # UC8.1, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/', views.chi_tiet_cuoc_tro_chuyen, name='chi_tiet_cuoc_tro_chuyen'),  # UC8.3: mở cuộc trò chuyện (P10 đã chờ sẵn name này)
    path('tin-nhan/<int:ma_cuoc>/gui/', views.gui_tin_nhan, name='gui_tin_nhan'),  # UC8.2: gửi tin, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/tin-moi/', views.tin_nhan_moi, name='tin_nhan_moi'),  # polling tin mới và tải tin cũ, trả JSON
]  # hết danh sách

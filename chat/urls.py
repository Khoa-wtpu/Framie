# chat/urls.py - P10, P11. Nối vào config/urls.py bằng: path('', include('chat.urls')) (Khoa đã nối sẵn)
from django.urls import path  # hàm khai báo đường dẫn

from chat import views  # các view của app chat

urlpatterns = [  # danh sách đường dẫn của app chat
    path('tin-nhan/', views.hop_thu, name='inbox'),  # P11: danh sách cuộc trò chuyện, menu "Tin nhắn" (core/navigation.py dùng name này)
    path('tin-nhan/dong-bo/', views.dong_bo_danh_sach, name='dong_bo_danh_sach'),  # cột trái tự cập nhật, trả JSON (phải đặt TRƯỚC tin-nhan/<int:...>)
    path('tin-nhan/bat-dau/<int:ma_nhiep_anh_gia>/', views.khoi_tao_cuoc_tro_chuyen, name='khoi_tao_cuoc_tro_chuyen'),  # UC8.1, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/', views.chi_tiet_cuoc_tro_chuyen, name='chi_tiet_cuoc_tro_chuyen'),  # UC8.3: mở cuộc trò chuyện (P10 đã chờ sẵn name này)
    path('tin-nhan/<int:ma_cuoc>/gui/', views.gui_tin_nhan, name='gui_tin_nhan'),  # UC8.2: gửi tin, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/doi-chua-doc/', views.doi_chua_doc, name='doi_chua_doc'),  # ba chấm: đánh dấu chưa đọc / đã đọc, chỉ POST
    path('tin-nhan/anh/<int:ma_dinh_kem>/', views.xem_anh_chat, name='xem_anh_chat'),  # xem một ảnh đính kèm (?nho=1 là bản thu nhỏ 400px), chỉ hai người trong cuộc
    path('tin-nhan/<int:ma_cuoc>/tin/<int:ma_tin>/thu-hoi/', views.thu_hoi_tin, name='thu_hoi_tin'),  # thu hồi một tin của chính mình, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/ghim/', views.doi_ghim, name='doi_ghim'),  # ba chấm: Ghim / Bỏ ghim, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/an/', views.doi_an, name='doi_an'),  # ba chấm: Ẩn / Bỏ ẩn cuộc trò chuyện, chỉ POST
    path('tin-nhan/<int:ma_cuoc>/xoa/', views.xoa_cuoc, name='xoa_cuoc'),  # ba chấm: Xóa cuộc trò chuyện (chỉ phía mình), chỉ POST
    path('tin-nhan/<int:ma_cuoc>/tim/', views.tim_trong_cuoc, name='tim_trong_cuoc'),  # bước 7: tìm từ khóa trong cuộc trò chuyện (?q=), trả JSON
    path('tin-nhan/<int:ma_cuoc>/den/', views.tin_nhan_den_tin, name='tin_nhan_den_tin'),  # bước 7: tải các tin cũ để nhảy tới một kết quả (?tin=&truoc=), trả JSON
    path('tin-nhan/<int:ma_cuoc>/tin-moi/', views.tin_nhan_moi, name='tin_nhan_moi'),  # polling tin mới và tải tin cũ, trả JSON
]  # hết danh sách

from django.urls import path

from . import views

urlpatterns = [
    path('ho-so/cap-nhat/', views.cap_nhat_ho_so, name='cap_nhat_ho_so'),  # K4: cập nhật hồ sơ (trang thật)
    path('thu-quyen/tao-ho-so/', views.tao_ho_so_thu, name='tao_ho_so_thu'),  # TRANG THỬ K3 (xóa sau)
]

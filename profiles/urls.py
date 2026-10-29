from django.urls import path

from . import views

urlpatterns = [
    path('thu-quyen/tao-ho-so/', views.tao_ho_so_thu, name='tao_ho_so_thu'),  # TRANG THỬ K3 (xóa sau)
]

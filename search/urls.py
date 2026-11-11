from django.urls import path

from . import tro_ly, views  # tro_ly: Trợ lý chọn Nhiếp ảnh gia (E4)

urlpatterns = [
    path('tim-kiem/', views.tim_kiem, name='search'),   # name='search' khớp menu trong core/navigation.py
    path('tro-ly/', tro_ly.assistant, name='assistant'),   # E4: form 5 bước (?buoc=1..5)
    path('tro-ly/ket-qua/', tro_ly.assistant_result, name='assistant_result'),   # E4: trang kết quả
]
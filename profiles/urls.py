from django.urls import path

from . import views, views_goi, views_portfolio

urlpatterns = [
    # K5: quản lý Portfolio (name='portfolio' khớp menu Nhiếp ảnh gia trong core/navigation.py)
    path('portfolio/', views_portfolio.portfolio, name='portfolio'),
    path('portfolio/them/', views_portfolio.project_them, name='project_them'),
    path('portfolio/<int:pk>/sua/', views_portfolio.project_sua, name='project_sua'),
    path('portfolio/<int:pk>/xoa/', views_portfolio.project_xoa, name='project_xoa'),
    # K6: quản lý gói dịch vụ (name='service_packages' khớp menu Nhiếp ảnh gia trong core/navigation.py)
    path('goi-dich-vu/', views_goi.danh_sach_goi, name='service_packages'),
    path('goi-dich-vu/them/', views_goi.goi_them, name='goi_them'),
    path('goi-dich-vu/<int:pk>/sua/', views_goi.goi_sua, name='goi_sua'),
    path('goi-dich-vu/<int:pk>/<slug:hanh_dong>/', views_goi.goi_hanh_dong, name='goi_hanh_dong'),
    path('ho-so/cap-nhat/', views.cap_nhat_ho_so, name='cap_nhat_ho_so'),  # K4: cập nhật hồ sơ (trang thật)
]

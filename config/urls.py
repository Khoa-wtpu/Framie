from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Cấu hình tiêu đề trang quản trị (nếu muốn giữ tùy chỉnh)
admin.site.site_header = "FRAMIE - Quản trị"
admin.site.site_title = 'FRAMIE'
admin.site.index_title = 'Quản trị hệ thống'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('profiles.urls')),
    path('', include('search.urls')),
    path('', include('payments.urls')),
    path('', include('delivery.urls')),
    path('', include('reviews.urls')),  # Đường dẫn tích hợp tính năng đánh giá (N11)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
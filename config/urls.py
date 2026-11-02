"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings                  # đọc cài đặt trong settings.py
from django.conf.urls.static import static        # hàm nối địa chỉ web với thư mục file
from django.contrib import admin
from django.urls import include, path             # (1) thêm include
admin.site.site_header = 'FRAMIE - Quản trị'
admin.site.site_title = 'FRAMIE'
admin.site.index_title = 'Quản trị hệ thống'

urlpatterns = [
    path('admin/', admin.site.urls),              # /admin dẫn tới trang quản trị

    path('bookings/', include('bookings.giu_cho')),
    path('bookings/', include('bookings.gui_booking')),
    path('bookings/', include('bookings.tiep_nhan')),
    path('', include('core.urls')),               # nối core/urls.py, có /ui-kit/
    path('', include('accounts.urls')),           # nối accounts/urls.py: /dang-nhap/, /dang-xuat/ (P3 của Phanh)
    path('', include('profiles.urls')),           # nối profiles/urls.py: trang thử K3 (xóa khi gộp bản cuối)
    path('', include('search.urls')),
    path('', include('schedule.urls')),
    path('', include('profiles.urls_cong_khai')),

]

# Khi chạy thử (DEBUG = True): địa chỉ /media/... dẫn tới thư mục media/ trên máy,
# để xem được ảnh đại diện, ảnh Portfolio được tải lên.
# Khi triển khai thật (DEBUG = False) đoạn này tự tắt, máy chủ thật sẽ phát file.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
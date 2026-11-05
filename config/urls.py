from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [

    path('admin/', admin.site.urls),              # /admin dẫn tới trang quản trị

    path('bookings/', include('bookings.giu_cho')),
    path('bookings/', include('bookings.gui_booking')),
    path('bookings/', include('bookings.tiep_nhan')),   # UC4.3-4.5 (đã có file, trước đây chưa nối)
    path('bookings/', include('bookings.da_chup')),     # T8: nút Đã chụp
    path('bookings/', include('bookings.huy_booking')), # T9 / UC4.6: Hủy Booking + xác nhận đã nhận lại tiền cọc
    path('bookings/', include('bookings.theo_doi')),    # T7 / UC4.7: Booking của tôi + Quản trị tra cứu
    path('', include('core.urls')),               # nối core/urls.py, có /ui-kit/
    path('', include('accounts.urls')),           # nối accounts/urls.py: /dang-nhap/, /dang-xuat/ (P3 của Phanh)
    path('', include('profiles.urls')),           # nối profiles/urls.py: trang thử K3 (xóa khi gộp bản cuối)
    path('', include('search.urls')),
    path('', include('schedule.urls')),
    path('', include('profiles.urls_cong_khai')),
    path('', include('profiles.urls_duyet')),
    path('', include('profiles.urls_cua_toi')),
    path('', include('payments.urls')),  # N2, N3, N9: minh chứng, xác nhận cọc, xác nhận phần còn lại
    path('', include('delivery.urls')),  # N4-N8: bàn giao ảnh
    path('', include('reviews.urls')),  # N11: đánh giá nhiếp ảnh gia

    # ---- Phần của Nguyên (N2-N11) ----
    path('', include('payments.urls')),           # N2, N3, N9: minh chứng, xác nhận cọc, xác nhận phần còn lại
    path('', include('delivery.urls')),           # N4-N8: bàn giao ảnh
    path('', include('reviews.urls')),            # N11: đánh giá nhiếp ảnh gia
]

# Khi chạy thử (DEBUG = True): địa chỉ /media/... dẫn tới thư mục media/ trên máy,
# để xem được ảnh đại diện, ảnh Portfolio được tải lên.
# Khi triển khai thật (DEBUG = False) đoạn này tự tắt, máy chủ thật sẽ phát file.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
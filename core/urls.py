# ▸ Nạp hàm path: dùng để khai báo "địa chỉ web nào thì chạy chức năng nào".
from django.urls import path

# ▸ Nạp 2 file xử lý của app core: views (chung, có trang ui_kit) và views_trang_chu (chỉ trang chủ B8).
from . import views, views_trang_chu

# ▸ urlpatterns là "bảng chỉ đường" của website: Django đọc danh sách này để biết địa chỉ nào dẫn tới trang nào.
urlpatterns = [
    # ▸ Địa chỉ rỗng "" = trang gốc (vd framie.vn/). Khi khách vào đây thì chạy hàm trang_chu. name="home" là tên gọi nội bộ
    # ▸ để chỗ khác (menu, header, footer) gọi tới trang chủ mà không phải gõ cứng địa chỉ.
    path("", views_trang_chu.trang_chu, name="home"),   # B8: Trang chủ; name="home" khớp menu, header, footer
    # ▸ Địa chỉ "ui-kit/" mở trang mẫu giao diện (bộ nút, màu, thẻ...) dành cho lập trình viên xem thử. name="ui_kit" là tên gọi nội bộ.
    path("ui-kit/", views.ui_kit, name="ui_kit"),       # chỉ nên mở khi DEBUG
# ▸ Đóng danh sách đường dẫn.
]

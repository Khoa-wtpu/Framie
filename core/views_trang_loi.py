# =====================================================================
# core/views_trang_loi.py  -  B10: Trang lỗi (403, 404, 500) và trang tĩnh (Giới thiệu, Điều khoản)
# Tất cả bằng tiếng Việt, có nút "Về trang chủ".
# Cách nối: config/urls.py khai báo handler403 / handler404 / handler500 trỏ vào 3 hàm bên dưới.
# Lưu ý: khi DEBUG = True, Django hiện trang lỗi chi tiết của nó để lập trình viên sửa lỗi;
# trang lỗi tiếng Việt này chỉ hiện khi DEBUG = False (chạy thật).
# =====================================================================
from django.shortcuts import redirect, render
from django.urls import reverse


def loi_403(request, exception=None):
    """403: đã đăng nhập nhưng không đủ quyền vào trang này."""
    return render(request, "core/loi_403.html", status=403)


def loi_404(request, exception=None):
    """404: địa chỉ không tồn tại (hoặc không được phép thấy)."""
    return render(request, "core/loi_404.html", status=404)


def loi_500(request):
    """500: lỗi hệ thống. Template độc lập (không extends base) vì lúc này context processor có thể cũng đang lỗi."""
    return render(request, "core/loi_500.html", status=500)


def gioi_thieu(request):
    """Trang tĩnh Giới thiệu (khớp menu của Khách: name='about'). Gồm cả Điều khoản sử dụng, Chính sách bảo mật và Câu hỏi thường gặp."""
    return render(request, "core/gioi_thieu.html")


def dieu_khoan(request):
    """Địa chỉ cũ /dieu-khoan/ (name='terms'): Điều khoản nay nằm trong trang Giới thiệu, nên chuyển tới đúng phần đó."""
    return redirect(reverse("about") + "#dieu-khoan")

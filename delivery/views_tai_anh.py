# delivery/views_tai_anh.py - N10 / UC5.8: Khách hàng tải về thiết bị ảnh hoàn chỉnh
from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from accounts.permissions import chi_khach_hang                # chỉ Khách hàng (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
from bookings.models import Booking
from delivery import services_tai_anh as services


def _doc_ma_anh(gia_tri):                                      # ['3', '5'] -> [3, 5]; sai kiểu -> None
    try:
        return [int(g) for g in gia_tri]
    except (TypeError, ValueError):
        return None


@chi_khach_hang
def tai_anh_hoan_chinh(request, ma_booking):                   # trang UC5.8
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaNhiepAnhGia'), pk=ma_booking, MaKhachHang=request.user)

    if request.method == 'POST':                               # bước 3: Khách bấm một trong ba nút tải
        ds, hop_le = None, True                                # ds=None nghĩa là tải tất cả ảnh hoàn chỉnh
        if 'tai_mot' in request.POST:                          # nút "Tải" cạnh từng ảnh
            ds = _doc_ma_anh([request.POST.get('tai_mot')])
            hop_le = ds is not None
        elif 'tai_tat_ca' in request.POST:                     # nút "Tải tất cả"
            pass
        elif 'tai_chon' in request.POST:                       # nút "Tải ảnh đã chọn"
            ds = _doc_ma_anh(request.POST.getlist('anh'))
            hop_le = ds is not None
        else:                                                  # nút lạ
            hop_le = False
        if not hop_le:
            messages.error(request, 'Thao tác không hợp lệ.')
        else:
            try:
                kq = services.chuan_bi_tai(booking.pk, request.user, ds)   # bước 4: hệ thống chuẩn bị tệp và ghi lịch sử
            except services.LoiTaiHoanChinh as loi:            # hết hạn (4a), lỗi tải (5a), chưa chọn ảnh...
                messages.error(request, str(loi))
            else:
                phan_hoi = FileResponse(kq['tep'], as_attachment=True, filename=kq['ten_tep'], content_type=kq['content_type'])
                phan_hoi['Cache-Control'] = 'private, no-store, max-age=0'      # không cho lưu bản sao vào bộ nhớ đệm / proxy
                phan_hoi['X-Content-Type-Options'] = 'nosniff'
                return phan_hoi                                # trình duyệt tải về thiết bị

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    ly_do = services.ly_do_khong_tai_duoc(booking)             # None = tải được
    han = services.han_tai_anh(booking)
    return render(request, 'delivery/tai_anh_hoan_chinh.html', {
        'booking': booking, 'ly_do': ly_do,
        'anhs': list(services.anh_hoan_chinh(booking)) if ly_do is None else [],   # bước 2: danh sách ảnh hoàn chỉnh
        'han_tai': timezone.localtime(han) if han else None,
        'lich_su': services.lich_su_tai(booking)})

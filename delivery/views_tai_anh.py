# delivery/views_tai_anh.py - N10 / UC5.8: Khách hàng tải về thiết bị ảnh hoàn chỉnh
# Nạp thư viện/module được sử dụng trong file.
import io

# Nạp thành phần từ module django.contrib để dùng bên dưới.
from django.contrib import messages
# Nạp thành phần từ module django.http để dùng bên dưới.
from django.http import FileResponse, Http404, HttpResponse
# Nạp thành phần từ module django.shortcuts để dùng bên dưới.
from django.shortcuts import get_object_or_404, render
# Nạp thành phần từ module django.utils để dùng bên dưới.
from django.utils import timezone
# Nạp thành phần từ module PIL để dùng bên dưới.
from PIL import Image, ImageOps

from accounts.permissions import chi_khach_hang                # chỉ Khách hàng (chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403)
# Nạp thành phần từ module bookings.models để dùng bên dưới.
from bookings.models import Booking
# Nạp thành phần từ module core.constants để dùng bên dưới.
from core.constants import LoaiAnh, LuuTruAnh
# Nạp thành phần từ module delivery để dùng bên dưới.
from delivery import services_tai_anh as services
# Nạp thành phần từ module delivery.models để dùng bên dưới.
from delivery.models import Anh


def _doc_ma_anh(gia_tri):                                      # ['3', '5'] -> [3, 5]; sai kiểu -> None
    # Bắt và xử lý lỗi để tránh làm gián đoạn luồng chính.
    try:
        # Trả kết quả của bước xử lý hiện tại.
        return [int(g) for g in gia_tri]
    except (TypeError, ValueError):
        # Trả kết quả của bước xử lý hiện tại.
        return None


@chi_khach_hang
def tai_anh_hoan_chinh(request, ma_booking):                   # trang UC5.8
    booking = get_object_or_404(                               # bước 1: chỉ mở được Booking của chính mình
        Booking.objects.select_related('MaGoi', 'MaNhiepAnhGia'), pk=ma_booking, MaKhachHang=request.user)

    if request.method == 'POST':                               # bước 3: Khách bấm một trong ba nút tải
        ds, hop_le = None, True                                # ds=None nghĩa là tải tất cả ảnh hoàn chỉnh
        if 'tai_mot' in request.POST:                          # nút "Tải" cạnh từng ảnh
            # Gán giá trị cho ds.
            ds = _doc_ma_anh([request.POST.get('tai_mot')])
            # Gán giá trị cho hop_le.
            hop_le = ds is not None
        elif 'tai_tat_ca' in request.POST:                     # nút "Tải tất cả"
            # Không thực hiện thao tác tại đây; giữ chỗ cho cấu trúc này.
            pass
        elif 'tai_chon' in request.POST:                       # nút "Tải ảnh đã chọn"
            # Gán giá trị cho ds.
            ds = _doc_ma_anh(request.POST.getlist('anh'))
            # Gán giá trị cho hop_le.
            hop_le = ds is not None
        else:                                                  # nút lạ
            # Gán giá trị cho hop_le.
            hop_le = False
        # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
        if not hop_le:
            # Thực hiện lời gọi hàm để xử lý bước này.
            messages.error(request, 'Thao tác không hợp lệ.')
        else:
            # Bắt và xử lý lỗi để tránh làm gián đoạn luồng chính.
            try:
                kq = services.chuan_bi_tai(booking.pk, request.user, ds)   # bước 4: hệ thống chuẩn bị tệp và ghi lịch sử
            except services.LoiTaiHoanChinh as loi:            # hết hạn (4a), lỗi tải (5a), chưa chọn ảnh...
                # Thực hiện lời gọi hàm để xử lý bước này.
                messages.error(request, str(loi))
            else:
                # Gán giá trị cho phan_hoi.
                phan_hoi = FileResponse(kq['tep'], as_attachment=True, filename=kq['ten_tep'], content_type=kq['content_type'])
                phan_hoi['Cache-Control'] = 'private, no-store, max-age=0'      # không cho lưu bản sao vào bộ nhớ đệm / proxy
                # Lưu kết quả xử lý vào biến.
                phan_hoi['X-Content-Type-Options'] = 'nosniff'
                return phan_hoi                                # trình duyệt tải về thiết bị

    booking.refresh_from_db()                                  # đọc lại trạng thái mới nhất
    ly_do = services.ly_do_khong_tai_duoc(booking)             # None = tải được
    # Gán giá trị cho han.
    han = services.han_tai_anh(booking)
    # Trả kết quả của bước xử lý hiện tại.
    return render(request, 'delivery/tai_anh_hoan_chinh.html', {
        'booking': booking, 'ly_do': ly_do,
        'anhs': list(services.anh_hoan_chinh(booking)) if ly_do is None else [],   # bước 2: danh sách ảnh hoàn chỉnh
        'han_tai': timezone.localtime(han) if han else None,
        'lich_su': services.lich_su_tai(booking)})


@chi_khach_hang
def xem_truoc_anh_hoan_chinh(request, ma_booking, ma_anh):      # ảnh THU NHỎ để Khách xem trước trong danh sách (không phải bản tải về)
    # Gán giá trị cho anh.
    anh = get_object_or_404(
        Anh.objects.select_related('MaBooking'), pk=ma_anh, MaBooking=ma_booking,
        MaBooking__MaKhachHang=request.user,                    # chỉ ảnh thuộc Booking của chính Khách
        LoaiAnh=LoaiAnh.HOAN_CHINH, TrangThaiLuuTru=LuuTruAnh.CON_LUU)
    if services.ly_do_khong_tai_duoc(anh.MaBooking):            # hết hạn / chưa hoàn thành thì không phục vụ
        # Phát sinh lỗi để báo trường hợp không hợp lệ.
        raise Http404
    # Bắt và xử lý lỗi để tránh làm gián đoạn luồng chính.
    try:
        # Mở ngữ cảnh xử lý; tài nguyên/transaction được quản lý theo khối này.
        with services.kho_anh().open(anh.DuongDanAnh, 'rb') as tep, Image.open(tep) as hinh:
            hinh = ImageOps.exif_transpose(hinh)                # xoay đúng chiều theo EXIF
            # Thực hiện lời gọi hàm để xử lý bước này.
            hinh.thumbnail((480, 480))
            if hinh.mode in ('RGBA', 'LA', 'P'):                # PNG trong suốt -> nền trắng
                # Gán giá trị cho hinh.
                hinh = hinh.convert('RGBA')
                # Gán giá trị cho nen.
                nen = Image.new('RGB', hinh.size, (255, 255, 255))
                # Thực hiện lời gọi hàm để xử lý bước này.
                nen.paste(hinh, mask=hinh.getchannel('A'))
                # Gán giá trị cho hinh.
                hinh = nen
            else:
                # Gán giá trị cho hinh.
                hinh = hinh.convert('RGB')
            # Gán giá trị cho dem.
            dem = io.BytesIO()
            # Thực hiện lời gọi hàm để xử lý bước này.
            hinh.save(dem, format='JPEG', quality=80, optimize=True)
    except Exception:
        # Phát sinh lỗi để báo trường hợp không hợp lệ.
        raise Http404
    # Gán giá trị cho phan_hoi.
    phan_hoi = HttpResponse(dem.getvalue(), content_type='image/jpeg')
    # Lưu kết quả xử lý vào biến.
    phan_hoi['Content-Disposition'] = 'inline'
    # Lưu kết quả xử lý vào biến.
    phan_hoi['Cache-Control'] = 'private, no-store, max-age=0'
    # Lưu kết quả xử lý vào biến.
    phan_hoi['X-Content-Type-Options'] = 'nosniff'
    # Trả kết quả của bước xử lý hiện tại.
    return phan_hoi
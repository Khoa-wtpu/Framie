# reviews/services.py - N11 / UC6.1: Đánh giá nhiếp ảnh gia (Nguyên)
#
#   ly_do_khong_danh_gia_duoc(booking)         -> câu báo nếu Khách KHÔNG đánh giá được lúc này, hoặc None
#   tao_danh_gia(ma_booking, khach, diem, nx)  -> tạo Đánh giá (1 Booking 1 lần)
#   gui_nhac_danh_gia(booking)                 -> gửi thông báo nhắc đánh giá (gọi khi Booking vừa Hoàn thành)
#   thong_ke_danh_gia(nag)                     -> điểm trung bình + số lượt + phân bố 1..5 sao
#   lay_trang_danh_gia(nag, so_trang)          -> (thống kê, trang đánh giá) để hiện công khai trên hồ sơ
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Avg, Count

from bookings.models import Booking
from core.constants import TrangThaiBooking
from notifications.models import ThongBao
from notifications.services import gui_thong_bao_kem_email
from reviews.models import DanhGia

logger = logging.getLogger(__name__)

DO_DAI_NHAN_XET_TOI_DA = 500                                   # DANHGIA.NhanXet VARCHAR(500)
SO_DANH_GIA_MOI_TRANG = 10                                     # số đánh giá mỗi trang ở hồ sơ công khai
TIEU_DE_NHAC_DANH_GIA = 'Hãy đánh giá nhiếp ảnh gia'           # tiêu đề thông báo nhắc (cũng dùng để không nhắc trùng)


class LoiDanhGia(Exception):                                   # lỗi nghiệp vụ của UC6.1: view bắt lại để hiện cho Khách hàng
    pass


def chuan_hoa_nhan_xet(nhan_xet):                              # bỏ khoảng trắng 2 đầu, đổi xuống dòng \r\n -> \n; rỗng -> None
    nhan_xet = (nhan_xet or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    return nhan_xet or None


def ly_do_khong_danh_gia_duoc(booking):                        # trả về câu báo nếu Khách KHÔNG đánh giá được lúc này, hoặc None nếu được
    if booking.TrangThai != TrangThaiBooking.HOAN_THANH:       # BR: chỉ Booking Hoàn thành mới đánh giá được
        return f'Chỉ Booking ở trạng thái "Hoàn thành" mới được đánh giá. Booking này đang ở trạng thái "{booking.TrangThai}".'
    if DanhGia.objects.filter(MaBooking=booking).exists():     # BR: mỗi Booking chỉ đánh giá một lần
        return 'Bạn đã đánh giá Booking này rồi. Mỗi Booking chỉ được đánh giá một lần.'
    return None


def tao_danh_gia(ma_booking, khach, diem, nhan_xet=None):      # lưu đánh giá; trả về đối tượng DanhGia
    try:
        diem = int(diem)                                       # điểm phải là số nguyên
    except (TypeError, ValueError):
        raise LoiDanhGia('Vui lòng chọn số sao từ 1 đến 5.')   # chưa chọn sao
    if not 1 <= diem <= 5:
        raise LoiDanhGia('Vui lòng chọn số sao từ 1 đến 5.')
    nhan_xet = chuan_hoa_nhan_xet(nhan_xet)                    # nhận xét không bắt buộc
    if nhan_xet and len(nhan_xet) > DO_DAI_NHAN_XET_TOI_DA:
        raise LoiDanhGia(f'Nhận xét tối đa {DO_DAI_NHAN_XET_TOI_DA} ký tự.')

    try:
        with transaction.atomic():                             # 1 giao dịch: khóa Booking rồi kiểm tra + tạo, tránh bấm 2 lần tạo trùng
            try:
                booking = (Booking.objects.select_for_update()
                           .get(pk=ma_booking, MaKhachHang=khach))   # phải là Booking của chính Khách này
            except Booking.DoesNotExist:
                raise LoiDanhGia('Booking không tồn tại hoặc không thuộc về bạn.')
            ly_do = ly_do_khong_danh_gia_duoc(booking)
            if ly_do:
                raise LoiDanhGia(ly_do)
            danh_gia = DanhGia(MaBooking=booking, MaNhiepAnhGia_id=booking.MaNhiepAnhGia_id,   # nhiếp ảnh gia luôn lấy từ Booking
                               Diem=diem, NhanXet=nhan_xet)
            danh_gia.full_clean()                              # kiểm tra lại các ràng buộc ở tầng ứng dụng của model
            danh_gia.save()
    except ValidationError as loi:
        raise LoiDanhGia(' '.join(loi.messages))
    except IntegrityError:                                     # hai yêu cầu cùng lúc: bản ghi thứ hai vi phạm UNIQUE(MaBooking)
        raise LoiDanhGia('Bạn đã đánh giá Booking này rồi. Mỗi Booking chỉ được đánh giá một lần.')
    except DatabaseError:
        logger.exception('reviews: lưu đánh giá thất bại (Booking %s)', ma_booking)
        raise LoiDanhGia('Không thể lưu đánh giá, vui lòng thử lại.')
    return danh_gia


def gui_nhac_danh_gia(booking):                                # nhắc Khách đánh giá; N9 gọi ngay sau khi Booking chuyển sang Hoàn thành
    """Trả về ThongBao vừa tạo, hoặc None nếu không cần nhắc (chưa Hoàn thành, đã đánh giá, đã nhắc rồi, lỗi).
    Gọi nhiều lần vẫn chỉ nhắc đúng một lần cho mỗi Booking."""
    try:
        booking = Booking.objects.select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan').get(pk=getattr(booking, 'pk', booking))
    except Booking.DoesNotExist:
        return None
    if booking.TrangThai != TrangThaiBooking.HOAN_THANH:       # chỉ nhắc khi Booking đã Hoàn thành
        return None
    if DanhGia.objects.filter(MaBooking=booking).exists():     # đã đánh giá rồi thì khỏi nhắc
        return None
    if ThongBao.objects.filter(MaNguoiNhan=booking.MaKhachHang, MaBooking=booking, TieuDe=TIEU_DE_NHAC_DANH_GIA).exists():
        return None                                            # đã nhắc rồi
    nag_user = booking.MaNhiepAnhGia.MaTaiKhoan
    ten_nag = nag_user.get_full_name() or nag_user.username
    return gui_thong_bao_kem_email(                            # web + email (TO-BE 12.1, P12); hàm của Phanh tự nuốt lỗi, không làm hỏng nghiệp vụ chính
        booking.MaKhachHang, TIEU_DE_NHAC_DANH_GIA,
        f'Booking #{booking.pk} đã hoàn thành. Hãy dành ít phút đánh giá nhiếp ảnh gia {ten_nag} '
        f'(chọn 1 đến 5 sao, nhận xét không bắt buộc) để giúp những khách hàng khác chọn đúng người.',
        booking=booking)


def thong_ke_danh_gia(nag):                                    # điểm trung bình + số lượt + phân bố sao của một nhiếp ảnh gia
    tong = DanhGia.objects.filter(MaNhiepAnhGia=nag).aggregate(diem_tb=Avg('Diem'), so_danh_gia=Count('pk'))
    theo_sao = dict(DanhGia.objects.filter(MaNhiepAnhGia=nag).values_list('Diem').annotate(n=Count('pk')))
    so = tong['so_danh_gia'] or 0
    phan_bo = [{'sao': sao, 'so': theo_sao.get(sao, 0),
                'phan_tram': round(theo_sao.get(sao, 0) * 100 / so) if so else 0} for sao in (5, 4, 3, 2, 1)]
    return {'diem_tb': round(tong['diem_tb'], 1) if tong['diem_tb'] is not None else None,
            'so_danh_gia': so, 'phan_bo': phan_bo}


def lay_trang_danh_gia(nag, so_trang=None):                    # (thống kê, trang đánh giá mới nhất trước) để hiện công khai
    ds = (DanhGia.objects.filter(MaNhiepAnhGia=nag)
          .select_related('MaBooking__MaKhachHang', 'MaBooking__MaGoi')
          .order_by('-NgayDanhGia', '-pk'))
    trang = Paginator(ds, SO_DANH_GIA_MOI_TRANG).get_page(so_trang)   # số trang sai -> về trang hợp lệ
    return thong_ke_danh_gia(nag), trang

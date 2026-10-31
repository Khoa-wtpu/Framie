# =====================================================================
# accounts/quan_tri.py  -  B7: số liệu cho trang tổng quan Quản trị
# =====================================================================
from django.contrib.auth import get_user_model  # lấy class User của dự án (accounts.User)
from django.db.models import Count  # hàm đếm dùng khi gom nhóm theo trạng thái

from core.constants import TrangThaiBooking, TrangThaiHoSo, TrangThaiThanhToan  # tên trạng thái, không tự gõ chữ tiếng Việt (README)


def thong_ke_tong_quan():  # gom các con số hiển thị ở trang tổng quan
    from bookings.models import Booking  # import trong hàm để tránh import vòng giữa các app
    from payments.models import ThanhToan  # như trên

    User = get_user_model()  # class User của dự án
    dem_booking = dict(  # từ điển: trạng thái -> số Booking
        Booking.objects.order_by().values_list('TrangThai').annotate(n=Count('pk'))  # GROUP BY TrangThai, order_by() để bỏ sắp xếp mặc định
    )  # hết truy vấn
    booking_theo_trang_thai = [  # danh sách đủ 13 trạng thái, kể cả trạng thái có 0 Booking
        {'ten': ten, 'so_luong': dem_booking.get(ten, 0)}  # lấy số lượng, không có thì 0
        for ten in TrangThaiBooking.ALL  # đúng thứ tự quy trình trong core/constants.py
    ]  # hết danh sách
    return {  # trả các số liệu cho view
        'ho_so_cho_duyet': User.objects.filter(trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET).count(),  # số hồ sơ đang chờ duyệt
        'tong_tai_khoan': User.objects.count(),  # tổng số tài khoản
        'tong_booking': sum(dem_booking.values()),  # tổng số Booking
        'thanh_toan_cho_xac_nhan': ThanhToan.objects.filter(  # số khoản thanh toán đang chờ xác nhận
            TrangThai__in=[TrangThaiThanhToan.CHO_XAC_NHAN_COC, TrangThaiThanhToan.CHO_XAC_NHAN_60]  # cọc 40% hoặc 60% còn lại
        ).count(),  # đếm
        'booking_theo_trang_thai': booking_theo_trang_thai,  # danh sách 13 trạng thái kèm số lượng
    }  # hết dict


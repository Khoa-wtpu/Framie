# =====================================================================
# accounts/quan_tri.py  -  B7: dữ liệu cho khung Quản trị (menu + số liệu tổng quan)
# =====================================================================
from django.contrib.auth import get_user_model  # lấy class User của dự án (accounts.User)
from django.db.models import Count  # hàm đếm dùng khi gom nhóm theo trạng thái

from core.constants import TrangThaiBooking, TrangThaiHoSo, TrangThaiThanhToan  # tên trạng thái, không tự gõ chữ tiếng Việt (README)
from core.navigation import resolve  # đổi tên URL thành đường dẫn; tên chưa tồn tại thì trả "#" (không gây lỗi)

TEN_URL_TONG_QUAN = 'admin_dashboard'  # tên URL trang tổng quan (khớp TRANG_CHU_THEO_VAI_TRO trong permissions.py)

# Menu bên trái khung Quản trị: (nhãn hiển thị, tên URL). Muốn thêm/bớt mục chỉ sửa danh sách này.
MENU_QUAN_TRI = [  # bắt đầu danh sách mục menu
    ('Tổng quan', TEN_URL_TONG_QUAN),  # trang tổng quan của B7
    ('Duyệt hồ sơ', 'admin_profile_review'),  # trang của Khoa (module profiles)
    ('Tài khoản và phân quyền', 'admin_accounts'),  # trang của Phanh (module accounts)
    ('Booking', 'admin_bookings'),  # trang của Tuyền (module bookings)
    ('Giao dịch', 'admin_payments'),  # trang của Nguyên (module payments)
]  # hết danh sách


def tao_menu(duong_dan_hien_tai):  # tạo danh sách mục menu kèm cờ "đang mở"
    ket_qua = []  # danh sách kết quả, mỗi phần tử là một dict
    for nhan, ten_url in MENU_QUAN_TRI:  # duyệt từng mục đã khai báo
        url = resolve(ten_url)  # đổi tên URL thành đường dẫn thật (hoặc "#")
        if url == '#':  # trang của module khác chưa làm xong
            dang_mo = False  # không thể "đang mở" một link tạm
        elif ten_url == TEN_URL_TONG_QUAN:  # trang tổng quan
            dang_mo = duong_dan_hien_tai == url  # chỉ sáng khi đúng trang này (tránh sáng khi ở trang con)
        else:  # các mục còn lại
            dang_mo = duong_dan_hien_tai.startswith(url)  # sáng cả khi đang ở trang con, ví dụ /quan-tri/booking/12/
        ket_qua.append({'label': nhan, 'url': url, 'active': dang_mo})  # thêm mục vào kết quả
    return ket_qua  # trả danh sách cho template


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

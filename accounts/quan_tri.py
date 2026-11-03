# =====================================================================
# accounts/quan_tri.py  -  B7: số liệu cho trang tổng quan Quản trị
# =====================================================================
from django.contrib.auth import get_user_model  # lấy class User của dự án (accounts.User)
from django.db.models import Count  # hàm đếm dùng khi gom nhóm theo trạng thái

from core.status_tones import tone_of  # Tuyền gán trạng thái -> tông màu, dùng lại để không gán màu ở 2 nơi
from core.constants import TrangThaiBooking, TrangThaiHoSo, TrangThaiThanhToan  # tên trạng thái, không tự gõ chữ tiếng Việt (README)

# ---- Hướng 7: 5 nhóm trạng thái Booking (tên nhóm và các trạng thái thuộc nhóm; màu lấy từ status_tones.py) ----
NHOM_BOOKING = [  # thứ tự nhóm = thứ tự trong quy trình, từ trái sang phải trên trang
    {'ma': 'cho-nag', 'ten': 'Chờ Nhiếp ảnh gia', 'trang_thai': [  # nhóm đang chờ Nhiếp ảnh gia xử lý
        TrangThaiBooking.CHO_XAC_NHAN,  # Chờ xác nhận
        TrangThaiBooking.CHO_HAU_KY,  # Chờ hậu kỳ
        TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN,  # Chờ xác nhận thanh toán
    ]},  # hết nhóm 1
    {'ma': 'cho-kh', 'ten': 'Chờ Khách hàng', 'trang_thai': [  # nhóm đang chờ Khách hàng xử lý
        TrangThaiBooking.CHO_DAT_COC,  # Chờ đặt cọc
        TrangThaiBooking.CHO_KH_CHON_ANH,  # Chờ lựa chọn ảnh
        TrangThaiBooking.CHO_KH_KIEM_TRA,  # Chờ kiểm tra
    ]},  # hết nhóm 2
    {'ma': 'dang-dien-ra', 'ten': 'Đang diễn ra', 'trang_thai': [  # nhóm đang thực hiện
        TrangThaiBooking.CHOT_BOOKING,  # Chốt Booking
        TrangThaiBooking.DA_CHUP,  # Đã chụp
        TrangThaiBooking.DANG_HAU_KY,  # Đang hậu kỳ
    ]},  # hết nhóm 3
    {'ma': 'hoan-tat', 'ten': 'Hoàn tất', 'trang_thai': [  # nhóm kết thúc tốt đẹp
        TrangThaiBooking.HOAN_THANH,  # Hoàn thành
    ]},  # hết nhóm 4
    {'ma': 'khong-thanh-cong', 'ten': 'Không thành công', 'trang_thai': [  # nhóm thất bại hoặc đã hủy
        TrangThaiBooking.DA_TU_CHOI,  # Đã từ chối
        TrangThaiBooking.HET_THOI_HAN_DAT_COC,  # Hết thời hạn đặt cọc
        TrangThaiBooking.DA_HUY,  # Đã hủy
    ]},  # hết nhóm 5
]  # hết danh sách nhóm


def booking_theo_nhom(dem_booking, tong):  # gom số Booking theo 5 nhóm, kèm phần trăm trên tổng
    ket_qua = []  # danh sách nhóm trả về cho template
    for nhom in NHOM_BOOKING:  # duyệt từng nhóm
        dong = [{'ten': ten, 'so_luong': dem_booking.get(ten, 0)} for ten in nhom['trang_thai']]  # từng trạng thái kèm số lượng
        so_nhom = sum(d['so_luong'] for d in dong)  # số Booking của cả nhóm
        ket_qua.append({  # thêm nhóm vào kết quả
            'ma': nhom['ma'],  # mã nhóm (test và giao diện dùng để nhận ra nhóm)
            'ten': nhom['ten'],  # tên nhóm
            'tone': tone_of(nhom['trang_thai'][0]),  # tông màu lấy từ core/status_tones.py (cả nhóm cùng màu), template ghép thành class tone-...
            'tong': so_nhom,  # số lớn trên thẻ
            'phan_tram': round(so_nhom * 100 / tong, 1) if tong else 0,  # % trên tổng Booking, 1 chữ số thập phân; tổng 0 thì tránh chia cho 0
            'muc': dong,  # các dòng trạng thái trong thẻ (tên khóa 'muc' khớp test có sẵn)
        })  # hết một nhóm
    return ket_qua  # trả danh sách 5 nhóm


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
        'booking_theo_trang_thai': booking_theo_trang_thai,  # danh sách 13 trạng thái kèm số lượng (test đang kiểm tra khóa này, đừng xóa)
        'booking_theo_nhom': booking_theo_nhom(dem_booking, sum(dem_booking.values())),  # 5 nhóm cho giao diện Hướng 7
    }  # hết dict

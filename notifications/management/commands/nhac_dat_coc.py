# notifications/management/commands/nhac_dat_coc.py - P9: nhắc Khách hàng đặt cọc sắp hết hạn (Phanh)
# Chạy tay: python manage.py nhac_dat_coc   |   Khi triển khai: đặt lịch chạy mỗi 15-30 phút (Task Scheduler hoặc cron)
from datetime import timedelta  # khoảng thời gian, để tính mốc "sắp hết hạn"

from django.core.management.base import BaseCommand  # lớp cha của mọi lệnh manage.py
from django.utils import timezone  # giờ hiện tại có múi giờ

from bookings.models import Booking  # model Booking của Tuyền (dùng các cột TrangThai, HanDatCoc, MaKhachHang)
from core.constants import TrangThaiBooking  # tên trạng thái Booking, không tự gõ chữ tiếng Việt
from notifications.models import ThongBao  # để kiểm tra đã nhắc Booking này chưa
from notifications.services import gui_thong_bao_kem_email  # gửi thông báo web + email

SO_GIO_NHAC_TRUOC = 6  # nhắc khi còn tối đa 6 giờ là hết hạn đặt cọc (hạn đặt cọc là 1 ngày); chỉnh theo đặc tả P9
TIEU_DE_NHAC = 'Nhắc đặt cọc Booking'  # tiêu đề cố định, cũng dùng để nhận biết đã nhắc rồi


class Command(BaseCommand):  # mỗi lệnh manage.py là một lớp tên Command
    help = 'Nhắc Khách hàng đặt cọc cho Booking ở trạng thái Chờ đặt cọc sắp hết hạn.'  # hiện khi gõ manage.py help nhac_dat_coc

    def handle(self, *args, **options):  # hàm chạy khi gõ lệnh
        bay_gio = timezone.now()  # giờ hiện tại
        sap_het_han = bay_gio + timedelta(hours=SO_GIO_NHAC_TRUOC)  # mốc: hạn đặt cọc nằm trong khoảng từ giờ đến mốc này là cần nhắc
        ds = Booking.objects.filter(  # tìm các Booking cần nhắc
            TrangThai=TrangThaiBooking.CHO_DAT_COC,  # đang chờ đặt cọc
            HanDatCoc__gt=bay_gio,  # chưa quá hạn (quá hạn thì hệ thống chuyển sang Hết thời hạn đặt cọc, không nhắc nữa)
            HanDatCoc__lte=sap_het_han,  # nhưng sắp hết hạn
        ).select_related('MaKhachHang')  # nạp sẵn Khách hàng để không truy vấn lặp
        so_da_nhac = 0  # đếm số lượt nhắc để in kết quả
        for booking in ds:  # duyệt từng Booking cần nhắc
            khach = booking.MaKhachHang  # tài khoản Khách hàng
            if ThongBao.objects.filter(MaBooking=booking, MaNguoiNhan=khach, TieuDe=TIEU_DE_NHAC).exists():  # đã nhắc rồi
                continue  # không nhắc lần hai, tránh spam khi lệnh chạy định kỳ
            han = timezone.localtime(booking.HanDatCoc)  # đổi sang giờ Việt Nam để hiển thị
            noi_dung = (f'Booking #{booking.pk} của bạn cần được đặt cọc 40% trước {han:%H:%M %d/%m/%Y}. '  # nội dung nhắc
                        'Quá hạn Booking sẽ hết hiệu lực và khung giờ được mở lại.')  # hệ quả khi quá hạn: slot được trả về cho người khác đặt
            gui_thong_bao_kem_email(khach, TIEU_DE_NHAC, noi_dung, booking=booking)  # thông báo web + email
            so_da_nhac += 1  # tăng bộ đếm
        self.stdout.write(f'Đã nhắc {so_da_nhac} Booking.')  # in kết quả ra Terminal
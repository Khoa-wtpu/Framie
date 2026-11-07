# notifications/tests_email.py - kiểm tra P9 (gửi email kèm thông báo). Chạy: python manage.py test notifications.tests_email
from datetime import date, time, timedelta  # ngày giờ để dựng slot và hạn đặt cọc (test nhac_dat_coc)
from io import StringIO  # hứng chữ lệnh nhac_dat_coc in ra
from unittest.mock import patch  # giả lập lỗi SMTP

from django.contrib.auth import get_user_model  # model User của project
from django.core import mail  # mail.outbox: hộp thư giả của Django khi chạy test
from django.core.management import call_command  # chạy lệnh manage.py ngay trong test
from django.test import TestCase, override_settings  # TestCase dùng DB tạm; override_settings đổi cấu hình trong test
from django.utils import timezone  # giờ hiện tại có múi giờ

from bookings.models import Booking  # model Booking của Tuyền
from core.constants import (LoaiHauKy, LoaiThanhToan, TrangThaiBooking, TrangThaiGuiEmail, TrangThaiSlot,  # hằng số trạng thái, không tự gõ chữ tiếng Việt
                            TrangThaiThanhToan)
from payments.models import ThanhToan  # khoản thanh toán (minh chứng cọc)
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia  # hồ sơ Nhiếp ảnh gia, gói, loại hình để dựng Booking
from schedule.models import LichKhaDung  # khung giờ của Nhiếp ảnh gia
from notifications.models import ThongBao  # đếm thông báo đã lưu
from notifications.services import (  # các hàm cần thử
    gui_thong_bao, gui_thong_bao_kem_email, gui_thong_bao_nhieu_nguoi_kem_email,
)

User = get_user_model()  # gán tên User
HOP_THU_GIA = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}  # email chỉ vào mail.outbox, không gửi thật


@override_settings(MAILERS=HOP_THU_GIA)  # mọi test trong lớp dùng hộp thư giả
class GuiEmailTestCase(TestCase):  # nhóm test P9
    @classmethod  # chạy một lần trước cả nhóm
    def setUpTestData(cls):  # tạo dữ liệu mẫu
        cls.a = User.objects.create_user('a', 'a@example.com', 'Matkhau@123', so_dien_thoai='0900000001')  # người dùng có email
        cls.b = User.objects.create_user('b', 'b@example.com', 'Matkhau@123', so_dien_thoai='0900000002')  # người dùng thứ hai
        cls.khong_email = User.objects.create_user('c', '', 'Matkhau@123', so_dien_thoai='0900000003')  # người dùng chưa có email

    def test_gui_thanh_cong(self):  # gửi được thì ghi 'Gửi thành công'
        with self.captureOnCommitCallbacks(execute=True):  # chạy luôn các việc "sau commit" (TestCase không commit thật)
            tb = gui_thong_bao_kem_email(self.a, 'Booking mới', 'Có yêu cầu mới')  # gửi thông báo + email
        self.assertEqual(len(mail.outbox), 1)  # đúng 1 email
        self.assertEqual(mail.outbox[0].to, ['a@example.com'])  # gửi đúng người
        self.assertEqual(mail.outbox[0].subject, 'Booking mới')  # đúng tiêu đề
        self.assertIn('Có yêu cầu mới', mail.outbox[0].body)  # nội dung có trong thư
        tb.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(tb.TrangThaiGuiEmail, TrangThaiGuiEmail.THANH_CONG)  # đã ghi kết quả

    def test_chua_gui_truoc_khi_commit(self):  # email chỉ gửi sau commit
        with self.captureOnCommitCallbacks(execute=False) as cac_viec:  # chỉ gom việc, chưa chạy
            gui_thong_bao_kem_email(self.a, 'x', 'y')  # gửi thông báo + email
            self.assertEqual(len(mail.outbox), 0)  # trước commit chưa có thư nào
        self.assertEqual(len(cac_viec), 1)  # có đúng 1 việc đang chờ commit
        cac_viec[0]()  # giả lập commit xong
        self.assertEqual(len(mail.outbox), 1)  # giờ mới có thư

    def test_smtp_loi_khong_lam_hong_thong_bao(self):  # lỗi SMTP: thông báo web vẫn còn, ghi 'Gửi thất bại'
        with patch('notifications.services.send_mail', side_effect=OSError('smtp lỗi')):  # giả lập SMTP hỏng
            with self.captureOnCommitCallbacks(execute=True):  # chạy việc sau commit
                tb = gui_thong_bao_kem_email(self.a, 'x', 'y')  # không được ném lỗi
        self.assertIsNotNone(tb)  # thông báo web vẫn tạo được
        tb.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(tb.TrangThaiGuiEmail, TrangThaiGuiEmail.THAT_BAI)  # ghi thất bại

    def test_nguoi_nhan_khong_co_email(self):  # không có email: không gửi, ghi thất bại
        with self.captureOnCommitCallbacks(execute=True):  # chạy việc sau commit
            tb = gui_thong_bao_kem_email(self.khong_email, 'x', 'y')  # gửi cho người không có email
        self.assertEqual(len(mail.outbox), 0)  # không có thư nào
        tb.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(tb.TrangThaiGuiEmail, TrangThaiGuiEmail.THAT_BAI)  # ghi thất bại

    def test_thieu_noi_dung_khong_gui(self):  # nội dung rỗng: không thông báo, không email
        with self.captureOnCommitCallbacks(execute=True):  # chạy việc sau commit
            tb = gui_thong_bao_kem_email(self.a, 'x', '   ')  # nội dung chỉ có khoảng trắng
        self.assertIsNone(tb)  # không tạo thông báo
        self.assertEqual(len(mail.outbox), 0)  # không gửi email

    def test_nhieu_nguoi_khong_gui_trung(self):  # một người xuất hiện hai lần chỉ nhận một lần
        with self.captureOnCommitCallbacks(execute=True):  # chạy việc sau commit
            ds = gui_thong_bao_nhieu_nguoi_kem_email([self.a, self.b, self.a], 'Hồ sơ mới', 'Có hồ sơ chờ duyệt')  # A hai lần
        self.assertEqual(len(ds), 2)  # 2 thông báo
        self.assertEqual(len(mail.outbox), 2)  # 2 email

    def test_gui_thong_bao_cu_khong_tu_gui_email(self):  # hàm cũ giữ nguyên: không email (tránh gửi trùng với nơi đã tự gọi gui_email_sau_commit)
        with self.captureOnCommitCallbacks(execute=True):  # chạy việc sau commit
            gui_thong_bao(self.a, 'x', 'y')  # gọi hàm cũ
        self.assertEqual(len(mail.outbox), 0)  # không có email
        self.assertEqual(ThongBao.objects.count(), 1)  # chỉ có thông báo web


# =====================================================================
# P12 (Khoa góp ý P9): TEST CHO LỆNH nhac_dat_coc. Chạy: python manage.py test notifications.tests_email
# Dựng dữ liệu giống bookings/test_qua_han.py của Tuyền (Booking có nhiều ràng buộc nên làm đúng cách của Tuyền).
# =====================================================================
@override_settings(MAILERS=HOP_THU_GIA, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # email vào hộp thư giả; băm mật khẩu nhanh
class NhacDatCocTestCase(TestCase):  # nhóm test của lệnh nhac_dat_coc
    def setUp(self):  # chạy trước mỗi test: dựng Khách, Nhiếp ảnh gia, gói dịch vụ
        self.khach = User.objects.create_user('kh_nhac', 'kh_nhac@example.com', 'Matkhau@123', so_dien_thoai='0900000011')  # Khách hàng có email
        nag_user = User.objects.create_user('nag_nhac', 'nag_nhac@example.com', 'Matkhau@123', so_dien_thoai='0900000012')  # tài khoản Nhiếp ảnh gia
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=nag_user, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',  # hồ sơ Nhiếp ảnh gia tối thiểu
                                              SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')  # các cột bắt buộc còn lại
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')  # loại hình chụp
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='G', Gia=1000000,  # gói dịch vụ
                                            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)  # hậu kỳ toàn bộ (giống test của Tuyền)
        self.dem = 0  # bộ đếm để mỗi slot một ngày khác nhau
        self.bay_gio = timezone.now()  # giờ chuẩn của cả test

    def _booking(self, han_dat_coc, trang_thai=TrangThaiBooking.CHO_DAT_COC):  # dựng một Booking với hạn đặt cọc cho trước
        self.dem += 1  # slot mới mỗi lần gọi
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=10 + self.dem),  # slot cách hôm nay vài ngày
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0), TrangThai=TrangThaiSlot.DANG_GIU)  # đang giữ chỗ
        bk = Booking.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,  # tạo Booking
                                    NgayGioChup=self.bay_gio + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,  # ngày chụp xa
                                    Concept='c', TongGiaTri=1000000)  # tổng giá trị 1 triệu
        Booking.objects.filter(pk=bk.pk).update(TrangThai=trang_thai, HanDatCoc=han_dat_coc,  # đặt trạng thái và hạn cọc bằng UPDATE
                                                NgayTao=self.bay_gio - timedelta(days=10))  # lùi NgayTao để hạn cọc luôn sau NgayTao (đúng CHECK của bảng)
        bk.refresh_from_db()  # đọc lại từ DB
        return bk  # trả về Booking

    def _chay_lenh(self):  # chạy lệnh nhac_dat_coc và chạy luôn các việc "sau commit" (gửi email)
        ket_qua = StringIO()  # nơi hứng chữ lệnh in ra
        with self.captureOnCommitCallbacks(execute=True):  # TestCase không commit thật nên phải chạy tay các việc sau commit
            call_command('nhac_dat_coc', stdout=ket_qua)  # chạy lệnh
        return ket_qua.getvalue()  # trả về chữ lệnh đã in

    def test_nhac_dung_booking_trong_6_gio_cuoi(self):  # còn 5 giờ thì phải nhắc: 1 thông báo web + 1 email
        bk = self._booking(self.bay_gio + timedelta(hours=5))  # hạn cọc sau 5 giờ
        chu = self._chay_lenh()  # chạy lệnh
        tb = ThongBao.objects.filter(MaNguoiNhan=self.khach, MaBooking=bk)  # thông báo gửi cho Khách của Booking này
        self.assertEqual(tb.count(), 1)  # đúng 1 thông báo
        self.assertEqual(tb.get().TieuDe, 'Nhắc đặt cọc Booking')  # đúng tiêu đề nhắc
        self.assertEqual(len(mail.outbox), 1)  # đúng 1 email
        self.assertEqual(mail.outbox[0].to, ['kh_nhac@example.com'])  # gửi đúng Khách
        self.assertEqual(tb.get().TrangThaiGuiEmail, TrangThaiGuiEmail.THANH_CONG)  # kết quả gửi được ghi lại
        self.assertIn('Đã nhắc 1 Booking', chu)  # lệnh in đúng số lượt nhắc

    def test_chua_toi_6_gio_thi_khong_nhac(self):  # còn 7 giờ thì chưa nhắc
        self._booking(self.bay_gio + timedelta(hours=7))  # hạn cọc sau 7 giờ
        chu = self._chay_lenh()  # chạy lệnh
        self.assertEqual(ThongBao.objects.count(), 0)  # không có thông báo nào
        self.assertEqual(len(mail.outbox), 0)  # không có email nào
        self.assertIn('Đã nhắc 0 Booking', chu)  # lệnh in 0

    def test_chay_lai_khong_nhac_lan_hai(self):  # chạy định kỳ nhiều lần vẫn chỉ nhắc một lần
        self._booking(self.bay_gio + timedelta(hours=5))  # hạn cọc sau 5 giờ
        self._chay_lenh()  # lần chạy thứ nhất: nhắc
        chu = self._chay_lenh()  # lần chạy thứ hai: không nhắc lại
        self.assertEqual(ThongBao.objects.count(), 1)  # vẫn chỉ 1 thông báo
        self.assertEqual(len(mail.outbox), 1)  # vẫn chỉ 1 email
        self.assertIn('Đã nhắc 0 Booking', chu)  # lần hai in 0

    def test_da_tai_minh_chung_coc_thi_khong_nhac(self):  # Khách đã chuyển khoản và tải minh chứng, đang chờ Nhiếp ảnh gia xác nhận
        bk = self._booking(self.bay_gio + timedelta(hours=5))  # hạn cọc sau 5 giờ (đúng khung cần nhắc)
        ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.TIEN_COC, SoTien=400000,  # khoản cọc 40% của 1 triệu
                                 TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_COC, NgayThanhToan=self.bay_gio - timedelta(hours=1))  # đang chờ xác nhận cọc
        self._chay_lenh()  # chạy lệnh
        self.assertEqual(ThongBao.objects.count(), 0)  # không nhắc
        self.assertEqual(len(mail.outbox), 0)  # không gửi email

    def test_da_qua_han_thi_khong_nhac(self):  # quá hạn thì để hệ thống chuyển Hết thời hạn đặt cọc, không nhắc nữa
        self._booking(self.bay_gio - timedelta(hours=1))  # hạn cọc đã qua 1 giờ
        self._chay_lenh()  # chạy lệnh
        self.assertEqual(ThongBao.objects.count(), 0)  # không nhắc
        self.assertEqual(len(mail.outbox), 0)  # không gửi email

    def test_booking_khong_con_cho_dat_coc_thi_khong_nhac(self):  # Booking đã chốt thì không nhắc đặt cọc
        self._booking(self.bay_gio + timedelta(hours=5), trang_thai=TrangThaiBooking.CHOT_BOOKING)  # đã Chốt Booking
        self._chay_lenh()  # chạy lệnh
        self.assertEqual(ThongBao.objects.count(), 0)  # không nhắc

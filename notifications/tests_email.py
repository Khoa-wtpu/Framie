# notifications/tests_email.py - kiểm tra P9 (gửi email kèm thông báo). Chạy: python manage.py test notifications.tests_email
from unittest.mock import patch  # giả lập lỗi SMTP

from django.contrib.auth import get_user_model  # model User của project
from django.core import mail  # mail.outbox: hộp thư giả của Django khi chạy test
from django.test import TestCase, override_settings  # TestCase dùng DB tạm; override_settings đổi cấu hình trong test

from core.constants import TrangThaiGuiEmail  # hằng số kết quả gửi email
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
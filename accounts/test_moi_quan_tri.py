# =====================================================================
# accounts/test_moi_quan_tri.py  -  kiểm thử mời Quản trị viên bằng link có chữ ký
# Chạy:  python manage.py test accounts.test_moi_quan_tri
# =====================================================================
import re  # tách link trong nội dung email
from datetime import timedelta  # khoảng thời gian, dùng để giả lập link hết hạn
from unittest import mock  # giả lập lỗi gửi mail và hạn dùng
from urllib.parse import urlparse  # lấy phần đường dẫn từ link tuyệt đối

from django.core import mail  # hộp thư giả khi chạy test
from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn

from accounts.models import User  # model User
from accounts.permissions import lay_vai_tro  # vai trò chính của User
from accounts.services import (  # hàm token và tạo tài khoản
    LoiMoiQuanTriKhongHopLe, doc_token_loi_moi_qtv, tao_token_loi_moi_qtv, tao_tai_khoan,
)
from core.constants import VaiTro  # tên vai trò

MAT_KHAU = 'Matkhau!2026'  # mật khẩu hợp lệ theo mọi luật
EMAIL_MOI = 'moi@example.com'  # email người được mời


class TokenLoiMoiTests(TestCase):  # hàm tạo/kiểm tra token
    def test_token_dung_tra_ve_email(self):
        self.assertEqual(doc_token_loi_moi_qtv(tao_token_loi_moi_qtv('A@Example.com')), 'a@example.com')  # email được chuẩn hóa chữ thường

    def test_token_bi_sua_bi_tu_choi(self):
        token = tao_token_loi_moi_qtv(EMAIL_MOI)
        with self.assertRaises(LoiMoiQuanTriKhongHopLe):
            doc_token_loi_moi_qtv(token[:-2] + ('aa' if token[-2:] != 'aa' else 'bb'))  # đổi 2 ký tự cuối (chữ ký)

    def test_token_rac_bi_tu_choi(self):
        with self.assertRaises(LoiMoiQuanTriKhongHopLe):
            doc_token_loi_moi_qtv('khong-phai-token')

    def test_token_het_han(self):
        token = tao_token_loi_moi_qtv(EMAIL_MOI)
        with self.assertRaisesMessage(LoiMoiQuanTriKhongHopLe, 'hết hạn'):
            doc_token_loi_moi_qtv(token, hieu_luc=timedelta(seconds=-1))  # hạn âm = chắc chắn quá hạn


class MoiQuanTriVienViewTests(TestCase):  # trang admin nhập email người được mời
    def setUp(self):
        self.admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0900000001', MAT_KHAU, vai_tro=VaiTro.QUAN_TRI_VIEN)
        self.khach = tao_tai_khoan('Khách Hàng', 'khach@example.com', '0900000002', MAT_KHAU)
        self.url = reverse('admin_invite')

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_khach_hang_bi_403_ca_get_lan_post(self):
        self.client.force_login(self.khach)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'email': EMAIL_MOI}).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)  # không có mail nào được gửi

    def test_trang_tai_khoan_co_nut_tao_admin(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('admin_accounts'))
        self.assertContains(r, 'Tạo tài khoản quản trị viên')
        self.assertContains(r, self.url)

    def test_gui_moi_thanh_cong(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url, {'email': ' MOI@Example.com '})  # có khoảng trắng và chữ hoa
        self.assertRedirects(r, reverse('admin_accounts'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [EMAIL_MOI])  # gửi tới email chữ thường
        self.assertRegex(mail.outbox[0].body, r'/dang-ky/quan-tri/\S+')  # có link mời trong thư
        self.assertNotIn(MAT_KHAU, mail.outbox[0].body)
        self.assertFalse(User.objects.filter(email=EMAIL_MOI).exists())  # chưa tạo tài khoản, chờ người được mời

    def test_email_da_co_tai_khoan_bi_tu_choi(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url, {'email': 'KHACH@example.com'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Email này đã có tài khoản.')
        self.assertEqual(len(mail.outbox), 0)

    def test_email_sai_dinh_dang(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url, {'email': 'abc'})
        self.assertContains(r, 'Email không đúng định dạng.')
        self.assertEqual(len(mail.outbox), 0)

    def test_gui_mail_loi_thi_hien_link_gui_tay(self):
        self.client.force_login(self.admin)
        with mock.patch('accounts.services.send_mail', side_effect=Exception('smtp loi')):  # giả lập mất mạng / sai SMTP
            r = self.client.post(self.url, {'email': EMAIL_MOI})
        self.assertEqual(r.status_code, 200)  # không chuyển trang
        self.assertContains(r, '/dang-ky/quan-tri/')  # link hiện ra để copy
        self.assertContains(r, 'Chưa gửi được email')  # có cảnh báo


class DangKyQuanTriTests(TestCase):  # trang người được mời đăng ký
    def setUp(self):
        self.token = tao_token_loi_moi_qtv(EMAIL_MOI)
        self.url = reverse('register_admin', args=[self.token])
        self.du_lieu = {'ho_ten': 'Trần Thị Bình', 'so_dien_thoai': '0911111111', 'mat_khau': MAT_KHAU, 'mat_khau_xac_nhan': MAT_KHAU}

    def test_get_hien_form_voi_email_khoa(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, EMAIL_MOI)  # email điền sẵn
        self.assertContains(r, 'disabled')  # ô email bị khóa

    def test_dang_ky_thanh_cong_tao_quan_tri_vien(self):
        r = self.client.post(self.url, self.du_lieu)
        self.assertRedirects(r, reverse('login'))
        u = User.objects.get(email=EMAIL_MOI)
        self.assertEqual(u.username, EMAIL_MOI)
        self.assertEqual((u.first_name, u.last_name), ('Bình', 'Trần Thị'))
        self.assertEqual(lay_vai_tro(u), VaiTro.QUAN_TRI_VIEN)
        self.assertTrue(u.groups.filter(name=VaiTro.QUAN_TRI_VIEN).exists())
        self.assertTrue(u.is_active)
        self.assertFalse(u.is_superuser)
        self.assertFalse(u.is_staff)
        self.assertIsNone(u.trang_thai_ho_so)
        self.assertTrue(u.check_password(MAT_KHAU))  # mật khẩu được băm đúng
        self.assertTrue(self.client.login(username=EMAIL_MOI, password=MAT_KHAU))  # đăng nhập được bằng email

    def test_khong_doi_duoc_email_bang_cach_gui_email_khac(self):
        self.client.post(self.url, {**self.du_lieu, 'email': 'ke-gian@example.com'})  # kẻ gian gửi email khác
        self.assertTrue(User.objects.filter(email=EMAIL_MOI).exists())  # vẫn dùng email trong token
        self.assertFalse(User.objects.filter(email='ke-gian@example.com').exists())

    def test_link_chi_dung_mot_lan(self):
        self.client.post(self.url, self.du_lieu)
        self.client.logout()
        r = self.client.get(self.url)  # mở lại link đã dùng
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, 'đã được sử dụng', status_code=400)
        r = self.client.post(self.url, {**self.du_lieu, 'so_dien_thoai': '0922222222'})  # thử đăng ký lần hai
        self.assertEqual(r.status_code, 400)
        self.assertEqual(User.objects.filter(email=EMAIL_MOI).count(), 1)

    def test_link_sai_bi_400(self):
        r = self.client.get(reverse('register_admin', args=['abc:def:ghi']))
        self.assertContains(r, 'không hợp lệ', status_code=400)

    def test_link_het_han_bi_400(self):
        with mock.patch('accounts.services.HIEU_LUC_LOI_MOI_QTV', timedelta(seconds=-1)):
            r = self.client.get(self.url)
        self.assertContains(r, 'hết hạn', status_code=400)
        self.assertFalse(User.objects.filter(email=EMAIL_MOI).exists())

    def test_so_dien_thoai_trung_bi_tu_choi(self):
        tao_tai_khoan('Khách', 'khach@example.com', '0911111111', MAT_KHAU)
        r = self.client.post(self.url, self.du_lieu)
        self.assertContains(r, 'Số điện thoại này đã được đăng ký.')
        self.assertFalse(User.objects.filter(email=EMAIL_MOI).exists())

    def test_so_dien_thoai_sai_dinh_dang(self):
        r = self.client.post(self.url, {**self.du_lieu, 'so_dien_thoai': '12345'})
        self.assertContains(r, 'Số điện thoại gồm 10 chữ số và bắt đầu bằng 0.')

    def test_mat_khau_yeu_bi_tu_choi(self):
        r = self.client.post(self.url, {**self.du_lieu, 'mat_khau': 'abc', 'mat_khau_xac_nhan': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email=EMAIL_MOI).exists())

    def test_da_dang_nhap_thi_chuyen_di(self):
        khach = tao_tai_khoan('Khách', 'khach@example.com', '0900000002', MAT_KHAU)
        self.client.force_login(khach)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_luong_day_du_tu_email_den_dang_ky(self):  # admin mời -> lấy link trong mail -> người được mời đăng ký
        admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0900000001', MAT_KHAU, vai_tro=VaiTro.QUAN_TRI_VIEN)
        self.client.force_login(admin)
        self.client.post(reverse('admin_invite'), {'email': 'luong@example.com'})
        link = re.search(r'https?://\S+/dang-ky/quan-tri/\S+', mail.outbox[0].body).group(0)
        self.client.logout()
        r = self.client.post(urlparse(link).path, {**self.du_lieu, 'so_dien_thoai': '0933333333'})
        self.assertRedirects(r, reverse('login'))
        self.assertEqual(lay_vai_tro(User.objects.get(email='luong@example.com')), VaiTro.QUAN_TRI_VIEN)

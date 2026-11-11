# =====================================================================
# accounts/test_tro_ly_sau_dang_ky.py  -  E5: sau khi Khách hàng mới đăng ký và đăng nhập thì chuyển sang Trợ lý
# Chạy:  python manage.py test accounts.test_tro_ly_sau_dang_ky
# =====================================================================
from unittest.mock import patch  # patch: thay tạm một hàm bằng hàm giả trong lúc test

from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn

from accounts.permissions import url_trang_chu  # trang đích mặc định theo vai trò
from accounts.services import tao_tai_khoan  # hàm tạo tài khoản của P4
from accounts.views import KHOA_CO_TRO_LY  # tên khóa cờ trong session (khai báo ở accounts/views.py)
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và trạng thái hồ sơ

MAT_KHAU = 'Matkhau!2026'  # mật khẩu hợp lệ theo luật của FRAMIE


class TroLySauDangKyTest(TestCase):
    def setUp(self):  # chạy trước mỗi test
        self.khach = tao_tai_khoan('Khách Hàng', 'khach@example.com', '0900000002', MAT_KHAU)  # Khách hàng (vai trò mặc định)
        self.nag = tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0900000003', MAT_KHAU,  # một Nhiếp ảnh gia
                                 vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)  # hồ sơ đang chờ duyệt

    def dat_co(self):  # giả lập "vừa đăng ký xong": đặt cờ vào session
        phien = self.client.session  # session của client test
        phien[KHOA_CO_TRO_LY] = True  # đặt cờ
        phien.save()  # lưu lại

    def dang_nhap(self, email, **them):  # gửi form đăng nhập; them = dữ liệu thêm như next
        return self.client.post(reverse('login'), {'username': email, 'password': MAT_KHAU, **them})  # ô Email tên 'username' (xem dang_nhap.html)

    # ---------------- đặt cờ lúc đăng ký ----------------
    def test_dang_ky_thanh_cong_dat_co(self):
        with patch('accounts.views.DangKyForm') as form_gia, \
                patch('accounts.views.tao_tai_khoan'), \
                patch('accounts.views.gui_email_dang_ky_thanh_cong', return_value=True):  # giả form, giả tạo tài khoản, giả gửi email
            form_gia.return_value.is_valid.return_value = True  # form luôn hợp lệ
            form_gia.return_value.cleaned_data = {'ho_ten': 'A', 'email': 'a@example.com', 'so_dien_thoai': '0911111111', 'mat_khau': MAT_KHAU}  # dữ liệu giả
            r = self.client.post(reverse('register'), {})  # gửi form đăng ký (tên URL 'register' theo core/navigation.py)
        self.assertRedirects(r, reverse('login'))  # vẫn chuyển sang trang đăng nhập như cũ
        self.assertIs(self.client.session.get(KHOA_CO_TRO_LY), True)  # và cờ đã được đặt

    # ---------------- dùng cờ lúc đăng nhập ----------------
    def test_co_con_thi_khach_hang_vao_tro_ly(self):
        self.dat_co()  # vừa đăng ký xong
        r = self.dang_nhap('khach@example.com')  # đăng nhập
        self.assertEqual(r.status_code, 302)  # chuyển trang
        self.assertEqual(r.url, reverse('assistant'))  # sang Trợ lý
        self.assertNotIn(KHOA_CO_TRO_LY, self.client.session)  # cờ đã bị xóa

    def test_khong_co_co_thi_ve_trang_chu_nhu_cu(self):
        r = self.dang_nhap('khach@example.com')  # đăng nhập bình thường
        self.assertEqual(r.url, url_trang_chu(self.khach))  # hành vi cũ không đổi

    def test_co_chi_dung_mot_lan(self):
        self.dat_co()  # vừa đăng ký xong
        self.assertEqual(self.dang_nhap('khach@example.com').url, reverse('assistant'))  # lần 1: vào Trợ lý
        self.client.logout()  # đăng xuất
        self.assertEqual(self.dang_nhap('khach@example.com').url, url_trang_chu(self.khach))  # lần 2: về trang chủ

    def test_co_voi_next_van_bi_xoa_khong_nhay_sang_lan_sau(self):
        self.dat_co()  # vừa đăng ký xong
        r = self.dang_nhap('khach@example.com', next=reverse('search'))  # đăng nhập kèm ?next=
        self.assertEqual(r.url, reverse('search'))  # next được ưu tiên
        self.assertNotIn(KHOA_CO_TRO_LY, self.client.session)  # nhưng cờ vẫn bị xóa (lỗi E1 đã cảnh báo)
        self.client.logout()  # đăng xuất
        self.assertEqual(self.dang_nhap('khach@example.com').url, url_trang_chu(self.khach))  # lần sau không bị đẩy vào Trợ lý

    def test_nhiep_anh_gia_khong_vao_tro_ly_va_co_bi_xoa(self):
        self.dat_co()  # cờ còn sót trong trình duyệt
        r = self.dang_nhap('nag@example.com')  # Nhiếp ảnh gia đăng nhập
        self.assertNotEqual(r.url, reverse('assistant'))  # không vào Trợ lý (sẽ bị 403)
        self.assertEqual(r.url, url_trang_chu(self.nag))  # về trang theo vai trò
        self.assertNotIn(KHOA_CO_TRO_LY, self.client.session)  # cờ vẫn bị xóa

    def test_dang_nhap_sai_mat_khau_thi_giu_co(self):
        self.dat_co()  # vừa đăng ký xong
        r = self.client.post(reverse('login'), {'username': 'khach@example.com', 'password': 'sai-mat-khau'})  # gõ sai mật khẩu
        self.assertEqual(r.status_code, 200)  # ở lại trang đăng nhập
        self.assertIs(self.client.session.get(KHOA_CO_TRO_LY), True)  # cờ còn nguyên cho lần gõ đúng
        self.assertEqual(self.dang_nhap('khach@example.com').url, reverse('assistant'))  # gõ đúng thì vào Trợ lý

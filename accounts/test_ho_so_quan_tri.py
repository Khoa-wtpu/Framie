# =====================================================================
# accounts/test_ho_so_quan_tri.py  -  Hồ sơ của tôi và Cập nhật hồ sơ của Quản trị viên
# Chạy:  python manage.py test accounts.test_ho_so_quan_tri
# =====================================================================
from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn

from accounts.models import User  # model User
from accounts.services import tao_tai_khoan  # hàm tạo tài khoản của P4
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và trạng thái hồ sơ

MAT_KHAU = 'Matkhau!2026'  # mật khẩu hiện tại của các tài khoản thử
MAT_KHAU_MOI = 'Doimoi@2027'  # mật khẩu mới hợp lệ


class HoSoQuanTriTests(TestCase):  # trang Hồ sơ của tôi, Cập nhật hồ sơ và đổi mật khẩu của Quản trị viên
    def setUp(self):  # chạy trước mỗi test
        self.admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0944444444', MAT_KHAU, vai_tro=VaiTro.QUAN_TRI_VIEN)  # Quản trị viên đang thao tác
        self.khach = tao_tai_khoan('Nguyễn Văn An', 'an@example.com', '0911111111', MAT_KHAU)  # Khách hàng
        self.nag = tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0933333333', MAT_KHAU,  # Nhiếp ảnh gia
                                 vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)  # hồ sơ đã duyệt
        self.url_ho_so = reverse('account_profile')  # trang Hồ sơ của tôi
        self.url_cap_nhat = reverse('account_profile_update')  # trang Cập nhật hồ sơ
        self.url_doi_mk = reverse('change_password')  # trang Đổi mật khẩu dùng chung

    def du_lieu(self, **doi):  # dữ liệu form cập nhật hợp lệ, ghi đè vài ô khi cần
        mac_dinh = {'ho_ten': 'Lê Hoàng Nam', 'so_dien_thoai': '0955555555', 'email': 'moi@example.com'}  # giá trị hợp lệ
        mac_dinh.update(doi)  # áp giá trị riêng của từng test
        return mac_dinh  # trả dict

    def test_chua_dang_nhap_ve_trang_dang_nhap(self):  # người lạ
        for url in (self.url_ho_so, self.url_cap_nhat):  # cả hai trang
            with self.subTest(url=url):  # báo riêng từng trang
                r = self.client.get(url)  # mở trang
                self.assertEqual(r.status_code, 302)  # bị chuyển trang
                self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_vai_tro_khac_bi_403(self):  # chỉ Quản trị viên được vào
        for user in (self.khach, self.nag):  # Khách hàng và Nhiếp ảnh gia
            for url in (self.url_ho_so, self.url_cap_nhat):  # cả hai trang
                with self.subTest(user=user.email, url=url):  # báo riêng
                    self.client.force_login(user)  # đăng nhập bằng vai trò này
                    self.assertEqual(self.client.get(url).status_code, 403)  # bị từ chối

    def test_quan_tri_vien_xem_duoc_ho_so(self):  # luồng chính
        self.client.force_login(self.admin)  # đăng nhập Quản trị viên
        r = self.client.get(self.url_ho_so)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertContains(r, 'admin@example.com')  # hiện email
        self.assertContains(r, '0944444444')  # hiện số điện thoại
        self.assertContains(r, f'QTV-{self.admin.pk:04d}')  # hiện mã hiển thị

    def test_trang_cap_nhat_dien_san_du_lieu_hien_tai(self):  # mở form lần đầu
        self.client.force_login(self.admin)  # đăng nhập
        r = self.client.get(self.url_cap_nhat)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertEqual(r.context['form'].initial['email'], 'admin@example.com')  # email điền sẵn
        self.assertEqual(r.context['form'].initial['so_dien_thoai'], '0944444444')  # số điện thoại điền sẵn

    def test_cap_nhat_hop_le(self):  # lưu thành công
        self.client.force_login(self.admin)  # đăng nhập
        r = self.client.post(self.url_cap_nhat, self.du_lieu(), follow=True)  # gửi dữ liệu hợp lệ
        self.assertRedirects(r, self.url_ho_so)  # về Hồ sơ của tôi
        self.assertContains(r, 'Đã cập nhật hồ sơ thành công.')  # có thông báo
        user = User.objects.get(pk=self.admin.pk)  # đọc lại từ DB
        self.assertEqual((user.first_name, user.last_name), ('Nam', 'Lê Hoàng'))  # họ tên tách đúng
        self.assertEqual(user.email, 'moi@example.com')  # email mới
        self.assertEqual(user.so_dien_thoai, '0955555555')  # số điện thoại mới

    def test_trung_email_hoac_so_dien_thoai_bi_chan(self):  # trùng với người khác
        self.client.force_login(self.admin)  # đăng nhập
        r = self.client.post(self.url_cap_nhat, self.du_lieu(email='an@example.com', so_dien_thoai='0911111111'))  # trùng Khách hàng
        self.assertContains(r, 'Email này đã được đăng ký.')  # báo trùng email
        self.assertContains(r, 'Số điện thoại này đã được đăng ký.')  # báo trùng số điện thoại
        self.assertEqual(User.objects.get(pk=self.admin.pk).email, 'admin@example.com')  # dữ liệu không đổi

    def test_giu_nguyen_email_va_so_cua_chinh_minh(self):  # không bị báo trùng với chính mình
        self.client.force_login(self.admin)  # đăng nhập
        r = self.client.post(self.url_cap_nhat, self.du_lieu(email='admin@example.com', so_dien_thoai='0944444444'))  # giữ nguyên
        self.assertRedirects(r, self.url_ho_so)  # lưu được

    def test_doi_mat_khau_xong_ve_ho_so_quan_tri(self):  # _ve_ho_so đã biết trang của Quản trị viên
        self.client.force_login(self.admin)  # đăng nhập
        r = self.client.post(self.url_doi_mk, {'mat_khau_cu': MAT_KHAU, 'mat_khau_moi': MAT_KHAU_MOI, 'nhap_lai': MAT_KHAU_MOI}, follow=True)  # đổi mật khẩu
        self.assertRedirects(r, self.url_ho_so)  # về Hồ sơ của tôi, không về trang tổng quan
        self.assertContains(r, 'Đổi mật khẩu thành công.')  # có thông báo

    def test_nut_huy_o_trang_doi_mat_khau_tro_ve_ho_so_quan_tri(self):  # đường dẫn Hủy
        self.client.force_login(self.admin)  # đăng nhập
        r = self.client.get(self.url_doi_mk)  # mở trang đổi mật khẩu
        self.assertEqual(r.context['huy_url'], self.url_ho_so)  # Hủy về hồ sơ của Quản trị viên

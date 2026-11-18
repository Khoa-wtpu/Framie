# =====================================================================
# accounts/test_khach_hang.py  -  Hồ sơ của tôi (Khách hàng), Cập nhật hồ sơ, Đổi mật khẩu
# Chạy:  python manage.py test accounts.test_khach_hang
# =====================================================================
from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn

from accounts.forms import CapNhatKhachHangForm, DoiMatKhauForm  # 2 form được kiểm thử
from accounts.models import User  # model User
from accounts.services import tao_tai_khoan  # hàm tạo tài khoản của P4
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và trạng thái hồ sơ

MAT_KHAU = 'Matkhau!2026'  # mật khẩu hiện tại của các tài khoản thử
MAT_KHAU_MOI = 'Doimoi@2027'  # mật khẩu mới hợp lệ (đủ chữ hoa, thường, số, ký tự đặc biệt)


class NenKhachHang(TestCase):  # lớp cha: tạo sẵn tài khoản dùng chung
    def setUp(self):  # chạy trước mỗi test
        self.khach = tao_tai_khoan('Nguyễn Văn An', 'an@example.com', '0911111111', MAT_KHAU)  # Khách hàng đang thao tác
        self.khac = tao_tai_khoan('Trần Thị Bình', 'binh@example.com', '0922222222', MAT_KHAU)  # Khách hàng khác (để thử trùng)
        self.nag = tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0933333333', MAT_KHAU,  # Nhiếp ảnh gia
                                 vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)  # hồ sơ đã duyệt
        self.admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0944444444', MAT_KHAU, vai_tro=VaiTro.QUAN_TRI_VIEN)  # Quản trị viên
        self.url_ho_so = reverse('customer_profile')  # trang Hồ sơ của tôi
        self.url_cap_nhat = reverse('customer_profile_update')  # trang Cập nhật hồ sơ
        self.url_doi_mk = reverse('change_password')  # trang Đổi mật khẩu

    def du_lieu(self, **doi):  # dữ liệu form cập nhật hợp lệ, ghi đè vài ô khi cần
        mac_dinh = {'ho_ten': 'Lê Hoàng Nam', 'so_dien_thoai': '0955555555', 'email': 'moi@example.com'}  # giá trị hợp lệ
        mac_dinh.update(doi)  # áp giá trị riêng của từng test
        return mac_dinh  # trả dict

    def lam_moi(self, user):  # đọc lại User từ DB
        return User.objects.get(pk=user.pk)  # lấy bản mới nhất


class HoSoKhachHangViewTests(NenKhachHang):  # trang Hồ sơ của tôi và Cập nhật hồ sơ
    def test_chua_dang_nhap_ve_trang_dang_nhap(self):  # người lạ
        for url in (self.url_ho_so, self.url_cap_nhat):  # cả hai trang
            with self.subTest(url=url):  # báo riêng từng trang
                r = self.client.get(url)  # mở trang
                self.assertEqual(r.status_code, 302)  # bị chuyển trang
                self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_vai_tro_khac_bi_403(self):  # chỉ Khách hàng được vào
        for user in (self.nag, self.admin):  # Nhiếp ảnh gia và Quản trị viên
            for url in (self.url_ho_so, self.url_cap_nhat):  # cả hai trang
                with self.subTest(user=user.email, url=url):  # báo riêng
                    self.client.force_login(user)  # đăng nhập bằng vai trò này
                    self.assertEqual(self.client.get(url).status_code, 403)  # bị từ chối

    def test_khach_hang_xem_duoc_ho_so(self):  # luồng chính
        self.client.force_login(self.khach)  # đăng nhập Khách hàng
        r = self.client.get(self.url_ho_so)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertContains(r, 'an@example.com')  # hiện email
        self.assertContains(r, '0911111111')  # hiện số điện thoại
        self.assertContains(r, f'KH-{self.khach.pk:04d}')  # hiện mã hiển thị

    def test_trang_cap_nhat_dien_san_du_lieu_hien_tai(self):  # mở form lần đầu
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.get(self.url_cap_nhat)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertEqual(r.context['form'].initial['email'], 'an@example.com')  # email điền sẵn
        self.assertEqual(r.context['form'].initial['so_dien_thoai'], '0911111111')  # số điện thoại điền sẵn

    def test_cap_nhat_hop_le_username_doi_theo_email(self):  # username đang bằng email thì đổi theo
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_cap_nhat, self.du_lieu(), follow=True)  # gửi dữ liệu hợp lệ
        self.assertRedirects(r, self.url_ho_so)  # về Hồ sơ của tôi
        self.assertContains(r, 'Đã cập nhật hồ sơ thành công.')  # có thông báo
        user = self.lam_moi(self.khach)  # đọc lại từ DB
        self.assertEqual((user.first_name, user.last_name), ('Nam', 'Lê Hoàng'))  # họ tên tách đúng
        self.assertEqual(user.email, 'moi@example.com')  # email mới
        self.assertEqual(user.username, 'moi@example.com')  # username đổi theo email
        self.assertEqual(user.so_dien_thoai, '0955555555')  # số điện thoại mới

    def test_dang_nhap_duoc_bang_email_moi(self):  # đổi email là đổi tên đăng nhập
        self.client.force_login(self.khach)  # đăng nhập
        self.client.post(self.url_cap_nhat, self.du_lieu())  # đổi email
        self.client.logout()  # đăng xuất
        self.assertTrue(self.client.login(username='moi@example.com', password=MAT_KHAU))  # đăng nhập bằng email mới
        self.assertFalse(self.client.login(username='an@example.com', password=MAT_KHAU))  # email cũ không còn dùng được

    def test_email_chu_hoa_duoc_luu_chu_thuong(self):  # chuẩn hóa email
        self.client.force_login(self.khach)  # đăng nhập
        self.client.post(self.url_cap_nhat, self.du_lieu(email='  MOI@Example.COM '))  # gõ chữ hoa, thừa khoảng trắng
        self.assertEqual(self.lam_moi(self.khach).email, 'moi@example.com')  # lưu chữ thường

    def test_trung_email_nguoi_khac_bi_chan(self):  # kể cả khác hoa thường
        self.client.force_login(self.khach)  # đăng nhập
        for email in ('binh@example.com', 'BINH@example.com'):  # trùng đúng và trùng khác hoa thường
            with self.subTest(email=email):  # báo riêng
                r = self.client.post(self.url_cap_nhat, self.du_lieu(email=email))  # gửi
                self.assertEqual(r.status_code, 200)  # ở lại form
                self.assertContains(r, 'Email này đã được đăng ký.')  # báo trùng
                user = self.lam_moi(self.khach)  # đọc lại
                self.assertEqual((user.email, user.first_name), ('an@example.com', 'An'))  # không có gì bị lưu

    def test_trung_so_dien_thoai_nguoi_khac_bi_chan(self):  # số của người khác
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_cap_nhat, self.du_lieu(so_dien_thoai='0922222222'))  # dùng số của Bình
        self.assertEqual(r.status_code, 200)  # ở lại form
        self.assertContains(r, 'Số điện thoại này đã được đăng ký.')  # báo trùng
        self.assertEqual(self.lam_moi(self.khach).so_dien_thoai, '0911111111')  # số cũ giữ nguyên

    def test_giu_nguyen_email_va_sdt_cua_chinh_minh_khong_bao_trung(self):  # loại chính mình khỏi so trùng
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_cap_nhat,  # chỉ đổi họ tên
                             self.du_lieu(email='an@example.com', so_dien_thoai='0911111111'), follow=True)
        self.assertRedirects(r, self.url_ho_so)  # lưu thành công
        self.assertNotContains(r, 'đã được đăng ký')  # không báo trùng
        self.assertEqual(self.lam_moi(self.khach).first_name, 'Nam')  # họ tên đã đổi

    def test_vai_tro_khac_khong_gui_duoc_post_cap_nhat(self):  # POST trực tiếp cũng bị chặn
        self.client.force_login(self.nag)  # đăng nhập Nhiếp ảnh gia
        r = self.client.post(self.url_cap_nhat, self.du_lieu())  # tự gửi POST
        self.assertEqual(r.status_code, 403)  # bị từ chối
        self.assertEqual(self.lam_moi(self.nag).email, 'nag@example.com')  # không đổi gì


class CapNhatKhachHangFormTests(NenKhachHang):  # kiểm thử trực tiếp form
    def form(self, **doi):  # tạo form gắn với self.khach
        return CapNhatKhachHangForm(self.du_lieu(**doi), user=self.khach)  # dữ liệu hợp lệ trừ ô bị ghi đè

    def test_du_lieu_hop_le(self):  # luồng chính
        self.assertTrue(self.form().is_valid())  # hợp lệ

    def test_dinh_dang_sai_bi_loi(self):  # từng ô sai định dạng
        ca_sai = {'so_dien_thoai': ['12345', '1911111111', '09111111119', 'abcdefghij'],  # thiếu số, không bắt đầu bằng 0, thừa số, chữ
                  'email': ['khong-phai-email', 'a@'],  # sai dạng email
                  'ho_ten': ['An123', '', '   ']}  # có số, trống
        for ten_o, gia_tri_sai in ca_sai.items():  # từng ô
            for gia_tri in gia_tri_sai:  # từng giá trị sai
                with self.subTest(o=ten_o, gia_tri=gia_tri):  # báo riêng
                    f = self.form(**{ten_o: gia_tri})  # form có đúng một ô sai
                    self.assertFalse(f.is_valid())  # không hợp lệ
                    self.assertIn(ten_o, f.errors)  # lỗi nằm đúng ô

    def test_save_khong_doi_username_khi_username_khac_email(self):  # chỉ đồng bộ khi username đang bằng email
        User.objects.filter(pk=self.khach.pk).update(username='ten_rieng')  # username không còn bằng email
        f = CapNhatKhachHangForm(self.du_lieu(), user=User.objects.get(pk=self.khach.pk))  # form với User mới đọc
        self.assertTrue(f.is_valid())  # hợp lệ
        user = f.save()  # lưu
        self.assertEqual(user.username, 'ten_rieng')  # username giữ nguyên
        self.assertEqual(user.email, 'moi@example.com')  # email vẫn đổi


class DoiMatKhauTests(NenKhachHang):  # trang và form Đổi mật khẩu
    def du_lieu_mk(self, **doi):  # dữ liệu đổi mật khẩu hợp lệ, ghi đè khi cần
        mac_dinh = {'mat_khau_cu': MAT_KHAU, 'mat_khau_moi': MAT_KHAU_MOI, 'nhap_lai': MAT_KHAU_MOI}  # hợp lệ
        mac_dinh.update(doi)  # áp giá trị riêng
        return mac_dinh  # trả dict

    def test_chua_dang_nhap_ve_trang_dang_nhap(self):  # người lạ
        r = self.client.get(self.url_doi_mk)  # mở trang
        self.assertEqual(r.status_code, 302)  # bị chuyển trang
        self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_moi_vai_tro_da_dang_nhap_vao_duoc(self):  # không giới hạn vai trò
        for user in (self.khach, self.nag, self.admin):  # cả 3 vai trò
            with self.subTest(user=user.email):  # báo riêng
                self.client.force_login(user)  # đăng nhập
                self.assertEqual(self.client.get(self.url_doi_mk).status_code, 200)  # vào được

    def test_sai_mat_khau_cu(self):  # mật khẩu hiện tại sai
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_doi_mk, self.du_lieu_mk(mat_khau_cu='Sai!Matkhau1'))  # gửi
        self.assertEqual(r.status_code, 200)  # ở lại form
        self.assertContains(r, 'Mật khẩu hiện tại không đúng.')  # báo sai
        self.assertTrue(self.lam_moi(self.khach).check_password(MAT_KHAU))  # mật khẩu không đổi

    def test_mat_khau_moi_trung_mat_khau_cu(self):  # phải khác mật khẩu cũ
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_doi_mk, self.du_lieu_mk(mat_khau_moi=MAT_KHAU, nhap_lai=MAT_KHAU))  # mới = cũ
        self.assertContains(r, 'Mật khẩu mới phải khác mật khẩu hiện tại.')  # báo trùng
        self.assertTrue(self.lam_moi(self.khach).check_password(MAT_KHAU))  # mật khẩu không đổi

    def test_nhap_lai_khong_khop(self):  # hai lần nhập mới khác nhau
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_doi_mk, self.du_lieu_mk(nhap_lai='Khac!Hoan2028'))  # nhập lại khác
        self.assertContains(r, 'Mật khẩu nhập lại không khớp.')  # báo không khớp
        self.assertTrue(self.lam_moi(self.khach).check_password(MAT_KHAU))  # mật khẩu không đổi

    def test_mat_khau_moi_qua_yeu_bi_chan(self):  # dùng chung luật mật khẩu của FRAMIE
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_doi_mk, self.du_lieu_mk(mat_khau_moi='doimoi@2027', nhap_lai='doimoi@2027'))  # thiếu chữ hoa
        self.assertContains(r, 'chữ hoa')  # báo thiếu chữ hoa
        self.assertTrue(self.lam_moi(self.khach).check_password(MAT_KHAU))  # mật khẩu không đổi

    def test_doi_thanh_cong_van_con_dang_nhap(self):  # update_session_auth_hash giữ phiên
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_doi_mk, self.du_lieu_mk(), follow=True)  # đổi mật khẩu
        self.assertRedirects(r, self.url_ho_so)  # về Hồ sơ của tôi, không bị đẩy ra trang đăng nhập
        self.assertContains(r, 'Đổi mật khẩu thành công.')  # có thông báo
        user = self.lam_moi(self.khach)  # đọc lại
        self.assertTrue(user.check_password(MAT_KHAU_MOI))  # mật khẩu mới có hiệu lực
        self.assertFalse(user.check_password(MAT_KHAU))  # mật khẩu cũ hết hiệu lực
        self.assertEqual(self.client.get(self.url_ho_so).status_code, 200)  # vẫn đăng nhập (không bị chuyển về login)

    def test_form_save_bam_mat_khau_moi(self):  # kiểm thử trực tiếp form
        f = DoiMatKhauForm(self.du_lieu_mk(), user=self.khach)  # form hợp lệ
        self.assertTrue(f.is_valid())  # hợp lệ
        f.save()  # lưu
        self.assertTrue(self.lam_moi(self.khach).check_password(MAT_KHAU_MOI))  # mật khẩu mới đã được băm và lưu

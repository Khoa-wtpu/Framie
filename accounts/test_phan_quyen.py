# =====================================================================
# accounts/test_phan_quyen.py  -  P7: kiểm thử quản lý tài khoản và vai trò
# Chạy:  python manage.py test accounts.test_phan_quyen
# =====================================================================
from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn

from accounts.models import User  # model User
from accounts.permissions import lay_vai_tro  # hàm lấy vai trò chính, để kiểm tra kết quả đổi
from accounts.services import tao_tai_khoan  # hàm tạo tài khoản của P4
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và trạng thái hồ sơ

MAT_KHAU = 'Matkhau!2026'  # mật khẩu dùng chung cho các tài khoản thử


class NenTest(TestCase):  # lớp cha: tạo sẵn các tài khoản dùng chung cho mọi test bên dưới
    def setUp(self):  # chạy trước mỗi test
        self.admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0900000001', MAT_KHAU, vai_tro=VaiTro.QUAN_TRI_VIEN)  # Quản trị viên đang thao tác
        self.admin2 = tao_tai_khoan('Quản Trị Hai', 'admin2@example.com', '0900000002', MAT_KHAU, vai_tro=VaiTro.QUAN_TRI_VIEN)  # Quản trị viên thứ hai (bị đổi/khóa trong test)
        self.khach = tao_tai_khoan('Khách Hàng', 'khach@example.com', '0900000003', MAT_KHAU)  # Khách hàng (vai trò mặc định)
        self.nag = tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0900000004', MAT_KHAU,  # Nhiếp ảnh gia
                                 vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)  # hồ sơ đã duyệt
        self.root = User.objects.create_superuser('root', 'root@example.com', MAT_KHAU, so_dien_thoai='0900000005')  # tài khoản hệ thống (createsuperuser)
        self.url_ds = reverse('admin_accounts')  # trang danh sách
        self.client.force_login(self.admin)  # mặc định đăng nhập bằng Quản trị viên

    def url_role(self, user):  # đường dẫn đổi vai trò của một tài khoản
        return reverse('admin_account_role', args=[user.pk])  # ghép pk vào đường dẫn

    def url_toggle(self, user):  # đường dẫn khóa/mở của một tài khoản
        return reverse('admin_account_toggle', args=[user.pk])  # ghép pk vào đường dẫn

    def nhom_cua(self, user):  # danh sách tên nhóm hiện tại của một tài khoản (đọc lại từ DB)
        return list(User.objects.get(pk=user.pk).groups.values_list('name', flat=True))  # lấy tên nhóm


class DanhSachTaiKhoanTests(NenTest):  # quyền xem và bộ lọc của trang danh sách
    def test_chua_dang_nhap_bi_chuyen_ve_login(self):  # người lạ
        self.client.logout()  # đăng xuất
        r = self.client.get(self.url_ds)  # mở trang
        self.assertEqual(r.status_code, 302)  # bị chuyển trang
        self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_khach_hang_va_nhiep_anh_gia_bi_403(self):  # chỉ Quản trị viên được xem
        for user in (self.khach, self.nag):  # thử từng vai trò
            with self.subTest(user=user.email):  # báo riêng nếu lỗi
                self.client.force_login(user)  # đăng nhập bằng vai trò này
                self.assertEqual(self.client.get(self.url_ds).status_code, 403)  # bị từ chối

    def test_quan_tri_vien_xem_duoc_du_lieu(self):  # đúng vai trò
        r = self.client.get(self.url_ds)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        for email in ('admin@example.com', 'khach@example.com', 'nag@example.com', 'root@example.com'):  # mọi tài khoản đều có mặt
            self.assertContains(r, email)  # email hiện trong bảng

    def test_tim_kiem_theo_email(self):  # ô tìm kiếm
        r = self.client.get(self.url_ds, {'q': 'khach@'})  # tìm "khach@"
        self.assertContains(r, 'khach@example.com')  # có người cần tìm
        self.assertNotContains(r, 'nag@example.com')  # người khác không hiện

    def test_tim_kiem_theo_ho_ten_nhieu_tu(self):  # tìm theo nhiều từ của họ tên
        r = self.client.get(self.url_ds, {'q': 'Khách Hàng'})  # tìm đủ họ tên
        self.assertContains(r, 'khach@example.com')  # khớp
        self.assertNotContains(r, 'nag@example.com')  # không khớp người khác

    def test_loc_theo_vai_tro(self):  # lọc vai trò
        for vai_tro, co, khong in (  # (vai trò lọc, email phải có, email không được có)
            (VaiTro.KHACH_HANG, 'khach@example.com', 'nag@example.com'),
            (VaiTro.NHIEP_ANH_GIA, 'nag@example.com', 'khach@example.com'),
            (VaiTro.QUAN_TRI_VIEN, 'root@example.com', 'khach@example.com'),  # superuser tính là Quản trị viên
        ):  # hết danh sách ca
            with self.subTest(vai_tro=vai_tro):  # báo riêng từng ca
                r = self.client.get(self.url_ds, {'vai_tro': vai_tro})  # lọc theo vai trò
                self.assertContains(r, co)  # có người đúng vai trò
                self.assertNotContains(r, khong)  # không có người sai vai trò

    def test_loc_theo_trang_thai(self):  # lọc tài khoản bị khóa
        self.khach.is_active = False  # khóa Khách hàng
        self.khach.save()  # lưu
        r = self.client.get(self.url_ds, {'trang_thai': 'bi_khoa'})  # chỉ xem tài khoản bị khóa
        self.assertContains(r, 'khach@example.com')  # có người bị khóa
        self.assertNotContains(r, 'nag@example.com')  # người đang hoạt động không hiện


class DoiVaiTroTests(NenTest):  # luật đổi vai trò
    def test_khach_hang_len_quan_tri_vien_chi_con_dung_mot_nhom(self):  # đổi thành công
        self.client.post(self.url_role(self.khach), {'vai_tro': VaiTro.QUAN_TRI_VIEN})  # đổi Khách hàng -> Quản trị viên
        self.assertEqual(self.nhom_cua(self.khach), [VaiTro.QUAN_TRI_VIEN])  # chỉ còn đúng 1 nhóm, không còn nhóm Khách hàng
        self.assertEqual(lay_vai_tro(User.objects.get(pk=self.khach.pk)), VaiTro.QUAN_TRI_VIEN)  # hàm kiểm quyền cũng thấy vai trò mới

    def test_quan_tri_vien_ha_xuong_khach_hang(self):  # đổi chiều ngược lại
        self.client.post(self.url_role(self.admin2), {'vai_tro': VaiTro.KHACH_HANG})  # hạ Quản trị viên thứ hai
        self.assertEqual(self.nhom_cua(self.admin2), [VaiTro.KHACH_HANG])  # chỉ còn nhóm Khách hàng

    def test_khong_doi_vai_tro_cua_chinh_minh(self):  # chống tự mất quyền
        r = self.client.post(self.url_role(self.admin), {'vai_tro': VaiTro.KHACH_HANG}, follow=True)  # tự hạ mình
        self.assertContains(r, 'chính mình')  # hiện câu báo lỗi
        self.assertEqual(self.nhom_cua(self.admin), [VaiTro.QUAN_TRI_VIEN])  # vai trò không đổi

    def test_khong_doi_vai_tro_nhiep_anh_gia(self):  # Nhiếp ảnh gia chỉ khóa được
        r = self.client.post(self.url_role(self.nag), {'vai_tro': VaiTro.KHACH_HANG}, follow=True)  # thử đổi
        self.assertContains(r, 'Không đổi vai trò của Nhiếp ảnh gia')  # hiện câu báo lỗi
        self.assertEqual(self.nhom_cua(self.nag), [VaiTro.NHIEP_ANH_GIA])  # vai trò không đổi
        self.assertEqual(User.objects.get(pk=self.nag.pk).trang_thai_ho_so, TrangThaiHoSo.DA_DUYET)  # hồ sơ cũng không bị đụng

    def test_khong_doi_vai_tro_superuser(self):  # tài khoản hệ thống
        r = self.client.post(self.url_role(self.root), {'vai_tro': VaiTro.KHACH_HANG}, follow=True)  # thử đổi
        self.assertContains(r, 'Tài khoản hệ thống')  # hiện câu báo lỗi
        self.assertEqual(lay_vai_tro(User.objects.get(pk=self.root.pk)), VaiTro.QUAN_TRI_VIEN)  # vẫn là Quản trị viên

    def test_khong_gan_vai_tro_la_hoac_nhiep_anh_gia(self):  # người dùng tự sửa form gửi vai trò không cho phép
        for gia_tri in ('Hacker', VaiTro.NHIEP_ANH_GIA, ''):  # vai trò lạ, Nhiếp ảnh gia (phải qua P5), rỗng
            with self.subTest(vai_tro=gia_tri):  # báo riêng từng ca
                r = self.client.post(self.url_role(self.khach), {'vai_tro': gia_tri}, follow=True)  # gửi giá trị này
                self.assertContains(r, 'Vai trò mới không hợp lệ')  # bị từ chối
                self.assertEqual(self.nhom_cua(self.khach), [VaiTro.KHACH_HANG])  # không đổi

    def test_doi_cung_vai_tro_bao_loi_nhe(self):  # đổi sang đúng vai trò đang có
        r = self.client.post(self.url_role(self.khach), {'vai_tro': VaiTro.KHACH_HANG}, follow=True)  # Khách hàng -> Khách hàng
        self.assertContains(r, 'đã ở vai trò này')  # báo không có gì để đổi

    def test_nguoi_khong_phai_quan_tri_bi_403_va_khong_doi_duoc(self):  # chỉ Quản trị viên được thay đổi vai trò
        for user in (self.khach, self.nag):  # thử Khách hàng và Nhiếp ảnh gia
            with self.subTest(user=user.email):  # báo riêng
                self.client.force_login(user)  # đăng nhập bằng họ
                r = self.client.post(self.url_role(self.khach), {'vai_tro': VaiTro.QUAN_TRI_VIEN})  # tự nâng quyền / nâng quyền người khác
                self.assertEqual(r.status_code, 403)  # bị từ chối
                self.assertEqual(self.nhom_cua(self.khach), [VaiTro.KHACH_HANG])  # vai trò không đổi

    def test_khong_dung_get_de_doi_vai_tro(self):  # đổi dữ liệu phải bằng POST
        self.assertEqual(self.client.get(self.url_role(self.khach)).status_code, 405)  # GET bị từ chối

    def test_tai_khoan_khong_ton_tai_tra_404(self):  # pk sai
        self.assertEqual(self.client.post(reverse('admin_account_role', args=[999999]), {'vai_tro': VaiTro.KHACH_HANG}).status_code, 404)  # không có tài khoản


class KhoaMoTaiKhoanTests(NenTest):  # luật khóa và mở tài khoản
    def test_khoa_roi_mo_lai(self):  # luồng chính
        self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'khoa'})  # khóa
        self.assertFalse(User.objects.get(pk=self.khach.pk).is_active)  # đã khóa
        self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'mo'})  # mở lại
        self.assertTrue(User.objects.get(pk=self.khach.pk).is_active)  # đã mở

    def test_co_the_khoa_nhiep_anh_gia(self):  # Nhiếp ảnh gia không đổi vai trò được nhưng khóa được
        self.client.post(self.url_toggle(self.nag), {'hanh_dong': 'khoa'})  # khóa
        self.assertFalse(User.objects.get(pk=self.nag.pk).is_active)  # đã khóa

    def test_khong_khoa_chinh_minh(self):  # chống tự khóa
        r = self.client.post(self.url_toggle(self.admin), {'hanh_dong': 'khoa'}, follow=True)  # tự khóa
        self.assertContains(r, 'khóa chính mình')  # báo lỗi
        self.assertTrue(User.objects.get(pk=self.admin.pk).is_active)  # vẫn hoạt động

    def test_khong_khoa_superuser(self):  # tài khoản hệ thống
        r = self.client.post(self.url_toggle(self.root), {'hanh_dong': 'khoa'}, follow=True)  # thử khóa
        self.assertContains(r, 'tài khoản hệ thống')  # báo lỗi
        self.assertTrue(User.objects.get(pk=self.root.pk).is_active)  # vẫn hoạt động

    def test_khoa_hai_lan_bao_loi_nhe(self):  # bấm Khóa lần hai (ví dụ hai Quản trị viên cùng bấm)
        self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'khoa'})  # khóa lần 1
        r = self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'khoa'}, follow=True)  # khóa lần 2
        self.assertContains(r, 'đã ở trạng thái này')  # báo nhẹ, không lỗi 500

    def test_tai_khoan_bi_khoa_khong_dang_nhap_duoc(self):  # hiệu lực của việc khóa
        self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'khoa'})  # khóa Khách hàng
        khach_moi = self.client_class()  # trình duyệt giả mới, chưa đăng nhập
        r = khach_moi.post(reverse('login'), {'username': 'khach@example.com', 'password': MAT_KHAU})  # đăng nhập đúng mật khẩu
        self.assertContains(r, 'đã bị khóa')  # hiện câu báo tài khoản bị khóa (có sẵn trong DangNhapForm)

    def test_phien_dang_nhap_cu_mat_hieu_luc_sau_khi_khoa(self):  # người đang đăng nhập bị khóa thì bị đá ra
        phien_khach = self.client_class()  # trình duyệt giả của Khách hàng
        phien_khach.force_login(self.khach)  # Khách hàng đang đăng nhập
        self.assertEqual(phien_khach.get(reverse('trang_tam')).status_code, 200)  # vào được trang cần đăng nhập
        self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'khoa'})  # Quản trị viên khóa
        self.assertEqual(phien_khach.get(reverse('trang_tam')).status_code, 302)  # bị chuyển về đăng nhập

    def test_nguoi_khong_phai_quan_tri_bi_403_khi_khoa(self):  # chỉ Quản trị viên được khóa
        self.client.force_login(self.khach)  # đăng nhập bằng Khách hàng
        r = self.client.post(self.url_toggle(self.nag), {'hanh_dong': 'khoa'})  # thử khóa người khác
        self.assertEqual(r.status_code, 403)  # bị từ chối
        self.assertTrue(User.objects.get(pk=self.nag.pk).is_active)  # không bị khóa

    def test_quay_lai_dung_trang_va_chan_dia_chi_la(self):  # tham số quay_lai
        r = self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'khoa', 'quay_lai': '/quan-tri/tai-khoan/?q=khach'})  # đường dẫn cùng website
        self.assertRedirects(r, '/quan-tri/tai-khoan/?q=khach')  # quay lại đúng bộ lọc
        r = self.client.post(self.url_toggle(self.khach), {'hanh_dong': 'mo', 'quay_lai': 'https://evil.example.com/'})  # đường dẫn ra trang lạ
        self.assertRedirects(r, self.url_ds)  # bị bỏ qua, về danh sách
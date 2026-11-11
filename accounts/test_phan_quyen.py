# =====================================================================
# accounts/test_phan_quyen.py  -  P7: kiểm thử quản lý tài khoản và vai trò
# Chạy:  python manage.py test accounts.test_phan_quyen
# =====================================================================
import html  # đổi &amp; trong link HTML về &
import re  # tìm link chuyển trang trong HTML
from urllib.parse import parse_qs, urljoin, urlsplit  # ghép đường dẫn trang với phần ?... của link; đọc các tham số trong link nút lọc

from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import NoReverseMatch, reverse  # đổi tên URL thành đường dẫn

from accounts.models import User  # model User
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

    def test_phan_trang_trang_2_va_giu_bo_loc(self):  # feedback P7-2: dùng phân trang chung, link chuyển trang giữ ô tìm kiếm
        for i in range(25):  # 25 tài khoản cùng chứa chữ locmau, nhiều hơn 20 dòng của một trang
            tao_tai_khoan(f'Khách Locmau {i:02d}', f'locmau{i:02d}@example.com', f'09100000{i:02d}', MAT_KHAU)  # email và số điện thoại không trùng nhau
        r1 = self.client.get(self.url_ds, {'q': 'locmau'})  # trang 1 khi đang lọc theo locmau
        self.assertEqual(len(r1.context['hang']), 20)  # trang 1 đủ 20 dòng
        href = re.search(r'href="([^"]*page=2[^"]*)"', r1.content.decode()).group(1)  # link sang trang 2 do includes/pagination.html in ra
        url2 = urljoin(self.url_ds, html.unescape(href))  # href chỉ gồm phần sau dấu ?, nên ghép với đường dẫn trang; unescape đổi &amp; thành &
        self.assertIn('q=locmau', url2)  # bộ lọc còn nguyên trong link
        r2 = self.client.get(url2)  # bấm link sang trang 2
        email_trang_2 = {h['user'].email for h in r2.context['hang']}  # email các dòng ở trang 2
        self.assertEqual(email_trang_2, {f'locmau{i:02d}@example.com' for i in range(5)})  # danh sách xếp mới nhất lên đầu nên trang 2 là 5 người tạo đầu tiên

    def test_nut_loc_ket_hop_vai_tro_va_trang_thai(self):  # P7: hai nhóm nút lọc kết hợp được, mỗi nút chỉ đổi bộ lọc của nhóm mình
        def nut(r, nhom, nhan):  # tìm một nút trong context theo nhóm và chữ trên nút
            return next(n for n in r.context[nhom] if n['nhan'] == nhan)  # trả về dict của nút
        def tham_so(n):  # các tham số trong link của nút
            return parse_qs(urlsplit(n['url']).query)  # dict tên tham số -> danh sách giá trị
        r = self.client.get(self.url_ds, {'q': 'khach', 'vai_tro': VaiTro.KHACH_HANG})  # đang lọc theo từ khóa và vai trò
        khoa = nut(r, 'nut_trang_thai', 'Đã khóa')  # nút Đã khóa
        self.assertFalse(khoa['dang_chon'])  # chưa được chọn
        self.assertEqual(tham_so(khoa), {'q': ['khach'], 'vai_tro': [VaiTro.KHACH_HANG], 'trang_thai': ['bi_khoa']})  # giữ từ khóa và vai trò, thêm trạng thái
        r = self.client.get(khoa['url'])  # bấm nút Đã khóa
        khoa = nut(r, 'nut_trang_thai', 'Đã khóa')  # nút Đã khóa sau khi bấm
        self.assertTrue(khoa['dang_chon'])  # nút đang được chọn
        self.assertNotIn('trang_thai', tham_so(khoa))  # bấm lần nữa là bỏ chọn trạng thái
        self.assertEqual(tham_so(khoa)['vai_tro'], [VaiTro.KHACH_HANG])  # vai trò vẫn còn
        tat_ca = nut(r, 'nut_vai_tro', 'Tất cả')  # nút Tất cả của nhóm vai trò
        self.assertNotIn('vai_tro', tham_so(tat_ca))  # bỏ lọc vai trò
        self.assertEqual(tham_so(tat_ca)['trang_thai'], ['bi_khoa'])  # nhưng giữ lọc trạng thái


class KhongConDoiVaiTroTests(NenTest):  # đổi vai trò ngay trên trang đã bỏ; Quản trị viên mới chỉ tạo bằng link mời hoặc createsuperuser
    def test_trang_khong_con_giao_dien_doi_vai_tro(self):  # danh sách không còn nút/hàng chỉnh sửa vai trò
        r = self.client.get(self.url_ds)  # mở danh sách bằng Quản trị viên
        for dau_hieu in ('data-sua-vai-tro', 'data-form-vai-tro', 'Lưu vai trò', 'Vai trò chính'):  # các dấu vết của giao diện cũ
            with self.subTest(dau_hieu=dau_hieu):  # báo riêng từng dấu vết
                self.assertNotContains(r, dau_hieu)  # không còn trong HTML

    def test_khong_con_duong_dan_doi_vai_tro(self):  # POST thẳng vào đường dẫn cũ cũng không đổi được gì
        with self.assertRaises(NoReverseMatch):  # tên URL đã bị xóa
            reverse('admin_account_role', args=[self.khach.pk])  # phải báo không tìm thấy
        r = self.client.post(f'/quan-tri/tai-khoan/{self.khach.pk}/doi-vai-tro/', {'vai_tro': VaiTro.QUAN_TRI_VIEN})  # tự ghép đường dẫn cũ
        self.assertEqual(r.status_code, 404)  # không còn đường dẫn
        self.assertEqual(self.nhom_cua(self.khach), [VaiTro.KHACH_HANG])  # vai trò không đổi


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

    def test_hanh_dong_khong_hop_le_khong_mo_khoa(self):  # feedback P7-1: POST thiếu hoặc sai hanh_dong không được hiểu là mở khóa
        self.khach.is_active = False  # khóa sẵn Khách hàng
        self.khach.save()  # lưu
        for du_lieu in ({'hanh_dong': ''}, {'hanh_dong': 'abc'}, {}):  # rỗng, giá trị lạ, không gửi gì
            with self.subTest(du_lieu=du_lieu):  # báo riêng từng ca
                r = self.client.post(self.url_toggle(self.khach), du_lieu, follow=True)  # gửi POST
                self.assertContains(r, 'Thao tác không hợp lệ')  # hiện câu báo lỗi
                self.assertFalse(User.objects.get(pk=self.khach.pk).is_active)  # tài khoản vẫn bị khóa

    def test_quan_tri_vien_khoa_duoc_quan_tri_vien_thuong_khac(self):  # hành vi có chủ ý đã được Khoa xác nhận
        self.client.post(self.url_toggle(self.admin2), {'hanh_dong': 'khoa'})  # Quản trị viên thường khóa Quản trị viên thường khác
        self.assertFalse(User.objects.get(pk=self.admin2.pk).is_active)  # tài khoản kia đã bị khóa

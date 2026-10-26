from django.contrib.auth.models import Group  # bảng nhóm quyền
from django.test import TestCase  # lớp test của Django, mỗi test chạy trên DB tạm

from accounts.models import User  # model User của FRAMIE
from core.constants import VaiTro  # tên vai trò


class DangNhapVaPhanQuyenTests(TestCase):  # nhóm test của P3
    def setUp(self):  # chạy trước mỗi test: tạo sẵn 1 Khách hàng
        self.khach = User.objects.create_user(  # tạo User với mật khẩu được mã hóa
            username='kh1', email='kh1@example.com',  # tên đăng nhập và email
            password='Abcd@1234', so_dien_thoai='0901234567',  # mật khẩu và số điện thoại hợp lệ
        )  # hết tạo User
        self.khach.groups.add(Group.objects.get(name=VaiTro.KHACH_HANG))  # gán nhóm Khách hàng (migration 0003 đã tạo nhóm)

    def test_sai_mat_khau_bao_dung_cau(self):  # sai mật khẩu phải báo đúng câu
        res = self.client.post('/dang-nhap/', {'username': 'kh1@example.com', 'password': 'sai'})  # gửi form sai
        self.assertContains(res, 'Email hoặc mật khẩu không chính xác')  # trang trả về có đúng câu báo lỗi

    def test_dang_nhap_dung_duoc_vao(self):  # đúng thông tin thì đăng nhập được
        res = self.client.post('/dang-nhap/', {'username': 'KH1@example.com', 'password': 'Abcd@1234'})  # email viết hoa vẫn được
        self.assertEqual(res.status_code, 302)  # 302 = đã chuyển trang
        self.assertIn('_auth_user_id', self.client.session)  # phiên đã ghi nhận người đăng nhập

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):  # chưa đăng nhập vào trang thử
        res = self.client.get('/thu-quyen/khach-hang/')  # truy cập trực tiếp
        self.assertEqual(res.status_code, 302)  # bị chuyển trang
        self.assertIn('/dang-nhap/', res['Location'])  # đích là trang đăng nhập

    def test_sai_vai_tro_bi_403(self):  # Khách hàng gõ đường dẫn trang Quản trị viên
        self.client.force_login(self.khach)  # đăng nhập thẳng, bỏ qua form
        self.assertEqual(self.client.get('/thu-quyen/quan-tri/').status_code, 403)  # bị chặn
        self.assertEqual(self.client.get('/thu-quyen/khach-hang/').status_code, 200)  # trang đúng vai trò thì vào được

    def test_dang_xuat_can_xac_nhan(self):  # GET chỉ hỏi, POST mới đăng xuất
        self.client.force_login(self.khach)  # đăng nhập
        self.client.get('/dang-xuat/')  # mở trang xác nhận
        self.assertIn('_auth_user_id', self.client.session)  # vẫn đang đăng nhập
        self.client.post('/dang-xuat/')  # bấm nút xác nhận
        self.assertNotIn('_auth_user_id', self.client.session)  # đã đăng xuất

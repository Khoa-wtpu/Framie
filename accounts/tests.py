from django.contrib.auth.models import Group  # bảng nhóm quyền
from django.http import HttpResponse  # tạo phản hồi đơn giản cho trang giả
from django.test import TestCase, override_settings  # TestCase: mỗi test chạy trên DB tạm; override_settings: đổi cấu hình riêng cho test
from django.urls import include, path  # khai báo đường dẫn

from accounts.models import User  # model User của FRAMIE
from accounts.permissions import (  # các công cụ kiểm tra quyền cần thử
    chi_khach_hang, chi_nhiep_anh_gia_da_duyet, chi_quan_tri_vien, url_trang_chu,
)
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và trạng thái hồ sơ


# ---- 3 trang GIẢ, chỉ tồn tại khi chạy test, không ảnh hưởng web thật ----
@chi_khach_hang  # chỉ Khách hàng được vào
def trang_gia_khach(request):  # trang giả 1
    return HttpResponse('ok')  # trả nội dung đơn giản


@chi_nhiep_anh_gia_da_duyet  # chỉ Nhiếp ảnh gia ĐÃ DUYỆT được vào
def trang_gia_nag(request):  # trang giả 2
    return HttpResponse('ok')  # trả nội dung đơn giản


@chi_quan_tri_vien  # chỉ Quản trị viên được vào
def trang_gia_quan_tri(request):  # trang giả 3
    return HttpResponse('ok')  # trả nội dung đơn giản


urlpatterns = [  # bảng đường dẫn dùng riêng cho test
    path('gia/khach-hang/', trang_gia_khach),  # đường dẫn trang giả 1
    path('gia/nhiep-anh-gia/', trang_gia_nag),  # đường dẫn trang giả 2
    path('gia/quan-tri/', trang_gia_quan_tri),  # đường dẫn trang giả 3
    path('', include('config.urls')),  # nối toàn bộ đường dẫn thật của dự án (đăng nhập, đăng xuất...)
]  # hết danh sách


@override_settings(ROOT_URLCONF='accounts.tests')  # trong class này dùng bảng đường dẫn ở trên
class DangNhapVaPhanQuyenTests(TestCase):  # nhóm test của P3

    def tao_user(self, ten, vai_tro, sdt, **them):  # hàm phụ: tạo nhanh 1 tài khoản đã gán nhóm
        user = User.objects.create_user(  # tạo User với mật khẩu được mã hóa
            username=ten,  # tên đăng nhập
            email=f'{ten}@example.com',  # email suy ra từ tên
            password='Abcd@1234',  # mật khẩu hợp lệ dùng chung cho mọi tài khoản thử
            so_dien_thoai=sdt,  # số điện thoại (mỗi tài khoản phải khác nhau)
            **them,  # các trường thêm, ví dụ trang_thai_ho_so hoặc is_active
        )  # hết tạo User
        user.groups.add(Group.objects.get(name=vai_tro))  # gán nhóm (migration 0003 đã tạo sẵn 3 nhóm)
        return user  # trả User vừa tạo

    def setUp(self):  # chạy trước mỗi test
        self.khach = self.tao_user('kh1', VaiTro.KHACH_HANG, '0901234567')  # tạo sẵn 1 Khách hàng

    def test_sai_mat_khau_bao_dung_cau(self):  # sai mật khẩu phải báo đúng câu
        res = self.client.post('/dang-nhap/', {'username': 'kh1@example.com', 'password': 'sai'})  # gửi form sai
        self.assertContains(res, 'Email hoặc mật khẩu không chính xác')  # trang trả về có đúng câu báo lỗi

    def test_dang_nhap_dung_duoc_vao(self):  # đúng thông tin thì đăng nhập được
        res = self.client.post('/dang-nhap/', {'username': 'KH1@example.com', 'password': 'Abcd@1234'})  # email viết hoa vẫn được
        self.assertEqual(res.status_code, 302)  # 302 = đã chuyển trang
        self.assertIn('_auth_user_id', self.client.session)  # phiên đã ghi nhận người đăng nhập

    def test_tai_khoan_bi_khoa_bao_dung_cau(self):  # tài khoản bị khóa phải báo đúng câu
        self.tao_user('khoa1', VaiTro.KHACH_HANG, '0912345678', is_active=False)  # tạo tài khoản bị khóa
        res = self.client.post('/dang-nhap/', {'username': 'khoa1@example.com', 'password': 'Abcd@1234'})  # đăng nhập đúng mật khẩu
        self.assertContains(res, 'Tài khoản của bạn đã bị khóa')  # phải báo bị khóa
        self.assertNotIn('_auth_user_id', self.client.session)  # và không được đăng nhập

    def test_chuyen_trang_theo_vai_tro(self):  # đăng nhập xong phải đến trang đúng vai trò
        admin = self.tao_user('ad1', VaiTro.QUAN_TRI_VIEN, '0923456789')  # tạo Quản trị viên
        for user in (self.khach, admin):  # thử lần lượt từng vai trò
            self.client.logout()  # đảm bảo đang ở trạng thái chưa đăng nhập
            res = self.client.post('/dang-nhap/', {'username': user.email, 'password': 'Abcd@1234'})  # đăng nhập
            self.assertRedirects(res, url_trang_chu(user), fetch_redirect_response=False)  # đích đến khớp url_trang_chu

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):  # chưa đăng nhập vào trang được bảo vệ
        res = self.client.get('/gia/khach-hang/')  # truy cập trực tiếp
        self.assertEqual(res.status_code, 302)  # bị chuyển trang
        self.assertIn('/dang-nhap/', res['Location'])  # đích là trang đăng nhập

    def test_sai_vai_tro_bi_403(self):  # Khách hàng gõ đường dẫn trang của vai trò khác
        self.client.force_login(self.khach)  # đăng nhập thẳng, bỏ qua form
        self.assertEqual(self.client.get('/gia/quan-tri/').status_code, 403)  # trang Quản trị viên bị chặn
        self.assertEqual(self.client.get('/gia/khach-hang/').status_code, 200)  # trang đúng vai trò thì vào được

    def test_nag_chua_duyet_bi_403(self):  # Nhiếp ảnh gia chờ duyệt hoặc bị từ chối gõ đường dẫn
        cac_trang_thai = (TrangThaiHoSo.CHO_DUYET, TrangThaiHoSo.DA_TU_CHOI)  # 2 trạng thái chưa được dùng đủ chức năng
        for i, trang_thai in enumerate(cac_trang_thai):  # thử lần lượt từng trạng thái
            nag = self.tao_user(f'nag{i}', VaiTro.NHIEP_ANH_GIA, f'090000000{i}', trang_thai_ho_so=trang_thai)  # tạo NAG chưa duyệt
            self.client.force_login(nag)  # đăng nhập
            self.assertEqual(self.client.get('/gia/nhiep-anh-gia/').status_code, 403)  # phải bị chặn

    def test_nag_da_duyet_duoc_vao(self):  # Nhiếp ảnh gia đã duyệt thì vào được
        nag = self.tao_user('nag9', VaiTro.NHIEP_ANH_GIA, '0988888888', trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)  # tạo NAG đã duyệt
        self.client.force_login(nag)  # đăng nhập
        self.assertEqual(self.client.get('/gia/nhiep-anh-gia/').status_code, 200)  # vào được

    def test_dang_xuat_can_xac_nhan(self):  # GET chỉ hỏi, POST mới đăng xuất
        self.client.force_login(self.khach)  # đăng nhập
        self.client.get('/dang-xuat/')  # mở trang xác nhận
        self.assertIn('_auth_user_id', self.client.session)  # vẫn đang đăng nhập
        self.client.post('/dang-xuat/')  # bấm nút xác nhận
        self.assertNotIn('_auth_user_id', self.client.session)  # đã đăng xuất

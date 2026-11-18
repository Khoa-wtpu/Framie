from unittest.mock import patch  # patch: thay tạm một hàm bằng hàm giả để giả lập lỗi
from django.contrib.auth.models import Group  # bảng nhóm quyền (vai trò)
from django.contrib.messages import get_messages  # đọc các thông báo (messages) mà view đã gửi
from django.core import mail  # mail.outbox: hộp thư giả, Django tự dùng khi chạy test nên không gửi email thật
from django.http import HttpResponse  # nội dung trả về của 3 trang giả
from django.test import TestCase, override_settings  # TestCase: database tạm; override_settings: đổi cấu hình trong test
from django.urls import include, path  # khai báo bảng đường dẫn riêng cho test

from accounts.models import User  # model User của FRAMIE
from accounts.permissions import (  # công cụ phân quyền nằm ở permissions.py
    chi_khach_hang, chi_nhiep_anh_gia_da_duyet, chi_quan_tri_vien, url_trang_chu,
)
from accounts.services import tach_ho_ten  # hàm tách họ tên cần kiểm tra
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

class DangKyTests(TestCase):  # nhóm test của P4 (UC7.1a)
    DU_LIEU = {  # dữ liệu hợp lệ dùng chung cho mọi test
        'ho_ten': 'Nguyễn Văn An',  # họ tên hợp lệ
        'email': 'an@example.com',  # email hợp lệ
        'so_dien_thoai': '0912345678',  # 10 số, bắt đầu bằng 0
        'mat_khau': 'Xk9#mQ2vLp',  # đủ 8 ký tự, có hoa, thường, số, ký tự đặc biệt, không phổ biến
    }  # hết dữ liệu mẫu

    def test_dang_ky_dung_tao_user_va_gui_mot_email(self):  # luồng chính
        res = self.client.post('/dang-ky/', self.DU_LIEU)  # gửi form đăng ký
        self.assertEqual(res.status_code, 302)  # thành công thì chuyển sang trang đăng nhập
        user = User.objects.get(email='an@example.com')  # tài khoản đã được tạo
        self.assertTrue(user.groups.filter(name=VaiTro.KHACH_HANG).exists())  # thuộc nhóm Khách hàng
        self.assertTrue(user.check_password('Xk9#mQ2vLp'))  # mật khẩu đăng nhập được
        self.assertNotEqual(user.password, 'Xk9#mQ2vLp')  # nhưng DB không lưu mật khẩu thô (đã băm)
        self.assertIsNone(user.trang_thai_ho_so)  # Khách hàng để trống trạng thái hồ sơ
        self.assertEqual(len(mail.outbox), 1)  # có đúng 1 email
        self.assertEqual(mail.outbox[0].to, ['an@example.com'])  # gửi đúng người nhận
        self.assertNotIn('Xk9#mQ2vLp', mail.outbox[0].body)  # nội dung email không chứa mật khẩu

    def test_email_trung_ke_ca_khac_hoa_thuong(self):  # email không được trùng
        self.client.post('/dang-ky/', self.DU_LIEU)  # đăng ký lần 1
        khac = {**self.DU_LIEU, 'email': 'AN@Example.com', 'so_dien_thoai': '0900000001'}  # cùng email nhưng viết hoa, khác số
        res = self.client.post('/dang-ky/', khac)  # đăng ký lần 2
        self.assertContains(res, 'Email này đã được đăng ký.')  # phải báo trùng
        self.assertEqual(User.objects.count(), 1)  # không tạo thêm tài khoản

    def test_so_dien_thoai_trung(self):  # số điện thoại không được trùng
        self.client.post('/dang-ky/', self.DU_LIEU)  # đăng ký lần 1
        res = self.client.post('/dang-ky/', {**self.DU_LIEU, 'email': 'binh@example.com'})  # khác email, cùng số
        self.assertContains(res, 'Số điện thoại này đã được đăng ký.')  # phải báo trùng
        self.assertEqual(User.objects.count(), 1)  # không tạo thêm tài khoản

    def test_so_dien_thoai_sai_dinh_dang(self):  # phải đúng 10 chữ số và bắt đầu bằng 0
        for so in ['123456789', '091234567', '09123456789', '09123abc78']:  # thiếu số 0 đầu / thiếu số / dư số / có chữ
            with self.subTest(so=so):  # báo riêng từng giá trị nếu có giá trị lỗi
                res = self.client.post('/dang-ky/', {**self.DU_LIEU, 'so_dien_thoai': so})  # gửi từng số
                self.assertContains(res, 'Số điện thoại gồm 10 chữ số và bắt đầu bằng 0.')  # đều bị báo lỗi
        self.assertEqual(User.objects.count(), 0)  # không có tài khoản nào được tạo

    def test_mat_khau_sai_tung_kieu(self):  # mỗi kiểu thiếu phải bị chặn
        ca_sai = {  # mật khẩu sai -> câu báo lỗi phải xuất hiện (None = chỉ kiểm tra bị chặn)
            'xk9#mq2vlp': 'ít nhất một chữ hoa',  # thiếu chữ hoa
            'XK9#MQ2VLP': 'ít nhất một chữ thường',  # thiếu chữ thường
            'Xkd#mQrvLp': 'ít nhất một chữ số',  # thiếu số
            'Xk9mQ2vLpa': 'ít nhất một ký tự đặc biệt',  # thiếu ký tự đặc biệt
            'Xk9mQ2vLpẩ': 'ít nhất một ký tự đặc biệt',  # chữ có dấu KHÔNG được tính là ký tự đặc biệt
            'Xk9#mQ2': None,  # ngắn hơn 8 ký tự (câu báo do Django sinh nên không kiểm tra chữ)
        }  # hết danh sách
        for mk, cau_bao in ca_sai.items():  # duyệt từng mật khẩu sai
            with self.subTest(mat_khau=mk):  # báo riêng từng mật khẩu nếu lỗi
                res = self.client.post('/dang-ky/', {**self.DU_LIEU, 'mat_khau': mk})  # gửi form
                self.assertEqual(res.status_code, 200)  # ở lại trang đăng ký, không chuyển trang
                if cau_bao:  # có câu báo cần kiểm tra
                    self.assertContains(res, cau_bao)  # trang hiện đúng câu báo lỗi
        self.assertEqual(User.objects.count(), 0)  # không có tài khoản nào được tạo

    def test_email_loi_van_tao_tai_khoan_va_co_canh_bao(self):  # gửi email lỗi không làm hỏng đăng ký
        with patch('accounts.services.send_mail', side_effect=OSError('SMTP lỗi')):  # giả lập send_mail luôn ném lỗi
            with self.assertLogs('accounts.services', level='ERROR'):  # hứng log lỗi để Terminal không bị in traceback
                res = self.client.post('/dang-ky/', self.DU_LIEU)  # gửi form đăng ký
        self.assertEqual(res.status_code, 302)  # vẫn chuyển sang trang đăng nhập
        self.assertTrue(User.objects.filter(email='an@example.com').exists())  # tài khoản vẫn được tạo
        muc = [m.level_tag for m in get_messages(res.wsgi_request)]  # lấy các mức thông báo đã gửi
        self.assertIn('success', muc)  # có thông báo đăng ký thành công
        self.assertIn('warning', muc)  # và có cảnh báo chưa gửi được email

    def test_tach_ho_ten(self):  # kiểm tra hàm tách họ tên
        self.assertEqual(tach_ho_ten('An'), ('An', ''))  # một chữ: là tên, họ để rỗng
        self.assertEqual(tach_ho_ten('Nguyễn Văn An'), ('An', 'Nguyễn Văn'))  # tên là chữ cuối
        self.assertEqual(tach_ho_ten('  Nguyễn   Văn  An  '), ('An', 'Nguyễn Văn'))  # khoảng trắng thừa được dọn
        self.assertEqual(tach_ho_ten(''), ('', ''))  # chuỗi rỗng không gây lỗi

    def test_loi_mat_khau_chi_hien_mot_lan(self):  # feedback P4-1: mỗi câu lỗi mật khẩu chỉ được hiện đúng 1 lần
        res = self.client.post('/dang-ky/', {**self.DU_LIEU, 'mat_khau': 'xk9#mq2vlp'})  # mật khẩu thiếu chữ hoa
        self.assertContains(res, 'Mật khẩu phải có ít nhất một chữ hoa.', count=1)  # câu báo xuất hiện đúng 1 lần, không bị lặp do hai nơi cùng kiểm tra

    @override_settings(ALLOWED_HOSTS=['framie.example.com'])  # cho phép tên miền giả này trong test, nếu không Django từ chối vì Host lạ
    def test_link_dang_nhap_trong_email_theo_dia_chi_dang_truy_cap(self):  # feedback P4-2: link không được cố định 127.0.0.1
        self.client.post('/dang-ky/', self.DU_LIEU, HTTP_HOST='framie.example.com')  # đăng ký khi truy cập qua tên miền khác
        self.assertIn('http://framie.example.com/dang-nhap/', mail.outbox[0].body)  # link lấy theo địa chỉ người dùng đang dùng, không phải 127.0.0.1
        self.assertNotIn('127.0.0.1', mail.outbox[0].body)  # và không chứa địa chỉ máy của người lập trình

    def test_get_full_name_dung_thu_tu_tieng_viet(self):  # câu hỏi C của Khoa (trước đây bị thụt vào class lồng nên không chạy)
        user = User(first_name='An', last_name='Nguyễn Văn')  # tên = An, họ và tên đệm = Nguyễn Văn
        self.assertEqual(user.get_full_name(), 'Nguyễn Văn An')  # phải ra "Họ Tên", không phải "Tên Họ"

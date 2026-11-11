import shutil  # shutil: xóa thư mục ảnh tạm sau khi test xong
import tempfile  # tempfile: tạo thư mục tạm cho ảnh test
from io import BytesIO  # BytesIO: giữ dữ liệu ảnh trong bộ nhớ, không ghi ra ổ đĩa
from unittest.mock import patch  # patch: thay tạm một hàm bằng hàm giả để giả lập lỗi

from django.contrib.auth.models import Group  # bảng nhóm quyền (vai trò)
from django.core.files.uploadedfile import SimpleUploadedFile  # file giả để "tải lên" trong test
from django.db import IntegrityError  # lỗi trùng dữ liệu của database
from django.test import TestCase, override_settings  # TestCase: database tạm; override_settings: đổi cấu hình trong test
from django.urls import reverse  # đổi tên URL thành đường dẫn
from PIL import Image  # Pillow: tạo ảnh thật (form ImageField kiểm tra file có đúng là ảnh)

from accounts.models import User  # model User của FRAMIE
from core.constants import TrangThaiHoSo, VaiTro  # trạng thái hồ sơ và tên vai trò
from notifications.models import ThongBao  # bảng thông báo (kiểm tra Quản trị viên được báo)
from profiles.forms import NGAN_HANG  # danh sách ngân hàng hợp lệ của form Khoa
from profiles.models import DuyetHoSo, KhuVuc, LoaiHinhChup, NhiepAnhGia, PhongCach  # các bảng hồ sơ

THU_MUC_ANH = tempfile.mkdtemp()  # ảnh test lưu ở đây, không làm bẩn thư mục media thật (giống profiles/tests.py)


def tao_anh(ten='a.png'):  # hàm phụ: tạo ảnh PNG 10x10 hợp lệ (cùng cách với profiles/tests.py)
    bo_nho = BytesIO()  # vùng nhớ tạm chứa dữ liệu ảnh
    Image.new('RGB', (10, 10), 'red').save(bo_nho, 'PNG')  # vẽ ảnh đỏ 10x10 rồi lưu dạng PNG vào vùng nhớ
    return SimpleUploadedFile(ten, bo_nho.getvalue(), content_type='image/png')  # bọc thành file tải lên


class TrangDangKyTests(TestCase):  # P5 (feedback d): trang đăng ký mở được, người đã đăng nhập bị chuyển đi

    def test_get_tra_200_va_co_nut_chon_vai_tro(self):  # mở trang đăng ký Nhiếp ảnh gia bằng GET
        res = self.client.get(reverse('register_photographer'))  # mở trang
        self.assertEqual(res.status_code, 200)  # trang hiện bình thường
        self.assertContains(res, 'role-switch')  # có khối chọn vai trò dùng class, không dùng style inline
        self.assertContains(res, 'href="/dang-nhap/"')  # dòng "Đã có tài khoản? Đăng nhập" trỏ đúng trang đăng nhập

    def test_trang_khach_hang_cung_co_khoi_chon_vai_tro(self):  # trang Khách hàng phải giống trang Nhiếp ảnh gia
        res = self.client.get(reverse('register'))  # mở trang đăng ký Khách hàng
        self.assertEqual(res.status_code, 200)  # trang hiện bình thường
        self.assertContains(res, 'role-switch')  # có cùng khối chọn vai trò
        self.assertContains(res, 'ho-so__khoi')  # có cùng kiểu khối "Thông tin tài khoản"

    def test_nguoi_da_dang_nhap_bi_chuyen_trang(self):  # đã đăng nhập thì không được đăng ký nữa
        user = User.objects.create_user(  # tạo nhanh một tài khoản
            username='da_dn', email='da_dn@example.com', password='Xk9#mQ2vLp', so_dien_thoai='0912345670',  # thông tin tối thiểu
        )  # hết tạo User
        self.client.force_login(user)  # đăng nhập thẳng, bỏ qua form
        for ten_url in ('register', 'register_photographer'):  # thử cả hai trang đăng ký
            with self.subTest(url=ten_url):  # báo riêng từng trang nếu lỗi
                res = self.client.get(reverse(ten_url))  # mở trang đăng ký
                self.assertEqual(res.status_code, 302)  # bị chuyển đi, không hiện form


@override_settings(MEDIA_ROOT=THU_MUC_ANH)  # mọi ảnh tải lên trong class này đi vào thư mục tạm
class DangKyNhiepAnhGiaThatTests(TestCase):  # P5 (feedback a, b, c): chạy với form hồ sơ THẬT của Khoa, không patch is_valid/save

    @classmethod
    def tearDownClass(cls):  # chạy một lần sau khi cả class test xong
        super().tearDownClass()  # để Django dọn phần của nó trước
        shutil.rmtree(THU_MUC_ANH, ignore_errors=True)  # xóa thư mục ảnh tạm

    def setUp(self):  # chạy trước mỗi test
        self.url = reverse('register_photographer')  # đường dẫn trang đăng ký Nhiếp ảnh gia
        self.loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')  # 1 loại hình để chọn
        self.cach = PhongCach.objects.create(TenPhongCach='Tự nhiên')  # 1 phong cách để chọn
        self.vuc = KhuVuc.objects.create(TenKhuVuc='TP.HCM')  # 1 khu vực để chọn

    def du_lieu(self, **doi):  # dữ liệu hợp lệ đủ cả tài khoản lẫn hồ sơ; **doi để ghi đè từng ô
        data = {  # phần tài khoản (form của Phanh)
            'ho_ten': 'Nguyễn Văn An', 'email': 'an@example.com',  # họ tên và email
            'so_dien_thoai': '0912345678', 'mat_khau': 'Xk9#mQ2vLp', 'mat_khau_xac_nhan': 'Xk9#mQ2vLp',  # SĐT 10 số; mật khẩu đủ 4 loại ký tự
            # phần hồ sơ (form của Khoa)
            'GioiThieu': 'Xin chào', 'NganHang': NGAN_HANG[0], 'SoTaiKhoan': '0123456789',  # giới thiệu và ngân hàng
            'ChuTaiKhoan': 'NGUYEN VAN AN',  # tên chủ tài khoản
            'loai_hinh': [self.loai.pk], 'phong_cach': [self.cach.pk], 'khu_vuc': [self.vuc.pk],  # 3 ô chọn nhiều
            'AnhDaiDien': tao_anh('avt.png'), 'AnhMaQR': tao_anh('qr.png'),  # 2 ảnh (tạo mới mỗi lần gọi vì file chỉ đọc được một lần)
        }  # hết dữ liệu mẫu
        data.update(doi)  # áp dụng các ô cần đổi
        return data  # trả dữ liệu

    def bo_o(self, *ten_o):  # hàm phụ: dữ liệu hợp lệ nhưng BỎ các ô được nêu tên (giả lập người dùng để trống)
        data = self.du_lieu()  # lấy dữ liệu đầy đủ
        for ten in ten_o:  # với từng ô cần bỏ
            data.pop(ten)  # xóa ô đó khỏi dữ liệu gửi lên
        return data  # trả dữ liệu đã bỏ ô

    def test_dang_ky_thanh_cong_voi_form_that(self):  # (a) luồng chính với form thật
        qtv = User.objects.create_user(  # tạo sẵn 1 Quản trị viên để kiểm tra thông báo
            username='qtv', email='qtv@example.com', password='Xk9#mQ2vLp', so_dien_thoai='0900000099',  # thông tin tối thiểu
        )  # hết tạo Quản trị viên
        qtv.groups.add(Group.objects.get(name=VaiTro.QUAN_TRI_VIEN))  # gán nhóm Quản trị viên (migration đã tạo sẵn nhóm)
        res = self.client.post(self.url, self.du_lieu())  # gửi form đầy đủ
        self.assertRedirects(res, reverse('login'), fetch_redirect_response=False)  # thành công thì chuyển sang trang đăng nhập
        user = User.objects.get(email='an@example.com')  # tài khoản đã được tạo
        self.assertTrue(user.groups.filter(name=VaiTro.NHIEP_ANH_GIA).exists())  # thuộc nhóm Nhiếp ảnh gia
        self.assertEqual(user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)  # trạng thái hồ sơ = Chờ duyệt
        nag = NhiepAnhGia.objects.get(MaTaiKhoan=user)  # có bản ghi NhiepAnhGia gắn với tài khoản
        self.assertEqual(list(nag.loai_hinh_chup.all()), [self.loai])  # đã lưu loại hình chọn
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=nag).count(), 1)  # có đúng 1 lượt duyệt
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=qtv).exists())  # Quản trị viên nhận được thông báo

    def test_thieu_loai_hinh_khong_tao_user(self):  # (b) hồ sơ sai thật thì không được tạo User
        res = self.client.post(self.url, self.bo_o('loai_hinh'))  # gửi form thiếu loại hình
        self.assertEqual(res.status_code, 200)  # ở lại trang đăng ký
        self.assertContains(res, 'Vui lòng chọn ít nhất một loại hình chụp.')  # hiện đúng câu báo lỗi của form Khoa
        self.assertEqual(User.objects.count(), 0)  # không có User nào được tạo
        self.assertEqual(NhiepAnhGia.objects.count(), 0)  # không có hồ sơ nào được tạo

    def test_khong_hien_cau_loi_thieu_tai_khoan(self):  # lỗi chung "Thiếu tài khoản" của form Khoa (do user=None) không được lộ ra người dùng
        res = self.client.post(self.url, self.bo_o('loai_hinh'))  # gửi form thiếu loại hình
        self.assertNotContains(res, 'Thiếu tài khoản')  # câu lỗi vô lý này phải bị ẩn

    def test_hien_loi_ca_hai_form_cung_luc(self):  # feedback P5-3: sai cả tài khoản lẫn hồ sơ thì thấy hết lỗi một lần
        res = self.client.post(self.url, {**self.bo_o('loai_hinh'), 'mat_khau': 'xk9#mq2vlp', 'mat_khau_xac_nhan': 'xk9#mq2vlp'})  # mật khẩu thiếu chữ hoa VÀ thiếu loại hình
        self.assertContains(res, 'Mật khẩu phải có ít nhất một chữ hoa.')  # lỗi của form tài khoản
        self.assertContains(res, 'Vui lòng chọn ít nhất một loại hình chụp.')  # lỗi của form hồ sơ, hiện cùng lúc
        self.assertEqual(User.objects.count(), 0)  # chưa tạo User nào

    def test_email_trung_giua_hai_lan_dang_ky(self):  # (c) email đã dùng ở lần đăng ký trước
        self.client.post(self.url, self.du_lieu())  # đăng ký lần 1 (thành công)
        res = self.client.post(self.url, self.du_lieu(email='AN@Example.com', so_dien_thoai='0900000001'))  # lần 2: cùng email viết hoa, khác SĐT
        self.assertContains(res, 'Email này đã được đăng ký.')  # báo trùng
        self.assertEqual(User.objects.count(), 1)  # vẫn chỉ có 1 User
        self.assertEqual(NhiepAnhGia.objects.count(), 1)  # vẫn chỉ có 1 hồ sơ

    def test_tranh_chap_trung_luc_tao_user_hoan_tac_va_bao_loi(self):  # có người đăng ký trùng đúng lúc view đang tạo User
        with patch('accounts.views.tao_tai_khoan', side_effect=IntegrityError):  # giả lập database báo trùng ở bước tạo User
            res = self.client.post(self.url, self.du_lieu())  # gửi form hợp lệ
        self.assertEqual(res.status_code, 200)  # ở lại trang đăng ký
        self.assertContains(res, 'vừa được đăng ký bởi người khác')  # hiện câu báo trùng
        self.assertEqual(NhiepAnhGia.objects.count(), 0)  # không có hồ sơ nào được tạo

class LoiMatKhauTiengVietTests(TestCase):
    """Thông báo lỗi mật khẩu phải bằng tiếng Việt (không còn câu 'This password is too short…' của Django)."""
    def test_mat_khau_ngan_bao_tieng_viet(self):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            validate_password('Ab1!')
        chu = ' '.join(ctx.exception.messages)
        self.assertIn('Mật khẩu quá ngắn, cần có ít nhất 8 ký tự.', chu)
        self.assertNotIn('This password', chu)


class XacNhanMatKhauTests(TestCase):
    """Form đăng ký (Khách hàng và Nhiếp ảnh gia dùng chung DangKyForm) bắt nhập mật khẩu 2 lần."""
    DU_LIEU = {'ho_ten': 'Nguyễn Văn An', 'email': 'an@example.com', 'so_dien_thoai': '0912345678',
               'mat_khau': 'Xk9#mQ2vLp', 'mat_khau_xac_nhan': 'Xk9#mQ2vLp'}

    def form(self, **doi):
        from accounts.forms import DangKyForm
        return DangKyForm({**self.DU_LIEU, **doi})

    def test_khop_thi_hop_le(self):
        self.assertTrue(self.form().is_valid())

    def test_khong_khop_bi_chan(self):
        f = self.form(mat_khau_xac_nhan='Xk9#mQ2vLq')
        self.assertFalse(f.is_valid())
        self.assertIn('Mật khẩu xác nhận không khớp.', f.errors['mat_khau_xac_nhan'])

    def test_de_trong_bi_chan(self):
        f = self.form(mat_khau_xac_nhan='')
        self.assertFalse(f.is_valid())
        self.assertIn('Vui lòng nhập lại mật khẩu để xác nhận.', f.errors['mat_khau_xac_nhan'])

    def test_hai_trang_dang_ky_deu_co_o_xac_nhan(self):
        for url in ('/dang-ky/', '/dang-ky/nhiep-anh-gia/'):
            self.assertContains(self.client.get(url), 'name="mat_khau_xac_nhan"')

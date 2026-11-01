# =====================================================================
# accounts/test_quan_tri.py  -  B7: kiểm thử trang tổng quan Quản trị
# Chạy:  python manage.py test accounts.test_quan_tri
# =====================================================================
from django.contrib.auth.models import Group  # bảng nhóm quyền (vai trò)
from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn

from accounts.services import tao_tai_khoan  # hàm tạo tài khoản của P4
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và trạng thái hồ sơ


class TongQuanQuanTriTests(TestCase):  # nhóm test của B7
    def setUp(self):  # chạy trước mỗi test
        self.admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0900000001', 'Matkhau!2026', vai_tro=VaiTro.QUAN_TRI_VIEN)  # tài khoản Quản trị viên
        self.khach = tao_tai_khoan('Khách Hàng', 'khach@example.com', '0900000002', 'Matkhau!2026')  # tài khoản Khách hàng (vai trò mặc định)
        self.url = reverse('admin_dashboard')  # đường dẫn trang tổng quan

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):  # người lạ không vào được
        r = self.client.get(self.url)  # mở trang khi chưa đăng nhập
        self.assertEqual(r.status_code, 302)  # bị chuyển trang
        self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_khach_hang_bi_403(self):  # sai vai trò
        self.client.force_login(self.khach)  # đăng nhập bằng Khách hàng
        self.assertEqual(self.client.get(self.url).status_code, 403)  # bị từ chối

    def test_quan_tri_vien_vao_duoc_va_dem_dung(self):  # đúng vai trò và số liệu đúng
        tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0900000003', 'Matkhau!2026',  # tạo 1 Nhiếp ảnh gia
                      vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)  # hồ sơ đang chờ duyệt
        self.client.force_login(self.admin)  # đăng nhập bằng Quản trị viên
        r = self.client.get(self.url)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertEqual(r.context['thong_ke']['ho_so_cho_duyet'], 1)  # đếm đúng 1 hồ sơ chờ duyệt
        self.assertEqual(len(r.context['thong_ke']['booking_theo_trang_thai']), 13)  # luôn đủ 13 trạng thái
        self.assertContains(r, 'Tổng quan')  # có chữ Tổng quan (menu và tiêu đề)

# core/test_trang_loi.py - B10. Chạy: python manage.py test core.test_trang_loi
from django.test import TestCase, override_settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse

from accounts.services import tao_tai_khoan
from core.constants import TrangThaiHoSo, VaiTro


def _req():
    r = RequestFactory().get('/')
    r.user = AnonymousUser()
    return r


class TrangTinhTest(TestCase):
    """Trang Giới thiệu gồm 4 phần (Giới thiệu, Điều khoản sử dụng, Chính sách bảo mật, Câu hỏi thường gặp)."""

    def test_gioi_thieu_mo_duoc_khong_can_dang_nhap(self):
        r = self.client.get(reverse('about'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'không giữ')              # ghi rõ không giữ / xử lý tiền

    def test_gioi_thieu_co_du_4_phan_co_dia_chi_rieng(self):
        r = self.client.get(reverse('about'))
        for ma in ('gioi-thieu', 'dieu-khoan', 'chinh-sach-bao-mat', 'cau-hoi-thuong-gap'):
            self.assertContains(r, f'id="{ma}"')           # phần nội dung
            self.assertContains(r, f'href="#{ma}"')        # mục tương ứng ở thanh mục lục

    def test_dieu_khoan_ghi_muc_dich_thu_thap(self):
        self.assertContains(self.client.get(reverse('about')), 'Mục đích thu thập thông tin khi đăng ký')

    def test_chinh_sach_bao_mat_va_faq_co_noi_dung(self):
        r = self.client.get(reverse('about'))
        self.assertContains(r, 'Ai xem được thông tin của bạn')
        self.assertContains(r, 'Lưu trong bao lâu')
        self.assertContains(r, 'FRAMIE có giữ tiền cọc của tôi không?')

    def test_dia_chi_cu_dieu_khoan_chuyen_sang_trang_gioi_thieu(self):
        r = self.client.get(reverse('terms'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('about') + '#dieu-khoan')

    def test_footer_tro_dung_tung_phan_cua_trang_gioi_thieu(self):
        r = self.client.get('/')
        gioi_thieu = reverse('about')
        self.assertContains(r, f'href="{gioi_thieu}#dieu-khoan"')
        self.assertContains(r, f'href="{gioi_thieu}#chinh-sach-bao-mat"')
        self.assertContains(r, f'href="{gioi_thieu}#cau-hoi-thuong-gap"')
        self.assertContains(r, f'href="{reverse("search")}">Tìm nhiếp ảnh gia')    # trước đây là "#"


class MenuGioiThieuTest(TestCase):
    """Mục "Giới thiệu" phải có ở header của Khách hàng và Nhiếp ảnh gia sau khi đăng nhập."""

    def _nhan_menu(self, user):
        self.client.force_login(user)
        r = self.client.get(reverse('about'))
        self.assertEqual(r.status_code, 200)
        return [nhan for nhan, _ in r.context['nav_items']] if isinstance(r.context['nav_items'][0], tuple) \
            else [m['label'] for m in r.context['nav_items']]

    def test_khach_hang_co_gioi_thieu_o_header(self):
        user = tao_tai_khoan('Khách Hàng', 'kh@example.com', '0911000001', 'Matkhau!2026')
        self.assertIn('Giới thiệu', self._nhan_menu(user))

    def test_nhiep_anh_gia_da_duyet_co_gioi_thieu_o_header(self):
        user = tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0911000002', 'Matkhau!2026',
                             vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        self.assertIn('Giới thiệu', self._nhan_menu(user))

    def test_nhiep_anh_gia_cho_duyet_van_xem_duoc_gioi_thieu(self):
        user = tao_tai_khoan('Nhiếp Ảnh Hai', 'nag2@example.com', '0911000003', 'Matkhau!2026',
                             vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)
        nhan = self._nhan_menu(user)
        self.assertIn('Giới thiệu', nhan)
        self.assertNotIn('Quản lý Booking', nhan)         # vẫn bị giới hạn các chức năng khác

    def test_nhiep_anh_gia_khong_thay_nut_tim_nhiep_anh_gia(self):
        """Nhiếp ảnh gia không được dẫn tới trang Tìm kiếm để đặt lịch: không có link /tim-kiem/ ở footer lẫn nút của trang Giới thiệu."""
        user = tao_tai_khoan('Nhiếp Ảnh Ba', 'nag3@example.com', '0911000004', 'Matkhau!2026',
                             vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        self.client.force_login(user)
        r = self.client.get(reverse('about'))
        self.assertNotContains(r, f'href="{reverse("search")}"')

    def test_khach_hang_va_khach_vang_lai_van_thay_nut_tim_nhiep_anh_gia(self):
        self.assertContains(self.client.get(reverse('about')), f'href="{reverse("search")}"')       # khách vãng lai
        user = tao_tai_khoan('Khách Hai', 'kh2@example.com', '0911000005', 'Matkhau!2026')
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('about')), f'href="{reverse("search")}"')       # Khách hàng


@override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
class TrangLoiTest(TestCase):
    def test_404_tieng_viet_co_nut_ve_trang_chu(self):
        r = self.client.get('/khong-co-trang-nay/')
        self.assertContains(r, 'Không tìm thấy trang', status_code=404)
        self.assertContains(r, 'Về trang chủ', status_code=404)

    def test_403_tieng_viet(self):
        from core.views_trang_loi import loi_403
        r = loi_403(_req())
        self.assertEqual(r.status_code, 403)
        self.assertIn('Về trang chủ', r.content.decode())

    def test_500_tieng_viet(self):
        from core.views_trang_loi import loi_500
        r = loi_500(_req())
        self.assertEqual(r.status_code, 500)
        self.assertIn('Về trang chủ', r.content.decode())

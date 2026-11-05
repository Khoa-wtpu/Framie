# core/test_trang_loi.py - B10. Chạy: python manage.py test core.test_trang_loi
from django.test import TestCase, override_settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse


def _req():
    r = RequestFactory().get('/')
    r.user = AnonymousUser()
    return r


class TrangTinhTest(TestCase):
    def test_gioi_thieu_va_dieu_khoan_mo_duoc_khong_can_dang_nhap(self):
        for ten in ('about', 'terms'):
            r = self.client.get(reverse(ten))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'không giữ')          # ghi rõ không giữ / xử lý tiền

    def test_dieu_khoan_ghi_muc_dich_thu_thap(self):
        self.assertContains(self.client.get(reverse('terms')), 'Mục đích thu thập thông tin khi đăng ký')

    def test_footer_co_link_that(self):
        r = self.client.get('/')
        self.assertContains(r, reverse('about'))
        self.assertContains(r, reverse('terms'))


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

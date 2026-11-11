from django.test import TestCase

# Create your tests here.


class MenuAvatarTongQuanTests(TestCase):
    """Menu avatar của Khách hàng / Nhiếp ảnh gia có mục 'Tổng quan' (lối về trang 'Xin chào')."""
    def test_menu_co_muc_tong_quan(self):
        from django.urls import reverse
        from core.navigation import ACCOUNT_MENUS, CUSTOMER, PHOTOGRAPHER
        for vai_tro in (CUSTOMER, PHOTOGRAPHER):
            self.assertIn(("Tổng quan", "dashboard"), ACCOUNT_MENUS[vai_tro])
        self.assertEqual(reverse('dashboard'), '/tong-quan/')

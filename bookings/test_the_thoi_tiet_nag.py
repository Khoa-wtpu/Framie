# Test thẻ dự báo thời tiết (E8) trên trang xử lý yêu cầu của Nhiếp ảnh gia (/bookings/quan-ly/<id>/) + bộ lọc chọn biểu tượng.
from unittest import mock

from django.urls import reverse

from bookings import test_tiep_nhan as nen
from bookings import the_thoi_tiet as uc
from bookings.templatetags.thoi_tiet_tags import nhom_thoi_tiet
from core.constants import TrangThaiBooking as BK
from profiles.models import KhuVuc, NhiepAnhGia_KhuVuc

TIEU_DE = 'Dự báo thời tiết buổi chụp'
MOCK = 'bookings.the_thoi_tiet.lay_du_bao_thoi_tiet'


class NagTrangXuLyTest(nen.TiepNhanBase):
    def setUp(self):
        super().setUp()
        NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=self.nag, MaKhuVuc=KhuVuc.objects.create(TenKhuVuc='Đà Nẵng'))

    def mo(self, bk):
        self.client.force_login(self.nag.MaTaiKhoan)
        return self.client.get(reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}))

    def test_co_du_bao(self):
        bk = self.tao_booking()
        with mock.patch(MOCK, return_value={'nhiet_do': 29.5, 'xac_suat_mua': 20, 'mo_ta': 'Mưa rào nhẹ'}):
            res = self.mo(bk)
        self.assertContains(res, TIEU_DE)
        self.assertContains(res, '29,5°C')
        self.assertContains(res, '20%')
        self.assertContains(res, 'tt--mua')
        self.assertNotContains(res, uc.TB_NHAC_DOI_LICH)

    def test_mua_cao_co_nut_tro_chuyen(self):
        bk = self.tao_booking()
        with mock.patch(MOCK, return_value={'nhiet_do': 27, 'xac_suat_mua': 80, 'mo_ta': 'Mưa'}):
            res = self.mo(bk)
        self.assertContains(res, uc.TB_NHAC_DOI_LICH)
        self.assertContains(res, reverse('mo_tro_chuyen_booking', kwargs={'ma_booking': bk.pk}))
        self.assertContains(res, 'Trao đổi qua trò chuyện')

    def test_khong_co_du_bao(self):
        bk = self.tao_booking()
        with mock.patch(MOCK, return_value={}):
            res = self.mo(bk)
        self.assertContains(res, 'Chưa có dự báo')


class NhomThoiTietTest(nen.TestCase if hasattr(nen, 'TestCase') else __import__('django.test', fromlist=['SimpleTestCase']).SimpleTestCase):
    def test_nhom(self):
        for mo_ta, nhom in (('Trời quang', 'nang'), ('Ít mây', 'it-may'), ('Có mây', 'it-may'), ('Nhiều mây', 'may'),
                            ('Sương mù', 'suong'), ('Mưa phùn nhẹ', 'phun'), ('Mưa rào nhẹ', 'mua'), ('Mưa', 'mua'),
                            ('Dông kèm mưa đá nhẹ', 'dong'), ('Dông', 'dong'), ('Chưa rõ thời tiết', 'may'), ('', 'may'), (None, 'may')):
            self.assertEqual(nhom_thoi_tiet(mo_ta), nhom, mo_ta)

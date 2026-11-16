# core/test_nap_khu_vuc.py   (task F1)
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from core import du_lieu_khu_vuc as dl34
from core.management.commands import _du_lieu_mau as mau
from profiles.models import KhuVuc


class DanhSach34Test(SimpleTestCase):
    def test_danh_sach_hop_le(self):
        self.assertEqual(dl34.kiem_tra(), [])

    def test_du_34_don_vi_gom_28_tinh_6_thanh_pho(self):
        self.assertEqual(len(dl34.TEN_34), 34)
        loai = [x[2] for x in dl34.DANH_SACH_34]
        self.assertEqual((loai.count('Tỉnh'), loai.count('Thành phố')), (28, 6))

    def test_du_lieu_mau_dung_ten_moi_va_khop_danh_sach(self):
        self.assertEqual(mau.KHU_VUC, ['Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Lâm Đồng', 'Khánh Hòa'])
        for ten in mau.KHU_VUC:
            self.assertIn(ten, dl34.TEN_34)


class NapKhuVucTest(TestCase):
    def chay(self, *args):
        out = StringIO()
        call_command('nap_khu_vuc', *args, stdout=out)
        return out.getvalue()

    def test_nap_du_34(self):
        self.chay()
        self.assertEqual(KhuVuc.objects.count(), 34)
        self.assertEqual(set(KhuVuc.objects.values_list('TenKhuVuc', flat=True)), set(dl34.TEN_34))

    def test_chay_hai_lan_khong_nhan_doi(self):
        self.chay()
        self.chay()
        self.assertEqual(KhuVuc.objects.count(), 34)

    def test_doi_ten_khu_vuc_cu_giu_nguyen_ma(self):
        cu = {t: KhuVuc.objects.create(TenKhuVuc=t) for t in ('TP. Hồ Chí Minh', 'Đà Lạt', 'Nha Trang')}
        self.chay()
        for ten_cu, ten_moi in (('TP. Hồ Chí Minh', 'Hồ Chí Minh'), ('Đà Lạt', 'Lâm Đồng'), ('Nha Trang', 'Khánh Hòa')):
            self.assertEqual(KhuVuc.objects.get(pk=cu[ten_cu].pk).TenKhuVuc, ten_moi)  # cùng khóa chính
            self.assertFalse(KhuVuc.objects.filter(TenKhuVuc=ten_cu).exists())
        self.assertEqual(KhuVuc.objects.count(), 34)

    def test_khong_xoa_khu_vuc_la(self):
        KhuVuc.objects.create(TenKhuVuc='Vùng tự thêm')
        self.chay()
        self.assertTrue(KhuVuc.objects.filter(TenKhuVuc='Vùng tự thêm').exists())
        self.assertEqual(KhuVuc.objects.count(), 35)

    def test_ten_moi_da_co_thi_khong_doi_va_khong_xoa(self):
        KhuVuc.objects.create(TenKhuVuc='Đà Lạt')
        KhuVuc.objects.create(TenKhuVuc='Lâm Đồng')
        self.chay()
        self.assertTrue(KhuVuc.objects.filter(TenKhuVuc='Đà Lạt').exists())
        self.assertEqual(KhuVuc.objects.filter(TenKhuVuc='Lâm Đồng').count(), 1)

    def test_chi_xem_khong_ghi_database(self):
        KhuVuc.objects.create(TenKhuVuc='Đà Lạt')
        kq = self.chay('--chi-xem')
        self.assertIn('CHỈ XEM', kq)
        self.assertEqual(list(KhuVuc.objects.values_list('TenKhuVuc', flat=True)), ['Đà Lạt'])

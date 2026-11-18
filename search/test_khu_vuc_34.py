# search/test_khu_vuc_34.py - F3: giao diện chọn khu vực với 34 tỉnh thành (nhóm theo miền + ô tìm).
# Chạy: python manage.py test search.test_khu_vuc_34
from io import StringIO

from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse

from core.du_lieu_khu_vuc import MIEN, TEN_34, nhom_theo_mien
from profiles.forms import NhiepAnhGiaForm
from search.forms import TimKiemForm
from search.test_tro_ly import TroLyTestCase


class NhomTheoMienTest(SimpleTestCase):
    def test_chia_dung_3_mien_va_du_34(self):
        nhom = nhom_theo_mien(TEN_34)
        self.assertEqual([m for m, _ in nhom], ['Miền Bắc', 'Miền Trung', 'Miền Nam'])
        self.assertEqual([len(ds) for _, ds in nhom], [15, 11, 8])
        self.assertEqual(sorted(t for _, ds in nhom for t in ds), sorted(TEN_34))

    def test_xep_a_z_theo_tieng_viet(self):
        trung = dict(nhom_theo_mien(TEN_34))['Miền Trung']
        self.assertEqual(trung, ['Đắk Lắk', 'Đà Nẵng', 'Gia Lai', 'Hà Tĩnh', 'Huế', 'Khánh Hòa', 'Lâm Đồng',
                                 'Nghệ An', 'Quảng Ngãi', 'Quảng Trị', 'Thanh Hóa'])   # Đ xếp ở vần D, không rơi xuống cuối

    def test_khu_vuc_la_vao_nhom_khac_o_cuoi(self):
        nhom = nhom_theo_mien(['Hà Nội', 'Vùng tự thêm'])
        self.assertEqual([m for m, _ in nhom], ['Miền Bắc', 'Khác'])

    def test_moi_tinh_nam_dung_mot_mien(self):
        tat_ca = [t for _, ds in MIEN for t in ds]
        self.assertEqual(len(tat_ca), len(set(tat_ca)))


class GiaoDien34Test(TroLyTestCase):
    def setUp(self):
        super().setUp()
        call_command('nap_khu_vuc', stdout=StringIO())    # 34 tỉnh (+ 2 khu vực mẫu của test cũ rơi vào nhóm Khác)

    def kiem_tra_giao_dien(self, html):
        for mien in ('Miền Bắc', 'Miền Trung', 'Miền Nam'):
            self.assertIn(mien, html)
        for ten in TEN_34:
            self.assertIn(f'>{ten}</span>', html)         # đủ 34 mục
        self.assertIn('data-loc-o', html)                  # có ô tìm cho JS
        self.assertIn('data-loc-khu-vuc', html)

    def test_cau_2_cua_tro_ly(self):
        self.buoc(1, dap_an=self.cuoi.pk)
        r = self.client.get(f'{self.url}?buoc=2')
        self.assertContains(r, 'Câu 2/5')
        self.assertContains(r, 'Bạn chụp ở khu vực nào?')
        self.assertContains(r, 'tro-ly__chon--tinh')
        self.assertNotContains(r, 'tro-ly__chon--luoi')
        self.kiem_tra_giao_dien(r.content.decode())

    def test_cau_2_van_chon_duoc_mot_tinh(self):
        from profiles.models import KhuVuc
        lam_dong = KhuVuc.objects.get(TenKhuVuc='Lâm Đồng')
        self.buoc(1, dap_an=self.cuoi.pk)
        r = self.buoc(2, dap_an=lam_dong.pk)
        self.assertRedirects(r, f'{self.url}?buoc=3')

    def test_cau_2_khong_chon_bi_bao_loi(self):
        self.buoc(1, dap_an=self.cuoi.pk)
        r = self.buoc(2)
        self.assertContains(r, 'Vui lòng chọn một khu vực.')

    def test_trang_tim_kiem_loc_theo_tinh(self):
        r = self.client.get(reverse('search'))
        self.kiem_tra_giao_dien(r.content.decode())
        self.assertContains(r, 'tim__muc')

    def test_bo_loc_tim_kiem_van_nhan_nhieu_tinh(self):
        from profiles.models import KhuVuc
        ids = list(KhuVuc.objects.filter(TenKhuVuc__in=['Lâm Đồng', 'Khánh Hòa']).values_list('pk', flat=True))
        form = TimKiemForm({'khu_vuc': ids})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['khu_vuc']), 2)

    def test_form_ho_so_nhiep_anh_gia(self):
        html = render_to_string('profiles/includes/_ho_so_chi_tiet.html', {'form': NhiepAnhGiaForm()})
        self.kiem_tra_giao_dien(html)
        self.assertIn('ho-so__muc', html)

    def test_trang_chu_chia_optgroup(self):
        r = self.client.get(reverse('home'))
        self.assertContains(r, '<optgroup label="Miền Trung">')
        self.assertContains(r, '>Lâm Đồng</option>')

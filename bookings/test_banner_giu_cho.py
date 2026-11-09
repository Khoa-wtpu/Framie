"""Test banner giữ chỗ dùng chung (bookings/context_processors.py + includes/banner_giu_cho.html).
Chạy: python manage.py test bookings.test_banner_giu_cho"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import THOI_GIAN_GIU_CHO, GiuCho
from core.constants import TrangThaiGiuCho as GC, TrangThaiHoSo, TrangThaiSlot as SL, VaiTro
from profiles.models import NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()
ID_BANNER = 'id="banner-giu-cho"'


def tao_user(ten, nhom=None, **kw):
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 so_dien_thoai=f'09{abs(hash(ten)) % 10**8:08d}', **kw)
    if nhom:
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    return u


class BannerGiuChoTests(TestCase):
    def setUp(self):
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        self.b = tao_user('khach_b', VaiTro.KHACH_HANG)
        self.nag_user = tao_user('nag', VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=self.nag_user, AnhDaiDien='a.jpg', GioiThieu='g',
                                              NganHang='b', SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')
        ngay = timezone.localdate() + timedelta(days=2)
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='09:00', GioKetThuc='10:00')
        self.trang = reverse('search')          # một trang bất kỳ dùng base.html

    def giu(self, user, slot):
        self.client.force_login(user)
        self.client.post(reverse('chon_slot', args=[slot.pk]), {'ma_nhiep_anh_gia': self.nag.pk})

    def het_gio(self):
        GiuCho.objects.update(ThoiDiemGiu=timezone.now() - THOI_GIAN_GIU_CHO - timedelta(minutes=1),
                              ThoiDiemHetHan=timezone.now() - timedelta(minutes=1))

    def test_hien_banner_va_nut_tiep_tuc_o_trang_khac(self):
        self.giu(self.a, self.s1)
        r = self.client.get(self.trang)
        g = GiuCho.objects.get()
        self.assertContains(r, ID_BANNER)
        self.assertContains(r, reverse('gui_booking', args=[g.pk]))
        self.assertContains(r, 'Tiếp tục đặt lịch')
        self.assertContains(r, '09:00–10:00')

    def test_chi_hien_cho_dung_khach_dang_giu(self):
        self.giu(self.a, self.s1)
        self.client.force_login(self.b)
        self.assertNotContains(self.client.get(self.trang), ID_BANNER)

    def test_het_han_thi_khong_hien(self):
        self.giu(self.a, self.s1)
        self.het_gio()
        self.assertNotContains(self.client.get(self.trang), ID_BANNER)

    def test_chua_dang_nhap_va_nhiep_anh_gia_khong_loi_khong_hien(self):
        self.giu(self.a, self.s1)
        self.client.logout()
        self.assertNotContains(self.client.get(self.trang), ID_BANNER)
        self.client.force_login(self.nag_user)
        r = self.client.get(self.trang)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, ID_BANNER)

    def test_luot_da_hoan_tat_khong_hien(self):
        self.giu(self.a, self.s1)
        GiuCho.objects.update(TrangThai=GC.DA_HOAN_TAT)
        self.assertNotContains(self.client.get(self.trang), ID_BANNER)

    def test_khong_hien_o_trang_da_co_dem_nguoc_rieng(self):
        self.giu(self.a, self.s1)
        g = GiuCho.objects.get()
        for ten, tham_so in (('man_hinh_giu_cho', [g.pk]), ('gui_booking', [g.pk]), ('lich_chon_slot', [self.nag.pk])):
            r = self.client.get(reverse(ten, args=tham_so))
            self.assertNotContains(r, ID_BANNER, msg_prefix=ten)

    def test_slot_van_dang_giu(self):             # banner chỉ đọc, không đổi gì
        self.giu(self.a, self.s1)
        self.client.get(self.trang)
        self.assertEqual(LichKhaDung.objects.get(pk=self.s1.pk).TrangThai, SL.DANG_GIU)

    def test_o_dem_nguoc_co_tong_giay_de_ve_thanh_tien_do(self):
        self.giu(self.a, self.s1)
        r = self.client.get(self.trang)
        tong = int(THOI_GIAN_GIU_CHO.total_seconds())
        self.assertContains(r, f'data-tong="{tong}"')
        self.assertContains(r, 'class="gc-timer"')
        self.assertContains(r, 'data-gc-phut')
        self.assertContains(r, 'data-gc-giay')
        self.assertGreaterEqual(r.context['giu_cho_banner']['tong_giay'], r.context['giu_cho_banner']['con_lai_giay'])

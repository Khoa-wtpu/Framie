"""Test UC4.1/4.2 luồng 6b: rời luồng đặt lịch thì nhả giữ chỗ ngay, không còn ô đếm ngược ở trang khác.
Chạy: python manage.py test bookings.test_roi_luong_giu_cho"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import GiuCho
from core.constants import TrangThaiGiuCho as GC, TrangThaiHoSo, TrangThaiSlot as SL, VaiTro
from profiles.models import NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()
HTML = {'HTTP_ACCEPT': 'text/html,application/xhtml+xml'}   # giống trình duyệt đang mở trang


def tao_user(ten, nhom=None, **kw):
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 so_dien_thoai=f'09{abs(hash(ten)) % 10**8:08d}', **kw)
    if nhom:
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    return u


class RoiLuongGiuChoTests(TestCase):
    def setUp(self):
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        nag_user = tao_user('nag', VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=nag_user, AnhDaiDien='a.jpg', GioiThieu='g',
                                              NganHang='b', SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')
        ngay = timezone.localdate() + timedelta(days=2)
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='09:00', GioKetThuc='10:00')
        self.client.force_login(self.a)
        self.client.post(reverse('chon_slot', args=[self.s1.pk]), {'ma_nhiep_anh_gia': self.nag.pk})
        self.giu = GiuCho.objects.get()

    def slot(self):
        self.s1.refresh_from_db()
        return self.s1.TrangThai

    def test_mo_trang_khac_thi_nha_giu_cho(self):
        for ten in ('search', 'home'):
            GiuCho.objects.filter(pk=self.giu.pk).update(TrangThai=GC.DANG_GIU)
            LichKhaDung.objects.filter(pk=self.s1.pk).update(TrangThai=SL.DANG_GIU)
            self.client.get(reverse(ten), **HTML)
            self.giu.refresh_from_db()
            self.assertEqual(self.giu.TrangThai, GC.HET_HAN, ten)
            self.assertEqual(self.slot(), SL.TRONG, ten)

    def test_trang_nao_cung_khong_con_o_dem_nguoc_giu_cho(self):
        r = self.client.get(reverse('search'), **HTML)
        self.assertNotContains(r, 'banner-giu-cho')

    def test_o_trong_luong_dat_lich_thi_khong_nha(self):
        for ten in ('man_hinh_giu_cho', 'gui_booking', 'lich_chon_slot'):
            args = [self.nag.pk] if ten == 'lich_chon_slot' else [self.giu.pk]
            self.client.get(reverse(ten, args=args), **HTML)
            self.giu.refresh_from_db()
            self.assertEqual(self.giu.TrangThai, GC.DANG_GIU, ten)

    def test_request_nen_khong_phai_mo_trang_thi_khong_nha(self):   # fetch() mặc định Accept */*
        self.client.get(reverse('search'), HTTP_ACCEPT='*/*', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.giu.refresh_from_db()
        self.assertEqual(self.giu.TrangThai, GC.DANG_GIU)

    def test_luot_da_gui_booking_khong_bi_nha(self):
        GiuCho.objects.filter(pk=self.giu.pk).update(TrangThai=GC.DA_HOAN_TAT)
        self.client.get(reverse('search'), **HTML)
        self.giu.refresh_from_db()
        self.assertEqual(self.giu.TrangThai, GC.DA_HOAN_TAT)
        self.assertEqual(self.slot(), SL.DANG_GIU)
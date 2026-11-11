# bookings/test_huy_giu_cho.py - Khách bấm "Chọn khung giờ khác" thì slot nhả ngay; rời trang thì giữ nguyên, đồng hồ đếm ngược vẫn hiện ở trang lịch.
# Chạy: python manage.py test bookings.test_huy_giu_cho
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


def tao_user(ten, nhom=None, **kw):
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 so_dien_thoai=f'09{abs(hash(ten)) % 10**8:08d}', **kw)
    if nhom:
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    return u


class HuyGiuChoTests(TestCase):
    def setUp(self):
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        self.b = tao_user('khach_b', VaiTro.KHACH_HANG)
        nag_user = tao_user('nag', VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=nag_user, AnhDaiDien='a.jpg', GioiThieu='g',
                                              NganHang='b', SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')
        ngay = timezone.localdate() + timedelta(days=2)
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='09:00', GioKetThuc='10:00')
        self.client.force_login(self.a)
        self.client.post(reverse('chon_slot', args=[self.s1.pk]), {'ma_nhiep_anh_gia': self.nag.pk})
        self.giu = GiuCho.objects.get(MaKhachHang=self.a)
        self.url_huy = reverse('huy_giu_cho', args=[self.giu.pk])

    def slot(self):
        return LichKhaDung.objects.get(pk=self.s1.pk).TrangThai

    def test_dang_giu_truoc_khi_huy(self):                         # đối chứng
        self.assertEqual(self.slot(), SL.DANG_GIU)
        self.assertEqual(self.giu.TrangThai, GC.DANG_GIU)

    def test_bam_chon_khung_gio_khac_nha_slot_va_ve_trang_lich(self):
        r = self.client.post(self.url_huy)
        self.assertRedirects(r, reverse('lich_chon_slot', args=[self.nag.pk]), fetch_redirect_response=False)
        self.giu.refresh_from_db()
        self.assertEqual(self.giu.TrangThai, GC.HET_HAN)
        self.assertEqual(self.slot(), SL.TRONG)

    def test_roi_trang_beacon_nha_slot_tra_204(self):
        r = self.client.post(self.url_huy, {'nhanh': '1'})
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.slot(), SL.TRONG)

    def test_goi_hai_lan_van_an_toan(self):
        self.client.post(self.url_huy, {'nhanh': '1'})
        self.assertEqual(self.client.post(self.url_huy, {'nhanh': '1'}).status_code, 204)
        self.assertEqual(self.slot(), SL.TRONG)

    def test_khach_khac_khong_huy_duoc_luot_cua_nguoi_khac(self):
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(self.url_huy).status_code, 404)
        self.assertEqual(self.slot(), SL.DANG_GIU)

    def test_phai_dung_post(self):
        self.assertEqual(self.client.get(self.url_huy).status_code, 405)
        self.assertEqual(self.slot(), SL.DANG_GIU)

    def test_luot_da_hoan_tat_booking_khong_bi_nha(self):          # đã gửi Booking: slot phải giữ nguyên
        GiuCho.objects.filter(pk=self.giu.pk).update(TrangThai=GC.DA_HOAN_TAT)
        self.client.post(self.url_huy, {'nhanh': '1'})
        self.giu.refresh_from_db()
        self.assertEqual(self.giu.TrangThai, GC.DA_HOAN_TAT)
        self.assertEqual(self.slot(), SL.DANG_GIU)

    def test_sau_khi_huy_khach_khac_chon_duoc_slot(self):
        self.client.post(self.url_huy, {'nhanh': '1'})
        self.client.force_login(self.b)
        self.client.post(reverse('chon_slot', args=[self.s1.pk]), {'ma_nhiep_anh_gia': self.nag.pk})
        self.assertTrue(GiuCho.objects.filter(MaKhachHang=self.b, TrangThai=GC.DANG_GIU).exists())

    def test_trang_giu_cho_va_gui_booking_co_form_huy_nhung_khong_tu_nha_khi_roi_trang(self):
        for ten in ('man_hinh_giu_cho', 'gui_booking'):
            html = self.client.get(reverse(ten, args=[self.giu.pk])).content.decode()
            self.assertIn(self.url_huy, html, ten)                   # vẫn có nút "Chọn khung giờ khác"
            self.assertNotIn('nha_giu_cho.js', html, ten)            # rời trang không còn tự nhả slot

    def test_roi_sang_trang_lich_van_con_dem_nguoc_va_slot_van_giu(self):
        html = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk])).content.decode()
        self.assertIn('id="dem-nguoc"', html)
        self.assertIn('dem_nguoc.js', html)
        self.assertIn(reverse('trang_thai_giu_cho', args=[self.giu.pk]), html)
        self.assertEqual(self.slot(), SL.DANG_GIU)
        self.giu.refresh_from_db()
        self.assertEqual(self.giu.TrangThai, GC.DANG_GIU)

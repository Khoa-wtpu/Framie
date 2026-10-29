from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings import giu_cho as uc
from bookings.models import GiuCho, THOI_GIAN_GIU_CHO
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


class UC41(TestCase):
    def setUp(self):
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        self.b = tao_user('khach_b', VaiTro.KHACH_HANG)
        self.nag_user = tao_user('nag', VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=self.nag_user, AnhDaiDien='a.jpg', GioiThieu='g',
                                              NganHang='b', SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')
        ngay = timezone.localdate() + timedelta(days=2)
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='09:00', GioKetThuc='10:00')
        self.s2 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='10:00', GioKetThuc='11:00')
        self.qua_khu = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=timezone.localdate() - timedelta(days=1),
                                                  GioBatDau='09:00', GioKetThuc='10:00')

    def trang_thai(self, slot):
        return LichKhaDung.objects.get(pk=slot.pk).TrangThai

    def chon(self, user, slot):
        self.client.force_login(user)
        return self.client.post(reverse('chon_slot', args=[slot.pk]),
                                {'ma_nhiep_anh_gia': self.nag.pk}, follow=True)

    # ---- Basic flow ----
    def test_luong_chinh(self):
        r = self.chon(self.a, self.s1)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)
        g = GiuCho.objects.get()
        self.assertEqual((g.MaKhachHang, g.MaLich, g.TrangThai), (self.a, self.s1, GC.DANG_GIU))
        self.assertEqual(g.ThoiDiemHetHan - g.ThoiDiemGiu, THOI_GIAN_GIU_CHO)
        self.assertEqual(r.redirect_chain[-1][0], reverse('man_hinh_giu_cho', args=[g.pk]))
        self.assertTrue(290 <= r.context['con_lai_giay'] <= 300)
        self.assertContains(r, 'id="dem-nguoc"')

    def test_trang_lich_chi_hien_slot_trong(self):
        self.chon(self.a, self.s1)
        self.client.force_login(self.b)
        r = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk]))
        ds = [s.pk for _, slots in r.context['lich_theo_ngay'] for s in slots]
        self.assertEqual(ds, [self.s2.pk])          # s1 đang giữ, slot quá khứ không hiện

    def test_banner_dang_giu_tren_trang_lich(self):
        self.chon(self.a, self.s1)
        r = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk]))
        self.assertContains(r, 'Bạn đang giữ chỗ một khung giờ')

    # ---- BR4.1-2 / 4a ----
    def test_nguoi_khac_khong_chon_duoc_slot_dang_giu(self):
        self.chon(self.a, self.s1)
        r = self.chon(self.b, self.s1)
        self.assertContains(r, 'Slot không còn khả dụng')
        self.assertEqual(GiuCho.objects.count(), 1)
        self.assertEqual(GiuCho.objects.get().MaKhachHang, self.a)
        self.assertEqual(r.redirect_chain[-1][0], reverse('lich_chon_slot', args=[self.nag.pk]))

    def test_slot_da_qua_gio_khong_chon_duoc(self):
        r = self.chon(self.a, self.qua_khu)
        self.assertContains(r, 'Slot không còn khả dụng')
        self.assertEqual(GiuCho.objects.count(), 0)
        self.assertEqual(self.trang_thai(self.qua_khu), SL.TRONG)

    def test_slot_khong_ton_tai(self):
        self.client.force_login(self.a)
        r = self.client.post(reverse('chon_slot', args=[9999]), {'ma_nhiep_anh_gia': self.nag.pk}, follow=True)
        self.assertContains(r, 'Slot không còn khả dụng')

    def test_rang_buoc_unique_chan_khi_du_lieu_lech(self):
        # Giả lập dữ liệu lệch: có lượt đang giữ nhưng slot vẫn "Lịch trống" -> vẫn không tạo lượt thứ hai, slot rollback.
        now = timezone.now()
        GiuCho.objects.create(MaKhachHang=self.a, MaLich=self.s1, ThoiDiemGiu=now,
                              ThoiDiemHetHan=now + THOI_GIAN_GIU_CHO)
        r = self.chon(self.b, self.s1)
        self.assertContains(r, 'Slot không còn khả dụng')
        self.assertEqual(GiuCho.objects.count(), 1)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    # ---- 3a: chọn slot khác ----
    def test_chon_slot_khac_ghi_nhan_slot_moi(self):
        self.chon(self.a, self.s1)
        self.chon(self.a, self.s2)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        self.assertEqual(self.trang_thai(self.s2), SL.DANG_GIU)
        cu = GiuCho.objects.get(MaLich=self.s1)
        moi = GiuCho.objects.get(MaLich=self.s2)
        self.assertEqual((cu.TrangThai, moi.TrangThai), (GC.HET_HAN, GC.DANG_GIU))
        # slot cũ chọn lại được bởi người khác
        self.chon(self.b, self.s1)
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)

    def test_chon_lai_dung_slot_khong_gia_han(self):
        self.chon(self.a, self.s1)
        g = GiuCho.objects.get()
        het = g.ThoiDiemHetHan
        self.chon(self.a, self.s1)
        self.assertEqual(GiuCho.objects.count(), 1)
        self.assertEqual(GiuCho.objects.get().ThoiDiemHetHan, het)

    def test_chon_slot_khac_that_bai_thi_giu_nguyen_slot_cu(self):
        self.chon(self.a, self.s1)
        self.chon(self.b, self.s2)                 # b đang giữ s2
        r = self.chon(self.a, self.s2)             # a muốn đổi sang s2 nhưng đã có người giữ
        self.assertContains(r, 'Slot không còn khả dụng')
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)          # slot cũ của a còn nguyên
        self.assertEqual(GiuCho.objects.get(MaLich=self.s1).TrangThai, GC.DANG_GIU)

    def test_loi_o_buoc_giu_slot_moi_thi_rollback_nha_slot_cu(self):
        self.chon(self.a, self.s1)
        that = uc.doi_trang_thai_khung_gio

        def gia(lich, moi):                         # chỉ hỏng ở bước giữ slot mới; nhả slot cũ vẫn chạy thật
            if moi == SL.DANG_GIU:
                raise uc.ValidationError('x')
            return that(lich, moi)
        with mock.patch.object(uc, 'doi_trang_thai_khung_gio', side_effect=gia):
            r = self.chon(self.a, self.s2)
        self.assertContains(r, 'Slot không còn khả dụng')
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)                 # slot cũ vẫn được giữ
        self.assertEqual(GiuCho.objects.get(MaLich=self.s1).TrangThai, GC.DANG_GIU)
        self.assertEqual(self.trang_thai(self.s2), SL.TRONG)

    def test_khong_nha_duoc_slot_cu(self):
        self.chon(self.a, self.s1)
        with mock.patch.object(uc, 'doi_trang_thai_khung_gio', side_effect=uc.ValidationError('x')):
            r = self.chon(self.a, self.s2)
        self.assertContains(r, 'Không thể thực hiện yêu cầu')
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)
        self.assertEqual(GiuCho.objects.get(MaLich=self.s1).TrangThai, GC.DANG_GIU)

    # ---- 5b: hết 5 phút ----
    def het_gio(self, g, phut=1):
        GiuCho.objects.filter(pk=g.pk).update(ThoiDiemGiu=timezone.now() - THOI_GIAN_GIU_CHO - timedelta(minutes=phut),
                                              ThoiDiemHetHan=timezone.now() - timedelta(minutes=phut))

    def test_het_5_phut_nha_slot_va_giu_cho_het_han(self):
        self.chon(self.a, self.s1)
        g = GiuCho.objects.get()
        self.het_gio(g)
        r = self.client.get(reverse('man_hinh_giu_cho', args=[g.pk]))
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)
        self.assertContains(r, 'Thời gian giữ chỗ đã hết hạn')
        self.assertEqual(r.context['con_lai_giay'], 0)
        self.assertFalse(r.context['dang_giu'])

    def test_api_trang_thai_con_han_va_het_han(self):
        self.chon(self.a, self.s1)
        g = GiuCho.objects.get()
        j = self.client.get(reverse('trang_thai_giu_cho', args=[g.pk])).json()
        self.assertFalse(j['het_han'])
        self.assertTrue(290 <= j['con_lai_giay'] <= 300)
        self.het_gio(g)
        j = self.client.get(reverse('trang_thai_giu_cho', args=[g.pk])).json()
        self.assertTrue(j['het_han'])
        self.assertEqual(j['con_lai_giay'], 0)
        self.assertEqual(j['trang_thai'], GC.HET_HAN)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    def test_nguoi_khac_chon_duoc_sau_khi_het_han(self):
        self.chon(self.a, self.s1)
        self.het_gio(GiuCho.objects.get())
        self.chon(self.b, self.s1)                 # không ai mở trang đếm ngược: giu_cho_slot tự dọn trước
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)
        self.assertEqual(GiuCho.objects.filter(MaKhachHang=self.b, TrangThai=GC.DANG_GIU).count(), 1)
        self.assertEqual(GiuCho.objects.get(MaKhachHang=self.a).TrangThai, GC.HET_HAN)

    def test_quet_khong_dung_luot_chua_het_han_hoac_da_hoan_tat(self):
        self.chon(self.a, self.s1)
        self.chon(self.b, self.s2)
        gb = GiuCho.objects.get(MaKhachHang=self.b)
        uc.hoan_tat_giu_cho(self.b, gb.pk)
        self.het_gio(GiuCho.objects.get(MaKhachHang=self.a))
        self.het_gio(gb)                           # đã hoàn tất => không bị nhả dù quá giờ
        self.assertEqual(uc.giai_phong_giu_cho_het_han(), 1)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        self.assertEqual(self.trang_thai(self.s2), SL.DANG_GIU)
        self.assertEqual(GiuCho.objects.get(pk=gb.pk).TrangThai, GC.DA_HOAN_TAT)
        self.assertEqual(uc.giai_phong_giu_cho_het_han(), 0)       # chạy lại không đổi gì

    # ---- hoan_tat_giu_cho (cho UC4.2) ----
    def test_hoan_tat_kip_han(self):
        self.chon(self.a, self.s1)
        g = uc.hoan_tat_giu_cho(self.a, GiuCho.objects.get().pk)
        self.assertEqual(g.TrangThai, GC.DA_HOAN_TAT)
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)

    def test_hoan_tat_qua_han(self):
        self.chon(self.a, self.s1)
        g = GiuCho.objects.get()
        self.het_gio(g)
        with self.assertRaises(uc.GiuChoLoi):
            uc.hoan_tat_giu_cho(self.a, g.pk)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)

    # ---- 4b ----
    def test_loi_he_thong(self):
        self.client.force_login(self.a)
        with mock.patch.object(uc, 'giai_phong_giu_cho_het_han', side_effect=OperationalError('db')):
            r = self.client.post(reverse('chon_slot', args=[self.s1.pk]), {'ma_nhiep_anh_gia': self.nag.pk})
        self.assertRedirects(r, reverse('lich_chon_slot', args=[self.nag.pk]), fetch_redirect_response=False)
        r = self.client.get(r['Location'])
        self.assertContains(r, 'Không thể thực hiện yêu cầu, vui lòng thử lại sau.')
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        self.assertEqual(GiuCho.objects.count(), 0)

    # ---- Quyền ----
    def test_chua_dang_nhap(self):
        r = self.client.post(reverse('chon_slot', args=[self.s1.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('next=', r['Location'])
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    def test_khong_phai_khach_hang(self):
        self.client.force_login(self.nag_user)
        r = self.client.post(reverse('chon_slot', args=[self.s1.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    def test_khong_xem_duoc_luot_cua_nguoi_khac(self):
        self.chon(self.a, self.s1)
        g = GiuCho.objects.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse('man_hinh_giu_cho', args=[g.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('trang_thai_giu_cho', args=[g.pk])).status_code, 404)

    def test_chon_slot_chi_nhan_post(self):
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse('chon_slot', args=[self.s1.pk])).status_code, 405)

    def test_nag_chua_duyet_khong_cong_khai(self):
        User.objects.filter(pk=self.nag_user.pk).update(trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse('lich_chon_slot', args=[self.nag.pk])).status_code, 404)

    def test_trang_lich_rong(self):
        LichKhaDung.objects.all().delete()
        self.client.force_login(self.a)
        r = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk]))
        self.assertContains(r, 'chưa có khung giờ trống')

# =====================================================================
# bookings/test_da_chup.py - Test cho bookings/da_chup.py (T8: Nhiếp ảnh gia bấm "Đã chụp")
# Chạy:  python manage.py test bookings.test_da_chup
# =====================================================================
from datetime import timedelta
from django.utils.html import escape

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from bookings import da_chup as uc
from bookings import test_tiep_nhan as nen
from bookings.models import LichSuTrangThaiBooking
from core.constants import BenThucHien, LoaiHauKy, TrangThaiBooking as BK
from profiles.models import GoiDichVu


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DaChupTest(nen.TiepNhanBase):
    def setUp(self):
        super().setUp()                                                      # đã đăng nhập bằng Nhiếp ảnh gia 'nag'; self.goi = Hậu kỳ toàn bộ
        self.goi_gioi_han = GoiDichVu.objects.create(
            MaNhiepAnhGia=self.nag, MaLoaiHinh=self.loai, TenGoi='Gói giới hạn', Gia=1000000,
            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.GIOI_HAN, SoLuongAnhToiDa=20) if _co_cot_so_luong() else \
            GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.loai, TenGoi='Gói giới hạn',
                                     Gia=1000000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.GIOI_HAN)

    def booking_chot(self, goi=None, da_qua_gio=True, **kw):
        """Booking 'Chốt Booking'; mặc định buổi chụp đã diễn ra (1 giờ trước, Booking tạo từ 2 ngày trước)."""
        bay_gio = timezone.now()
        gio_chup = bay_gio - timedelta(hours=1) if da_qua_gio else bay_gio + timedelta(days=2)
        return self.tao_booking(goi=goi, trang_thai=BK.CHOT_BOOKING, NgayGioChup=gio_chup,
                                NgayTao=bay_gio - timedelta(days=2), **kw)

    def bam(self, bk, **kw):
        return self.client.post(reverse('da_chup_booking', kwargs={'ma_booking': bk.pk}), **kw)

    def test_goi_gioi_han_dung_o_da_chup_cho_tai_anh(self):
        bk = self.booking_chot(goi=self.goi_gioi_han)
        res = self.bam(bk)
        self.assertRedirects(res, reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}))
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_CHUP)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk, TrangThaiMoi=BK.DA_CHUP).count(), 1)

    def test_goi_hau_ky_toan_bo_di_thang_sang_cho_hau_ky(self):
        bk = self.booking_chot(goi=self.goi)
        self.bam(bk)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_HAU_KY)
        cac_buoc = list(LichSuTrangThaiBooking.objects.filter(MaBooking=bk).values_list('TrangThaiCu', 'TrangThaiMoi', 'BenThucHien'))
        self.assertEqual(cac_buoc, [(BK.CHOT_BOOKING, BK.DA_CHUP, BenThucHien.NHIEP_ANH_GIA),
                                    (BK.DA_CHUP, BK.CHO_HAU_KY, BenThucHien.NHIEP_ANH_GIA)])

    def test_buoi_chup_chua_dien_ra_khong_bam_duoc(self):
        bk = self.booking_chot(da_qua_gio=False)
        res = self.bam(bk, follow=True)
        self.assertContains(res, escape(uc.TB_CHUA_DEN_GIO_CHUP))   # dấu " trong câu được HTML đổi thành &quot;
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHOT_BOOKING)

    def test_chi_bam_duoc_khi_dang_chot_booking(self):
        for tt in (BK.CHO_XAC_NHAN, BK.CHO_DAT_COC, BK.DA_CHUP, BK.HOAN_THANH, BK.DA_HUY):
            bk = self.tao_booking(trang_thai=tt, gio=f'{BK.ALL.index(tt):02d}:00',
                                  NgayGioChup=timezone.now() - timedelta(hours=1), NgayTao=timezone.now() - timedelta(days=2))
            self.bam(bk)
            bk.refresh_from_db()
            self.assertEqual(bk.TrangThai, tt)

    def test_bam_hai_lan_khong_ghi_lich_su_hai_lan(self):
        bk = self.booking_chot(goi=self.goi_gioi_han)
        self.bam(bk)
        self.bam(bk)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk, TrangThaiMoi=BK.DA_CHUP).count(), 1)

    def test_booking_cua_nag_khac_tra_404_va_khong_doi(self):
        bk = self.booking_chot(nag=self.nag_khac)
        self.assertEqual(self.bam(bk).status_code, 404)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHOT_BOOKING)

    def test_khach_hang_khong_bam_duoc(self):
        bk = self.booking_chot()
        self.client.force_login(self.khach)
        self.assertEqual(self.bam(bk).status_code, 403)

    def test_chi_nhan_post(self):
        bk = self.booking_chot()
        res = self.client.get(reverse('da_chup_booking', kwargs={'ma_booking': bk.pk}))
        self.assertEqual(res.status_code, 405)

    def test_trang_chi_tiet_hien_nut_da_chup_dung_luc(self):
        sau = self.booking_chot()
        truoc = self.booking_chot(da_qua_gio=False, gio='15:00')
        url_nut = lambda b: reverse('da_chup_booking', kwargs={'ma_booking': b.pk})
        self.assertContains(self.client.get(reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': sau.pk})), url_nut(sau))
        self.assertNotContains(self.client.get(reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': truoc.pk})), url_nut(truoc))


def _co_cot_so_luong():
    """Gói giới hạn có thể bắt buộc cột số lượng ảnh (tùy models của Khoa); kiểm tra để test không phụ thuộc phiên bản."""
    return any(f.name == 'SoLuongAnhToiDa' for f in GoiDichVu._meta.get_fields())

# =====================================================================
# bookings/test_da_chup.py - Test cho bookings/da_chup.py (T8: Nhiếp ảnh gia bấm "Đã chụp")
# Chạy:  python manage.py test bookings.test_da_chup
# =====================================================================
from datetime import timedelta
from django.utils.html import escape

from contextlib import contextmanager
from unittest.mock import patch

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
        """Booking 'Chốt Booking' có slot 09:00-11:00.
        da_qua_gio=True : slot của hôm qua (đã kết thúc từ lâu). False : slot 2 ngày nữa (chưa tới)."""
        bay_gio = timezone.now()
        ngay = timezone.localdate() + timedelta(days=-1 if da_qua_gio else 2)
        return self.tao_booking(goi=goi, trang_thai=BK.CHOT_BOOKING, gio='09:00', ngay=ngay,
                                NgayTao=bay_gio - timedelta(days=3), **kw)

    @contextmanager
    def vao_luc(self, bk, gio, phut=0):
        """Giả lập 'bây giờ' là hh:mm của NGÀY slot của Booking (để thử trước / trong / sau khung giờ).
        Phiên đăng nhập chỉ sống 30 phút nên phải đăng nhập lại NGAY trong lúc giả lập giờ."""
        gia_lap = timezone.make_aware(timezone.datetime.combine(
            bk.MaLich.Ngay, timezone.datetime.min.time().replace(hour=gio, minute=phut)))
        with patch('django.utils.timezone.now', return_value=gia_lap):
            self.client.force_login(self.nag.MaTaiKhoan)
            yield

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

    def test_dang_trong_khung_gio_chup_chua_bam_duoc(self):                   # Cách B: slot 09:00-11:00
        bk = self.booking_chot(da_qua_gio=False)
        for gio, phut in ((8, 0), (9, 0), (10, 59)):                          # trước giờ, đúng giờ bắt đầu, sát giờ kết thúc
            with self.vao_luc(bk, gio, phut):
                res = self.bam(bk, follow=True)
            self.assertContains(res, escape(uc.TB_CHUA_DEN_GIO_CHUP))
            bk.refresh_from_db()
            self.assertEqual(bk.TrangThai, BK.CHOT_BOOKING, f'{gio}:{phut:02d} chưa được bấm')

    def test_dung_gio_ket_thuc_slot_bam_duoc(self):
        bk = self.booking_chot(da_qua_gio=False, goi=self.goi_gioi_han)
        with self.vao_luc(bk, 11, 0):
            self.bam(bk)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_CHUP)

    def test_chi_bam_duoc_khi_dang_chot_booking(self):
        for tt in (BK.CHO_XAC_NHAN, BK.CHO_DAT_COC, BK.DA_CHUP, BK.HOAN_THANH, BK.DA_HUY):
            bk = self.tao_booking(trang_thai=tt, gio=f'{BK.ALL.index(tt):02d}:00', ngay=timezone.localdate() - timedelta(days=1),
                                  NgayTao=timezone.now() - timedelta(days=3))
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
        bk = self.booking_chot(da_qua_gio=False)
        url_nut = reverse('da_chup_booking', kwargs={'ma_booking': bk.pk})
        url_ct = reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk})
        with self.vao_luc(bk, 10, 0):                                         # đang trong khung giờ: ẩn nút
            self.assertNotContains(self.client.get(url_ct), url_nut)
        with self.vao_luc(bk, 11, 0):                                         # hết khung giờ: hiện nút
            self.assertContains(self.client.get(url_ct), url_nut)

def _co_cot_so_luong():
    """Gói giới hạn có thể bắt buộc cột số lượng ảnh (tùy models của Khoa); kiểm tra để test không phụ thuộc phiên bản."""
    return any(f.name == 'SoLuongAnhToiDa' for f in GoiDichVu._meta.get_fields())

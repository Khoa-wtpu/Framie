# schedule/tests.py - kiểm tra hàm khung giờ của K2. Chạy: python manage.py test schedule
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.constants import TrangThaiSlot, VaiTro
from profiles.models import NhiepAnhGia
from schedule.models import LichKhaDung
from schedule.services import dem_khung_gio_trong, doi_trang_thai_khung_gio, khung_gio_trong

User = get_user_model()


class KhungGioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        nhom, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        user = User.objects.create_user('nag1', 'nag1@example.com', 'Matkhau@123',
                                        so_dien_thoai='0900000001')
        user.groups.add(nhom)
        # Không qua form nên chỉ cần điền đường dẫn ảnh (không cần file thật).
        cls.nag = NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='x',
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')

    def tao_slot(self, so_ngay_sau_hom_nay, gio=9, trang_thai=TrangThaiSlot.TRONG):
        ngay = timezone.localdate() + timedelta(days=so_ngay_sau_hom_nay)
        return LichKhaDung.objects.create(
            MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau=time(gio, 0),
            GioKetThuc=time(gio + 1, 0), TrangThai=trang_thai)

    # ---- khung_gio_trong / dem_khung_gio_trong ----
    def test_chi_lay_slot_trong_chua_qua(self):
        trong = self.tao_slot(1)
        self.tao_slot(2, trang_thai=TrangThaiSlot.DANG_GIU)
        self.tao_slot(3, trang_thai=TrangThaiSlot.DA_DAT)
        self.tao_slot(-1)                      # hôm qua: đã qua
        self.assertEqual(list(khung_gio_trong(self.nag)), [trong])

    def test_gioi_han_so_ngay(self):
        self.tao_slot(1)
        self.tao_slot(6)                       # hôm nay + 6 = ngày thứ 7
        self.tao_slot(7)                       # ngoài 7 ngày
        self.assertEqual(dem_khung_gio_trong(self.nag, 7), 2)
        self.assertEqual(khung_gio_trong(self.nag).count(), 3)

    def test_nhan_ma_hoac_doi_tuong(self):
        self.tao_slot(1)
        self.assertEqual(khung_gio_trong(self.nag.pk).count(), 1)

    # ---- doi_trang_thai_khung_gio ----
    def test_chuyen_hop_le(self):
        slot = self.tao_slot(1)
        doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DANG_GIU)
        doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DA_DAT)
        doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.TRONG)
        slot.refresh_from_db()
        self.assertEqual(slot.TrangThai, TrangThaiSlot.TRONG)

    def test_giu_cho_roi_tha(self):
        slot = self.tao_slot(1)
        doi_trang_thai_khung_gio(slot, TrangThaiSlot.DANG_GIU)       # nhận cả đối tượng
        doi_trang_thai_khung_gio(slot, TrangThaiSlot.TRONG)

    def test_chuyen_khong_hop_le(self):
        slot = self.tao_slot(1)
        with self.assertRaises(ValidationError):                      # Trống -> Đã đặt: cấm
            doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DA_DAT)
        doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DANG_GIU)
        with self.assertRaises(ValidationError):                      # Đang giữ -> Đang giữ: cấm
            doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DANG_GIU)

    def test_da_dat_chi_ve_trong(self):
        slot = self.tao_slot(1, trang_thai=TrangThaiSlot.DA_DAT)
        with self.assertRaises(ValidationError):
            doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DANG_GIU)

    def test_trang_thai_la_hoac_slot_khong_ton_tai(self):
        slot = self.tao_slot(1)
        with self.assertRaises(ValidationError):
            doi_trang_thai_khung_gio(slot.pk, 'Trạng thái bậy')
        with self.assertRaises(ValidationError):
            doi_trang_thai_khung_gio(999999, TrangThaiSlot.DANG_GIU)

    def test_khong_giu_cho_slot_da_qua(self):
        slot = self.tao_slot(-1)
        with self.assertRaises(ValidationError):
            doi_trang_thai_khung_gio(slot.pk, TrangThaiSlot.DANG_GIU)
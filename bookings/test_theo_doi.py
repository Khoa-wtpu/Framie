# =====================================================================
# bookings/test_theo_doi.py - Test cho bookings/theo_doi.py (T7 / UC4.7 Theo dõi trạng thái Booking)
# Chạy:  python manage.py test bookings.test_theo_doi
# =====================================================================
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from bookings import test_tiep_nhan as nen             # dùng lại dữ liệu mẫu của UC4.3 (khách, Nhiếp ảnh gia, gói, tao_booking)
from bookings import theo_doi as uc
from bookings.models import LichSuTrangThaiBooking
from bookings.services import chuyen_trang_thai_booking
from core.constants import BenThucHien, LoaiThanhToan, TrangThaiBooking as BK, TrangThaiThanhToan as TT, VaiTro
from core.status_tones import TONE_BY_STATUS
from payments.models import ThanhToan, tinh_so_tien


class TheoDoiBase(nen.TiepNhanBase):
    def setUp(self):
        super().setUp()
        self.admin = nen.tao_user('qtv', VaiTro.QUAN_TRI_VIEN)
        self.client.logout()

    def dang_nhap(self, user):
        self.client.force_login(user)

    def tao_thanh_toan(self, bk, loai, trang_thai):
        da_xn = trang_thai in (TT.DA_DAT_COC, TT.DA_THANH_TOAN)
        return ThanhToan.objects.create(
            MaBooking=bk, LoaiThanhToan=loai, SoTien=tinh_so_tien(bk.TongGiaTri, loai), TrangThai=trang_thai,
            NgayXacNhan=timezone.now() if da_xn else None)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UC47KhachHang(TheoDoiBase):
    url = property(lambda self: reverse('my_bookings'))

    def test_khach_chi_thay_booking_cua_minh_kem_trang_thai(self):          # bước 2 + BR4.7-1
        cua_minh = self.tao_booking(gio='09:00')
        da_chap = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)
        cua_khach_b = self.tao_booking(gio='16:00', MaKhachHang=self.khach_b)
        self.dang_nhap(self.khach)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        ds = list(res.context['page_obj'])
        self.assertCountEqual(ds, [cua_minh, da_chap])
        self.assertNotIn(cua_khach_b, ds)
        self.assertContains(res, BK.CHO_XAC_NHAN)
        self.assertContains(res, BK.CHO_DAT_COC)

    def test_chua_co_booking_nao(self):                                      # ngoại lệ 1a
        self.dang_nhap(self.khach)
        self.assertContains(self.client.get(self.url), uc.TB_CHUA_CO_BOOKING)

    def test_loc_theo_trang_thai(self):                                      # luồng 2a
        moi = self.tao_booking(gio='09:00')
        coc = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)
        self.dang_nhap(self.khach)
        res = self.client.get(self.url, {'trang_thai': BK.CHO_DAT_COC})
        self.assertEqual(list(res.context['page_obj']), [coc])
        res = self.client.get(self.url, {'trang_thai': 'gõ_bậy'})            # giá trị lạ -> xem tất cả, không lỗi
        self.assertCountEqual(list(res.context['page_obj']), [moi, coc])

    def test_loc_ra_rong_bao_theo_bo_loc_khong_phai_chua_co_booking(self):
        self.tao_booking()
        self.dang_nhap(self.khach)
        res = self.client.get(self.url, {'trang_thai': BK.HOAN_THANH})
        self.assertContains(res, uc.TB_KHONG_KHOP_BO_LOC)
        self.assertNotContains(res, uc.TB_CHUA_CO_BOOKING)

    def test_chi_tiet_co_dong_thoi_gian_lich_su(self):                       # bước 3-4
        bk = self.tao_booking()
        chuyen_trang_thai_booking(bk, BK.CHO_DAT_COC, BenThucHien.NHIEP_ANH_GIA)
        self.dang_nhap(self.khach)
        res = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context['lich_su']), list(LichSuTrangThaiBooking.objects.filter(MaBooking=bk)))
        self.assertContains(res, 'Lịch sử trạng thái')
        self.assertContains(res, 'td-timeline')
        self.assertContains(res, BenThucHien.NHIEP_ANH_GIA)

    def test_khong_xem_duoc_booking_cua_nguoi_khac(self):                    # BR4.7-1
        bk = self.tao_booking(MaKhachHang=self.khach_b)
        self.dang_nhap(self.khach)
        self.assertEqual(self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk})).status_code, 404)

    def test_chua_dang_nhap_ve_trang_dang_nhap(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_khach_khong_vao_trang_quan_tri(self):
        self.dang_nhap(self.khach)
        self.assertEqual(self.client.get(reverse('admin_bookings')).status_code, 403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UC47NhiepAnhGia(TheoDoiBase):
    def test_nag_chi_thay_booking_gui_den_minh(self):
        cua_minh = self.tao_booking()
        cua_nag_khac = self.tao_booking(nag=self.nag_khac, gio='13:00')
        self.dang_nhap(self.nag.MaTaiKhoan)
        res = self.client.get(reverse('my_bookings'))
        self.assertEqual(list(res.context['page_obj']), [cua_minh])
        self.assertEqual(self.client.get(
            reverse('chi_tiet_booking', kwargs={'ma_booking': cua_nag_khac.pk})).status_code, 404)

    def test_nag_chi_tiet_co_link_xu_ly_khi_cho_xac_nhan(self):
        bk = self.tao_booking()
        self.dang_nhap(self.nag.MaTaiKhoan)
        res = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))
        self.assertContains(res, reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UC47QuanTriVien(TheoDoiBase):
    def test_quan_tri_thay_tat_ca_va_tim_kiem(self):
        a = self.tao_booking(gio='09:00')
        b = self.tao_booking(nag=self.nag_khac, gio='13:00', MaKhachHang=self.khach_b)
        self.dang_nhap(self.admin)
        res = self.client.get(reverse('admin_bookings'))
        self.assertCountEqual(list(res.context['page_obj']), [a, b])
        res = self.client.get(reverse('admin_bookings'), {'q': 'khach_b'})
        self.assertEqual(list(res.context['page_obj']), [b])
        res = self.client.get(reverse('admin_bookings'), {'q': f'#{a.pk}'})
        self.assertEqual(list(res.context['page_obj']), [a])
        self.assertEqual(self.client.get(reverse('admin_booking_detail', kwargs={'ma_booking': b.pk})).status_code, 200)

    def test_nag_khong_vao_trang_quan_tri(self):
        self.dang_nhap(self.nag.MaTaiKhoan)
        self.assertEqual(self.client.get(reverse('admin_bookings')).status_code, 403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UC47DongBoThanhToan(TheoDoiBase):                                      # BR4.7-2
    def test_khop_thi_khong_canh_bao(self):
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)
        self.assertEqual(uc.doi_chieu_thanh_toan(bk), [])

    def test_chot_booking_ma_coc_chua_xac_nhan_la_lech(self):
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.CHO_XAC_NHAN_COC)
        self.assertEqual(len(uc.doi_chieu_thanh_toan(bk)), 1)

    def test_coc_da_xac_nhan_ma_booking_van_cho_dat_coc_la_lech(self):
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC)
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)
        self.assertEqual(len(uc.doi_chieu_thanh_toan(bk)), 1)

    def test_hoan_thanh_phai_co_60_da_thanh_toan(self):
        bk = self.tao_booking(trang_thai=BK.HOAN_THANH)
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)
        self.assertEqual(len(uc.doi_chieu_thanh_toan(bk)), 1)                # thiếu khoản 60%
        self.tao_thanh_toan(bk, LoaiThanhToan.PHAN_CON_LAI, TT.DA_THANH_TOAN)
        self.assertEqual(uc.doi_chieu_thanh_toan(bk), [])

    def test_chi_quan_tri_thay_canh_bao_lech(self):
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)                     # chưa có khoản cọc nào -> lệch
        url_kh = reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk})
        self.dang_nhap(self.khach)
        self.assertNotContains(self.client.get(url_kh), 'không khớp dữ liệu thanh toán')
        self.dang_nhap(self.admin)
        res = self.client.get(reverse('admin_booking_detail', kwargs={'ma_booking': bk.pk}))
        self.assertContains(res, 'không khớp dữ liệu thanh toán')

    def test_chi_tiet_hien_khoan_thanh_toan_canh_trang_thai(self):
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)
        self.dang_nhap(self.khach)
        res = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))
        self.assertContains(res, TT.DA_DAT_COC)
        self.assertContains(res, LoaiThanhToan.TIEN_COC)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UC47NhanVaMau(TheoDoiBase):
    def test_moi_trang_thai_booking_co_mau_khai_bao_ro_rang(self):
        for tt in BK.ALL:
            self.assertIn(tt, TONE_BY_STATUS, f'"{tt}" chưa có màu trong core/status_tones.py')

    def test_danh_sach_va_chi_tiet_dung_cung_mot_mau_cho_cung_trang_thai(self):
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC)
        tone = TONE_BY_STATUS[BK.CHO_DAT_COC]
        self.dang_nhap(self.khach)
        ds = self.client.get(reverse('my_bookings'))
        ct = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))
        for res in (ds, ct):
            self.assertContains(res, f'badge badge--{tone}')

from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings import giu_cho as uc41
from bookings import gui_booking as uc
from bookings.models import Booking, GiuCho, LichSuTrangThaiBooking
from core.constants import (
    BenThucHien, LoaiHauKy, TrangThaiBooking as BK, TrangThaiGiuCho as GC, TrangThaiGoi,
    TrangThaiGuiEmail, TrangThaiHoSo, TrangThaiSlot as SL, VaiTro,
)
from notifications.models import ThongBao
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()


def tao_user(ten, nhom=None, **kw):
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 so_dien_thoai=f'09{abs(hash(ten)) % 10**8:08d}', **kw)
    if nhom:
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    return u


def tao_nag(ten):
    user = tao_user(ten, VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
    return NhiepAnhGia.objects.create(MaTaiKhoan=user, AnhDaiDien='a.jpg', GioiThieu='g', NganHang='b',
                                      SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')


class UC42(TestCase):
    def setUp(self):
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        self.b = tao_user('khach_b', VaiTro.KHACH_HANG)
        self.nag = tao_nag('nag')
        self.nag_khac = tao_nag('nag_khac')
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.chan_dung, TenGoi='Gói cơ bản',
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.goi_cuoi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.cuoi, TenGoi='Gói cưới',
                                                 Gia=9000000, ThoiLuongChup=240, LoaiHauKy=LoaiHauKy.GIOI_HAN,
                                                 SoAnhHauKyToiDa=50)
        self.goi_ngung = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.chan_dung,
                                                  TenGoi='Gói cũ', Gia=1000000, ThoiLuongChup=60,
                                                  LoaiHauKy=LoaiHauKy.TOAN_BO, TrangThai=TrangThaiGoi.NGUNG_AP_DUNG)
        self.goi_nguoi_khac = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag_khac, MaLoaiHinh=self.chan_dung,
                                                       TenGoi='Gói người khác', Gia=2000000, ThoiLuongChup=60,
                                                       LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.ngay = timezone.localdate() + timedelta(days=2)
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay,
                                             GioBatDau='09:00', GioKetThuc='11:00')
        self.s2 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay,
                                             GioBatDau='13:00', GioKetThuc='15:00')

    # ---- tiện ích ----
    def giu(self, user, slot):
        return uc41.giu_cho_slot(user, slot.pk)

    def url(self, giu_cho):
        return reverse('gui_booking', kwargs={'ma_giu_cho': giu_cho.pk})

    def du_lieu(self, **ghi_de):
        d = {'loai_hinh': self.chan_dung.pk, 'goi': self.goi.pk, 'ngay_gio_chup': f'{self.ngay:%Y-%m-%d}T09:30',
             'dia_diem': 'Hồ Gươm, Hà Nội', 'so_nguoi': 2, 'concept': 'Vintage', 'yeu_cau_rieng': 'Mang theo phụ kiện'}
        d.update(ghi_de)
        return d

    def gui(self, user, giu_cho, **ghi_de):
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url(giu_cho), self.du_lieu(**ghi_de), follow=True)

    def slot(self, slot):
        return LichKhaDung.objects.get(pk=slot.pk).TrangThai

    def lam_het_han(self, giu_cho):
        bay_gio = timezone.now()    # lùi cả giờ giữ lẫn giờ hết hạn (ràng buộc: hết hạn phải sau giờ giữ)
        GiuCho.objects.filter(pk=giu_cho.pk).update(ThoiDiemGiu=bay_gio - timedelta(minutes=6),
                                                    ThoiDiemHetHan=bay_gio - timedelta(minutes=1))

    # ---- Basic flow ----
    def test_luong_chinh(self):
        g = self.giu(self.a, self.s1)
        r = self.gui(self.a, g)
        self.assertEqual(r.status_code, 200)

        b = Booking.objects.get()
        self.assertEqual((b.MaKhachHang, b.MaNhiepAnhGia, b.MaGoi, b.MaLich), (self.a, self.nag, self.goi, self.s1))
        self.assertEqual(b.TrangThai, BK.CHO_XAC_NHAN)
        self.assertEqual(b.TongGiaTri, self.goi.Gia)                               # tổng giá trị = giá gói
        self.assertEqual((b.DiaDiem, b.SoNguoi, b.Concept), ('Hồ Gươm, Hà Nội', 2, 'Vintage'))
        self.assertEqual(b.YeuCauRieng, 'Mang theo phụ kiện')
        self.assertEqual(timezone.localtime(b.NgayGioChup).strftime('%H:%M'), '09:30')

        self.assertEqual(GiuCho.objects.get().TrangThai, GC.DA_HOAN_TAT)           # lượt giữ chỗ hoàn tất
        self.assertEqual(self.slot(self.s1), SL.DANG_GIU)                          # slot vẫn giữ cho tới khi NAG xử lý
        self.assertContains(r, 'Yêu cầu Booking đã được gửi')                      # bước 8

        ls = LichSuTrangThaiBooking.objects.get()                                  # dòng lịch sử đầu tiên
        self.assertEqual((ls.MaBooking, ls.TrangThaiCu, ls.TrangThaiMoi, ls.BenThucHien),
                         (b, None, BK.CHO_XAC_NHAN, BenThucHien.KHACH_HANG))

    def test_thong_bao_web_va_email(self):
        g = self.giu(self.a, self.s1)
        self.gui(self.a, g)
        b = Booking.objects.get()
        tb_nag = ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan)
        self.assertEqual((tb_nag.TieuDe, tb_nag.MaBooking), ('Yêu cầu Booking mới', b))
        self.assertIn('Gói cơ bản', tb_nag.NoiDung)
        tb_khach = ThongBao.objects.get(MaNguoiNhan=self.a)
        self.assertEqual(tb_khach.TieuDe, 'Yêu cầu Booking đã được gửi')
        self.assertEqual(len(mail.outbox), 1)                                      # Email cho Nhiếp ảnh gia
        self.assertEqual(mail.outbox[0].to, [self.nag.MaTaiKhoan.email])
        tb_nag.refresh_from_db()
        self.assertEqual(tb_nag.TrangThaiGuiEmail, TrangThaiGuiEmail.THANH_CONG)

    def test_gui_email_loi_thi_booking_van_tao(self):
        g = self.giu(self.a, self.s1)
        with mock.patch.object(uc, 'send_mail', side_effect=OSError('smtp down')):
            self.gui(self.a, g)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan).TrangThaiGuiEmail,
                         TrangThaiGuiEmail.THAT_BAI)

    def test_yeu_cau_rieng_de_trong_thi_luu_null(self):
        g = self.giu(self.a, self.s1)
        self.gui(self.a, g, yeu_cau_rieng='   ')
        self.assertIsNone(Booking.objects.get().YeuCauRieng)

    def test_trang_hien_dung_form(self):
        g = self.giu(self.a, self.s1)
        self.client.force_login(self.a)
        r = self.client.get(self.url(g))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="dem-nguoc"')
        ds_goi = [o.pk for o in r.context['form'].fields['goi'].queryset]
        self.assertCountEqual(ds_goi, [self.goi.pk, self.goi_cuoi.pk])              # chỉ gói Đang áp dụng của NAG này
        self.assertEqual([o.pk for o in r.context['form'].fields['loai_hinh'].queryset],
                         [self.chan_dung.pk, self.cuoi.pk])                        # xếp theo tên: Chân dung, Cưới

    def test_man_hinh_giu_cho_co_nut_tiep_tuc(self):
        g = self.giu(self.a, self.s1)
        self.client.force_login(self.a)
        r = self.client.get(reverse('man_hinh_giu_cho', args=[g.pk]))
        self.assertContains(r, self.url(g))                                        # link 'gui_booking' của UC4.1 hoạt động

    # ---- 1a: thông tin không hợp lệ ----
    def test_thieu_truong_bat_buoc(self):
        g = self.giu(self.a, self.s1)
        self.client.force_login(self.a)
        r = self.client.post(self.url(g), {})
        self.assertEqual(r.status_code, 200)
        loi = r.context['form'].errors
        for ten in ('loai_hinh', 'goi', 'ngay_gio_chup', 'dia_diem', 'so_nguoi', 'concept'):
            self.assertIn(ten, loi)
        self.assertNotIn('yeu_cau_rieng', loi)                                     # không bắt buộc
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.DANG_GIU)              # vẫn giữ chỗ, được sửa tiếp

    def test_sua_loi_roi_gui_lai_thanh_cong(self):
        g = self.giu(self.a, self.s1)
        r = self.gui(self.a, g, dia_diem='   ')
        self.assertEqual(Booking.objects.count(), 0)
        self.assertIn('dia_diem', r.context['form'].errors)
        r = self.gui(self.a, g)
        self.assertEqual(Booking.objects.count(), 1)

    def test_gio_chup_ngoai_khung_gio_cua_slot(self):
        g = self.giu(self.a, self.s1)
        for gio in ('08:59', '11:00', '12:00'):
            r = self.gui(self.a, g, ngay_gio_chup=f'{self.ngay:%Y-%m-%d}T{gio}')
            self.assertIn('ngay_gio_chup', r.context['form'].errors, gio)
        r = self.gui(self.a, g, ngay_gio_chup=f'{self.ngay + timedelta(days=1):%Y-%m-%d}T09:30')   # sai ngày
        self.assertIn('ngay_gio_chup', r.context['form'].errors)
        self.assertEqual(Booking.objects.count(), 0)
        r = self.gui(self.a, g, ngay_gio_chup=f'{self.ngay:%Y-%m-%d}T09:00')                         # đúng giờ bắt đầu slot
        self.assertEqual(Booking.objects.count(), 1)

    def test_goi_ngung_ap_dung_hoac_cua_nguoi_khac_bi_chan(self):
        g = self.giu(self.a, self.s1)
        for goi in (self.goi_ngung, self.goi_nguoi_khac):
            r = self.gui(self.a, g, goi=goi.pk)
            self.assertIn('goi', r.context['form'].errors, goi.TenGoi)
        self.assertEqual(Booking.objects.count(), 0)

    def test_goi_khong_khop_loai_hinh(self):
        g = self.giu(self.a, self.s1)
        r = self.gui(self.a, g, loai_hinh=self.cuoi.pk)            # gói cơ bản là Chân dung
        self.assertIn('goi', r.context['form'].errors)
        self.assertEqual(Booking.objects.count(), 0)

    def test_so_nguoi_khong_hop_le(self):
        g = self.giu(self.a, self.s1)
        for v in ('0', '-1', 'abc'):
            r = self.gui(self.a, g, so_nguoi=v)
            self.assertIn('so_nguoi', r.context['form'].errors, v)
        self.assertEqual(Booking.objects.count(), 0)

    def test_service_loi_clean_cua_booking_ve_dung_o_nhap_va_khong_dong_giu_cho(self):
        g = self.giu(self.a, self.s1)
        with self.assertRaises(uc.GuiBookingLoi) as ctx:           # bỏ qua form: đưa thẳng gói đã ngừng vào service
            uc.gui_yeu_cau_booking(self.a, g.pk, self.goi_ngung.pk,
                                   timezone.make_aware(datetime.combine(self.ngay, datetime.strptime('09:30', '%H:%M').time())),
                                   'x', 1, 'y')
        self.assertIn('MaGoi', ctx.exception.loi_truong)
        self.assertFalse(ctx.exception.het_han)
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.DANG_GIU)   # rollback: lượt giữ chỗ không bị đóng

    # ---- 4a / BR4.2-1 / BR4.2-2: hết thời gian giữ chỗ ----
    def test_het_5_phut_khi_gui(self):
        g = self.giu(self.a, self.s1)
        self.lam_het_han(g)
        r = self.gui(self.a, g)
        self.assertContains(r, 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại')
        self.assertEqual(r.redirect_chain[-1][0], reverse('lich_chon_slot', args=[self.nag.pk]))
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)
        self.assertEqual(self.slot(self.s1), SL.TRONG)                             # slot được giải phóng (BR4.2-1)
        self.assertEqual(ThongBao.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_het_5_phut_khi_mo_trang(self):
        g = self.giu(self.a, self.s1)
        self.lam_het_han(g)
        self.client.force_login(self.a)
        r = self.client.get(self.url(g), follow=True)
        self.assertContains(r, 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại')
        self.assertEqual(self.slot(self.s1), SL.TRONG)

    def test_het_han_dung_luc_service_chay_van_nha_slot(self):
        # Hết hạn đúng khoảng giữa lúc mở view và lúc service chạy (bỏ qua bước quét sớm): slot phải được nhả thật.
        g = self.giu(self.a, self.s1)
        self.lam_het_han(g)
        with mock.patch.object(uc, 'giai_phong_giu_cho_het_han'):
            with self.assertRaises(uc.GuiBookingLoi) as ctx:
                uc.gui_yeu_cau_booking(self.a, g.pk, self.goi.pk, timezone.now() + timedelta(days=2),
                                       'x', 1, 'y')
        self.assertTrue(ctx.exception.het_han)
        self.assertEqual(str(ctx.exception), 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại')
        self.assertEqual(self.slot(self.s1), SL.TRONG)
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)
        self.assertEqual(Booking.objects.count(), 0)

    def test_chon_lai_sau_khi_het_han_lam_lai_duoc_uc41(self):
        g = self.giu(self.a, self.s1)
        self.lam_het_han(g)
        self.gui(self.a, g)
        g2 = self.giu(self.b, self.s1)                              # slot đã trống, người khác chọn được
        self.assertEqual(g2.TrangThai, GC.DANG_GIU)

    # ---- BR4.2-3 / gửi trùng ----
    def test_gui_hai_lan_chi_tao_mot_booking(self):
        g = self.giu(self.a, self.s1)
        self.gui(self.a, g)
        r = self.gui(self.a, g)
        self.assertContains(r, 'Lượt giữ chỗ này đã được dùng để gửi yêu cầu Booking.')
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.nag.MaTaiKhoan).count(), 1)

    def test_slot_da_gan_booking_con_hieu_luc_khong_tao_them(self):
        g = self.giu(self.a, self.s1)
        self.gui(self.a, g)
        # Giả lập dữ liệu lệch: một lượt giữ mới trên slot đã có Booking còn hiệu lực.
        now = timezone.now()
        g2 = GiuCho.objects.create(MaKhachHang=self.b, MaLich=self.s1, ThoiDiemGiu=now,
                                   ThoiDiemHetHan=now + uc41.THOI_GIAN_GIU_CHO)
        r = self.gui(self.b, g2)
        self.assertContains(r, 'đã gắn với một Booking đang có hiệu lực')
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(GiuCho.objects.get(pk=g2.pk).TrangThai, GC.DANG_GIU)       # không đóng lượt giữ khi lỗi

    def test_slot_cua_booking_da_tu_choi_dat_lai_duoc(self):
        g = self.giu(self.a, self.s1)
        self.gui(self.a, g)
        from bookings.services import chuyen_trang_thai_booking
        chuyen_trang_thai_booking(Booking.objects.get(), BK.DA_TU_CHOI, BenThucHien.NHIEP_ANH_GIA, ly_do='Bận')
        g2 = self.giu(self.b, self.s1)
        self.gui(self.b, g2)
        self.assertEqual(Booking.objects.count(), 2)
        self.assertEqual(Booking.objects.filter(MaLich=self.s1).exclude(TrangThai=BK.DA_TU_CHOI).count(), 1)

    # ---- Quyền ----
    def test_chi_xem_va_gui_duoc_luot_giu_cua_chinh_minh(self):
        g = self.giu(self.a, self.s1)
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(self.url(g)).status_code, 404)
        self.assertEqual(self.client.post(self.url(g), self.du_lieu()).status_code, 404)
        self.assertEqual(Booking.objects.count(), 0)

    def test_chua_dang_nhap_va_sai_vai_tro(self):
        g = self.giu(self.a, self.s1)
        self.assertEqual(self.client.get(self.url(g)).status_code, 302)             # sang trang đăng nhập
        self.client.force_login(self.nag.MaTaiKhoan)
        self.assertEqual(self.client.get(self.url(g)).status_code, 403)

    def test_chi_nhan_get_va_post(self):
        g = self.giu(self.a, self.s1)
        self.client.force_login(self.a)
        self.assertEqual(self.client.delete(self.url(g)).status_code, 405)

    # ---- Ghi nhận booking đầu tiên của hai khách ở hai slot ----
    def test_hai_khach_hai_slot_doc_lap(self):
        ga, gb = self.giu(self.a, self.s1), self.giu(self.b, self.s2)
        self.gui(self.a, ga)
        self.gui(self.b, gb, ngay_gio_chup=f'{self.ngay:%Y-%m-%d}T13:30', goi=self.goi_cuoi.pk,
                 loai_hinh=self.cuoi.pk)
        self.assertEqual(Booking.objects.get(MaKhachHang=self.b).TongGiaTri, self.goi_cuoi.Gia)
        self.assertEqual(Booking.objects.count(), 2)

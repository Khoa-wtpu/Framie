# core/test_tong_quan.py - B9: kiểm tra Trang tổng quan sau đăng nhập. Chạy: python manage.py test core.test_tong_quan
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import url_trang_chu
from bookings.models import Booking
from bookings.test_tiep_nhan import tao_nag, tao_user          # hàm dựng tài khoản / Nhiếp ảnh gia mẫu của nhóm Booking
from core.constants import (KetQuaDuyetHoSo, LoaiHauKy, TrangThaiBooking as BK, TrangThaiDoc, TrangThaiHoSo,
                            TrangThaiSlot as SL, VaiTro)
from notifications.models import ThongBao
from profiles.models import DuyetHoSo, GoiDichVu, LoaiHinhChup
from schedule.models import LichKhaDung

URL = '/tong-quan/'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TongQuanBase(TestCase):
    def setUp(self):
        self.khach = tao_user('khach_a', VaiTro.KHACH_HANG, first_name='An', last_name='Nguyễn')
        self.khach_b = tao_user('khach_b', VaiTro.KHACH_HANG)
        self.nag = tao_nag('nag')
        self.nag_khac = tao_nag('nag_khac')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='Gói cơ bản',
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.goi_khac = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag_khac, MaLoaiHinh=loai,
                                                 TenGoi='Gói người khác', Gia=2000000, ThoiLuongChup=60,
                                                 LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.ngay = timezone.localdate() + timedelta(days=3)
        self._gio = 7

    def tao_booking(self, nag=None, khach=None, trang_thai=BK.CHO_XAC_NHAN):
        nag = nag or self.nag
        goi = self.goi if nag == self.nag else self.goi_khac
        self._gio += 1                                   # mỗi Booking một khung giờ riêng
        gio = f'{self._gio:02d}:00'
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=self.ngay, GioBatDau=gio,
                                          GioKetThuc=f'{self._gio + 2:02d}:00', TrangThai=SL.DANG_GIU)
        return Booking.objects.create(
            MaKhachHang=khach or self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.make_aware(timezone.datetime.combine(self.ngay, timezone.datetime.strptime(gio, '%H:%M').time())),
            DiaDiem='Hồ Gươm', SoNguoi=2, Concept='Vintage', TrangThai=trang_thai)

    def mo(self, user):
        self.client.force_login(user)
        return self.client.get(URL)


class TruyCap(TongQuanBase):
    def test_chua_dang_nhap_chuyen_ve_dang_nhap(self):
        res = self.client.get(URL)
        self.assertRedirects(res, f"{reverse('login')}?next={URL}", fetch_redirect_response=False)

    def test_quan_tri_chuyen_sang_trang_quan_tri(self):
        admin = tao_user('qt', VaiTro.QUAN_TRI_VIEN)
        self.assertRedirects(self.mo(admin), reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_trang_dich_sau_dang_nhap_la_tong_quan(self):
        self.assertEqual(reverse('dashboard'), URL)
        self.assertEqual(url_trang_chu(self.khach), URL)
        self.assertEqual(url_trang_chu(self.nag.MaTaiKhoan), URL)


class KhachHang(TongQuanBase):
    def test_chi_hien_booking_dang_xu_ly_cua_minh(self):
        dang = self.tao_booking(trang_thai=BK.CHO_DAT_COC)
        self.tao_booking(trang_thai=BK.HOAN_THANH)
        self.tao_booking(trang_thai=BK.DA_HUY)
        self.tao_booking(khach=self.khach_b)                          # của người khác
        res = self.mo(self.khach)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'core/tong_quan.html')
        self.assertEqual(res.context['khach']['so_dang_xu_ly'], 1)
        self.assertEqual([b['ma'] for b in res.context['khach']['dang_xu_ly']], [dang.pk])
        self.assertContains(res, reverse('chi_tiet_booking', args=[dang.pk]))
        self.assertContains(res, BK.CHO_DAT_COC)

    def test_chua_co_booking_hien_cau_trong(self):
        res = self.mo(self.khach)
        self.assertContains(res, 'Bạn chưa có Booking nào đang xử lý.')
        self.assertContains(res, 'Tìm nhiếp ảnh gia')

    def test_chi_hien_thong_bao_chua_doc_cua_minh(self):
        ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe='Yêu cầu được chấp nhận', NoiDung='Hãy đặt cọc.')
        ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe='Thông báo cũ', NoiDung='x', TrangThaiDoc=TrangThaiDoc.DA_DOC)
        ThongBao.objects.create(MaNguoiNhan=self.khach_b, TieuDe='Của người khác', NoiDung='x')
        res = self.mo(self.khach)
        self.assertContains(res, 'Yêu cầu được chấp nhận')
        self.assertNotContains(res, 'Thông báo cũ')
        self.assertNotContains(res, 'Của người khác')
        self.assertEqual(res.context['khach']['so_thong_bao'], 1)

    def test_khong_co_thong_bao(self):
        self.assertContains(self.mo(self.khach), 'Không có thông báo mới.')

    def test_chi_hien_toi_da_5_dong(self):
        for _ in range(7):
            self.tao_booking()
        res = self.mo(self.khach)
        self.assertEqual(res.context['khach']['so_dang_xu_ly'], 7)
        self.assertEqual(len(res.context['khach']['dang_xu_ly']), 5)


class NhiepAnhGiaDaDuyet(TongQuanBase):
    def test_yeu_cau_moi_va_lich_sap_toi(self):
        moi = self.tao_booking(trang_thai=BK.CHO_XAC_NHAN)
        chot = self.tao_booking(trang_thai=BK.CHOT_BOOKING)
        self.tao_booking(trang_thai=BK.HOAN_THANH)
        self.tao_booking(nag=self.nag_khac)                           # Booking của Nhiếp ảnh gia khác
        res = self.mo(self.nag.MaTaiKhoan)
        nag = res.context['nag']
        self.assertTrue(nag['da_duyet'])
        self.assertEqual(nag['so_yeu_cau_moi'], 1)
        self.assertEqual([b['ma'] for b in nag['yeu_cau_moi']], [moi.pk])
        self.assertEqual(nag['so_lich_sap_toi'], 1)
        self.assertEqual([b['ma'] for b in nag['lich_sap_toi']], [chot.pk])
        self.assertContains(res, reverse('chi_tiet_yeu_cau_booking', args=[moi.pk]))
        self.assertContains(res, 'Yêu cầu Booking mới')
        self.assertContains(res, 'Lịch sắp tới')

    def test_dem_khung_gio_trong(self):
        LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay, GioBatDau='06:00',
                                   GioKetThuc='07:00', TrangThai=SL.TRONG)
        self.assertEqual(self.mo(self.nag.MaTaiKhoan).context['nag']['so_khung_gio_trong'], 1)

    def test_khong_co_gi(self):
        res = self.mo(self.nag.MaTaiKhoan)
        self.assertContains(res, 'Không có yêu cầu Booking mới.')
        self.assertContains(res, 'Chưa có buổi chụp nào sắp tới.')
        self.assertContains(res, TrangThaiHoSo.DA_DUYET)


class NhiepAnhGiaChuaDuyet(TongQuanBase):
    def _doi_trang_thai(self, trang_thai):
        user = self.nag.MaTaiKhoan
        user.trang_thai_ho_so = trang_thai
        user.save()
        return user

    def test_cho_duyet_chi_thay_tinh_trang_ho_so(self):
        self.tao_booking()
        res = self.mo(self._doi_trang_thai(TrangThaiHoSo.CHO_DUYET))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['nag']['da_duyet'])
        self.assertNotIn('yeu_cau_moi', res.context['nag'])
        self.assertContains(res, 'Tình trạng hồ sơ')
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')
        self.assertNotContains(res, 'Yêu cầu Booking mới')
        self.assertNotContains(res, 'Lịch sắp tới')

    def test_bi_tu_choi_hien_ly_do(self):
        admin = tao_user('qt', VaiTro.QUAN_TRI_VIEN)
        DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag, MaQuanTriVien=admin, ThoiDiemDuyet=timezone.now(),
                                 KetQua=KetQuaDuyetHoSo.DA_TU_CHOI, NoiDungPhanHoi='Ảnh Portfolio chưa rõ nét.')
        res = self.mo(self._doi_trang_thai(TrangThaiHoSo.DA_TU_CHOI))
        self.assertContains(res, 'Ảnh Portfolio chưa rõ nét.')
        self.assertContains(res, TrangThaiHoSo.DA_TU_CHOI)

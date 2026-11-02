# schedule/tests_lich.py - K10: Quản lý lịch khả dụng (UC3.1). Chạy: python manage.py test schedule
import importlib.util
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, GiuCho
from core.constants import (LoaiHauKy, TrangThaiBooking as BK, TrangThaiGiuCho as GC,
                            TrangThaiHoSo, TrangThaiSlot as SL, VaiTro)
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule import quan_ly
from schedule.forms import KhungGioForm
from schedule.models import LichKhaDung
from schedule.quan_ly import LichLoi, url_lich

User = get_user_model()
CO_GIU_CHO = importlib.util.find_spec('bookings.giu_cho') is not None      # file của Tuyền (T3-T4)
CHO_T34 = 'Chờ merge bookings/giu_cho.py (T3-T4 của Tuyền)'
GIO_8 = '08:00:00'
GIO_9 = '09:00:00'
GIO_10 = '10:00:00'
GIO_11 = '11:00:00'
GIO_12 = '12:00:00'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])   # test nhanh hơn, không ảnh hưởng web thật
class LichTestCase(TestCase):
    def setUp(self):
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.nhom_khach, _ = Group.objects.get_or_create(name=VaiTro.KHACH_HANG)
        self.dem = 0
        self.user, self.nag = self.tao_nag('nag1')
        self.user2, self.nag2 = self.tao_nag('nag2')
        self.khach = self.tao_khach()
        self.client.force_login(self.user)
        self.hom_nay = timezone.localdate()
        self.ngay = self.hom_nay + timedelta(days=3)       # một ngày chắc chắn ở tương lai

    # ---- dữ liệu mẫu ----
    def tao_nag(self, ten, trang_thai=TrangThaiHoSo.DA_DUYET):
        self.dem += 1
        user = User.objects.create_user(ten, f'{ten}@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09400000{self.dem:02d}')
        user.groups.add(self.nhom_nag)
        user.trang_thai_ho_so = trang_thai
        user.save()
        nag = NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='x',
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        return user, nag

    def tao_khach(self):
        self.dem += 1
        user = User.objects.create_user('khach', 'khach@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09400000{self.dem:02d}')
        user.groups.add(self.nhom_khach)
        return user

    def tao_slot(self, nag=None, ngay=None, bat_dau=time(8, 0), ket_thuc=time(10, 0), trang_thai=SL.TRONG):
        return LichKhaDung.objects.create(
            MaNhiepAnhGia=nag or self.nag, Ngay=ngay or self.ngay,
            GioBatDau=bat_dau, GioKetThuc=ket_thuc, TrangThai=trang_thai)

    def tao_giu_cho(self, lich, trang_thai=GC.HET_HAN):
        bg = timezone.now()
        return GiuCho.objects.create(
            MaKhachHang=self.khach, MaLich=lich, ThoiDiemGiu=bg - timedelta(minutes=10),
            ThoiDiemHetHan=bg - timedelta(minutes=5), TrangThai=trang_thai)

    def tao_booking(self, lich, trang_thai=BK.CHOT_BOOKING):
        loai, _ = LoaiHinhChup.objects.get_or_create(TenLoaiHinh='Chân dung')
        goi = GoiDichVu.objects.create(
            MaNhiepAnhGia=lich.MaNhiepAnhGia, MaLoaiHinh=loai, TenGoi='Gói cơ bản', Gia=Decimal(1500000),
            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        return Booking.objects.create(
            MaKhachHang=self.khach, MaNhiepAnhGia=lich.MaNhiepAnhGia, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.now() + timedelta(days=3), DiaDiem='Hồ Gươm', SoNguoi=2,
            Concept='Vintage', TrangThai=trang_thai,
            # Ràng buộc ck_booking_lydotuchoi: "Đã từ chối" bắt buộc có lý do, trạng thái khác thì lý do phải để trống.
            LyDoTuChoi='Trùng lịch cá nhân' if trang_thai == BK.DA_TU_CHOI else None)

    def du_lieu(self, ngay=None, bat_dau=GIO_8, ket_thuc=GIO_10, **them):
        data = {'Ngay': (ngay or self.ngay).isoformat(), 'GioBatDau': bat_dau, 'GioKetThuc': ket_thuc}
        data.update(them)
        return data

    def tin_nhan(self, res):
        return [str(m) for m in get_messages(res.wsgi_request)]

    def cac_slot(self, res):
        """Các khung giờ hiển thị ở chế độ tuần."""
        return [s['lich'] for ngay in res.context['cac_ngay'] for s in ngay['cac_slot']]

    def mo_ta_slot(self, res, lich):
        for ngay in res.context['cac_ngay']:
            for s in ngay['cac_slot']:
                if s['lich'].pk == lich.pk:
                    return s
        self.fail('Không thấy khung giờ trên trang')

    def url_ds(self, **tham_so):
        return reverse('my_calendar') + ('?' + '&'.join(f'{k}={v}' for k, v in tham_so.items()) if tham_so else '')

    def gio_gia_lap(self, gio, phut=0):
        """Giả lập 'bây giờ' là gio:phut của hôm nay."""
        return mock.patch('schedule.quan_ly.bay_gio', return_value=timezone.localtime(
            timezone.make_aware(datetime.combine(self.hom_nay, time(gio, phut)))))

    # =================================================================
    # Quyền truy cập
    # =================================================================
    def cac_url(self, lich):
        return [reverse('my_calendar'), reverse('lich_them'),
                reverse('lich_sua', args=[lich.pk]), reverse('lich_xoa', args=[lich.pk])]

    def test_chua_dang_nhap_bi_chuyen_ve_dang_nhap(self):
        lich = self.tao_slot()
        self.client.logout()
        for url in self.cac_url(lich):
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 302)
                self.assertIn('dang-nhap', res['Location'])

    def test_khach_hang_khong_vao_duoc(self):
        lich = self.tao_slot()
        self.client.force_login(self.khach)
        for url in self.cac_url(lich):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse('lich_them'), self.du_lieu()).status_code, 403)
        self.assertEqual(self.client.post(reverse('lich_xoa', args=[lich.pk])).status_code, 403)
        self.assertTrue(LichKhaDung.objects.filter(pk=lich.pk).exists())

    def test_ho_so_chua_duyet_khong_vao_duoc(self):
        user, _ = self.tao_nag('nag_cho', TrangThaiHoSo.CHO_DUYET)
        lich = self.tao_slot()
        self.client.force_login(user)
        for url in self.cac_url(lich):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(reverse('lich_them'), self.du_lieu()).status_code, 302)
        self.assertEqual(LichKhaDung.objects.filter(MaNhiepAnhGia__MaTaiKhoan=user).count(), 0)

    # =================================================================
    # Xem lịch (UC3.1 bước 1-2)
    # =================================================================
    def test_tuan_chi_thay_lich_cua_minh(self):
        cua_minh = self.tao_slot()
        cua_nguoi_khac = self.tao_slot(nag=self.nag2)
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.cac_slot(res), [cua_minh])
        self.assertNotIn(cua_nguoi_khac, self.cac_slot(res))

    def test_chuyen_tuan_theo_tham_so_ngay(self):
        xa = self.tao_slot(ngay=self.hom_nay + timedelta(days=21))
        res = self.client.get(self.url_ds(ngay=xa.Ngay.isoformat()))
        self.assertEqual(self.cac_slot(res), [xa])
        res = self.client.get(self.url_ds())                       # tuần hiện tại: không có khung giờ nào
        self.assertEqual(self.cac_slot(res), [])
        self.assertContains(res, 'chưa có khung giờ nào')

    def test_tuan_bat_dau_tu_thu_hai(self):
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        ngay_dau = res.context['cac_ngay'][0]['ngay']
        self.assertEqual(ngay_dau.weekday(), 0)
        self.assertLessEqual(ngay_dau, self.ngay)
        self.assertEqual(len(res.context['cac_ngay']), 7)

    def test_tham_so_la_tren_url_quay_ve_mac_dinh(self):
        for ngay in ('abc', '1900-01-01', '2999-12-31', ''):
            with self.subTest(ngay=ngay):
                res = self.client.get(self.url_ds(ngay=ngay, che_do='xyz'))
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.context['che_do'], 'tuan')
                ngay_trong_tuan = [n['ngay'] for n in res.context['cac_ngay']]
                self.assertIn(self.hom_nay, ngay_trong_tuan)

    def test_che_do_thang(self):
        self.tao_slot()
        self.tao_slot(bat_dau=time(10, 0), ket_thuc=time(12, 0), trang_thai=SL.DANG_GIU)
        self.tao_slot(bat_dau=time(14, 0), ket_thuc=time(16, 0), trang_thai=SL.DA_DAT)
        res = self.client.get(self.url_ds(che_do='thang', ngay=self.ngay.isoformat()))
        self.assertEqual(res.status_code, 200)
        o_ngay = [o for tuan in res.context['cac_tuan'] for o in tuan if o['ngay'] == self.ngay][0]
        self.assertEqual((o_ngay['dem_trong'], o_ngay['dem_giu'], o_ngay['dem_dat']), (1, 1, 1))
        for tuan in res.context['cac_tuan']:
            self.assertEqual(len(tuan), 7)
            self.assertEqual(tuan[0]['ngay'].weekday(), 0)
        self.assertContains(res, '1 trống')

    def test_thang_khong_lan_lich_nguoi_khac(self):
        self.tao_slot(nag=self.nag2)
        res = self.client.get(self.url_ds(che_do='thang', ngay=self.ngay.isoformat()))
        o_ngay = [o for tuan in res.context['cac_tuan'] for o in tuan if o['ngay'] == self.ngay][0]
        self.assertEqual(o_ngay['dem_trong'], 0)

    def test_chuyen_thang_truoc_sau(self):
        neo = self.hom_nay.replace(day=15)
        dau_thang = neo.replace(day=1)
        cuoi_thang_truoc = dau_thang - timedelta(days=1)
        dau_thang_sau = (neo.replace(day=28) + timedelta(days=5)).replace(day=1)
        res = self.client.get(self.url_ds(che_do='thang', ngay=neo.isoformat()))
        self.assertIn(cuoi_thang_truoc.isoformat(), res.context['truoc'])
        self.assertIn(dau_thang_sau.isoformat(), res.context['sau'])
        self.assertEqual(res.context['nhan_khoang'], f'Tháng {neo:%m/%Y}')

    def test_chu_thich_co_du_ba_trang_thai(self):
        res = self.client.get(self.url_ds())
        for nhan in (SL.TRONG, SL.DANG_GIU, SL.DA_DAT):
            self.assertContains(res, nhan)

    def test_dang_giu_va_da_dat_chi_xem(self):
        giu = self.tao_slot(trang_thai=SL.DANG_GIU)
        dat = self.tao_slot(bat_dau=time(14, 0), ket_thuc=time(16, 0), trang_thai=SL.DA_DAT)
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        for lich in (giu, dat):
            s = self.mo_ta_slot(res, lich)
            self.assertFalse(s['co_the_sua'])
            self.assertFalse(s['co_the_xoa'])
        self.assertNotContains(res, reverse('lich_sua', args=[giu.pk]))
        self.assertNotContains(res, reverse('lich_xoa', args=[dat.pk]))

    def test_slot_trong_co_nut_sua_va_xoa(self):
        lich = self.tao_slot()
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        self.assertContains(res, reverse('lich_sua', args=[lich.pk]))
        self.assertContains(res, reverse('lich_xoa', args=[lich.pk]))

    def test_slot_da_qua_chi_xem(self):
        qua = self.tao_slot(ngay=self.hom_nay - timedelta(days=1))
        res = self.client.get(self.url_ds(ngay=qua.Ngay.isoformat()))
        s = self.mo_ta_slot(res, qua)
        self.assertTrue(s['da_qua'])
        self.assertFalse(s['co_the_sua'])
        self.assertFalse(s['co_the_xoa'])

    def test_slot_da_dat_dan_toi_booking(self):
        dat = self.tao_slot(trang_thai=SL.DA_DAT)
        bk = self.tao_booking(dat)
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        self.assertEqual(self.mo_ta_slot(res, dat)['ma_booking'], bk.pk)
        self.assertContains(res, f'Booking #{bk.pk}')

    def test_booking_het_hieu_luc_khong_hien_tren_slot(self):
        lich = self.tao_slot(trang_thai=SL.DANG_GIU)
        self.tao_booking(lich, trang_thai=BK.DA_TU_CHOI)
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        self.assertIsNone(self.mo_ta_slot(res, lich)['ma_booking'])

    @skipUnless(CO_GIU_CHO, CHO_T34)
    def test_nha_giu_cho_het_han_truoc_khi_hien(self):                   # BR4.1-1: phải nhả trước khi hiển thị
        lich = self.tao_slot(trang_thai=SL.DANG_GIU)
        giu = self.tao_giu_cho(lich, trang_thai=GC.DANG_GIU)
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        lich.refresh_from_db()
        giu.refresh_from_db()
        self.assertEqual(lich.TrangThai, SL.TRONG)
        self.assertEqual(giu.TrangThai, GC.HET_HAN)
        self.assertEqual(self.mo_ta_slot(res, lich)['lich'].TrangThai, SL.TRONG)

    def test_giu_cho_con_han_van_hien_dang_giu(self):
        lich = self.tao_slot(trang_thai=SL.DANG_GIU)
        bg = timezone.now()
        GiuCho.objects.create(MaKhachHang=self.khach, MaLich=lich, ThoiDiemGiu=bg,
                              ThoiDiemHetHan=bg + timedelta(minutes=5), TrangThai=GC.DANG_GIU)
        self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        lich.refresh_from_db()
        self.assertEqual(lich.TrangThai, SL.DANG_GIU)

    # =================================================================
    # Thêm khung giờ (UC3.1 bước 3-7)
    # =================================================================
    def test_mo_form_them(self):
        res = self.client.get(reverse('lich_them'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Thiết lập khung giờ')
        self.assertContains(res, 'Chọn giờ')

    def test_form_them_dien_san_ngay_dang_xem(self):
        res = self.client.get(reverse('lich_them') + f'?ngay={self.ngay.isoformat()}')
        self.assertContains(res, f'value="{self.ngay.isoformat()}"')

    def test_them_thanh_cong(self):
        res = self.client.post(reverse('lich_them'), self.du_lieu())
        self.assertRedirects(res, url_lich('tuan', self.ngay))
        lich = LichKhaDung.objects.get()
        self.assertEqual((lich.MaNhiepAnhGia, lich.Ngay, lich.GioBatDau, lich.GioKetThuc),
                         (self.nag, self.ngay, time(8, 0), time(10, 0)))
        self.assertEqual(lich.TrangThai, SL.TRONG)                      # BR3.1: mới thêm là "Lịch trống"
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_THANH_CONG])   # bước 7

    def test_them_nhan_gio_dang_hh_mm(self):
        self.client.post(reverse('lich_them'), self.du_lieu(bat_dau='08:00', ket_thuc='09:30'))
        self.assertEqual(LichKhaDung.objects.get().GioKetThuc, time(9, 30))

    def test_them_lien_ke_khong_bi_coi_la_chong(self):
        self.tao_slot(bat_dau=time(8, 0), ket_thuc=time(10, 0))
        res = self.client.post(reverse('lich_them'), self.du_lieu(bat_dau=GIO_10, ket_thuc=GIO_12))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(LichKhaDung.objects.count(), 2)

    def test_them_chong_gio_bi_chan(self):                               # ngoại lệ 4a
        self.tao_slot(bat_dau=time(8, 0), ket_thuc=time(10, 0))
        truong_hop = [('07:00:00', GIO_9), (GIO_9, GIO_11), (GIO_8, GIO_10), ('08:30:00', '09:30:00'),
                      ('07:00:00', GIO_11), (GIO_8, GIO_9)]              # chồng đầu, chồng cuối, trùng hệt, nằm trong, bao ngoài, cùng giờ bắt đầu
        for bat_dau, ket_thuc in truong_hop:
            with self.subTest(bat_dau=bat_dau, ket_thuc=ket_thuc):
                res = self.client.post(reverse('lich_them'), self.du_lieu(bat_dau=bat_dau, ket_thuc=ket_thuc))
                self.assertEqual(res.status_code, 200)
                self.assertContains(res, 'bị chồng lên một khung giờ đã có', count=1)
                self.assertContains(res, 'Thông tin lịch không hợp lệ', count=1)   # chỉ MỘT hộp báo lỗi, lý do nằm trong cùng hộp
                self.assertContains(res, 'alert--danger', count=1)
                self.assertEqual(LichKhaDung.objects.count(), 1)

    def test_lich_nguoi_khac_khong_gay_chong(self):
        self.tao_slot(nag=self.nag2, bat_dau=time(8, 0), ket_thuc=time(10, 0))
        res = self.client.post(reverse('lich_them'), self.du_lieu())
        self.assertEqual(res.status_code, 302)
        self.assertEqual(LichKhaDung.objects.filter(MaNhiepAnhGia=self.nag).count(), 1)

    def test_chong_voi_ca_slot_dang_giu_va_da_dat(self):
        self.tao_slot(bat_dau=time(8, 0), ket_thuc=time(10, 0), trang_thai=SL.DA_DAT)
        res = self.client.post(reverse('lich_them'), self.du_lieu(bat_dau=GIO_9, ket_thuc=GIO_11))
        self.assertContains(res, 'bị chồng lên một khung giờ đã có')

    def test_gio_ket_thuc_phai_sau_gio_bat_dau(self):
        for bat_dau, ket_thuc in ((GIO_10, GIO_8), (GIO_10, GIO_10)):
            with self.subTest(bat_dau=bat_dau, ket_thuc=ket_thuc):
                res = self.client.post(reverse('lich_them'), self.du_lieu(bat_dau=bat_dau, ket_thuc=ket_thuc))
                self.assertEqual(res.status_code, 200)
                form = res.context['form']
                self.assertEqual(form.errors['GioKetThuc'], ['Giờ kết thúc phải sau giờ bắt đầu.'])   # đúng MỘT câu báo
                self.assertEqual(list(form.non_field_errors()), [])
                self.assertEqual(LichKhaDung.objects.count(), 0)

    def test_thieu_truong_bat_buoc(self):
        res = self.client.post(reverse('lich_them'), {})
        self.assertEqual(res.status_code, 200)
        form = res.context['form']
        for ten in ('Ngay', 'GioBatDau', 'GioKetThuc'):
            self.assertIn(ten, form.errors)
        self.assertContains(res, 'Thông tin lịch không hợp lệ')           # UC3.1 ngoại lệ 4a
        self.assertContains(res, 'Vui lòng chọn ngày.')
        self.assertEqual(LichKhaDung.objects.count(), 0)

    def test_gia_tri_ngay_gio_sai_dinh_dang(self):
        res = self.client.post(reverse('lich_them'), {'Ngay': 'abc', 'GioBatDau': '25:99', 'GioKetThuc': 'x'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(LichKhaDung.objects.count(), 0)

    def test_khong_them_vao_qua_khu(self):
        res = self.client.post(reverse('lich_them'), self.du_lieu(ngay=self.hom_nay - timedelta(days=1)))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['form'].errors['Ngay'], ['Ngày không được ở trong quá khứ.'])
        self.assertEqual(LichKhaDung.objects.count(), 0)

    def test_hom_nay_gio_da_qua_bi_chan_con_gio_toi_thi_duoc(self):
        with self.gio_gia_lap(12):
            res = self.client.post(reverse('lich_them'), self.du_lieu(ngay=self.hom_nay, bat_dau=GIO_11, ket_thuc=GIO_12))
            self.assertEqual(res.context['form'].errors['GioBatDau'], ['Giờ bắt đầu phải sau thời điểm hiện tại.'])
            res = self.client.post(reverse('lich_them'), self.du_lieu(ngay=self.hom_nay, bat_dau='12:00:00', ket_thuc='13:00:00'))
            self.assertEqual(res.status_code, 200)                       # đúng bằng giờ hiện tại cũng đã bắt đầu
            res = self.client.post(reverse('lich_them'), self.du_lieu(ngay=self.hom_nay, bat_dau='13:00:00', ket_thuc='14:00:00'))
            self.assertEqual(res.status_code, 302)
        self.assertEqual(LichKhaDung.objects.count(), 1)

    def test_khung_gio_luon_thuoc_ve_nguoi_dang_nhap(self):
        self.client.post(reverse('lich_them'), self.du_lieu(MaNhiepAnhGia=self.nag2.pk, TrangThai=SL.DA_DAT))
        lich = LichKhaDung.objects.get()
        self.assertEqual(lich.MaNhiepAnhGia, self.nag)                   # không cho gán cho người khác qua form
        self.assertEqual(lich.TrangThai, SL.TRONG)                       # không cho tự đặt trạng thái qua form

    def test_loi_luu_du_lieu_bao_thong_bao_chung(self):                  # UC3.1 ngoại lệ 6a
        with mock.patch.object(KhungGioForm, 'save', side_effect=DatabaseError('hỏng')), \
                self.assertLogs('schedule.quan_ly', level='ERROR'):
            res = self.client.post(reverse('lich_them'), self.du_lieu())
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, quan_ly.TB_LOI_LUU)
        self.assertEqual(LichKhaDung.objects.count(), 0)

    # =================================================================
    # Sửa khung giờ
    # =================================================================
    def test_mo_form_sua_dien_san_gia_tri_cu(self):
        lich = self.tao_slot()
        res = self.client.get(reverse('lich_sua', args=[lich.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Chỉnh sửa khung giờ')
        self.assertContains(res, f'value="{self.ngay.isoformat()}"')
        self.assertContains(res, '<option value="08:00:00" selected>08:00</option>')
        self.assertContains(res, '<option value="10:00:00" selected>10:00</option>')

    def test_form_sua_giu_duoc_gio_le_phut(self):                        # khung giờ cũ tạo ở admin, vd 09:15
        lich = self.tao_slot(bat_dau=time(9, 15), ket_thuc=time(10, 45))
        res = self.client.get(reverse('lich_sua', args=[lich.pk]))
        self.assertContains(res, '<option value="09:15:00" selected>09:15</option>')

    def test_sua_thanh_cong(self):
        lich = self.tao_slot()
        res = self.client.post(reverse('lich_sua', args=[lich.pk]), self.du_lieu(bat_dau=GIO_9, ket_thuc=GIO_11))
        self.assertRedirects(res, url_lich('tuan', self.ngay))
        lich.refresh_from_db()
        self.assertEqual((lich.GioBatDau, lich.GioKetThuc), (time(9, 0), time(11, 0)))
        self.assertEqual(lich.TrangThai, SL.TRONG)
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_THANH_CONG])

    def test_sua_doi_ngay(self):
        lich = self.tao_slot()
        moi = self.ngay + timedelta(days=10)
        res = self.client.post(reverse('lich_sua', args=[lich.pk]), self.du_lieu(ngay=moi))
        self.assertRedirects(res, url_lich('tuan', moi))
        lich.refresh_from_db()
        self.assertEqual(lich.Ngay, moi)

    def test_sua_khong_tu_chong_voi_chinh_no(self):
        lich = self.tao_slot(bat_dau=time(8, 0), ket_thuc=time(10, 0))
        res = self.client.post(reverse('lich_sua', args=[lich.pk]), self.du_lieu(bat_dau='08:30:00', ket_thuc='09:30:00'))
        self.assertEqual(res.status_code, 302)

    def test_sua_chong_khung_gio_khac_bi_chan(self):
        lich = self.tao_slot(bat_dau=time(8, 0), ket_thuc=time(10, 0))
        self.tao_slot(bat_dau=time(10, 0), ket_thuc=time(12, 0))
        res = self.client.post(reverse('lich_sua', args=[lich.pk]), self.du_lieu(bat_dau=GIO_9, ket_thuc=GIO_11))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'bị chồng lên một khung giờ đã có')
        lich.refresh_from_db()
        self.assertEqual((lich.GioBatDau, lich.GioKetThuc), (time(8, 0), time(10, 0)))

    def test_sua_sai_gio_giu_nguyen_du_lieu(self):
        lich = self.tao_slot()
        res = self.client.post(reverse('lich_sua', args=[lich.pk]), self.du_lieu(bat_dau=GIO_11, ket_thuc=GIO_9))
        self.assertEqual(res.status_code, 200)
        lich.refresh_from_db()
        self.assertEqual((lich.GioBatDau, lich.GioKetThuc), (time(8, 0), time(10, 0)))

    def tao_slot_dang_giu_hoac_da_dat(self, trang_thai, gio):
        lich = self.tao_slot(bat_dau=time(gio, 0), ket_thuc=time(gio + 2, 0), trang_thai=trang_thai)
        if trang_thai == SL.DANG_GIU:
            bg = timezone.now()
            GiuCho.objects.create(MaKhachHang=self.khach, MaLich=lich, ThoiDiemGiu=bg,
                                  ThoiDiemHetHan=bg + timedelta(minutes=5), TrangThai=GC.DANG_GIU)
        return lich

    def test_khong_sua_duoc_dang_giu_va_da_dat(self):
        for trang_thai, gio in ((SL.DANG_GIU, 14), (SL.DA_DAT, 17)):
            with self.subTest(trang_thai=trang_thai):
                lich = self.tao_slot_dang_giu_hoac_da_dat(trang_thai, gio)
                url = reverse('lich_sua', args=[lich.pk])
                res = self.client.get(url)
                self.assertRedirects(res, url_lich('tuan', self.ngay))
                self.assertEqual(self.tin_nhan(res), [quan_ly.TB_CHI_XEM])
                res = self.client.post(url, self.du_lieu(bat_dau=GIO_9, ket_thuc=GIO_11), follow=True)
                self.assertEqual(self.tin_nhan(res), [quan_ly.TB_CHI_XEM])
                lich.refresh_from_db()
                self.assertEqual((lich.GioBatDau, lich.TrangThai), (time(gio, 0), trang_thai))

    def test_khong_sua_slot_nguoi_khac(self):
        cua_nguoi_khac = self.tao_slot(nag=self.nag2)
        url = reverse('lich_sua', args=[cua_nguoi_khac.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.du_lieu(bat_dau=GIO_9, ket_thuc=GIO_11)).status_code, 404)
        cua_nguoi_khac.refresh_from_db()
        self.assertEqual(cua_nguoi_khac.GioBatDau, time(8, 0))

    def test_khong_sua_slot_khong_ton_tai(self):
        self.assertEqual(self.client.get(reverse('lich_sua', args=[99999])).status_code, 404)

    def test_khong_sua_slot_da_qua(self):
        qua = self.tao_slot(ngay=self.hom_nay - timedelta(days=1))
        res = self.client.get(reverse('lich_sua', args=[qua.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_DA_QUA])

    @skipUnless(CO_GIU_CHO, CHO_T34)
    def test_slot_giu_cho_het_han_duoc_nha_roi_moi_cho_sua(self):
        lich = self.tao_slot(trang_thai=SL.DANG_GIU)
        self.tao_giu_cho(lich, trang_thai=GC.DANG_GIU)                   # quá 5 phút chưa ai nhả
        res = self.client.get(reverse('lich_sua', args=[lich.pk]))
        self.assertEqual(res.status_code, 200)
        lich.refresh_from_db()
        self.assertEqual(lich.TrangThai, SL.TRONG)

    def test_luu_sua_bi_chan_neu_co_nguoi_vua_giu_cho(self):             # tình huống đua: form hợp lệ nhưng khách giữ chỗ ngay trước khi lưu
        lich = self.tao_slot()
        form = KhungGioForm(self.du_lieu(bat_dau=GIO_9, ket_thuc=GIO_11), instance=LichKhaDung.objects.get(pk=lich.pk), nag=self.nag)
        self.assertTrue(form.is_valid())
        LichKhaDung.objects.filter(pk=lich.pk).update(TrangThai=SL.DANG_GIU)
        with self.assertRaises(LichLoi) as ctx:
            quan_ly.luu_khung_gio_sua(self.nag, form)
        self.assertEqual(ctx.exception.thong_bao, quan_ly.TB_CHI_XEM)
        lich.refresh_from_db()
        self.assertEqual((lich.GioBatDau, lich.TrangThai), (time(8, 0), SL.DANG_GIU))

    # =================================================================
    # Xóa khung giờ
    # =================================================================
    def test_get_xoa_hien_trang_xac_nhan_khong_xoa(self):
        lich = self.tao_slot()
        res = self.client.get(reverse('lich_xoa', args=[lich.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Xóa khung giờ?')
        self.assertContains(res, 'sẽ không còn hiển thị cho Khách hàng')
        self.assertTrue(LichKhaDung.objects.filter(pk=lich.pk).exists())

    def test_xoa_thanh_cong(self):
        lich = self.tao_slot()
        giu_lai = self.tao_slot(bat_dau=time(14, 0), ket_thuc=time(16, 0))
        res = self.client.post(reverse('lich_xoa', args=[lich.pk]))
        self.assertRedirects(res, url_lich('tuan', self.ngay))
        self.assertFalse(LichKhaDung.objects.filter(pk=lich.pk).exists())
        self.assertTrue(LichKhaDung.objects.filter(pk=giu_lai.pk).exists())
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_THANH_CONG])

    def test_khong_xoa_duoc_dang_giu_va_da_dat(self):
        for trang_thai, gio in ((SL.DANG_GIU, 14), (SL.DA_DAT, 17)):
            with self.subTest(trang_thai=trang_thai):
                lich = self.tao_slot_dang_giu_hoac_da_dat(trang_thai, gio)
                res = self.client.post(reverse('lich_xoa', args=[lich.pk]), follow=True)
                self.assertEqual(self.tin_nhan(res), [quan_ly.TB_CHI_XEM])
                self.assertTrue(LichKhaDung.objects.filter(pk=lich.pk).exists())

    def test_khong_xoa_khi_da_co_luot_giu_cho_cu(self):                  # GIUCHO trỏ vào slot bằng khóa ngoại PROTECT
        lich = self.tao_slot()
        self.tao_giu_cho(lich, trang_thai=GC.HET_HAN)
        res = self.client.post(reverse('lich_xoa', args=[lich.pk]))      # không được sập vì ProtectedError
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_CO_LICH_SU])
        self.assertTrue(LichKhaDung.objects.filter(pk=lich.pk).exists())

    def test_khong_xoa_khi_da_co_booking_bi_tu_choi(self):               # BOOKING trỏ vào slot bằng khóa ngoại PROTECT
        lich = self.tao_slot()
        self.tao_booking(lich, trang_thai=BK.DA_TU_CHOI)
        res = self.client.post(reverse('lich_xoa', args=[lich.pk]))
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_CO_LICH_SU])
        self.assertTrue(LichKhaDung.objects.filter(pk=lich.pk).exists())

    def test_slot_co_lich_su_van_sua_duoc_nhung_khong_hien_nut_xoa(self):
        lich = self.tao_slot()
        self.tao_giu_cho(lich, trang_thai=GC.HET_HAN)
        res = self.client.get(self.url_ds(ngay=self.ngay.isoformat()))
        s = self.mo_ta_slot(res, lich)
        self.assertTrue(s['co_the_sua'])
        self.assertFalse(s['co_the_xoa'])
        self.assertContains(res, reverse('lich_sua', args=[lich.pk]))
        self.assertNotContains(res, reverse('lich_xoa', args=[lich.pk]))
        self.assertNotContains(res, 'không xóa được')                      # không giải thích dài dòng trong ô lịch

    def test_get_xoa_slot_co_lich_su_bao_loi_ngay(self):
        lich = self.tao_slot()
        self.tao_giu_cho(lich)
        res = self.client.get(reverse('lich_xoa', args=[lich.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_CO_LICH_SU])

    def test_khong_xoa_slot_nguoi_khac(self):
        cua_nguoi_khac = self.tao_slot(nag=self.nag2)
        url = reverse('lich_xoa', args=[cua_nguoi_khac.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(LichKhaDung.objects.filter(pk=cua_nguoi_khac.pk).exists())

    def test_khong_xoa_slot_da_qua(self):
        qua = self.tao_slot(ngay=self.hom_nay - timedelta(days=1))
        res = self.client.post(reverse('lich_xoa', args=[qua.pk]))
        self.assertEqual(self.tin_nhan(res), [quan_ly.TB_DA_QUA])
        self.assertTrue(LichKhaDung.objects.filter(pk=qua.pk).exists())

    def test_xoa_bang_phuong_thuc_khac_bi_tu_choi(self):
        lich = self.tao_slot()
        self.assertEqual(self.client.put(reverse('lich_xoa', args=[lich.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse('my_calendar')).status_code, 405)

    # =================================================================
    # Hàm hỗ trợ
    # =================================================================
    def test_da_bat_dau_dung_moc_gio(self):
        lich = self.tao_slot(ngay=self.hom_nay, bat_dau=time(12, 0), ket_thuc=time(13, 0))
        with self.gio_gia_lap(11, 59):
            self.assertFalse(quan_ly.da_bat_dau(lich))
        with self.gio_gia_lap(12, 0):
            self.assertTrue(quan_ly.da_bat_dau(lich))
        with self.gio_gia_lap(12, 1):
            self.assertTrue(quan_ly.da_bat_dau(lich))

    def test_phan_tich_ngay(self):
        gan = self.hom_nay + timedelta(days=5)
        self.assertEqual(quan_ly.phan_tich_ngay(gan.isoformat(), self.hom_nay), gan)
        self.assertEqual(quan_ly.phan_tich_ngay(None, self.hom_nay), self.hom_nay)
        self.assertEqual(quan_ly.phan_tich_ngay('khong-phai-ngay', self.hom_nay), self.hom_nay)
        self.assertEqual(quan_ly.phan_tich_ngay('2999-01-01', self.hom_nay), self.hom_nay)
        self.assertEqual(quan_ly.phan_tich_ngay('1900-01-01', self.hom_nay), self.hom_nay)

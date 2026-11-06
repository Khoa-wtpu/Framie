# bookings/test_qua_han.py - T10: kiểm tra tự động xử lý quá hạn. Chạy: python manage.py test bookings.test_qua_han
import tempfile
from datetime import date, time, timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings import qua_han
from bookings.models import Booking, GiuCho, LichSuTrangThaiBooking
from core.constants import (BenThucHien, DinhDangTep, HOAN_TAT_BAN_GIAO, LoaiAnh, LoaiHauKy, LoaiThanhToan,
                            LuuTruAnh, TrangThaiBooking as TT, TrangThaiGiuCho, TrangThaiSlot,
                            TrangThaiThanhToan as TTT)
from delivery.models import Anh, BanGiao
from delivery.services import duong_dan_goc          # hàm của Nguyên: đường dẫn bản gốc
from notifications.models import ThongBao
from payments.models import MinhChungThanhToan, ThanhToan
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()


# Không gửi email thật khi test (tránh chờ kết nối SMTP); email vào mail.outbox.
@override_settings(MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])   # băm mật khẩu nhanh cho test
class QuaHanBase(TestCase):
    def setUp(self):
        self.kh = User.objects.create_user('kh', 'kh@x.vn', 'p', so_dien_thoai='0900000001')
        nag_user = User.objects.create_user('nag', 'nag@x.vn', 'p', so_dien_thoai='0900000002')
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=nag_user, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',
                                              SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='G', Gia=1000000,
                                            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.dem = 0
        self.bay_gio = timezone.now()

    def slot(self, trang_thai=TrangThaiSlot.DANG_GIU):
        self.dem += 1
        return LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=10 + self.dem),
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0), TrangThai=trang_thai)

    def booking(self, trang_thai, slot_trang_thai=TrangThaiSlot.DANG_GIU, **han):
        lich = self.slot(slot_trang_thai)
        bk = Booking.objects.create(MaKhachHang=self.kh, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,
                                    NgayGioChup=self.bay_gio + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
                                    Concept='c', TongGiaTri=1000000)
        Booking.objects.filter(pk=bk.pk).update(TrangThai=trang_thai, NgayTao=self.bay_gio - timedelta(days=10), **han)
        bk.refresh_from_db()
        return bk


class HetHanDatCoc(QuaHanBase):
    def test_qua_1_ngay_chua_coc_thanh_het_han_va_nha_slot(self):
        bk = self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        self.assertEqual(qua_han.xu_ly_het_han_dat_coc(), 1)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HET_THOI_HAN_DAT_COC)
        self.assertEqual(bk.MaLich.TrangThai, TrangThaiSlot.TRONG)
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk)
        self.assertEqual((ls.TrangThaiCu, ls.TrangThaiMoi, ls.BenThucHien),
                         (TT.CHO_DAT_COC, TT.HET_THOI_HAN_DAT_COC, BenThucHien.HE_THONG))
        self.assertEqual(ThongBao.objects.filter(MaBooking=bk).count(), 2)   # báo Khách và Nhiếp ảnh gia

    def test_chua_den_han_thi_giu_nguyen(self):
        bk = self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio + timedelta(hours=1))
        self.assertEqual(qua_han.xu_ly_het_han_dat_coc(), 0)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)

    def test_khach_da_tai_minh_chung_coc_thi_khong_het_han(self):
        bk = self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.TIEN_COC, SoTien=400000,
                                 TrangThai=TTT.CHO_XAC_NHAN_COC, NgayThanhToan=self.bay_gio - timedelta(hours=2))
        self.assertEqual(qua_han.xu_ly_het_han_dat_coc(), 0)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)

    def test_chay_lai_khong_xu_ly_hai_lan(self):
        self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        self.assertEqual(qua_han.xu_ly_het_han_dat_coc(), 1)
        self.assertEqual(qua_han.xu_ly_het_han_dat_coc(), 0)


class QuaHanThanhToan(QuaHanBase):
    def _tt60(self, han, **kw):
        bk = self.booking(TT.CHO_XAC_NHAN_THANH_TOAN, TrangThaiSlot.DA_DAT, HanThanhToanConLai=han)
        tt = ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI, SoTien=600000,
                                      TrangThai=TTT.CHO_XAC_NHAN_60, **kw)
        return bk, tt

    def test_qua_2_ngay_chua_tra_60_thanh_qua_han(self):
        bk, tt = self._tt60(self.bay_gio - timedelta(hours=1))
        self.assertEqual(qua_han.xu_ly_qua_han_thanh_toan(), 1)
        tt.refresh_from_db(); bk.refresh_from_db()
        self.assertEqual(tt.TrangThai, TTT.QUA_HAN)
        self.assertEqual(bk.TrangThai, TT.CHO_XAC_NHAN_THANH_TOAN)      # Booking giữ nguyên
        self.assertEqual(ThongBao.objects.filter(MaBooking=bk).count(), 2)

    def test_chua_den_han(self):
        _, tt = self._tt60(self.bay_gio + timedelta(hours=1))
        self.assertEqual(qua_han.xu_ly_qua_han_thanh_toan(), 0)
        tt.refresh_from_db()
        self.assertEqual(tt.TrangThai, TTT.CHO_XAC_NHAN_60)

    def test_khach_da_tai_minh_chung_thi_khong_qua_han(self):
        _, tt = self._tt60(self.bay_gio - timedelta(hours=1), NgayThanhToan=self.bay_gio - timedelta(hours=3))
        MinhChungThanhToan.objects.create(MaThanhToan=tt, TenTep='a.png', DuongDanTep='a.png',
                                          DinhDangTep=DinhDangTep.PNG, KichThuocTep=10)
        self.assertEqual(qua_han.xu_ly_qua_han_thanh_toan(), 0)
        tt.refresh_from_db()
        self.assertEqual(tt.TrangThai, TTT.CHO_XAC_NHAN_60)


class XoaAnhHetHan(QuaHanBase):
    def setUp(self):
        super().setUp()
        self.thu_muc = tempfile.TemporaryDirectory()
        self.addCleanup(self.thu_muc.cleanup)
        self.goc = Path(self.thu_muc.name)
        patcher = override_settings(PRIVATE_MEDIA_ROOT=self.goc)    # kho_anh() của Nguyên đọc cài đặt này
        patcher.enable()
        self.addCleanup(patcher.disable)

    def _ban_giao(self, thoi_han):
        bk = self.booking(TT.HOAN_THANH, TrangThaiSlot.DA_DAT)
        BanGiao.objects.create(MaBooking=bk, NgayXacNhan=self.bay_gio - timedelta(days=5),
                               TrangThaiBanGiao=HOAN_TAT_BAN_GIAO, ThoiHanTaiAnh=thoi_han)
        return bk

    def _anh(self, bk, ten='x.jpg', duong_dan=None):
        duong_dan = duong_dan or f'bk{bk.pk}/{ten}'
        f = self.goc / duong_dan
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b'jpg')
        goc = self.goc / duong_dan_goc(duong_dan)                  # bản GỐC không watermark, Nguyên lưu ở thư mục "goc"
        goc.parent.mkdir(parents=True, exist_ok=True)
        goc.write_bytes(b'jpg-goc')
        self.tep_goc = goc
        return f, Anh.objects.create(MaBooking=bk, TenAnh=ten, DuongDanAnh=duong_dan, DinhDangAnh=DinhDangTep.JPG,
                                     KichThuocAnh=3, LoaiAnh=LoaiAnh.HOAN_CHINH, CoWatermark=0)

    def test_qua_han_tai_thi_xoa_file_va_danh_dau_da_xoa(self):
        bk = self._ban_giao(self.bay_gio - timedelta(minutes=1))
        f, anh = self._anh(bk)
        self.assertEqual(qua_han.xu_ly_xoa_anh_het_han(), 1)
        anh.refresh_from_db()
        self.assertFalse(f.exists())
        self.assertFalse(self.tep_goc.exists())                        # bản gốc cũng bị xóa
        self.assertEqual(anh.TrangThaiLuuTru, LuuTruAnh.DA_XOA)
        self.assertEqual(qua_han.xu_ly_xoa_anh_het_han(), 0)             # chạy lại không làm gì thêm

    def test_chua_het_han_tai_thi_giu_file(self):
        bk = self._ban_giao(self.bay_gio + timedelta(days=1))
        f, anh = self._anh(bk)
        self.assertEqual(qua_han.xu_ly_xoa_anh_het_han(), 0)
        anh.refresh_from_db()
        self.assertTrue(f.exists())
        self.assertEqual(anh.TrangThaiLuuTru, LuuTruAnh.CON_LUU)

    def test_chua_mo_quyen_tai_thi_khong_xoa(self):
        bk = self._ban_giao(None)
        f, _ = self._anh(bk)
        self.assertEqual(qua_han.xu_ly_xoa_anh_het_han(), 0)
        self.assertTrue(f.exists())

    def test_duong_dan_ngoai_thu_muc_anh_khong_bi_xoa(self):
        bk = self._ban_giao(self.bay_gio - timedelta(minutes=1))
        ngoai = Path(self.thu_muc.name).parent / 'file_ngoai_thu_muc.txt'
        ngoai.write_text('giữ lại')
        self.addCleanup(lambda: ngoai.unlink(missing_ok=True))
        Anh.objects.create(MaBooking=bk, TenAnh='l', DuongDanAnh='../file_ngoai_thu_muc.txt',
                           DinhDangAnh=DinhDangTep.JPG, KichThuocAnh=1, LoaiAnh=LoaiAnh.HOAN_CHINH, CoWatermark=0)
        qua_han.xu_ly_xoa_anh_het_han()
        self.assertTrue(ngoai.exists())


class GiuChoVaTongHop(QuaHanBase):
    def test_giu_cho_qua_5_phut_nha_slot(self):
        lich = self.slot(TrangThaiSlot.DANG_GIU)
        gc = GiuCho.objects.create(MaKhachHang=self.kh, MaLich=lich, ThoiDiemGiu=self.bay_gio - timedelta(minutes=10),
                                   ThoiDiemHetHan=self.bay_gio - timedelta(minutes=5))
        self.assertEqual(qua_han.xu_ly_qua_han()['giu_cho'], 1)
        gc.refresh_from_db(); lich.refresh_from_db()
        self.assertEqual(gc.TrangThai, TrangThaiGiuCho.HET_HAN)
        self.assertEqual(lich.TrangThai, TrangThaiSlot.TRONG)

    def test_mot_viec_loi_khong_chan_viec_khac(self):
        self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        with mock.patch.object(qua_han, 'xu_ly_giu_cho_het_han', side_effect=RuntimeError('lỗi giả')):
            kq = qua_han.xu_ly_qua_han()
        self.assertIsNone(kq['giu_cho'])
        self.assertEqual(kq['dat_coc'], 1)


class KichHoat(QuaHanBase):
    def test_mo_trang_lien_quan_thi_tu_xu_ly(self):
        bk = self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        self.client.get('/bookings/cua-toi/')      # chưa đăng nhập vẫn chạy middleware rồi mới chuyển hướng
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HET_THOI_HAN_DAT_COC)

    def test_trang_khong_lien_quan_khong_xu_ly(self):
        bk = self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        self.client.get('/dang-nhap/')
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)

    def test_lenh_chay_dinh_ky(self):
        self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        out = StringIO()
        call_command('xu_ly_qua_han', stdout=out)
        self.assertIn('Hết hạn đặt cọc: 1', out.getvalue())

    def _mo_trang_roi_kiem_tra_het_han(self, duong_dan):
        bk = self.booking(TT.CHO_DAT_COC, HanDatCoc=self.bay_gio - timedelta(hours=1))
        self.client.get(duong_dan.format(pk=bk.pk))    # chưa đăng nhập vẫn chạy middleware rồi mới chuyển hướng
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HET_THOI_HAN_DAT_COC, f'Middleware không chạy ở {duong_dan}')

    def test_mo_trang_thanh_toan_thi_tu_xu_ly(self):
        self._mo_trang_roi_kiem_tra_het_han('/booking/{pk}/minh-chung/')        # payments: tải minh chứng

    def test_mo_trang_ban_giao_thi_tu_xu_ly(self):
        self._mo_trang_roi_kiem_tra_het_han('/booking/{pk}/tai-anh/')           # delivery: Nhiếp ảnh gia tải ảnh

    def test_mo_trang_tim_kiem_thi_tu_xu_ly(self):
        self._mo_trang_roi_kiem_tra_het_han('/tim-kiem/')

    def test_tien_to_khop_duong_dan_that(self):
        """Chống lệch: mọi trang thanh toán, bàn giao, tìm kiếm, tổng quan phải nằm trong TIEN_TO_LIEN_QUAN."""
        from django.urls import reverse
        from bookings.middleware import TIEN_TO_LIEN_QUAN
        cac_trang = [('tai_len_minh_chung', {'ma_booking': 1}), ('xem_minh_chung', {'ma_minh_chung': 1}),
                     ('xac_nhan_thanh_toan_coc', {'ma_booking': 1}), ('xac_nhan_thanh_toan_con_lai', {'ma_booking': 1}),
                     ('tai_anh_len', {'ma_booking': 1}), ('xem_anh', {'ma_anh': 1}),
                     ('chon_anh_hau_ky', {'ma_booking': 1}), ('bat_dau_hau_ky', {'ma_booking': 1}),
                     ('yeu_cau_chinh_sua', {'ma_booking': 1}), ('xac_nhan_ban_giao', {'ma_booking': 1}),
                     ('tai_anh_hoan_chinh', {'ma_booking': 1}), ('search', {}), ('dashboard', {})]
        for ten, kwargs in cac_trang:
            with self.subTest(ten=ten):
                duong_dan = reverse(ten, kwargs=kwargs)
                self.assertTrue(duong_dan.startswith(TIEN_TO_LIEN_QUAN), f'{ten} -> {duong_dan} không khớp tiền tố nào')

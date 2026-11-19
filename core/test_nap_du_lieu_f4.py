# core/test_nap_du_lieu_f4.py   (task F4)
# Kiểm tra dữ liệu demo mới do nap_du_lieu_mau tạo ra. Chạy: python manage.py test core.test_nap_du_lieu_f4
import os
import tempfile
from datetime import timedelta
from io import StringIO
from unittest import mock
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.models import Booking
from bookings.the_thoi_tiet import _khu_vuc_can_tra
from core.constants import TrangThaiBooking, TrangThaiSlot
from delivery.models import Anh
from profiles.models import GoiDichVu, HinhAnhProject, NhiepAnhGia, Project
from schedule.models import LichKhaDung

CO_ANH_THAT = (Path(settings.BASE_DIR) / 'du_lieu_mau' / 'anh' / 'avatar' / 'nag05.jpg').is_file()


class DuLieuDemoTest(TestCase):
    @classmethod
    def setUpClass(cls):
        # Phải bật thư mục tạm TRƯỚC super().setUpClass(), vì setUpTestData (nạp dữ liệu) chạy bên trong nó;
        # nếu không, ảnh mẫu sẽ bị ghi vào thư mục media thật của dự án.
        cls._tam = tempfile.TemporaryDirectory()
        cls._ghi_de = override_settings(MEDIA_ROOT=cls._tam.name + '/media', PRIVATE_MEDIA_ROOT=cls._tam.name + '/rieng')
        cls._ghi_de.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._ghi_de.disable()
        cls._tam.cleanup()
        super().tearDownClass()

    @classmethod
    def nap(cls, *args):
        out = StringIO()
        call_command('nap_du_lieu_mau', *args, stdout=out)
        return out.getvalue()

    def nag05(self):
        return NhiepAnhGia.objects.get(MaTaiKhoan__username='nag05')


class DuLieuDemoCauTrucTest(DuLieuDemoTest):
    @classmethod
    def setUpTestData(cls):
        cls.nap('--khong-anh-that')          # nạp một lần cho cả lớp; không phụ thuộc có ảnh thật hay không

    def test_so_luong_booking(self):
        self.assertEqual(Booking.objects.count(), 19 + 14)

    def test_bay_nag_da_duyet_deu_nhan_khach_o_da_nang(self):
        da_nang = NhiepAnhGia.objects.filter(khu_vuc__TenKhuVuc='Đà Nẵng', MaTaiKhoan__trang_thai_ho_so='Đã duyệt')
        self.assertEqual(da_nang.count(), 7)

    def test_lich_trong_phu_45_ngay(self):
        homnay = timezone.localdate()
        for n in NhiepAnhGia.objects.filter(MaTaiKhoan__trang_thai_ho_so='Đã duyệt'):
            trong = LichKhaDung.objects.filter(MaNhiepAnhGia=n, TrangThai=TrangThaiSlot.TRONG, Ngay__gt=homnay)
            self.assertGreaterEqual(trong.count(), 30, n)
            self.assertGreaterEqual(max(trong.values_list('Ngay', flat=True)) - homnay, timedelta(days=40), n)
            self.assertTrue(trong.filter(Ngay__lte=homnay + timedelta(days=7)).exists(), n)

    def test_nag_chinh_co_nhieu_goi_khac_loai_hinh(self):
        goi = GoiDichVu.objects.filter(MaNhiepAnhGia=self.nag05(), TrangThai='Đang áp dụng')
        self.assertGreaterEqual(goi.count(), 6)
        self.assertEqual({g.MaLoaiHinh.TenLoaiHinh for g in goi}, {'Chân dung', 'Cưới', 'Gia đình'})
        self.assertGreater(len({g.Gia for g in goi}), 4)

    def test_nag_chinh_co_3_project(self):
        ds = list(Project.objects.filter(MaNhiepAnhGia=self.nag05()).order_by('pk'))
        self.assertEqual([p.TenProject for p in ds], ['Cưới - Khởi đầu mới', 'Gia đình - Khoảnh khắc lưu mãi', 'Chân dung'])
        self.assertEqual([HinhAnhProject.objects.filter(MaProject=p).count() for p in ds], [8, 8, 7])

    def test_booking_thoi_tiet_trong_16_ngay_o_da_nang(self):
        bk = Booking.objects.get(MaKhachHang__username='kh01', MaNhiepAnhGia=self.nag05(), DiaDiem='Đà Nẵng - Bãi Xép',
                                 TrangThai=TrangThaiBooking.CHOT_BOOKING, NgayGioChup__gt=timezone.now())
        cho = timezone.now()
        self.assertLess(bk.NgayGioChup - cho, timedelta(days=16))
        self.assertGreater(bk.NgayGioChup, cho)
        self.assertEqual([k.TenKhuVuc for k in _khu_vuc_can_tra(bk)], ['Đà Nẵng'])   # đúng khu vực để thẻ thời tiết tra

    def test_booking_cho_nag_chinh_chap_nhan(self):
        bk = Booking.objects.get(MaNhiepAnhGia=self.nag05(), TrangThai=TrangThaiBooking.CHO_XAC_NHAN)
        self.assertTrue(bk.DiaDiem.startswith('Đà Nẵng'))

    def test_booking_slider_co_cap_anh_truoc_sau(self):
        bk = Booking.objects.get(MaNhiepAnhGia=self.nag05(), MaKhachHang__username='kh01',
                                 TrangThai=TrangThaiBooking.CHO_KH_KIEM_TRA)
        anh = Anh.objects.filter(MaBooking=bk)
        self.assertEqual(anh.count(), 7)
        self.assertEqual(anh.exclude(DuongDanAnhTruoc__isnull=True).exclude(DuongDanAnhTruoc='').count(), 3)

    def test_nap_lai_khi_khach_mau_da_nhan_tin_thu(self):
        """kh01 nhắn thử với các NAG mẫu rồi nạp lại: cuộc trò chuyện của khách mẫu được xóa cùng, lệnh không báo lỗi."""
        from chat.models import CuocTroChuyen, TinNhan
        from django.contrib.auth import get_user_model
        kh = get_user_model().objects.get(username='kh01')
        for u in ('nag01', 'nag05'):
            cuoc = CuocTroChuyen.objects.create(MaKhachHang=kh, MaNhiepAnhGia=NhiepAnhGia.objects.get(MaTaiKhoan__username=u))
            TinNhan.objects.create(MaCuocTroChuyen=cuoc, MaNguoiGui=kh, NoiDung='Chào bạn')
        self.nap('--khong-anh-that', '--khong-danh-gia-nen')
        self.assertEqual(CuocTroChuyen.objects.count(), 0)
        self.assertEqual(TinNhan.objects.count(), 0)
        self.assertEqual(Booking.objects.count(), 19)

    def test_moi_booking_dung_dia_diem_trong_khu_vuc_cua_nag(self):
        for bk in Booking.objects.select_related('MaNhiepAnhGia'):
            kv = {k.TenKhuVuc for k in bk.MaNhiepAnhGia.khu_vuc.all()}
            self.assertIn(bk.DiaDiem.split(' - ')[0], kv, bk.pk)


import unittest


@unittest.skipUnless(CO_ANH_THAT, 'chưa có du_lieu_mau/anh')
class DuLieuDemoAnhThatTest(DuLieuDemoTest):
    @classmethod
    def setUpTestData(cls):
        cls.nap()

    def test_anh_dai_dien_that_cho_7_nag(self):
        for i in range(1, 8):
            n = NhiepAnhGia.objects.get(MaTaiKhoan__username=f'nag0{i}')
            self.assertTrue(str(n.AnhDaiDien).endswith(f'mau_nag0{i}.jpg'), n.AnhDaiDien)
            self.assertTrue((Path(settings.MEDIA_ROOT) / str(n.AnhDaiDien)).is_file())

    def test_portfolio_giu_nguyen_tep_goc(self):
        goc = Path(settings.BASE_DIR) / 'du_lieu_mau' / 'anh' / 'nag05'
        p = Project.objects.get(MaNhiepAnhGia=self.nag05(), TenProject='Cưới - Khởi đầu mới')
        ha = HinhAnhProject.objects.filter(MaProject=p).order_by('ThuTu').first()
        self.assertEqual((Path(settings.MEDIA_ROOT) / str(ha.DuongDanHinhAnh)).read_bytes(), (goc / 'cuoi' / '01.jpg').read_bytes())
        self.assertTrue((Path(settings.MEDIA_ROOT) / str(p.AnhBia)).is_file())

    def test_ca_3_nag_noi_bat_o_trang_chu_deu_co_anh_bia_that(self):
        from profiles.services import nhiep_anh_gia_noi_bat
        ds = nhiep_anh_gia_noi_bat(3)
        self.assertEqual({d['nhiep_anh_gia'].MaTaiKhoan.username for d in ds}, {'nag02', 'nag05', 'nag06'})
        for d in ds:
            self.assertTrue(str(d['anh_portfolio']).endswith('.jpg'), (d['ten'], d['anh_portfolio']))
            self.assertTrue((Path(settings.MEDIA_ROOT) / str(d['anh_portfolio'])).is_file())
        bia = [str(d['anh_portfolio']) for d in ds]
        self.assertEqual(len(set(bia)), 3)                         # không có hai thẻ dùng cùng một ảnh
        # Ảnh bìa của 2 NAG nổi bật còn lại phải là ảnh sạch (không logo/watermark của bên khác) trong du_lieu_mau/anh/nag05
        goc = Path(settings.BASE_DIR) / 'du_lieu_mau' / 'anh' / 'nag05'
        sach = {(goc / k / f).read_bytes() for k, ds_f in __import__('core.management.commands._du_lieu_mau', fromlist=['x']).ANH_BIA_SACH.items() for f in ds_f}
        for d in ds:
            if d['nhiep_anh_gia'].MaTaiKhoan.username != 'nag05':
                self.assertIn((Path(settings.MEDIA_ROOT) / str(d['anh_portfolio'])).read_bytes(), sach)

    def test_slider_truoc_mau_sau_den_trang(self):
        from PIL import Image
        bk = Booking.objects.get(MaNhiepAnhGia=self.nag05(), TrangThai=TrangThaiBooking.CHO_KH_KIEM_TRA)
        a = Anh.objects.filter(MaBooking=bk).exclude(DuongDanAnhTruoc__isnull=True).order_by('pk').first()
        goc = Path(settings.PRIVATE_MEDIA_ROOT)

        def do_mau(duong_dan):
            im = Image.open(goc / duong_dan).convert('RGB').resize((64, 64))
            return sum(max(px) - min(px) for px in im.getdata()) / (64 * 64)
        self.assertLess(do_mau(a.DuongDanAnh), 6)          # bản hiện tại: đen trắng
        self.assertGreater(do_mau(a.DuongDanAnhTruoc), 12)  # bản trước: có màu


class DuLieuDemoEmailThatTest(DuLieuDemoTest):
    """DEMO_EMAIL_<USER> trong .env: ..."""
    MOI_TRUONG = {'DEMO_EMAIL_NAG05': 'nguoi.demo+nag05@gmail.com', 'DEMO_EMAIL_KH01': 'nguoi.demo+kh01@gmail.com'}
    KHONG_EMAIL_THAT = {'DEMO_EMAIL_NAG05': '', 'DEMO_EMAIL_KH01': ''}

    def setUp(self):
        super().setUp()
        # Mặc định mọi test chạy như "máy chưa đặt email thật", bất kể .env của người chạy có gì.
        p = mock.patch.dict(os.environ, self.KHONG_EMAIL_THAT)
        p.start()
        self.addCleanup(p.stop)

    def test_dat_email_that_cho_nag05_va_kh01(self):
        User = get_user_model()
        with mock.patch.dict(os.environ, self.MOI_TRUONG):
            out = self.nap('--khong-anh-that', '--khong-danh-gia-nen')
        self.assertEqual(User.objects.get(username='nag05').email, 'nguoi.demo+nag05@gmail.com')
        self.assertEqual(User.objects.get(username='kh01').email, 'nguoi.demo+kh01@gmail.com')
        self.assertEqual(User.objects.get(username='nag01').email, 'nag01@example.com')   # các tài khoản khác vẫn là email giả
        self.assertIn('nguoi.demo+nag05@gmail.com', out)                                    # tóm tắt in ra email đăng nhập

    def test_nap_lai_nhieu_lan_khong_nhan_doi_tai_khoan(self):
        User = get_user_model()
        with mock.patch.dict(os.environ, self.MOI_TRUONG):
            self.nap('--khong-anh-that', '--khong-danh-gia-nen')
            self.nap('--khong-anh-that', '--khong-danh-gia-nen')      # lần 2: tìm ra tài khoản mang email thật để xóa
        self.assertEqual(User.objects.filter(username__in=['nag05', 'kh01']).count(), 2)
        self.assertEqual(Booking.objects.count(), 19)

    def test_doi_tu_email_gia_sang_email_that(self):
        User = get_user_model()
        self.nap('--khong-anh-that', '--khong-danh-gia-nen')               # lần đầu: chưa có .env -> email giả
        self.assertEqual(User.objects.get(username='kh01').email, 'kh01@example.com')
        with mock.patch.dict(os.environ, self.MOI_TRUONG):
            self.nap('--khong-anh-that', '--khong-danh-gia-nen')           # đặt email thật rồi nạp lại -> thay email, không lỗi
        self.assertEqual(User.objects.get(username='kh01').email, 'nguoi.demo+kh01@gmail.com')
        self.assertEqual(User.objects.filter(username='kh01').count(), 1)

    def test_email_khong_hop_le_hoac_trung_nhau_bi_chan_truoc_khi_xoa(self):
        self.nap('--khong-anh-that', '--khong-danh-gia-nen')
        for moi_truong, loi in (({'DEMO_EMAIL_NAG05': 'khong-phai-email'}, 'không phải địa chỉ email hợp lệ'),
                                ({'DEMO_EMAIL_NAG05': 'a@gmail.com', 'DEMO_EMAIL_KH01': 'A@gmail.com'}, 'trùng với'),
                                ({'DEMO_EMAIL_KH01': 'x@example.com'}, 'không được dùng đuôi')):
            with mock.patch.dict(os.environ, moi_truong), self.assertRaises(CommandError) as ctx:
                self.nap('--khong-anh-that', '--khong-danh-gia-nen')
            self.assertIn(loi, str(ctx.exception))
        self.assertEqual(Booking.objects.count(), 19)                     # dữ liệu cũ còn nguyên: lỗi được báo trước khi xóa

    def test_tai_khoan_that_trung_email_bi_bao_loi(self):
        User = get_user_model()
        User.objects.create_user(username='nguoi_that', email='nguoi.demo+kh01@gmail.com', password='Abc12345!',
                                 so_dien_thoai='0987654321')
        with mock.patch.dict(os.environ, self.MOI_TRUONG), self.assertRaises(CommandError):
            self.nap('--khong-anh-that', '--khong-danh-gia-nen')

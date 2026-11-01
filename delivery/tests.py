# Chạy: python manage.py test delivery      (N4: UC5.3 tải ảnh lên hệ thống)
import io
import itertools
import tempfile
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from PIL import Image

from bookings.models import Booking, LichSuTrangThaiBooking
from core.constants import BenThucHien, LoaiAnh, LoaiHauKy, TrangThaiBooking as TT
from delivery import services
from delivery.forms import TaiAnhForm
from delivery.models import Anh, YeuCauChinhSua, YeuCauChinhSua_Anh
from delivery.watermark import chen_watermark
from notifications.models import ThongBao
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()
NGAY_KE_TIEP = itertools.count(1)                            # mỗi Booking một ngày khác nhau để khung giờ không trùng


def tep_anh(ten='a.jpg', dinh_dang='JPEG', kich_thuoc=(80, 60)):   # tạo tệp ảnh thật trong bộ nhớ
    bo_nho = io.BytesIO()
    Image.new('RGB', kich_thuoc, (30, 120, 200)).save(bo_nho, dinh_dang)
    return SimpleUploadedFile(ten, bo_nho.getvalue())


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())      # tệp test ghi vào thư mục tạm, không đụng private_media
class TaiAnhTests(TestCase):                                   # nghiệp vụ UC5.3
    @classmethod
    def setUpTestData(cls):
        cls.kh = User.objects.create_user('kh', 'kh@x.vn', 'p', so_dien_thoai='0900000001')
        cls.nag_user = User.objects.create_user('nag', 'nag@x.vn', 'p', so_dien_thoai='0900000002')
        cls.nag_khac = User.objects.create_user('nag2', 'nag2@x.vn', 'p', so_dien_thoai='0900000003')
        cls.nag = NhiepAnhGia.objects.create(MaTaiKhoan=cls.nag_user, AnhDaiDien='a.jpg', GioiThieu='x',
                                             NganHang='B', SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        cls.goi_gh = GoiDichVu.objects.create(MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G1', Gia=1000000,
                                              ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.GIOI_HAN, SoAnhHauKyToiDa=5)
        cls.goi_tb = GoiDichVu.objects.create(MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G2', Gia=1000000,
                                              ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)

    def tao_booking(self, goi, trang_thai):                    # Booking ở trạng thái mong muốn
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=10 + next(NGAY_KE_TIEP)),
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0))
        bk = Booking.objects.create(MaKhachHang=self.kh, MaNhiepAnhGia=self.nag, MaGoi=goi, MaLich=lich,
                                    NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
                                    Concept='c', TongGiaTri=goi.Gia)
        cap_nhat = {'TrangThai': trang_thai}
        if trang_thai == TT.DANG_HAU_KY:
            cap_nhat['HanHauKy'] = timezone.now() + timedelta(days=3)
        Booking.objects.filter(pk=bk.pk).update(**cap_nhat)
        bk.refresh_from_db()
        return bk

    def tao_anh(self, bk, ten, loai=LoaiAnh.CHUA_HAU_KY, chon=0, ngay=None, that=False):   # tạo bản ghi ảnh (that=True: tạo cả tệp thật)
        duong_dan = f'booking_{bk.pk}/{ten}'
        if that:
            kho = services.kho_anh()
            kho.save(duong_dan, ContentFile(b'cu'))
            kho.save(services.duong_dan_goc(duong_dan), ContentFile(b'cu-goc'))
        return Anh.objects.create(MaBooking=bk, TenAnh=ten, DuongDanAnh=duong_dan, DinhDangAnh='JPG',
                                  KichThuocAnh=100, LoaiAnh=loai, DuocChonHauKy=chon,
                                  NgayTaiLen=ngay or timezone.now() - timedelta(days=5))

    # ---------------- Giai đoạn 1: ảnh chưa hậu kỳ ----------------
    def test_tai_anh_goc_goi_gioi_han(self):
        bk = self.tao_booking(self.goi_gh, TT.DA_CHUP)
        kq = services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('a1.jpg'), tep_anh('a2.png', 'PNG'), tep_anh('a3.jpeg')])
        self.assertEqual(kq['so_anh'], 3)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_KH_CHON_ANH)                                  # gói giới hạn: Khách chọn ảnh
        self.assertAlmostEqual((bk.HanChonAnh - timezone.now()).total_seconds(), 2 * 86400, delta=120)   # hạn 2 ngày
        kho = services.kho_anh()
        anhs = list(Anh.objects.filter(MaBooking=bk))
        self.assertEqual(len(anhs), 3)
        for a in anhs:
            self.assertEqual((a.LoaiAnh, a.CoWatermark, a.PhienBanAnh, a.DuocChonHauKy), (LoaiAnh.CHUA_HAU_KY, 1, 1, 0))
            self.assertTrue(kho.exists(a.DuongDanAnh))                                     # bản có watermark
            self.assertTrue(kho.exists(services.duong_dan_goc(a.DuongDanAnh)))             # bản gốc
        a = anhs[0]
        self.assertNotEqual(kho.open(a.DuongDanAnh).read(), kho.open(services.duong_dan_goc(a.DuongDanAnh)).read())
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())
        self.assertTrue(LichSuTrangThaiBooking.objects.filter(
            MaBooking=bk, TrangThaiMoi=TT.CHO_KH_CHON_ANH, BenThucHien=BenThucHien.NHIEP_ANH_GIA).exists())

    def test_tai_anh_goc_goi_toan_bo_vao_cho_hau_ky(self):
        bk = self.tao_booking(self.goi_tb, TT.DA_CHUP)
        services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('b1.jpg')])
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_HAU_KY)                                       # bỏ qua bước Khách chọn ảnh

    def test_ten_trung_voi_anh_da_co_bi_chan(self):
        bk = self.tao_booking(self.goi_gh, TT.DA_CHUP)
        self.tao_anh(bk, 'X1.jpg')
        with self.assertRaises(services.LoiTaiAnh):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('x1.png', 'PNG')])          # cùng tên, khác đuôi, khác hoa/thường
        self.assertEqual(Anh.objects.filter(MaBooking=bk).count(), 1)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.DA_CHUP)                                          # lỗi thì Booking giữ nguyên

    def test_trung_ten_trong_cung_lan_tai_bi_chan(self):
        bk = self.tao_booking(self.goi_gh, TT.DA_CHUP)
        with self.assertRaises(services.LoiTaiAnh):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('a.jpg'), tep_anh('a.png', 'PNG')])
        self.assertFalse(Anh.objects.filter(MaBooking=bk).exists())

    def test_sai_trang_thai_booking_bi_chan(self):
        bk = self.tao_booking(self.goi_gh, TT.CHO_DAT_COC)
        with self.assertRaises(services.LoiTaiAnh):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh()])

    def test_nhiep_anh_gia_khac_bi_chan(self):
        bk = self.tao_booking(self.goi_gh, TT.DA_CHUP)
        with self.assertRaises(services.LoiTaiAnh):
            services.tai_anh_len(bk.pk, self.nag_khac, [tep_anh()])

    # ---------------- Giai đoạn 2: ảnh đã hậu kỳ ----------------
    def booking_dang_hau_ky(self):                             # gói giới hạn: p1, p2 Khách đã chọn; p3 không chọn
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)
        self.tao_anh(bk, 'p1.jpg', chon=1, that=True)
        self.tao_anh(bk, 'p2.jpg', chon=1)
        self.tao_anh(bk, 'p3.jpg', chon=0)
        return bk

    def test_hau_ky_tung_dot_den_khi_du_thi_chuyen_cho_khach_kiem_tra(self):
        bk = self.booking_dang_hau_ky()
        kq = services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('P1.JPG')])                # khớp tên không phân biệt hoa/thường
        self.assertEqual((kq['trang_thai_moi'], kq['con_thieu']), (None, 1))
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)                                      # còn thiếu ảnh nên chưa chuyển
        self.assertFalse(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())
        kq = services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('p2.jpg')])
        self.assertEqual(kq['trang_thai_moi'], TT.CHO_KH_KIEM_TRA)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)
        p1, p3 = Anh.objects.get(MaBooking=bk, TenAnh__iexact='p1.jpg'), Anh.objects.get(MaBooking=bk, TenAnh='p3.jpg')
        self.assertEqual((p1.LoaiAnh, p1.PhienBanAnh, p1.CoWatermark), (LoaiAnh.DA_HAU_KY, 1, 1))   # lần đầu hậu kỳ: chưa tăng phiên bản
        self.assertEqual(p3.LoaiAnh, LoaiAnh.CHUA_HAU_KY)                                   # ảnh không được chọn: giữ nguyên
        self.assertEqual(Anh.objects.filter(MaBooking=bk).count(), 3)                       # mỗi ảnh vẫn một bản ghi
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())

    def test_ten_khong_khop_anh_can_hau_ky_bi_chan(self):
        bk = self.booking_dang_hau_ky()
        with self.assertRaises(services.LoiTaiAnh):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('p3.jpg')])                 # p3 không nằm trong ảnh Khách chọn
        with self.assertRaises(services.LoiTaiAnh):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('khong-co.jpg')])

    def test_ban_hau_ky_thay_the_va_xoa_file_cu(self):
        bk = self.booking_dang_hau_ky()
        p1 = Anh.objects.get(MaBooking=bk, TenAnh='p1.jpg')
        kho, cu = services.kho_anh(), p1.DuongDanAnh
        self.assertTrue(kho.exists(cu))
        with self.captureOnCommitCallbacks(execute=True):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('p1.jpg')])
        p1.refresh_from_db()
        self.assertNotEqual(p1.DuongDanAnh, cu)
        self.assertFalse(kho.exists(cu))                                                   # chỉ giữ bản mới nhất: file cũ bị xóa
        self.assertFalse(kho.exists(services.duong_dan_goc(cu)))
        self.assertTrue(kho.exists(p1.DuongDanAnh))

    def test_tai_lai_sau_yeu_cau_chinh_sua_tang_phien_ban(self):
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)
        q1 = self.tao_anh(bk, 'q1.jpg', loai=LoaiAnh.DA_HAU_KY, chon=1, ngay=timezone.now() - timedelta(days=3))
        q2 = self.tao_anh(bk, 'q2.jpg', loai=LoaiAnh.DA_HAU_KY, chon=1, ngay=timezone.now() - timedelta(days=3))
        yc = YeuCauChinhSua.objects.create(MaBooking=bk, NgayYeuCau=timezone.now() - timedelta(days=1),
                                           NoiDung='Sáng hơn', SoLanYeuCau=1)
        YeuCauChinhSua_Anh.objects.create(MaYeuCauChinhSua=yc, MaAnh=q1, NoiDungChinhSua='Sáng hơn')   # chỉ q1 cần sửa
        kq = services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('q1.jpg')])
        self.assertEqual(kq['trang_thai_moi'], TT.CHO_KH_KIEM_TRA)
        q1.refresh_from_db(); q2.refresh_from_db()
        self.assertEqual((q1.PhienBanAnh, q2.PhienBanAnh), (2, 1))                         # chỉ ảnh được sửa tăng phiên bản


class TaiAnhFormTests(TestCase):                               # bước 4 / ngoại lệ 4a: kiểm tra định dạng, dung lượng, số lượng
    def form(self, *ds_tep):
        return TaiAnhForm({}, MultiValueDict({'anh': list(ds_tep)}))

    def test_nhan_jpg_jpeg_png(self):
        self.assertTrue(self.form(tep_anh('a.jpg'), tep_anh('b.jpeg'), tep_anh('c.png', 'PNG')).is_valid())

    def test_khong_chon_tep(self):
        self.assertFalse(self.form().is_valid())

    def test_sai_duoi_hoac_dinh_dang_that(self):
        self.assertFalse(self.form(tep_anh('a.gif', 'GIF')).is_valid())                    # sai đuôi
        self.assertFalse(self.form(tep_anh('a.png', 'GIF')).is_valid())                    # đổi đuôi gif thành png
        self.assertFalse(self.form(SimpleUploadedFile('a.jpg', b'khong phai anh')).is_valid())   # không phải ảnh thật

    def test_qua_dung_luong(self):
        lon = SimpleUploadedFile('a.png', b'x' * (services.DUNG_LUONG_TOI_DA + 1))
        self.assertFalse(self.form(lon).is_valid())

    def test_qua_so_luong(self):
        nhieu = [tep_anh(f'a{i}.png', 'PNG', (8, 8)) for i in range(services.SO_ANH_TOI_DA + 1)]
        self.assertFalse(self.form(*nhieu).is_valid())


class WatermarkTests(TestCase):                                # bước 6: chèn watermark
    def test_anh_thay_doi_nhung_giu_nguyen_kich_thuoc_va_dinh_dang(self):
        goc = tep_anh('a.jpg', 'JPEG', (320, 200))
        kq = Image.open(io.BytesIO(chen_watermark(goc, 'JPEG')))
        self.assertEqual((kq.size, kq.format), ((320, 200), 'JPEG'))
        goc.seek(0)
        self.assertNotEqual(chen_watermark(goc, 'JPEG'), tep_anh('a.jpg', 'JPEG', (320, 200)).read())

    def test_png(self):
        kq = Image.open(io.BytesIO(chen_watermark(tep_anh('a.png', 'PNG', (100, 300)), 'PNG')))
        self.assertEqual((kq.size, kq.format), ((100, 300), 'PNG'))

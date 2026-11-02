# Chạy: python manage.py test delivery      (N4: UC5.3 tải ảnh lên hệ thống; N5: watermark và bảo vệ ảnh)
import io
import itertools
import os
import tempfile
import time as dong_ho
from datetime import date, time, timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from PIL import Image

from bookings.models import Booking, LichSuTrangThaiBooking
from core.constants import BenThucHien, LoaiAnh, LoaiHauKy, TrangThaiBooking as TT
from delivery import services
from delivery.forms import TaiAnhForm
from delivery.models import Anh, YeuCauChinhSua, YeuCauChinhSua_Anh
from delivery.watermark import GIOI_HAN_GIAY, chen_watermark
from notifications.models import ThongBao
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()
urlpatterns = [path('', include('delivery.urls')),            # bảng đường dẫn riêng cho test (không phụ thuộc config/urls.py)
               path('dang-nhap/', lambda request: HttpResponse('dang nhap'), name='login')]   # LOGIN_URL = 'login' cần có tên này để chuyển hướng
NGAY_KE_TIEP = itertools.count(1)                            # mỗi Booking một ngày khác nhau để khung giờ không trùng


def tep_anh(ten='a.jpg', dinh_dang='JPEG', kich_thuoc=(80, 60)):   # tạo tệp ảnh thật trong bộ nhớ
    bo_nho = io.BytesIO()
    Image.new('RGB', kich_thuoc, (30, 120, 200)).save(bo_nho, dinh_dang)
    return SimpleUploadedFile(ten, bo_nho.getvalue())


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(), ROOT_URLCONF='delivery.tests')   # tệp test ghi vào thư mục tạm, không đụng private_media
class _NenAnh(TestCase):                                       # dữ liệu nền + hàm tạo Booking/ảnh dùng chung (không có test riêng)
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


class TaiAnhTests(_NenAnh):                                    # N4 / UC5.3: nghiệp vụ tải ảnh
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


class BaoVeAnhTests(_NenAnh):                                  # N5: watermark và bảo vệ ảnh
    def anh_da_tai(self):                                      # Booking đã có 1 ảnh tải qua hệ thống (có watermark)
        bk = self.tao_booking(self.goi_gh, TT.DA_CHUP)
        tep = tep_anh('s1.jpg')
        self.ban_goc = tep.read()
        tep.seek(0)
        services.tai_anh_len(bk.pk, self.nag_user, [tep])
        return bk, Anh.objects.get(MaBooking=bk)

    def noi_dung(self, phan_hoi):                              # đọc toàn bộ nội dung FileResponse
        return b''.join(phan_hoi.streaming_content)

    def test_khach_va_nhiep_anh_gia_cua_booking_xem_duoc_ban_co_watermark(self):
        bk, anh = self.anh_da_tai()
        for nguoi in (self.kh, self.nag_user):
            self.client.force_login(nguoi)
            phan_hoi = self.client.get(reverse('xem_anh', args=[anh.pk]))
            self.assertEqual(phan_hoi.status_code, 200)
            self.assertNotEqual(self.noi_dung(phan_hoi), self.ban_goc)              # luôn là bản có watermark, không bao giờ là bản gốc
            self.assertEqual(phan_hoi['Content-Disposition'], 'inline')             # chỉ xem, không tự tải
            self.assertIn('no-store', phan_hoi['Cache-Control'])
            self.assertEqual(phan_hoi['X-Content-Type-Options'], 'nosniff')

    def test_nguoi_ngoai_quan_tri_va_khach_vang_lai_khong_xem_duoc(self):
        bk, anh = self.anh_da_tai()
        quan_tri = User.objects.create_superuser('root', 'root@x.vn', 'p', so_dien_thoai='0900000008')
        for nguoi in (self.nag_khac, quan_tri):                # đúng khách và nhiếp ảnh gia của Booking mới được xem
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get(reverse('xem_anh', args=[anh.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('xem_anh', args=[anh.pk])).status_code, 302)   # chưa đăng nhập: chuyển về trang đăng nhập

    def test_thu_muc_anh_khong_nam_trong_media_cong_khai(self):
        bk, anh = self.anh_da_tai()
        kho = services.kho_anh()
        self.assertFalse(Path(kho.location).resolve().is_relative_to(Path(settings.MEDIA_ROOT).resolve()))
        self.assertTrue(kho.exists(services.duong_dan_goc(anh.DuongDanAnh)))        # bản gốc có, nhưng chỉ nằm trong thư mục riêng

    def test_anh_da_xoa_khong_xem_duoc(self):
        bk, anh = self.anh_da_tai()
        Anh.objects.filter(pk=anh.pk).update(TrangThaiLuuTru='Đã xóa')
        self.client.force_login(self.kh)
        self.assertEqual(self.client.get(reverse('xem_anh', args=[anh.pk])).status_code, 404)

    def test_anh_hoan_chinh_khong_watermark(self):
        bk = self.tao_booking(self.goi_tb, TT.DA_CHUP)                              # gói hậu kỳ toàn bộ
        tep_goc = tep_anh('h1.jpg', 'JPEG', (80, 60))
        services.tai_anh_len(bk.pk, self.nag_user, [tep_goc])
        Booking.objects.filter(pk=bk.pk).update(TrangThai=TT.DANG_HAU_KY, HanHauKy=timezone.now() + timedelta(days=3))
        tep_hau_ky = tep_anh('h1.jpg', 'JPEG', (90, 70))                            # bản đã chỉnh sửa
        ban_hau_ky = tep_hau_ky.read()
        tep_hau_ky.seek(0)
        services.tai_anh_len(bk.pk, self.nag_user, [tep_hau_ky])
        anh = Anh.objects.get(MaBooking=bk)
        self.assertEqual((anh.LoaiAnh, anh.CoWatermark), (LoaiAnh.DA_HAU_KY, 1))    # trước khi thanh toán đủ: còn watermark
        kho, ban_co_wm = services.kho_anh(), anh.DuongDanAnh

        with self.captureOnCommitCallbacks(execute=True):
            so_anh = services.chuyen_thanh_anh_hoan_chinh(bk)

        anh.refresh_from_db()
        self.assertEqual(so_anh, 1)
        self.assertEqual((anh.LoaiAnh, anh.CoWatermark, anh.PhienBanAnh), (LoaiAnh.HOAN_CHINH, 0, 1))
        self.assertEqual(kho.open(anh.DuongDanAnh).read(), ban_hau_ky)              # đúng bản đã hậu kỳ, KHÔNG có watermark
        self.assertFalse(kho.exists(ban_co_wm))                                     # bản có watermark đã bị xóa
        self.client.force_login(self.kh)                                            # trang xem ảnh không phục vụ ảnh Hoàn chỉnh (do chức năng tải ảnh của Khách xử lý)
        self.assertEqual(self.client.get(reverse('xem_anh', args=[anh.pk])).status_code, 403)

    def test_chi_chuyen_anh_da_hau_ky(self):
        bk = self.tao_booking(self.goi_gh, TT.CHO_KH_KIEM_TRA)
        chua = self.tao_anh(bk, 'c1.jpg', loai=LoaiAnh.CHUA_HAU_KY)
        self.assertEqual(services.chuyen_thanh_anh_hoan_chinh(bk), 0)               # không có ảnh Đã hậu kỳ thì không đổi gì
        chua.refresh_from_db()
        self.assertEqual((chua.LoaiAnh, chua.CoWatermark), (LoaiAnh.CHUA_HAU_KY, 1))

    def test_thieu_ban_goc_thi_bao_loi_va_khong_doi_gi(self):
        bk = self.tao_booking(self.goi_gh, TT.CHO_KH_KIEM_TRA)
        anh = self.tao_anh(bk, 'm1.jpg', loai=LoaiAnh.DA_HAU_KY, chon=1)             # ảnh mẫu: không có tệp 'goc'
        with self.assertRaises(services.LoiTaiAnh):
            services.chuyen_thanh_anh_hoan_chinh(bk)
        anh.refresh_from_db()
        self.assertEqual((anh.LoaiAnh, anh.CoWatermark), (LoaiAnh.DA_HAU_KY, 1))

    def test_chen_watermark_duoi_5_giay_cho_anh_nang(self):
        anh_nang = io.BytesIO()
        Image.frombytes('RGB', (4000, 3000), os.urandom(4000 * 3000 * 3)).save(anh_nang, 'JPEG', quality=92)   # ảnh nhiễu: khó nén nhất
        bat_dau = dong_ho.monotonic()
        chen_watermark(anh_nang, 'JPEG')
        self.assertLess(dong_ho.monotonic() - bat_dau, GIOI_HAN_GIAY)

    def test_form_chan_anh_qua_lon_theo_megapixel(self):
        with mock.patch('delivery.forms.SO_PIXEL_TOI_DA', 100):                     # hạ giới hạn xuống 100 điểm ảnh để thử nhanh
            form = TaiAnhForm({}, MultiValueDict({'anh': [tep_anh('a.jpg', 'JPEG', (80, 60))]}))
            self.assertFalse(form.is_valid())

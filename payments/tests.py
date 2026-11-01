# Chạy: python manage.py test payments
import io
import tempfile
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from bookings.models import Booking
from core.constants import LoaiHauKy, LoaiThanhToan, TrangThaiBooking as TT, TrangThaiThanhToan
from notifications.models import ThongBao
from payments import services
from payments.forms import MinhChungForm
from payments.models import MinhChungThanhToan, ThanhToan
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()


def tep_anh(ten='bien-lai.png', dinh_dang='PNG'):              # tạo tệp ảnh thật trong bộ nhớ
    bo_nho = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(bo_nho, dinh_dang)
    return SimpleUploadedFile(ten, bo_nho.getvalue())


@override_settings(MINH_CHUNG_ROOT=tempfile.mkdtemp())         # tệp test ghi vào thư mục tạm, không đụng private_media
class TaiLenMinhChungTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.kh = User.objects.create_user('kh', 'kh@x.vn', 'p', so_dien_thoai='0900000001')
        cls.kh2 = User.objects.create_user('kh2', 'kh2@x.vn', 'p', so_dien_thoai='0900000003')
        nag_user = User.objects.create_user('nag', 'nag@x.vn', 'p', so_dien_thoai='0900000002')
        cls.nag_user = nag_user
        cls.nag = NhiepAnhGia.objects.create(MaTaiKhoan=nag_user, AnhDaiDien='a.jpg', GioiThieu='x',
                                             NganHang='B', SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        cls.goi = GoiDichVu.objects.create(MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G1', Gia=1000001,
                                           ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)

    def tao_booking(self, han=None):                           # Booking ở Chờ đặt cọc
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=20),
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0))
        bk = Booking.objects.create(MaKhachHang=self.kh, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,
                                    NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
                                    Concept='c', TongGiaTri=self.goi.Gia)
        Booking.objects.filter(pk=bk.pk).update(TrangThai=TT.CHO_DAT_COC,
                                                HanDatCoc=han or timezone.now() + timedelta(days=1))
        bk.refresh_from_db()
        return bk

    def test_tai_lan_dau_tao_khoan_coc_minh_chung_va_thong_bao(self):
        bk = self.tao_booking()
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual((tt.LoaiThanhToan, tt.SoTien, tt.TrangThai),
                         (LoaiThanhToan.TIEN_COC, 400000, TrangThaiThanhToan.CHO_XAC_NHAN_COC))  # 40% của 1.000.001, làm tròn
        self.assertEqual(MinhChungThanhToan.objects.filter(MaThanhToan=tt).count(), 1)
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).exists())

    def test_gui_lai_nhieu_lan_va_xoa_yeu_cau_bo_sung(self):
        bk = self.tao_booking()
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        ThanhToan.objects.filter(MaBooking=bk).update(LyDoTuChoi='Ảnh mờ')
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh('lan-2.png'))
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual(tt.minh_chungs.count(), 2)            # không tạo thêm khoản thanh toán
        self.assertIsNone(tt.LyDoTuChoi)                       # lý do cũ được xóa

    def test_qua_han_bi_chan(self):
        bk = self.tao_booking(han=timezone.now() + timedelta(seconds=1))
        Booking.objects.filter(pk=bk.pk).update(HanDatCoc=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(services.LoiTaiMinhChung):
            services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        self.assertFalse(MinhChungThanhToan.objects.exists())

    def test_booking_cua_nguoi_khac_bi_chan(self):
        bk = self.tao_booking()
        with self.assertRaises(services.LoiTaiMinhChung):
            services.tai_len_minh_chung(bk.pk, self.kh2, tep_anh())

    def test_form_chi_nhan_jpg_jpeg_png_va_gioi_han_dung_luong(self):
        self.assertTrue(MinhChungForm({}, {'tep': tep_anh('a.png')}).is_valid())
        self.assertTrue(MinhChungForm({}, {'tep': tep_anh('a.jpg', 'JPEG')}).is_valid())
        self.assertFalse(MinhChungForm({}, {'tep': tep_anh('a.gif', 'GIF')}).is_valid())   # sai đuôi
        self.assertFalse(MinhChungForm({}, {'tep': tep_anh('a.png', 'GIF')}).is_valid())   # đổi đuôi gif thành png
        lon = SimpleUploadedFile('a.png', b'x' * (services.DUNG_LUONG_TOI_DA + 1))
        self.assertFalse(MinhChungForm({}, {'tep': lon}).is_valid())                        # quá 5 MB

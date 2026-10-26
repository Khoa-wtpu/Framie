# profiles/tests.py - kiểm tra form hồ sơ + hàm nổi bật của K2. Chạy: python manage.py test profiles
import shutil
import tempfile
from datetime import time, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from bookings.models import Booking
from core.constants import (KetQuaDuyetHoSo, LoaiHauKy, TrangThaiBooking,
                            TrangThaiHoSo, VaiTro)
from profiles.forms import NhiepAnhGiaForm
from profiles.models import (DuyetHoSo, GoiDichVu, KhuVuc, LoaiHinhChup,
                             NhiepAnhGia, PhongCach)
from profiles.services import nhiep_anh_gia_noi_bat
from reviews.models import DanhGia
from schedule.models import LichKhaDung

User = get_user_model()
THU_MUC_ANH = tempfile.mkdtemp()      # ảnh test lưu ở đây, không làm bẩn thư mục media thật


def tao_anh(ten='a.png'):
    bo_nho = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(bo_nho, 'PNG')
    return SimpleUploadedFile(ten, bo_nho.getvalue(), content_type='image/png')


def tao_user(ten, vai_tro, so=1):
    user = User.objects.create_user(ten, f'{ten}@example.com', 'Matkhau@123',
                                    so_dien_thoai=f'09000000{so:02d}')
    nhom, _ = Group.objects.get_or_create(name=vai_tro)
    user.groups.add(nhom)
    return user


@override_settings(MEDIA_ROOT=THU_MUC_ANH)
class FormHoSoTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_ANH, ignore_errors=True)

    def setUp(self):
        self.user = tao_user('nag1', VaiTro.NHIEP_ANH_GIA)
        self.loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.loai2 = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.cach = PhongCach.objects.create(TenPhongCach='Tự nhiên')
        self.vuc = KhuVuc.objects.create(TenKhuVuc='TP.HCM')

    def du_lieu(self, **doi):
        data = {'GioiThieu': 'Xin chào', 'NganHang': 'Vietcombank', 'SoTaiKhoan': '0123456789',
                'ChuTaiKhoan': 'NGUYEN VAN A', 'loai_hinh': [self.loai.pk],
                'phong_cach': [self.cach.pk], 'khu_vuc': [self.vuc.pk]}
        data.update(doi)
        return data

    def tep(self):
        return {'AnhDaiDien': tao_anh('avt.png'), 'AnhMaQR': tao_anh('qr.png')}

    def test_gui_ho_so_hop_le(self):
        form = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        nag = form.save()
        self.assertEqual(nag.MaTaiKhoan, self.user)
        self.assertEqual(list(nag.loai_hinh_chup.all()), [self.loai])
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=nag).count(), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)

    def test_thieu_danh_muc(self):
        form = NhiepAnhGiaForm(self.du_lieu(loai_hinh=[]), self.tep(), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('loai_hinh', form.errors)

    def test_so_tai_khoan_khong_phai_so(self):
        form = NhiepAnhGiaForm(self.du_lieu(SoTaiKhoan='12ab'), self.tep(), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('SoTaiKhoan', form.errors)

    def test_gioi_thieu_toan_dau_cach(self):
        form = NhiepAnhGiaForm(self.du_lieu(GioiThieu='   '), self.tep(), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('GioiThieu', form.errors)

    def test_anh_qua_5mb(self):
        tep = self.tep()
        tep['AnhDaiDien'].size = 6 * 1024 * 1024
        form = NhiepAnhGiaForm(self.du_lieu(), tep, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('AnhDaiDien', form.errors)

    def test_khong_phai_nhiep_anh_gia(self):
        khach = tao_user('khach1', VaiTro.KHACH_HANG, so=2)
        form = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=khach)
        self.assertFalse(form.is_valid())

    def test_cap_nhat_ho_so_tao_luot_moi_khi_da_duyet(self):
        form = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        nag = form.save()
        # Quản trị viên duyệt lượt 1
        qtv = tao_user('qtv', VaiTro.QUAN_TRI_VIEN, so=3)
        luot = DuyetHoSo.objects.get(MaNhiepAnhGia=nag)
        luot.MaQuanTriVien = qtv
        luot.KetQua = KetQuaDuyetHoSo.DA_DUYET
        luot.ThoiDiemDuyet = timezone.now()
        luot.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.DA_DUYET)
        # Nhiếp ảnh gia cập nhật: đổi sang 2 loại hình, giữ ảnh cũ
        form = NhiepAnhGiaForm(self.du_lieu(loai_hinh=[self.loai.pk, self.loai2.pk]),
                               None, instance=nag)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(nag.loai_hinh_chup.count(), 2)
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=nag).count(), 2)
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)


class NoiBatTestCase(TestCase):
    def setUp(self):
        self.khach = tao_user('khach', VaiTro.KHACH_HANG, so=50)
        self.dem = 0

    def tao_nag(self, ten, trang_thai=TrangThaiHoSo.DA_DUYET, diem=()):
        self.dem += 1
        user = tao_user(ten, VaiTro.NHIEP_ANH_GIA, so=self.dem)
        user.trang_thai_ho_so = trang_thai
        user.save()
        nag = NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='x',
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        for d in diem:
            self.danh_gia(nag, d)
        return nag

    def danh_gia(self, nag, diem):
        # Mỗi đánh giá cần một Booking Hoàn thành, mỗi Booking cần một khung giờ riêng.
        self.dem += 1
        ngay = timezone.localdate() + timedelta(days=30 + self.dem)
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=ngay,
                                          GioBatDau=time(9, 0), GioKetThuc=time(10, 0))
        loai, _ = LoaiHinhChup.objects.get_or_create(TenLoaiHinh='Cưới')
        goi = GoiDichVu.objects.create(
            MaNhiepAnhGia=nag, MaLoaiHinh=loai, TenGoi='G', Gia=1000000, ThoiLuongChup=60,
            LoaiHauKy=LoaiHauKy.TOAN_BO)
        bk = Booking.objects.create(
            MaKhachHang=self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
            Concept='c', TrangThai=TrangThaiBooking.HOAN_THANH)
        DanhGia.objects.create(MaBooking=bk, MaNhiepAnhGia=nag, Diem=diem)

    def test_chua_co_danh_gia_thi_rong(self):
        self.tao_nag('a')
        self.assertEqual(nhiep_anh_gia_noi_bat(), [])

    def test_chi_lay_da_duyet_va_diem_tu_4(self):
        tot = self.tao_nag('tot', diem=[5, 4])               # tb 4.5
        self.tao_nag('thap', diem=[3, 4])                    # tb 3.5 -> loại
        self.tao_nag('chuaduyet', TrangThaiHoSo.CHO_DUYET, diem=[5])
        kq = nhiep_anh_gia_noi_bat()
        self.assertEqual([k['nhiep_anh_gia'] for k in kq], [tot])
        self.assertEqual(kq[0]['diem_trung_binh'], 4.5)
        self.assertEqual(kq[0]['so_danh_gia'], 2)

    def test_xep_theo_diem_va_gioi_han_so_luong(self):
        a = self.tao_nag('a', diem=[4])
        b = self.tao_nag('b', diem=[5])
        c = self.tao_nag('c', diem=[4, 5])
        d = self.tao_nag('d', diem=[5, 5])
        kq = nhiep_anh_gia_noi_bat(so_luong=3)
        self.assertEqual([k['nhiep_anh_gia'] for k in kq], [d, b, c])   # 5.0 (2 lượt), 5.0 (1), 4.5
        self.assertNotIn(a, [k['nhiep_anh_gia'] for k in kq])

    def test_du_lieu_tra_ve(self):
        nag = self.tao_nag('x', diem=[5])
        loai = LoaiHinhChup.objects.get(TenLoaiHinh='Cưới')
        nag.loai_hinh_chup.through.objects.create(MaNhiepAnhGia=nag, MaLoaiHinh=loai)
        ngay = timezone.localdate() + timedelta(days=2)
        LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=ngay,
                                   GioBatDau=time(14, 0), GioKetThuc=time(15, 0))
        mot = nhiep_anh_gia_noi_bat()[0]
        self.assertEqual(mot['loai_hinh'], 'Cưới')
        self.assertEqual(mot['so_khung_gio_trong'], 1)
        self.assertEqual(mot['anh_portfolio'], nag.AnhDaiDien)   # chưa có project -> dùng ảnh đại diện
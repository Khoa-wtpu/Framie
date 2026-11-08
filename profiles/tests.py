# profiles/tests.py - kiểm tra form hồ sơ + hàm nổi bật của K2. Chạy: python manage.py test profiles
import shutil
import tempfile
from datetime import time, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from bookings.models import Booking
from core.constants import (KetQuaDuyetHoSo, LoaiHauKy, TrangThaiBooking,
                            TrangThaiHoSo, VaiTro)
from notifications.models import ThongBao
from profiles.forms import NGAN_HANG, CapNhatHoSoForm, NhiepAnhGiaForm
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

HOP_THU_GIA = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}   # email chỉ vào mail.outbox, không gửi thật (P12)


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


# =====================================================================
# K3 - Tạo hồ sơ: thông báo cho Quản trị viên, ô chọn ngân hàng, trang thử
# =====================================================================
@override_settings(MEDIA_ROOT=THU_MUC_ANH)
class TaoHoSoK3TestCase(TestCase):
    def setUp(self):
        self.user = tao_user('nag1', VaiTro.NHIEP_ANH_GIA)
        self.qtv = tao_user('qtv', VaiTro.QUAN_TRI_VIEN, so=3)
        self.loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.cach = PhongCach.objects.create(TenPhongCach='Tự nhiên')
        self.vuc = KhuVuc.objects.create(TenKhuVuc='TP.HCM')

    def du_lieu(self, **doi):
        data = {'GioiThieu': 'Xin chào', 'NganHang': NGAN_HANG[0], 'SoTaiKhoan': '0123456789',
                'ChuTaiKhoan': 'NGUYEN VAN A', 'loai_hinh': [self.loai.pk],
                'phong_cach': [self.cach.pk], 'khu_vuc': [self.vuc.pk]}
        data.update(doi)
        return data

    def tep(self):
        return {'AnhDaiDien': tao_anh('avt.png'), 'AnhMaQR': tao_anh('qr.png')}

    def test_gui_ho_so_bao_quan_tri_vien(self):
        form = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        tb = ThongBao.objects.filter(MaNguoiNhan=self.qtv)
        self.assertEqual(tb.count(), 1)
        self.assertIn('mới', tb.first().TieuDe)
        # Nhiếp ảnh gia không tự nhận thông báo của chính mình
        self.assertFalse(ThongBao.objects.filter(MaNguoiNhan=self.user).exists())

    @override_settings(MAILERS=HOP_THU_GIA)
    def test_gui_ho_so_gui_email_cho_quan_tri_vien(self):          # P12: hồ sơ mới gửi cả email cho Quản trị viên
        form = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        with self.captureOnCommitCallbacks(execute=True):
            form.save()
        self.assertEqual([m.to for m in mail.outbox], [['qtv@example.com']])

    def test_cap_nhat_ho_so_bao_quan_tri_vien_lan_hai(self):
        nag = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=self.user)
        self.assertTrue(nag.is_valid(), nag.errors)
        nag = nag.save()
        luot = DuyetHoSo.objects.get(MaNhiepAnhGia=nag)
        luot.MaQuanTriVien, luot.KetQua, luot.ThoiDiemDuyet = self.qtv, KetQuaDuyetHoSo.DA_DUYET, timezone.now()
        luot.save()
        form = NhiepAnhGiaForm(self.du_lieu(GioiThieu='Giới thiệu mới'), None, instance=nag)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.qtv).count(), 2)
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.qtv, TieuDe__icontains='cập nhật').exists())

    def test_ngan_hang_ngoai_danh_sach_bi_tu_choi(self):
        form = NhiepAnhGiaForm(self.du_lieu(NganHang='Ngân hàng không có'), self.tep(), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('NganHang', form.errors)

    def test_thieu_ngan_hang(self):
        form = NhiepAnhGiaForm(self.du_lieu(NganHang=''), self.tep(), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('Vui lòng chọn ngân hàng.', form.errors['NganHang'])

    def test_ho_so_cu_ngan_hang_ngoai_danh_sach_van_sua_duoc(self):
        form = NhiepAnhGiaForm(self.du_lieu(), self.tep(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        nag = form.save()
        NhiepAnhGia.objects.filter(pk=nag.pk).update(NganHang='Ngân hàng nhập tay')
        nag.refresh_from_db()
        form = NhiepAnhGiaForm(self.du_lieu(NganHang='Ngân hàng nhập tay'), None, instance=nag)
        self.assertTrue(form.is_valid(), form.errors)

    # ---- trang thử /thu-quyen/tao-ho-so/ (cần config/urls.py có include('profiles.urls')) ----
    def test_trang_thu_chua_dang_nhap_ve_dang_nhap(self):
        res = self.client.get(reverse('tao_ho_so_thu'))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dang-nhap/', res['Location'])

    def test_trang_thu_khach_hang_bi_403(self):
        khach = tao_user('khach1', VaiTro.KHACH_HANG, so=2)
        self.client.force_login(khach)
        self.assertEqual(self.client.get(reverse('tao_ho_so_thu')).status_code, 403)

    def test_trang_thu_hien_form_dung_wireframe(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('tao_ho_so_thu'))
        self.assertEqual(res.status_code, 200)
        for chu in ('Ảnh đại diện', 'Giới thiệu bản thân', 'Loại hình chụp', 'Phong cách',
                    'Khu vực hoạt động', 'Thông tin nhận thanh toán', 'Chọn ngân hàng',
                    'Tên chủ tài khoản', 'Ảnh mã QR', 'Gửi hồ sơ'):
            self.assertContains(res, chu)

    def test_trang_thu_gui_hop_le(self):
        self.client.force_login(self.user)
        res = self.client.post(reverse('tao_ho_so_thu'), {**self.du_lieu(), **self.tep()})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(NhiepAnhGia.objects.filter(MaTaiKhoan=self.user).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)

    def test_trang_thu_thieu_gioi_thieu_bao_loi(self):
        self.client.force_login(self.user)
        res = self.client.post(reverse('tao_ho_so_thu'), {**self.du_lieu(GioiThieu=''), **self.tep()})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Vui lòng nhập giới thiệu bản thân.')
        self.assertFalse(NhiepAnhGia.objects.filter(MaTaiKhoan=self.user).exists())


# =====================================================================
# K4 - Cập nhật hồ sơ cá nhân (UC1.2): trang /ho-so/cap-nhat/ và CapNhatHoSoForm
# =====================================================================
@override_settings(MEDIA_ROOT=THU_MUC_ANH)
class CapNhatHoSoK4TestCase(TestCase):
    def setUp(self):
        self.user = tao_user('nag1', VaiTro.NHIEP_ANH_GIA)
        self.qtv = tao_user('qtv', VaiTro.QUAN_TRI_VIEN, so=3)
        self.loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.loai2 = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.cach = PhongCach.objects.create(TenPhongCach='Tự nhiên')
        self.vuc = KhuVuc.objects.create(TenKhuVuc='TP.HCM')
        # Hồ sơ đã nộp (lượt 1, đang chờ duyệt)
        form = NhiepAnhGiaForm(self.du_lieu_ho_so(), self.tep(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.nag = form.save()
        self.url = reverse('cap_nhat_ho_so')

    # ---- dữ liệu mẫu ----
    def du_lieu_ho_so(self, **doi):
        data = {'GioiThieu': 'Xin chào', 'NganHang': NGAN_HANG[0], 'SoTaiKhoan': '0123456789',
                'ChuTaiKhoan': 'NGUYEN VAN A', 'loai_hinh': [self.loai.pk],
                'phong_cach': [self.cach.pk], 'khu_vuc': [self.vuc.pk]}
        data.update(doi)
        return data

    def du_lieu(self, **doi):
        data = self.du_lieu_ho_so(ho_ten='Nguyễn Văn An', so_dien_thoai='0911111111',
                                  email='nag1@example.com')
        data.update(doi)
        return data

    def tep(self):
        return {'AnhDaiDien': tao_anh('avt.png'), 'AnhMaQR': tao_anh('qr.png')}

    def xu_ly_luot_moi_nhat(self, ket_qua, phan_hoi=None):
        luot = DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).order_by('-LanNop').first()
        luot.MaQuanTriVien, luot.KetQua = self.qtv, ket_qua
        luot.ThoiDiemDuyet, luot.NoiDungPhanHoi = timezone.now(), phan_hoi
        luot.save()

    def lay_tin_nhan(self, res):
        return [str(m) for m in get_messages(res.wsgi_request)]

    # ---- quyền truy cập ----
    def test_chua_dang_nhap_ve_trang_dang_nhap(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dang-nhap/', res['Location'])

    def test_khach_hang_bi_403(self):
        self.client.force_login(tao_user('khach1', VaiTro.KHACH_HANG, so=2))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_chua_co_ho_so_thi_chuyen_di(self):
        user_moi = tao_user('nag2', VaiTro.NHIEP_ANH_GIA, so=4)
        self.client.force_login(user_moi)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(any('chưa có hồ sơ' in t for t in self.lay_tin_nhan(res)))

    # ---- đang chờ duyệt: chỉ được theo dõi ----
    def test_dang_cho_duyet_khong_vao_duoc_trang_sua(self):
        self.client.force_login(self.user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(any('đang chờ Quản trị viên duyệt' in t for t in self.lay_tin_nhan(res)))

    def test_dang_cho_duyet_gui_thang_post_van_bi_chan(self):
        self.client.force_login(self.user)
        res = self.client.post(self.url, self.du_lieu(GioiThieu='Sửa lén'))
        self.assertEqual(res.status_code, 302)
        self.nag.refresh_from_db()
        self.assertEqual(self.nag.GioiThieu, 'Xin chào')
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).count(), 1)

    def test_form_tu_choi_khi_dang_cho_duyet(self):
        form = CapNhatHoSoForm(self.du_lieu(), None, instance=self.nag)
        self.assertFalse(form.is_valid())
        self.assertTrue(any('đang chờ' in e for e in form.non_field_errors()))

    # ---- hồ sơ Đã duyệt: sửa và nộp lại ----
    def test_hien_form_dien_san_khi_da_duyet(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.user.first_name, self.user.last_name = 'An', 'Nguyễn Văn'
        self.user.save()
        self.client.force_login(self.user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        for chu in ('Cập nhật hồ sơ cá nhân', 'Họ tên / Tên hiển thị', 'Số điện thoại', 'Email',
                    'Giới thiệu bản thân', 'Thông tin nhận thanh toán', 'Gửi lại hồ sơ', 'Hủy',
                    'Nguyễn Văn An', 'Xin chào', 'đang hiển thị công khai'):
            self.assertContains(res, chu)
        self.assertNotContains(res, 'type="password"')                 # wireframe: không có ô mật khẩu

    def test_sua_hop_le_tao_luot_moi_va_ve_cho_duyet(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.DA_DUYET)
        self.client.force_login(self.user)
        res = self.client.post(self.url, self.du_lieu(GioiThieu='Giới thiệu mới',
                                                      loai_hinh=[self.loai.pk, self.loai2.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(any('Đã gửi lại hồ sơ thành công' in t for t in self.lay_tin_nhan(res)))
        self.nag.refresh_from_db()
        self.assertEqual(self.nag.GioiThieu, 'Giới thiệu mới')
        self.assertEqual(self.nag.loai_hinh_chup.count(), 2)
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).count(), 2)
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)

    def test_sua_thong_tin_tai_khoan(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.client.force_login(self.user)
        self.client.post(self.url, self.du_lieu(ho_ten='Trần  Thị Bích Ngọc',
                                                so_dien_thoai='0922222222', email='MOI@Example.com'))
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Ngọc', 'Trần Thị Bích'))
        self.assertEqual(self.user.get_full_name(), 'Trần Thị Bích Ngọc')
        self.assertEqual(self.user.so_dien_thoai, '0922222222')
        self.assertEqual(self.user.email, 'moi@example.com')          # luôn lưu chữ thường
        # Cập nhật thông tin tài khoản không làm mất trạng thái 'Chờ duyệt' vừa đặt
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)

    def test_username_theo_email_khi_dang_bang_nhau(self):
        user = User.objects.create_user('b@example.com', 'b@example.com', 'Matkhau@123',
                                        so_dien_thoai='0933333333')
        user.groups.add(Group.objects.get(name=VaiTro.NHIEP_ANH_GIA))
        form = NhiepAnhGiaForm(self.du_lieu_ho_so(), self.tep(), user=user)
        self.assertTrue(form.is_valid(), form.errors)
        nag = form.save()
        luot = DuyetHoSo.objects.get(MaNhiepAnhGia=nag)
        luot.MaQuanTriVien, luot.KetQua, luot.ThoiDiemDuyet = self.qtv, KetQuaDuyetHoSo.DA_DUYET, timezone.now()
        luot.save()
        self.client.force_login(user)
        self.client.post(self.url, self.du_lieu(so_dien_thoai='0933333333', email='b2@example.com'))
        user.refresh_from_db()
        self.assertEqual((user.email, user.username), ('b2@example.com', 'b2@example.com'))
        self.assertTrue(self.client.login(username='b2@example.com', password='Matkhau@123'))

    def test_bao_quan_tri_vien_khi_cap_nhat(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        truoc = ThongBao.objects.filter(MaNguoiNhan=self.qtv).count()
        self.client.force_login(self.user)
        self.client.post(self.url, self.du_lieu())
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.qtv).count(), truoc + 1)
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.qtv, TieuDe__icontains='cập nhật').exists())

    # ---- Yêu cầu chỉnh sửa / Đã từ chối: cùng một form ----
    def test_yeu_cau_chinh_sua_hien_phan_hoi_va_nop_lai_duoc(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA, 'Ảnh đại diện chưa rõ mặt')
        self.client.force_login(self.user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Quản trị viên yêu cầu chỉnh sửa hồ sơ')
        self.assertContains(res, 'Ảnh đại diện chưa rõ mặt')
        self.assertEqual(self.client.post(self.url, self.du_lieu()).status_code, 302)
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).count(), 2)

    def test_da_tu_choi_hien_ly_do_va_nop_lai_duoc(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_TU_CHOI, 'Thông tin chưa đầy đủ')
        self.client.force_login(self.user)
        res = self.client.get(self.url)
        self.assertContains(res, 'Hồ sơ chưa được phê duyệt')
        self.assertContains(res, 'Thông tin chưa đầy đủ')
        self.client.post(self.url, self.du_lieu())
        self.user.refresh_from_db()
        self.assertEqual(self.user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).count(), 2)

    # ---- kiểm tra dữ liệu ----
    def test_thieu_gioi_thieu_khong_luu_gi(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.client.force_login(self.user)
        res = self.client.post(self.url, self.du_lieu(GioiThieu='', ho_ten='Tên Mới'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Vui lòng nhập giới thiệu bản thân.')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, '')                       # ô tài khoản cũng không bị lưu
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).count(), 1)

    def test_email_trung_nguoi_khac(self):
        tao_user('khac', VaiTro.KHACH_HANG, so=5)                        # email khac@example.com
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.client.force_login(self.user)
        res = self.client.post(self.url, self.du_lieu(email='KHAC@example.com'))
        self.assertContains(res, 'Email này đã được đăng ký.')

    def test_so_dien_thoai_trung_nguoi_khac(self):
        tao_user('khac', VaiTro.KHACH_HANG, so=5)                        # SĐT 0900000005
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.client.force_login(self.user)
        res = self.client.post(self.url, self.du_lieu(so_dien_thoai='0900000005'))
        self.assertContains(res, 'Số điện thoại này đã được đăng ký.')

    def test_giu_nguyen_email_va_so_dien_thoai_cua_chinh_minh(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        form = CapNhatHoSoForm(self.du_lieu(so_dien_thoai='0900000001'), None, instance=self.nag)
        self.assertTrue(form.is_valid(), form.errors)

    def test_so_dien_thoai_va_ho_ten_sai(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        for doi, truong in (({'so_dien_thoai': '123'}, 'so_dien_thoai'),
                            ({'so_dien_thoai': '09abc12345'}, 'so_dien_thoai'),
                            ({'ho_ten': 'An 123'}, 'ho_ten'),
                            ({'ho_ten': '   '}, 'ho_ten'),
                            ({'email': 'khong-phai-email'}, 'email')):
            form = CapNhatHoSoForm(self.du_lieu(**doi), None, instance=self.nag)
            self.assertFalse(form.is_valid(), doi)
            self.assertIn(truong, form.errors)

    # ---- ảnh ----
    def test_khong_tai_anh_moi_thi_giu_anh_cu(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        ten_cu = self.nag.AnhDaiDien.name
        self.client.force_login(self.user)
        self.client.post(self.url, self.du_lieu())
        self.nag.refresh_from_db()
        self.assertEqual(self.nag.AnhDaiDien.name, ten_cu)
        self.assertTrue(self.nag.AnhDaiDien.storage.exists(ten_cu))

    def test_thay_anh_thi_xoa_file_cu(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        ten_cu = self.nag.AnhDaiDien.name
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(self.url, {**self.du_lieu(), 'AnhDaiDien': tao_anh('moi.png')})
        self.assertEqual(res.status_code, 302)
        self.nag.refresh_from_db()
        self.assertNotEqual(self.nag.AnhDaiDien.name, ten_cu)
        self.assertTrue(self.nag.AnhDaiDien.storage.exists(self.nag.AnhDaiDien.name))
        self.assertFalse(self.nag.AnhDaiDien.storage.exists(ten_cu))

    def test_file_khong_phai_anh_bi_tu_choi(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        self.client.force_login(self.user)
        tep_sai = SimpleUploadedFile('x.exe', b'abc', content_type='application/octet-stream')
        res = self.client.post(self.url, {**self.du_lieu(), 'AnhMaQR': tep_sai})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).count(), 1)

    # ---- chỉ sửa hồ sơ của chính mình ----
    def test_chi_sua_ho_so_cua_chinh_minh(self):
        self.xu_ly_luot_moi_nhat(KetQuaDuyetHoSo.DA_DUYET)
        user2 = tao_user('nag2', VaiTro.NHIEP_ANH_GIA, so=6)
        form = NhiepAnhGiaForm(self.du_lieu_ho_so(GioiThieu='Của người số 2'), self.tep(), user=user2)
        self.assertTrue(form.is_valid(), form.errors)
        nag2 = form.save()
        luot = DuyetHoSo.objects.get(MaNhiepAnhGia=nag2)
        luot.MaQuanTriVien, luot.KetQua, luot.ThoiDiemDuyet = self.qtv, KetQuaDuyetHoSo.DA_DUYET, timezone.now()
        luot.save()
        self.client.force_login(self.user)
        self.client.post(self.url, self.du_lieu(GioiThieu='Của người số 1'))
        nag2.refresh_from_db()
        self.assertEqual(nag2.GioiThieu, 'Của người số 2')
        self.assertEqual(DuyetHoSo.objects.filter(MaNhiepAnhGia=nag2).count(), 1)

# profiles/tests_cua_toi.py - K3b: "Hồ sơ của tôi" (SC1.2). Chạy: python manage.py test profiles.tests_cua_toi
# Cần config/urls.py có include('profiles.urls_cua_toi') và profiles.urls (K4: name='cap_nhat_ho_so').
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.constants import KetQuaDuyetHoSo as KQ, TrangThaiHoSo, VaiTro
from profiles import views_cua_toi as v
from profiles.models import (DuyetHoSo, KhuVuc, LoaiHinhChup, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach, PhongCach)

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HoSoCuaToiTestCase(TestCase):
    def setUp(self):
        self.dem = 0
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.nhom_khach, _ = Group.objects.get_or_create(name=VaiTro.KHACH_HANG)
        self.nhom_qtv, _ = Group.objects.get_or_create(name=VaiTro.QUAN_TRI_VIEN)
        self.qtv = self.tao_user('qtv', self.nhom_qtv)
        self.nag = self.tao_nag('Nguyễn', 'Minh Anh')
        self.url = reverse('photographer_profile')
        self.url_cap_nhat = reverse('cap_nhat_ho_so')
        self.client.force_login(self.nag.MaTaiKhoan)

    # ---- dữ liệu mẫu ----
    def tao_user(self, ten_dang_nhap, nhom, **kw):
        self.dem += 1
        user = User.objects.create_user(ten_dang_nhap, f'{ten_dang_nhap}@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09400000{self.dem:02d}', **kw)
        user.groups.add(nhom)
        return user

    def tao_nag(self, ho, ten):
        user = self.tao_user(f'nag{self.dem + 1}', self.nhom_nag, first_name=ten, last_name=ho)
        user.trang_thai_ho_so = TrangThaiHoSo.CHO_DUYET
        user.save()
        nag = NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='Chuyên ảnh chân dung\nphong cách tự nhiên',
            NganHang='Vietcombank', SoTaiKhoan='0123456789', ChuTaiKhoan='NGUYEN MINH ANH', AnhMaQR='qr/a.png')
        NhiepAnhGia_LoaiHinhChup.objects.create(
            MaNhiepAnhGia=nag, MaLoaiHinh=LoaiHinhChup.objects.get_or_create(TenLoaiHinh='Chân dung')[0])
        NhiepAnhGia_PhongCach.objects.create(
            MaNhiepAnhGia=nag, MaPhongCach=PhongCach.objects.get_or_create(TenPhongCach='Tự nhiên')[0])
        NhiepAnhGia_KhuVuc.objects.create(
            MaNhiepAnhGia=nag, MaKhuVuc=KhuVuc.objects.get_or_create(TenKhuVuc='TP. Hồ Chí Minh')[0])
        DuyetHoSo.objects.create(MaNhiepAnhGia=nag)                       # lượt 1, đang chờ
        return nag

    def xu_ly(self, ket_qua, noi_dung=None, lan=None):
        """Quản trị viên xử lý lượt mới nhất (hoặc lượt `lan`)."""
        luot = (DuyetHoSo.objects.get(MaNhiepAnhGia=self.nag, LanNop=lan) if lan
                else DuyetHoSo.objects.filter(MaNhiepAnhGia=self.nag).order_by('-LanNop').first())
        luot.MaQuanTriVien, luot.KetQua = self.qtv, ket_qua
        luot.ThoiDiemDuyet, luot.NoiDungPhanHoi = timezone.now(), noi_dung
        luot.save()
        return luot

    # ---- quyền truy cập ----
    def test_chua_dang_nhap_ve_trang_dang_nhap(self):
        self.client.logout()
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dang-nhap/', res['Location'])

    def test_khach_hang_va_quan_tri_vien_bi_403(self):
        for user in (self.tao_user('khach', self.nhom_khach), self.qtv):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403, user.username)

    def test_chi_xem_ho_so_cua_chinh_minh(self):
        khac = self.tao_nag('Trần', 'Zebra')
        res = self.client.get(self.url)
        self.assertContains(res, 'Minh Anh')
        self.assertNotContains(res, 'Zebra')
        self.assertEqual(res.context['nag'], self.nag)
        self.assertNotEqual(res.context['nag'], khac)

    def test_chua_co_ho_so_hien_trang_trong_khong_chuyen_di(self):
        user = self.tao_user('nagmoi', self.nhom_nag)
        self.client.force_login(user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)                              # K4 chuyển về đây khi chưa có hồ sơ: không được chuyển ngược lại
        self.assertContains(res, 'chưa có hồ sơ Nhiếp ảnh gia')

    # ---- nội dung chung ----
    def test_hien_du_thong_tin_ho_so_va_thanh_toan(self):
        res = self.client.get(self.url)
        for chu in ('Nguyễn Minh Anh', f'ID: NAG-{self.nag.pk:04d}', self.nag.MaTaiKhoan.so_dien_thoai,
                    self.nag.MaTaiKhoan.email, 'Chân dung', 'Tự nhiên', 'TP. Hồ Chí Minh', 'Chuyên ảnh chân dung',
                    'Vietcombank', '0123456789', 'NGUYEN MINH ANH'):
            self.assertContains(res, chu)
        self.assertContains(res, '/qr/a.png')                               # ảnh mã QR
        self.assertContains(res, '/avatars/a.png')

    def test_hien_nhieu_loai_hinh_cach_nhau_dau_phay(self):
        NhiepAnhGia_LoaiHinhChup.objects.create(
            MaNhiepAnhGia=self.nag, MaLoaiHinh=LoaiHinhChup.objects.create(TenLoaiHinh='Cưới'))
        self.assertContains(self.client.get(self.url), 'Chân dung, Cưới')

    # ---- 4 trạng thái ----
    def test_trang_thai_cho_duyet_chi_theo_doi_nut_bi_khoa(self):
        res = self.client.get(self.url)
        self.assertEqual(res.context['trang_thai'], v.CHO_DUYET)
        self.assertContains(res, 'Hồ sơ đang chờ duyệt')
        self.assertContains(res, 'is-disabled')
        self.assertNotContains(res, f'href="{self.url_cap_nhat}"')           # không có đường dẫn sang trang sửa (K4 cũng chặn)

    def test_trang_thai_yeu_cau_chinh_sua_hien_noi_dung_va_cho_nop_lai(self):
        self.xu_ly(KQ.YEU_CAU_CHINH_SUA, 'Tải lại ảnh mã QR rõ nét hơn')
        res = self.client.get(self.url)
        self.assertEqual(res.context['trang_thai'], v.CAN_CHINH_SUA)
        self.assertEqual(self.nag.MaTaiKhoan.__class__.objects.get(pk=self.nag.MaTaiKhoan_id).trang_thai_ho_so,
                         TrangThaiHoSo.CHO_DUYET)                           # ở User vẫn là 'Chờ duyệt'
        self.assertContains(res, 'Nội dung Quản trị viên yêu cầu chỉnh sửa')
        self.assertContains(res, 'Tải lại ảnh mã QR rõ nét hơn')
        self.assertContains(res, 'Quản trị viên gửi lúc')
        self.assertContains(res, f'href="{self.url_cap_nhat}"')
        self.assertContains(res, 'btn btn--primary btn--block')              # nút đặc: cần hành động ngay

    def test_trang_thai_da_tu_choi_hien_ly_do_va_nut_nop_lai(self):
        self.xu_ly(KQ.DA_TU_CHOI, 'Giới thiệu chưa đủ thông tin')
        res = self.client.get(self.url)
        self.assertEqual(res.context['trang_thai'], v.DA_TU_CHOI)
        self.assertContains(res, 'Lý do từ chối')
        self.assertContains(res, 'Giới thiệu chưa đủ thông tin')
        self.assertContains(res, 'Chỉnh sửa &amp; nộp lại hồ sơ')
        self.assertContains(res, f'href="{self.url_cap_nhat}"')
        self.assertContains(res, 'Đã từ chối')                               # huy hiệu trạng thái

    def test_trang_thai_da_duyet(self):
        self.xu_ly(KQ.DA_DUYET)
        res = self.client.get(self.url)
        self.assertEqual(res.context['trang_thai'], v.DA_DUYET)
        self.assertContains(res, 'Hồ sơ đã được duyệt')
        self.assertContains(res, 'Cập nhật hồ sơ sẽ đưa hồ sơ về &quot;Chờ duyệt&quot;')
        self.assertContains(res, f'href="{self.url_cap_nhat}"')
        self.assertContains(res, 'Đã duyệt')
        self.assertNotContains(res, 'btn btn--primary btn--block')          # nút viền, không đặc

    def test_trang_thai_theo_luot_moi_nhat_khong_theo_luot_cu(self):
        self.xu_ly(KQ.DA_TU_CHOI, 'Lý do cũ')                                # lần 1: từ chối
        DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag, LanNop=2)           # nộp lại: lượt 2 đang chờ
        res = self.client.get(self.url)
        self.assertEqual(res.context['trang_thai'], v.CHO_DUYET)
        self.assertNotContains(res, 'Lý do cũ')                              # không hiện phản hồi của lượt cũ
        self.assertNotContains(res, f'href="{self.url_cap_nhat}"')

    def test_xac_dinh_trang_thai_khi_chua_co_luot_nao(self):
        self.assertEqual(v.xac_dinh_trang_thai(None), v.CHO_DUYET)

    def test_noi_dung_phan_hoi_khong_chen_duoc_html(self):
        self.xu_ly(KQ.YEU_CAU_CHINH_SUA, '<script>alert(1)</script>')
        res = self.client.get(self.url)
        self.assertNotContains(res, '<script>alert(1)</script>')
        self.assertContains(res, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_thoi_diem_gui_theo_gio_dia_phuong(self):
        luot = self.xu_ly(KQ.YEU_CAU_CHINH_SUA, 'Sửa')
        luot.ThoiDiemDuyet = timezone.make_aware(datetime(2026, 10, 4, 9, 30))
        luot.ThoiDiemNop = luot.ThoiDiemDuyet - timedelta(days=1)
        luot.save()
        self.assertContains(self.client.get(self.url), '04/10/2026 · 09:30')

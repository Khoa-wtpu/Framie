# profiles/tests_cong_khai.py - K9: hồ sơ công khai Nhiếp ảnh gia (UC2.3). Chạy: python manage.py test profiles.tests_cong_khai
# Cần config/urls.py có include('profiles.urls_cong_khai') và include('bookings.giu_cho').
import importlib.util
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, GiuCho
from core.constants import (LoaiHauKy, TrangThaiBooking, TrangThaiGiuCho as GC, TrangThaiGoi, TrangThaiHoSo,
                            TrangThaiSlot as SL, VaiTro)
from profiles import views_cong_khai as vck
from profiles.models import (GoiDichVu, HinhAnhProject, KhuVuc, LoaiHinhChup, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach, PhongCach, Project)
from reviews.models import DanhGia
from schedule import quan_ly
from schedule.models import LichKhaDung

User = get_user_model()
CO_GIU_CHO = importlib.util.find_spec('bookings.giu_cho') is not None


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])   # test nhanh hơn, không ảnh hưởng web thật
class HoSoCongKhaiTestCase(TestCase):
    def setUp(self):
        self.dem = 0
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.nhom_khach, _ = Group.objects.get_or_create(name=VaiTro.KHACH_HANG)
        self.khach = self.tao_user('khach', self.nhom_khach, first_name='Vân', last_name='Nguyễn')
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.nag = self.tao_nag('Lê Minh', 'Khôi', gioi_thieu='Chuyên ảnh cưới\nphong cách tự nhiên')
        self.url = reverse('photographer_detail', args=[self.nag.pk])
        self.hom_nay = timezone.localdate()
        self.ngay = quan_ly.dau_tuan(self.hom_nay) + timedelta(days=8)       # thứ Ba tuần sau: chắc chắn ở tương lai
        self.url_tuan = f'{self.url}?tuan={self.ngay.isoformat()}'

    # ---- dữ liệu mẫu ----
    def tao_user(self, ten_dang_nhap, nhom, **kw):
        self.dem += 1
        user = User.objects.create_user(ten_dang_nhap, f'{ten_dang_nhap}@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09200000{self.dem:02d}', **kw)
        user.groups.add(nhom)
        return user

    def tao_nag(self, ho, ten, trang_thai=TrangThaiHoSo.DA_DUYET, hoat_dong=True, gioi_thieu='Giới thiệu'):
        self.dem += 1
        user = self.tao_user(f'nag{self.dem}', self.nhom_nag, first_name=ten, last_name=ho, is_active=hoat_dong)
        user.trang_thai_ho_so = trang_thai
        user.save()
        nag = NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu=gioi_thieu,
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        NhiepAnhGia_LoaiHinhChup.objects.create(MaNhiepAnhGia=nag, MaLoaiHinh=self.cuoi)
        NhiepAnhGia_PhongCach.objects.create(MaNhiepAnhGia=nag, MaPhongCach=PhongCach.objects.get_or_create(
            TenPhongCach='Tự nhiên')[0])
        NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=nag, MaKhuVuc=KhuVuc.objects.get_or_create(
            TenKhuVuc='TP.HCM')[0])
        return nag

    def tao_goi(self, nag=None, ten='Gói cơ bản', gia=1500000, trang_thai=TrangThaiGoi.DANG_AP_DUNG, loai=None,
                phut=60, hau_ky=LoaiHauKy.TOAN_BO, so_anh=None, mo_ta=None):
        return GoiDichVu.objects.create(
            MaNhiepAnhGia=nag or self.nag, MaLoaiHinh=loai or self.cuoi, TenGoi=ten, Gia=Decimal(gia),
            ThoiLuongChup=phut, LoaiHauKy=hau_ky, SoAnhHauKyToiDa=so_anh, TrangThai=trang_thai, MoTa=mo_ta)

    def tao_slot(self, bat_dau=time(8, 0), ket_thuc=time(10, 0), trang_thai=SL.TRONG, ngay=None, nag=None):
        return LichKhaDung.objects.create(MaNhiepAnhGia=nag or self.nag, Ngay=ngay or self.ngay,
                                          GioBatDau=bat_dau, GioKetThuc=ket_thuc, TrangThai=trang_thai)

    def tao_danh_gia(self, diem, nhan_xet=None, nag=None, khach=None, ngay=None):
        nag = nag or self.nag
        self.dem += 1
        lich = LichKhaDung.objects.create(
            MaNhiepAnhGia=nag, Ngay=timezone.localdate() + timedelta(days=60 + self.dem),
            GioBatDau=time(9, 0), GioKetThuc=time(10, 0))
        goi = self.tao_goi(nag, ten=f'Ẩn {self.dem}', gia=100000 + self.dem, trang_thai=TrangThaiGoi.DA_AN)
        bk = Booking.objects.create(
            MaKhachHang=khach or self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2, Concept='c',
            TrangThai=TrangThaiBooking.HOAN_THANH)
        return DanhGia.objects.create(MaBooking=bk, MaNhiepAnhGia=nag, Diem=diem, NhanXet=nhan_xet,
                                      NgayDanhGia=ngay or timezone.now())

    def tao_project(self, ten='Cưới Đà Lạt', nag=None, so_anh=2):
        project = Project.objects.create(MaNhiepAnhGia=nag or self.nag, MaLoaiHinh=self.cuoi, TenProject=ten,
                                         Concept='Concept nhẹ nhàng', AnhBia='portfolio/bia.png')
        for i in range(1, so_anh + 1):
            HinhAnhProject.objects.create(MaProject=project, DuongDanHinhAnh=f'portfolio/{ten}-{i}.png', ThuTu=i)
        return project

    def slot_trong_ngay(self, res, ngay=None):
        """[(giờ, lớp CSS)] của các khung giờ hiện trên trang trong ngày cho trước."""
        ngay = ngay or self.ngay
        for n in res.context['cac_ngay']:
            if n['ngay'] == ngay:
                return [(s['gio'], s['lop']) for s in n['cac_slot']]
        self.fail('Ngày không nằm trong tuần đang hiển thị')

    def gio_gia_lap(self, gio):
        return mock.patch('schedule.quan_ly.bay_gio', return_value=timezone.localtime(
            timezone.make_aware(datetime.combine(self.hom_nay, time(gio, 0)))))

    # =================================================================
    # Truy cập và phạm vi
    # =================================================================
    def test_khong_can_dang_nhap_va_hien_thong_tin_chinh(self):
        self.tao_goi()
        self.tao_danh_gia(5)
        self.tao_danh_gia(4)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Lê Minh Khôi')
        self.assertContains(res, f'ID: NAG-{self.nag.pk:04d}')
        self.assertContains(res, 'Chuyên ảnh cưới')
        self.assertContains(res, '<strong>4.5</strong> (2 đánh giá)')
        self.assertContains(res, reverse('search'))                              # link "Quay lại tìm kiếm"

    def test_loai_hinh_phong_cach_khu_vuc_tach_rieng_co_nhan(self):
        res = self.client.get(self.url)
        for nhan in ('Loại hình chụp', 'Phong cách', 'Khu vực nhận chụp'):
            self.assertContains(res, f'<dt>{nhan}</dt>')
        self.assertContains(res, 'hscc__chip--loai">Cưới<')
        self.assertContains(res, 'hscc__chip--cach">Tự nhiên<')
        self.assertContains(res, 'hscc__chip--vuc">TP.HCM<')

    def test_chua_co_gi_thi_bao_ro(self):
        res = self.client.get(self.url)
        self.assertContains(res, 'Chưa có đánh giá', count=2)       # dòng điểm trên đầu và mục Đánh giá
        self.assertContains(res, 'chưa có gói dịch vụ')
        self.assertContains(res, 'chưa đăng project nào')

    def test_ho_so_khong_cong_khai_thi_404(self):
        cho_duyet = self.tao_nag('Cho', 'Duyet', trang_thai=TrangThaiHoSo.CHO_DUYET)
        tu_choi = self.tao_nag('Tu', 'Choi', trang_thai=TrangThaiHoSo.DA_TU_CHOI)
        bi_khoa = self.tao_nag('Bi', 'Khoa', hoat_dong=False)
        for nag in (cho_duyet, tu_choi, bi_khoa):
            with self.subTest(nag=nag.pk):
                self.assertEqual(self.client.get(reverse('photographer_detail', args=[nag.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('photographer_detail', args=[99999])).status_code, 404)

    # =================================================================
    # Gói dịch vụ (wireframe: Đang áp dụng chọn được, Ngừng áp dụng hiện mờ, Đã ẩn không hiện)
    # =================================================================
    def test_dang_ap_dung_chon_duoc_ngung_hien_mo_da_an_khong_hien(self):
        dang = self.tao_goi(ten='Gói đang bán', gia=2000000)
        ngung = self.tao_goi(ten='Gói đã ngừng', trang_thai=TrangThaiGoi.NGUNG_AP_DUNG)
        self.tao_goi(ten='Gói đã ẩn', trang_thai=TrangThaiGoi.DA_AN)
        self.tao_goi(nag=self.tao_nag('Người', 'Khác'), ten='Gói của người khác')
        res = self.client.get(self.url)
        cac_goi = {g['ten']: g for g in res.context['cac_goi']}
        self.assertEqual(set(cac_goi), {'Gói đang bán', 'Gói đã ngừng'})
        self.assertTrue(cac_goi['Gói đang bán']['ap_dung'])
        self.assertIn(f'goi={dang.pk}', cac_goi['Gói đang bán']['url_chon'])
        self.assertFalse(cac_goi['Gói đã ngừng']['ap_dung'])
        self.assertEqual(cac_goi['Gói đã ngừng']['url_chon'], '')              # không chọn được
        self.assertContains(res, '2.000.000đ')
        self.assertContains(res, 'Ngừng áp dụng')
        self.assertNotContains(res, 'Gói đã ẩn')
        self.assertNotContains(res, 'Gói của người khác')
        self.assertNotContains(res, f'goi={ngung.pk}')

    def test_thoi_luong_va_hau_ky(self):
        self.tao_goi(ten='Một', phut=90, hau_ky=LoaiHauKy.GIOI_HAN, so_anh=30)
        self.tao_goi(ten='Hai', phut=120, gia=2000000)
        self.tao_goi(ten='Ba', phut=45, gia=3000000)
        res = self.client.get(self.url)
        self.assertContains(res, '<dd>1 giờ 30 phút</dd>')
        self.assertContains(res, '<dd>giới hạn 30 ảnh</dd>')
        self.assertContains(res, '<dd>2 giờ</dd>')
        self.assertContains(res, '<dd>45 phút</dd>')
        self.assertContains(res, '<dd>toàn bộ ảnh</dd>')
        self.assertEqual([vck.nhan_thoi_luong(p) for p in (45, 60, 90, 120)], ['45 phút', '1 giờ', '1 giờ 30 phút', '2 giờ'])

    def test_chon_goi_va_goi_khong_hop_le_bi_bo_qua(self):
        goi = self.tao_goi(ten='Gói ba tiếng', phut=180)
        ngung = self.tao_goi(ten='Ngừng', trang_thai=TrangThaiGoi.NGUNG_AP_DUNG)
        cua_nguoi_khac = self.tao_goi(nag=self.tao_nag('Người', 'Khác'), ten='Khác')
        res = self.client.get(f'{self.url}?goi={goi.pk}')
        self.assertEqual(res.context['goi_chon'], goi)
        self.assertContains(res, 'Đang xem lịch cho')
        self.assertContains(res, 'Đã chọn ✓')
        for sai in (ngung.pk, cua_nguoi_khac.pk, 'abc', '99999', ''):
            with self.subTest(goi=sai):
                self.assertIsNone(self.client.get(f'{self.url}?goi={sai}').context['goi_chon'])

    # =================================================================
    # Nút "Nhắn tin" (thẻ nut_nhan_tin của chat, P10) / "Đặt lịch"
    # =================================================================
    def test_nut_dau_trang(self):
        self.tao_goi()
        res = self.client.get(self.url)
        self.assertContains(res, 'Nhắn tin')
        self.assertNotContains(res, 'Chọn lịch chụp')                              # không còn nút này ở đầu trang
        self.assertContains(res, 'href="#lich-kha-dung">Đặt lịch<')                # "Đặt lịch" cuộn xuống lịch bên dưới
        self.client.force_login(self.tao_nag('Người', 'Khác').MaTaiKhoan)           # Nhiếp ảnh gia xem: không có nút nào
        res = self.client.get(self.url)
        self.assertNotContains(res, 'Nhắn tin')
        self.assertNotContains(res, 'Đặt lịch<')

    def test_chua_co_goi_dang_ap_dung_thi_khong_co_nut_dat_lich(self):
        self.tao_goi(trang_thai=TrangThaiGoi.NGUNG_AP_DUNG)
        self.assertNotContains(self.client.get(self.url), 'Đặt lịch<')

    # =================================================================
    # Lịch khả dụng
    # =================================================================
    def test_lich_hien_ba_trang_thai(self):
        self.tao_slot(time(8, 0), time(10, 0), SL.TRONG)
        self.tao_slot(time(10, 0), time(12, 0), SL.DANG_GIU)
        self.tao_slot(time(14, 0), time(16, 0), SL.DA_DAT)
        res = self.client.get(self.url_tuan)
        self.assertEqual(self.slot_trong_ngay(res), [('08:00 – 10:00', 'trong'), ('10:00 – 12:00', 'giu'), ('14:00 – 16:00', 'dat')])

    def test_lich_dung_bo_cuc_giong_quan_ly_lich_cua_nhiep_anh_gia(self):
        self.tao_slot(time(8, 0), time(10, 0), SL.TRONG)
        self.tao_slot(time(10, 0), time(12, 0), SL.DANG_GIU)
        self.tao_slot(time(14, 0), time(16, 0), SL.DA_DAT)
        res = self.client.get(self.url_tuan)
        self.assertContains(res, 'schedule/css/lich.css')
        for mau in ('sky', 'amber', 'blue'):                       # viền trái 3 màu như màn Quản lý lịch
            self.assertContains(res, f'lich-slot lich-slot--{mau}')
        self.assertEqual(res.context['chu_thich'], [SL.TRONG, SL.DANG_GIU, SL.DA_DAT])
        self.assertContains(res, 'Chưa có khung giờ')                  # các ngày không có slot
        self.assertContains(res, 'class="lich__hom-nay"')

    def test_slot_da_bat_dau_khong_hien(self):
        self.tao_slot(time(8, 0), time(10, 0), ngay=self.hom_nay)
        self.tao_slot(time(15, 0), time(17, 0), ngay=self.hom_nay)
        with self.gio_gia_lap(9):
            res = self.client.get(self.url)
        self.assertEqual(self.slot_trong_ngay(res, self.hom_nay), [('15:00 – 17:00', 'trong')])

    def test_lich_cua_nguoi_khac_khong_lan_sang(self):
        khac = self.tao_nag('Người', 'Khác')
        self.tao_slot(time(8, 0), time(10, 0), nag=khac)
        self.assertEqual(self.slot_trong_ngay(self.client.get(self.url_tuan)), [])

    def test_khach_hang_chon_slot_trong_bang_form_post(self):
        trong = self.tao_slot(time(8, 0), time(10, 0), SL.TRONG)
        giu = self.tao_slot(time(10, 0), time(12, 0), SL.DANG_GIU)
        dat = self.tao_slot(time(14, 0), time(16, 0), SL.DA_DAT)
        self.client.force_login(self.khach)
        res = self.client.get(self.url_tuan)
        self.assertContains(res, f'action="{reverse("chon_slot", args=[trong.pk])}"')
        self.assertContains(res, f'name="ma_nhiep_anh_gia" value="{self.nag.pk}"')
        self.assertNotContains(res, reverse('chon_slot', args=[giu.pk]))
        self.assertNotContains(res, reverse('chon_slot', args=[dat.pk]))

    def test_chua_dang_nhap_bam_slot_thi_sang_dang_nhap(self):
        trong = self.tao_slot(time(8, 0), time(10, 0), SL.TRONG)
        res = self.client.get(self.url_tuan)
        self.assertNotContains(res, reverse('chon_slot', args=[trong.pk]))
        self.assertContains(res, f'href="{res.context["url_dang_nhap"]}"')
        self.assertIn('next=', res.context['url_dang_nhap'])
        self.assertContains(res, 'Bạn cần đăng nhập để đặt lịch')

    def test_nhiep_anh_gia_chi_xem_lich(self):
        trong = self.tao_slot(time(8, 0), time(10, 0), SL.TRONG)
        self.client.force_login(self.tao_nag('Người', 'Khác').MaTaiKhoan)
        res = self.client.get(self.url_tuan)
        self.assertEqual(self.slot_trong_ngay(res), [('08:00 – 10:00', 'trong')])
        self.assertNotContains(res, reverse('chon_slot', args=[trong.pk]))
        self.assertContains(res, 'Chỉ tài khoản Khách hàng mới đặt được lịch')

    def test_khung_gio_ngan_hon_goi_da_chon_bi_khoa(self):
        ngan = self.tao_slot(time(8, 0), time(10, 0))            # 2 giờ
        dai = self.tao_slot(time(13, 0), time(17, 0))            # 4 giờ
        goi = self.tao_goi(ten='Trọn bộ', phut=180)               # cần 3 giờ
        self.client.force_login(self.khach)
        res = self.client.get(f'{self.url_tuan}&goi={goi.pk}')
        self.assertNotContains(res, reverse('chon_slot', args=[ngan.pk]))
        self.assertContains(res, 'Quá ngắn cho gói')
        self.assertContains(res, f'action="{reverse("chon_slot", args=[dai.pk])}"')
        self.assertContains(res, f'name="goi" value="{goi.pk}"')                    # mang mã gói theo khi giữ chỗ
        res = self.client.get(self.url_tuan)                                          # chưa chọn gói thì không khóa gì
        self.assertContains(res, reverse('chon_slot', args=[ngan.pk]))
        self.assertNotContains(res, 'Quá ngắn cho gói')

    def test_chuyen_tuan_va_gioi_han(self):
        tuan_nay = quan_ly.dau_tuan(self.hom_nay)
        res = self.client.get(self.url)
        self.assertEqual(res.context['url_tuan_truoc'], '')                           # không lùi về quá khứ
        self.assertIn(f'tuan={(tuan_nay + timedelta(weeks=1)).isoformat()}', res.context['url_tuan_sau'])
        self.assertIn('#lich-kha-dung', res.context['url_tuan_sau'])
        tuan_cuoi = tuan_nay + timedelta(weeks=vck.SO_TUAN_TOI_DA)
        for chuoi, mong_doi in ((tuan_cuoi + timedelta(weeks=20), tuan_cuoi), ('2000-01-01', tuan_nay),
                                ('abc', tuan_nay), (tuan_cuoi.isoformat(), tuan_cuoi)):
            with self.subTest(tuan=str(chuoi)):
                res = self.client.get(f'{self.url}?tuan={chuoi}')
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.context['cac_ngay'][0]['ngay'], mong_doi)
        self.assertEqual(self.client.get(f'{self.url}?tuan={tuan_cuoi}').context['url_tuan_sau'], '')
        self.assertTrue(self.client.get(f'{self.url}?tuan={tuan_cuoi}').context['url_tuan_truoc'])

    def test_doi_tuan_giu_nguyen_goi_da_chon(self):
        goi = self.tao_goi()
        res = self.client.get(f'{self.url}?goi={goi.pk}')
        self.assertIn(f'goi={goi.pk}', res.context['url_tuan_sau'])

    @skipUnless(CO_GIU_CHO, 'Cần bookings/giu_cho.py (T3-T4 của Tuyền)')
    def test_giu_cho_het_han_duoc_nha_truoc_khi_hien(self):                         # BR4.1-1
        lich = self.tao_slot(time(8, 0), time(10, 0), SL.DANG_GIU)
        bg = timezone.now()
        GiuCho.objects.create(MaKhachHang=self.khach, MaLich=lich, ThoiDiemGiu=bg - timedelta(minutes=10),
                              ThoiDiemHetHan=bg - timedelta(minutes=5), TrangThai=GC.DANG_GIU)
        res = self.client.get(self.url_tuan)
        self.assertEqual(self.slot_trong_ngay(res), [('08:00 – 10:00', 'trong')])

    # =================================================================
    # Đánh giá
    # =================================================================
    def test_danh_gia_hien_ten_nhan_xet_va_moi_nhat_truoc(self):
        cu = self.tao_danh_gia(3, 'Tạm ổn', ngay=timezone.now() - timedelta(days=5))
        moi = self.tao_danh_gia(5, 'Rất tuyệt\nsẽ quay lại', ngay=timezone.now())
        res = self.client.get(self.url)
        self.assertEqual([d['diem'] for d in res.context['cac_danh_gia']], [moi.Diem, cu.Diem])
        self.assertContains(res, '<strong>Vân</strong>')                    # tên gọi, không lộ họ tên đầy đủ
        self.assertNotContains(res, 'Nguyễn Vân')
        self.assertContains(res, 'Rất tuyệt<br>sẽ quay lại')
        self.assertContains(res, '5 trên 5 sao')

    def test_chi_hien_so_danh_gia_toi_da(self):
        for i in range(vck.SO_DANH_GIA_HIEN + 2):
            self.tao_danh_gia(5, f'Nhận xét số {i}')
        res = self.client.get(self.url)
        self.assertEqual(len(res.context['cac_danh_gia']), vck.SO_DANH_GIA_HIEN)
        self.assertContains(res, f'trong tổng số {vck.SO_DANH_GIA_HIEN + 2}')

    def test_danh_gia_cua_nguoi_khac_khong_lan_sang(self):
        khac = self.tao_nag('Người', 'Khác')
        self.tao_danh_gia(1, 'Của người khác', nag=khac)
        res = self.client.get(self.url)
        self.assertNotContains(res, 'Của người khác')
        self.assertContains(res, 'Chưa có đánh giá', count=2)

    # =================================================================
    # Portfolio (SC2.4)
    # =================================================================
    def test_portfolio_va_trang_project(self):
        project = self.tao_project('Cưới Đà Lạt', so_anh=3)
        res = self.client.get(self.url)
        trang = reverse('photographer_project', args=[self.nag.pk, project.pk])
        self.assertContains(res, f'href="{trang}"')
        self.assertContains(res, 'Cưới Đà Lạt')
        self.assertContains(res, '3 ảnh')
        res = self.client.get(trang)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Concept nhẹ nhàng')
        self.assertContains(res, 'Hình ảnh <span class="hscc__ghi">(3)</span>')
        self.assertEqual([a.ThuTu for a in res.context['cac_anh']], [1, 2, 3])
        self.assertContains(res, reverse('photographer_detail', args=[self.nag.pk]))     # link quay lại

    def test_chuyen_giua_cac_project(self):
        p1, p2, p3 = (self.tao_project(ten) for ten in ('Một', 'Hai', 'Ba'))      # mới nhất hiện trước: Ba, Hai, Một
        res = self.client.get(reverse('photographer_project', args=[self.nag.pk, p2.pk]))
        self.assertEqual((res.context['truoc'], res.context['sau']), (p3, p1))
        res = self.client.get(reverse('photographer_project', args=[self.nag.pk, p3.pk]))
        self.assertEqual((res.context['truoc'], res.context['sau']), (None, p2))
        res = self.client.get(reverse('photographer_project', args=[self.nag.pk, p1.pk]))
        self.assertEqual((res.context['truoc'], res.context['sau']), (p2, None))

    def test_project_cua_nguoi_khac_hoac_ho_so_an_la_404(self):
        khac = self.tao_nag('Người', 'Khác')
        project_khac = self.tao_project('Của người khác', nag=khac)
        self.assertEqual(self.client.get(reverse('photographer_project', args=[self.nag.pk, project_khac.pk])).status_code, 404)
        cho_duyet = self.tao_nag('Cho', 'Duyet', trang_thai=TrangThaiHoSo.CHO_DUYET)
        project_an = self.tao_project('Đang chờ', nag=cho_duyet)
        self.assertEqual(self.client.get(reverse('photographer_project', args=[cho_duyet.pk, project_an.pk])).status_code, 404)

    def test_project_khong_co_anh(self):
        project = self.tao_project('Trống', so_anh=0)
        res = self.client.get(reverse('photographer_project', args=[self.nag.pk, project.pk]))
        self.assertContains(res, 'chưa có ảnh')

    # ---- liên kết từ trang Tìm kiếm ----
    def test_the_o_trang_tim_kiem_dan_toi_ho_so(self):
        self.tao_goi()
        self.assertContains(self.client.get(reverse('search')), f'href="{self.url}"')

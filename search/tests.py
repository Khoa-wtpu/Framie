# search/tests.py - K8: tìm kiếm và lọc nhiếp ảnh gia. Chạy: python manage.py test search
# (cần config/urls.py có include('search.urls'))
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from core.constants import LoaiHauKy, TrangThaiBooking, TrangThaiGoi, TrangThaiHoSo, VaiTro
from profiles.models import (GoiDichVu, KhuVuc, LoaiHinhChup, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach, PhongCach)
from reviews.models import DanhGia
from schedule.models import LichKhaDung
from search.services import bo_dau, dinh_dang_tien

User = get_user_model()


class TimKiemTestCase(TestCase):
    def setUp(self):
        self.url = reverse('search')
        self.dem = 0
        nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.nhom_nag = nhom_nag
        self.khach = User.objects.create_user('khach', 'khach@example.com', 'Matkhau@123',
                                              so_dien_thoai='0988888888')
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.tu_nhien = PhongCach.objects.create(TenPhongCach='Tự nhiên')
        self.cinematic = PhongCach.objects.create(TenPhongCach='Cinematic')
        self.hcm = KhuVuc.objects.create(TenKhuVuc='TP.HCM')
        self.da_lat = KhuVuc.objects.create(TenKhuVuc='Đà Lạt')

        # A: Lê Minh Khôi - cưới, tự nhiên, TP.HCM, 1 gói 2.000.000, điểm 5 và 4
        self.a = self.tao_nag('Lê Minh', 'Khôi', [self.cuoi], [self.tu_nhien], [self.hcm],
                              gia=[2000000], gioi_thieu='Chuyên chụp ảnh cưới phong cách tự nhiên')
        self.danh_gia(self.a, 5)
        self.danh_gia(self.a, 4)
        # B: Trần Bảo Ngọc - chân dung, cinematic, Đà Lạt, 2 gói 1.000.000 và 4.000.000, chưa có đánh giá
        self.b = self.tao_nag('Trần Bảo', 'Ngọc', [self.chan_dung], [self.cinematic], [self.da_lat],
                              gia=[1000000, 4000000])
        # F: chỉ có gói "Ngừng áp dụng" 500.000 -> không tính vào giá
        self.f = self.tao_nag('Phạm Gia', 'Huy', [self.cuoi, self.chan_dung], [self.tu_nhien], [self.hcm],
                              gia=[], goi_ngung=[500000])
        # Không được hiện công khai:
        self.cho_duyet = self.tao_nag('Cho', 'Duyet', [self.cuoi], [self.tu_nhien], [self.hcm],
                                      trang_thai=TrangThaiHoSo.CHO_DUYET, gia=[2000000])
        self.tu_choi = self.tao_nag('Tu', 'Choi', [self.cuoi], [self.tu_nhien], [self.hcm],
                                    trang_thai=TrangThaiHoSo.DA_TU_CHOI, gia=[2000000])
        self.bi_khoa = self.tao_nag('Bi', 'Khoa', [self.cuoi], [self.tu_nhien], [self.hcm],
                                    gia=[2000000], hoat_dong=False)

    # ---- dữ liệu mẫu ----
    def tao_nag(self, ho, ten, loai, cach, vuc, trang_thai=TrangThaiHoSo.DA_DUYET, gia=(),
                goi_ngung=(), hoat_dong=True, gioi_thieu='Giới thiệu'):
        self.dem += 1
        user = User.objects.create_user(
            f'u{self.dem}', f'u{self.dem}@example.com', 'Matkhau@123', first_name=ten, last_name=ho,
            so_dien_thoai=f'09100000{self.dem:02d}', is_active=hoat_dong)
        user.groups.add(self.nhom_nag)
        user.trang_thai_ho_so = trang_thai
        user.save()
        nag = NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu=gioi_thieu,
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        for m in loai:
            NhiepAnhGia_LoaiHinhChup.objects.create(MaNhiepAnhGia=nag, MaLoaiHinh=m)
        for m in cach:
            NhiepAnhGia_PhongCach.objects.create(MaNhiepAnhGia=nag, MaPhongCach=m)
        for m in vuc:
            NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=nag, MaKhuVuc=m)
        for g in gia:
            self.tao_goi(nag, g, TrangThaiGoi.DANG_AP_DUNG)
        for g in goi_ngung:
            self.tao_goi(nag, g, TrangThaiGoi.NGUNG_AP_DUNG)
        return nag

    def tao_goi(self, nag, gia, trang_thai):
        return GoiDichVu.objects.create(
            MaNhiepAnhGia=nag, MaLoaiHinh=self.cuoi, TenGoi=f'Gói {gia}', Gia=Decimal(gia),
            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO, TrangThai=trang_thai)

    def danh_gia(self, nag, diem):
        # Mỗi đánh giá cần một Booking Hoàn thành; dùng gói "Đã ẩn" để không ảnh hưởng giá.
        self.dem += 1
        lich = LichKhaDung.objects.create(
            MaNhiepAnhGia=nag, Ngay=timezone.localdate() + timedelta(days=30 + self.dem),
            GioBatDau=time(9, 0), GioKetThuc=time(10, 0))
        goi = self.tao_goi(nag, 123000 + self.dem, TrangThaiGoi.DA_AN)
        bk = Booking.objects.create(
            MaKhachHang=self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
            Concept='c', TrangThai=TrangThaiBooking.HOAN_THANH)
        DanhGia.objects.create(MaBooking=bk, MaNhiepAnhGia=nag, Diem=diem)

    def ten(self, nag):
        return nag.MaTaiKhoan.get_full_name()

    def hien(self, res, *cac_nag):
        for nag in cac_nag:
            self.assertContains(res, f'ID: NAG-{nag.pk:04d}')

    def khong_hien(self, res, *cac_nag):
        for nag in cac_nag:
            self.assertNotContains(res, f'ID: NAG-{nag.pk:04d}')

    # ---- truy cập và phạm vi hiển thị ----
    def test_khong_can_dang_nhap_va_chi_hien_ho_so_da_duyet(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.hien(res, self.a, self.b, self.f)
        self.khong_hien(res, self.cho_duyet, self.tu_choi, self.bi_khoa)
        self.assertContains(res, 'Tìm kiếm Nhiếp ảnh gia')

    def test_ho_so_ve_cho_duyet_thi_bien_mat_khoi_ket_qua(self):
        self.a.MaTaiKhoan.trang_thai_ho_so = TrangThaiHoSo.CHO_DUYET
        self.a.MaTaiKhoan.save()
        self.khong_hien(self.client.get(self.url), self.a)

    def test_the_hien_id_gia_va_danh_gia(self):
        res = self.client.get(self.url)
        self.assertContains(res, f'ID: NAG-{self.a.pk:04d}')
        self.assertContains(res, 'Từ 2.000.000đ')
        self.assertContains(res, '★ 4.5 (2 đánh giá)')
        self.assertContains(res, 'Chưa có đánh giá')          # B và F
        self.assertContains(res, 'Chưa có gói dịch vụ')       # F chỉ có gói ngừng áp dụng
        self.assertContains(res, 'Lê Minh Khôi')

    # ---- UC2.1: từ khóa và ID ----
    def test_tim_theo_id_nhieu_dang(self):
        for q in (f'NAG-{self.a.pk:04d}', f'nag {self.a.pk}', f'{self.a.pk:04d}', str(self.a.pk)):
            res = self.client.get(self.url, {'q': q})
            self.hien(res, self.a)
            self.khong_hien(res, self.b, self.f)

    def test_id_cua_ho_so_chua_duyet_khong_tim_thay(self):
        res = self.client.get(self.url, {'q': f'NAG-{self.cho_duyet.pk:04d}'})
        self.khong_hien(res, self.cho_duyet)
        self.assertContains(res, 'Không tìm thấy Nhiếp ảnh gia phù hợp với thông tin tìm kiếm.')

    def test_tim_khong_can_go_dau_va_khong_phan_biet_hoa_thuong(self):
        for q in ('le minh', 'LÊ MINH KHÔI', 'khoi', 'minh khoi'):
            res = self.client.get(self.url, {'q': q})
            self.hien(res, self.a)
            self.khong_hien(res, self.b)

    def test_tim_theo_loai_hinh_khu_vuc_va_gioi_thieu(self):
        self.hien(self.client.get(self.url, {'q': 'da lat'}), self.b)             # khu vực "Đà Lạt"
        self.khong_hien(self.client.get(self.url, {'q': 'da lat'}), self.a)
        self.hien(self.client.get(self.url, {'q': 'chan dung'}), self.b, self.f)  # loại hình
        self.hien(self.client.get(self.url, {'q': 'chuyen chup'}), self.a)        # giới thiệu

    def test_nhieu_tu_phai_khop_du(self):
        res = self.client.get(self.url, {'q': 'cuoi tu nhien'})
        self.hien(res, self.a, self.f)
        res = self.client.get(self.url, {'q': 'cuoi cinematic'})                  # không ai có cả hai
        self.assertContains(res, 'Không tìm thấy Nhiếp ảnh gia phù hợp với thông tin tìm kiếm.')

    def test_khong_co_ket_qua_thi_bao_ro(self):
        res = self.client.get(self.url, {'q': 'khongtontai'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Không tìm thấy Nhiếp ảnh gia phù hợp với thông tin tìm kiếm.')

    def test_tu_khoa_khong_hop_le(self):
        res = self.client.get(self.url, {'q': '%%%'})
        self.assertContains(res, 'Từ khóa không hợp lệ')
        self.khong_hien(res, self.a, self.b, self.f)
        res = self.client.get(self.url, {'q': 'a' * 101})
        self.assertContains(res, 'Từ khóa tối đa 100 ký tự.')
        self.khong_hien(res, self.a)

    # ---- UC2.2: bộ lọc ----
    def test_loc_loai_hinh(self):
        res = self.client.get(self.url, {'loai_hinh': [self.cuoi.pk]})
        self.hien(res, self.a, self.f)
        self.khong_hien(res, self.b)

    def test_chon_nhieu_muc_trong_mot_nhom_la_hoac(self):
        res = self.client.get(self.url, {'loai_hinh': [self.cuoi.pk, self.chan_dung.pk]})
        self.hien(res, self.a, self.b, self.f)

    def test_nhieu_nhom_la_va(self):
        res = self.client.get(self.url, {'loai_hinh': [self.cuoi.pk], 'phong_cach': [self.tu_nhien.pk],
                                         'khu_vuc': [self.hcm.pk]})
        self.hien(res, self.a, self.f)
        self.khong_hien(res, self.b)
        res = self.client.get(self.url, {'loai_hinh': [self.cuoi.pk], 'khu_vuc': [self.da_lat.pk]})
        self.assertContains(res, 'Không có Nhiếp ảnh gia phù hợp với các tiêu chí đã chọn.')

    def test_loc_khoang_gia_chi_tinh_goi_dang_ap_dung(self):
        res = self.client.get(self.url, {'gia_tu': 1500000, 'gia_den': 2500000})
        self.hien(res, self.a)
        self.khong_hien(res, self.b, self.f)          # B: 1tr và 4tr đều ngoài khoảng; F: gói 500k đã ngừng
        res = self.client.get(self.url, {'gia_den': 1000000})
        self.hien(res, self.b)
        self.khong_hien(res, self.f)                  # gói 500.000 của F đã "Ngừng áp dụng"
        res = self.client.get(self.url, {'gia_tu': 3000000})
        self.hien(res, self.b)                        # B có gói 4tr
        self.khong_hien(res, self.a)

    def test_loc_khong_nhan_nham_nguoi_chua_duyet(self):
        res = self.client.get(self.url, {'loai_hinh': [self.cuoi.pk], 'gia_tu': 1000000})
        self.khong_hien(res, self.cho_duyet, self.tu_choi, self.bi_khoa)

    def test_tieu_chi_loc_khong_hop_le(self):
        truong_hop = (
            ({'gia_tu': 5000000, 'gia_den': 1000000}, 'Khoảng giá không hợp lệ'),
            ({'gia_tu': 'abc'}, 'Giá bắt đầu phải là số nguyên.'),
            ({'gia_den': '-5'}, 'Giá kết thúc không được âm.'),
            ({'loai_hinh': [999999]}, 'Loại hình chụp đã chọn không hợp lệ.'),
            ({'khu_vuc': ['abc']}, 'Khu vực đã chọn không hợp lệ.'),
            ({'sap_xep': 'abc'}, 'Cách sắp xếp không hợp lệ.'),
        )
        for tham_so, thong_bao in truong_hop:
            res = self.client.get(self.url, tham_so)
            self.assertEqual(res.status_code, 200, tham_so)
            self.assertContains(res, thong_bao)
            self.khong_hien(res, self.a, self.b, self.f)

    def test_tu_khoa_ket_hop_bo_loc(self):
        res = self.client.get(self.url, {'q': 'tu nhien', 'khu_vuc': [self.da_lat.pk]})
        self.assertContains(res, 'Không có Nhiếp ảnh gia phù hợp với các tiêu chí đã chọn.')
        res = self.client.get(self.url, {'q': 'khoi', 'khu_vuc': [self.hcm.pk]})
        self.hien(res, self.a)
        self.khong_hien(res, self.f)

    # ---- sắp xếp ----
    def vi_tri(self, res, *cac_nag):
        html = res.content.decode()
        return [html.index(f'ID: NAG-{n.pk:04d}') for n in cac_nag]

    def test_sap_xep_mac_dinh_danh_gia_cao_truoc(self):
        res = self.client.get(self.url)
        vt = self.vi_tri(res, self.a, self.b, self.f)
        self.assertEqual(vt, sorted(vt))              # A (điểm 4.5) trước; B, F chưa có điểm theo mã tăng dần

    def test_sap_xep_theo_gia(self):
        res = self.client.get(self.url, {'sap_xep': 'gia_tang'})
        vt = self.vi_tri(res, self.b, self.a, self.f)
        self.assertEqual(vt, sorted(vt))              # B (từ 1tr), A (2tr), F (chưa có gói) cuối
        res = self.client.get(self.url, {'sap_xep': 'gia_giam'})
        vt = self.vi_tri(res, self.a, self.b, self.f)
        self.assertEqual(vt, sorted(vt))

    def test_sap_xep_nhieu_danh_gia(self):
        res = self.client.get(self.url, {'sap_xep': 'danh_gia'})
        vt = self.vi_tri(res, self.a, self.b, self.f)
        self.assertEqual(vt, sorted(vt))

    # ---- phân trang ----
    def test_phan_trang(self):
        for i in range(10):                            # tổng 3 + 10 = 13 người
            self.tao_nag(f'Ho{i}', f'Ten{i}', [self.cuoi], [self.tu_nhien], [self.hcm], gia=[1000000])
        res = self.client.get(self.url)
        self.assertContains(res, 'class="card tim__the', count=12)
        self.assertContains(res, '13 nhiếp ảnh gia')
        res = self.client.get(self.url, {'page': 2})
        self.assertContains(res, 'class="card tim__the', count=1)
        self.assertEqual(self.client.get(self.url, {'page': 999}).status_code, 200)
        self.assertEqual(self.client.get(self.url, {'page': 'abc'}).status_code, 200)

    def test_phan_trang_giu_tieu_chi_loc(self):
        for i in range(12):
            self.tao_nag(f'Ho{i}', f'Ten{i}', [self.cuoi], [self.tu_nhien], [self.hcm], gia=[1000000])
        res = self.client.get(self.url, {'loai_hinh': [self.cuoi.pk]})
        self.assertContains(res, f'loai_hinh={self.cuoi.pk}')     # liên kết sang trang 2 vẫn mang bộ lọc
        self.assertContains(res, 'page=2')

    # ---- hàm phụ ----
    def test_bo_dau_va_dinh_dang_tien(self):
        self.assertEqual(bo_dau('Đặng Lê Ánh'), 'dang le anh')
        self.assertEqual(dinh_dang_tien(Decimal('1500000')), '1.500.000đ')
        self.assertEqual(dinh_dang_tien(500), '500đ')

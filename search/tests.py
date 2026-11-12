# search/tests.py - K8: tìm kiếm và lọc nhiếp ảnh gia. Chạy: python manage.py test search
# (cần config/urls.py có include('search.urls'))
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
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
            Concept='c',
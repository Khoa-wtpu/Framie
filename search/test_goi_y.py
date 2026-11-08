# search/test_goi_y.py - E3: Trợ lý chọn Nhiếp ảnh gia. Chạy: python manage.py test search.test_goi_y
# Các con số kỳ vọng được tính tay theo công thức ở E1 (mục 2.2); chú thích cạnh từng test.
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookings.giu_cho import SO_NGAY_HIEN_THI_LICH
from bookings.models import Booking
from core.constants import (LoaiHauKy, TrangThaiBooking, TrangThaiGoi, TrangThaiHoSo, TrangThaiSlot,
                            VaiTro)
from profiles.models import (GoiDichVu, KhuVuc, LoaiHinhChup, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach, PhongCach)
from reviews.models import DanhGia
from schedule.models import LichKhaDung
from search import goi_y
from search.goi_y import (NGUONG_HIEN_THI, SO_NGAY_CHON_TOI_DA, _danh_sach_ung_vien, goi_y_nhiep_anh_gia,
                          goi_y_noi_tieu_chi, kiem_tra_cau_tra_loi, lam_tron_half_up)

User = get_user_model()
D = Decimal


class GoiYTestCase(TestCase):
    def setUp(self):
        self.dem = 0
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.khach = self.tao_user('khach')
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.s1 = PhongCach.objects.create(TenPhongCach='Tự nhiên')
        self.s2 = PhongCach.objects.create(TenPhongCach='Cinematic')
        self.s3 = PhongCach.objects.create(TenPhongCach='Vintage')
        self.s4 = PhongCach.objects.create(TenPhongCach='Tối giản')
        self.hcm = KhuVuc.objects.create(TenKhuVuc='TP.HCM')
        self.da_lat = KhuVuc.objects.create(TenKhuVuc='Đà Lạt')
        self.ngay = timezone.localdate() + timedelta(days=5)

    # ---------------- dữ liệu mẫu ----------------
    def tao_user(self, ten, **kw):
        self.dem += 1
        # create() thay vì create_user() để khỏi băm mật khẩu (chậm); test không cần đăng nhập.
        return User.objects.create(username=f'{ten}{self.dem}', email=f'{ten}{self.dem}@example.com',
                                   so_dien_thoai=f'09{self.dem:08d}', **kw)

    def tao_goi(self, nag, loai, gia, phut=60, trang_thai=TrangThaiGoi.DANG_AP_DUNG):
        return GoiDichVu.objects.create(MaNhiepAnhGia=nag, MaLoaiHinh=loai, TenGoi=f'Gói {gia}-{phut}', Gia=D(gia),
                                        ThoiLuongChup=phut, LoaiHauKy=LoaiHauKy.TOAN_BO, TrangThai=trang_thai)

    def tao_slot(self, nag, ngay=None, bat_dau=time(9, 0), ket_thuc=time(12, 0), trang_thai=TrangThaiSlot.TRONG):
        return LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=ngay or self.ngay, GioBatDau=bat_dau,
                                          GioKetThuc=ket_thuc, TrangThai=trang_thai)

    def danh_gia(self, nag, diem):
        # Mỗi đánh giá cần một Booking Hoàn thành. Slot đặt xa (>= 40 ngày) để không lọt vào khoảng chọn ngày;
        # gói "Đã ẩn" để không ảnh hưởng tập gói áp dụng.
        self.dem += 1
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=timezone.localdate() + timedelta(days=40 + self.dem),
                                          GioBatDau=time(9, 0), GioKetThuc=time(10, 0))
        goi = self.tao_goi(nag, self.cuoi, 123000 + self.dem, trang_thai=TrangThaiGoi.DA_AN)
        bk = Booking.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
                                    NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
                                    Concept='c', TrangThai=TrangThaiBooking.HOAN_THANH)
        DanhGia.objects.create(MaBooking=bk, MaNhiepAnhGia=nag, Diem=diem)

    def tao_nag(self, loai=None, cach=(), vuc=None, goi=None, slot=True, danh_gia=(),
                trang_thai=TrangThaiHoSo.DA_DUYET, hoat_dong=True):
        """loai/vuc mặc định (Cưới, TP.HCM); goi = [(loại hình, giá, số phút)] mặc định 1 gói Cưới 2.000.000 / 60 phút."""
        loai = [self.cuoi] if loai is None else loai
        vuc = [self.hcm] if vuc is None else vuc
        goi = [(self.cuoi, 2000000, 60)] if goi is None else goi
        user = self.tao_user('nag', first_name='A', last_name='B', is_active=hoat_dong,
                             trang_thai_ho_so=trang_thai)
        user.groups.add(self.nhom_nag)
        nag = NhiepAnhGia.objects.create(MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='Giới thiệu',
                                         NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        for m in loai:
            NhiepAnhGia_LoaiHinhChup.objects.create(MaNhiepAnhGia=nag, MaLoaiHinh=m)
        for m in cach:
            NhiepAnhGia_PhongCach.objects.create(MaNhiepAnhGia=nag, MaPhongCach=m)
        for m in vuc:
            NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=nag, MaKhuVuc=m)
        for lh, gia, phut in goi:
            self.tao_goi(nag, lh, gia, phut)
        if slot:
            self.tao_slot(nag)
        for d in danh_gia:
            self.danh_gia(nag, d)
        return nag

    def cau(self, **kw):
        c = dict(loai_hinh=self.cuoi.pk, khu_vuc=self.hcm.pk, ngan_sach=None, ngay_chup=self.ngay, phong_cach=[])
        c.update(kw)
        return c

    def ids(self, ket_qua):
        return [k.nhiep_anh_gia.pk for k in ket_qua]

    def uv(self, **kw):
        """{mã NAG: _UngVien} - xem điểm của cả người bị loại bởi ngưỡng."""
        return {u.nag.pk: u for u in _danh_sach_ung_vien(kiem_tra_cau_tra_loi(self.cau(**kw)))}


# =====================================================================
# Chấm điểm từng tiêu chí
# =====================================================================
class ChamDiemTest(GoiYTestCase):
    def test_lam_tron_half_up_khong_phai_ve_so_chan(self):
        self.assertEqual(lam_tron_half_up(D('62.5')), 63)       # round(62.5) của Python ra 62
        self.assertEqual(lam_tron_half_up(D('87.5')), 88)
        self.assertEqual(lam_tron_half_up(D('59.49')), 59)

    def test_loai_hinh_va_khu_vuc(self):
        # Không giới hạn ngân sách (20), bỏ qua phong cách (tổng 80), chưa ai có đánh giá.
        du = self.tao_nag()                                    # đúng loại + đúng khu: 30+20+20 = 70 -> 87,5 -> 88
        sai_khu = self.tao_nag(vuc=[self.da_lat])              # 30+0+20 = 50 -> 62,5 -> 63
        sai_loai = self.tao_nag(loai=[self.chan_dung])         # 0+20+20 = 40 -> 50 (dưới ngưỡng)
        sai_ca_hai = self.tao_nag(loai=[self.chan_dung], vuc=[self.da_lat])   # 20 -> 25
        uv = self.uv()
        self.assertEqual([uv[n.pk].phan_tram for n in (du, sai_khu, sai_loai, sai_ca_hai)], [88, 63, 50, 25])
        # Chỉ hai người đầu qua ngưỡng 60.
        self.assertEqual(self.ids(goi_y_nhiep_anh_gia(self.cau())), [du.pk, sai_khu.pk])

    def test_ngan_sach_dung_100_dung_120_va_vuot_120(self):
        # Ngân sách 3.000.000: 120% = 3.600.000. Các tiêu chí khác đều đủ (30+20), tổng 80.
        trong = self.tao_nag(goi=[(self.cuoi, 3000000, 60)])      # 100% -> đủ 20 -> 70 -> 88
        dung_120 = self.tao_nag(goi=[(self.cuoi, 3600000, 60)])   # đúng 120% -> 10 -> 60 -> 75
        vuot = self.tao_nag(goi=[(self.cuoi, 3600300, 60)])       # 120,01% -> 0 -> 50 -> 62,5 -> 63
        ket_qua = goi_y_nhiep_anh_gia(self.cau(ngan_sach=D('3000000')))
        self.assertEqual([(k.nhiep_anh_gia.pk, k.diem) for k in ket_qua],
                         [(trong.pk, 88), (dung_120.pk, 75), (vuot.pk, 63)])

    def test_ngan_sach_khong_gioi_han_du_diem_va_khong_co_chip_tien(self):
        nag = self.tao_nag(goi=[(self.cuoi, 99000000, 60)])
        k = goi_y_nhiep_anh_gia(self.cau(ngan_sach=None))[0]
        self.assertEqual(k.nhiep_anh_gia.pk, nag.pk)
        self.assertEqual(k.diem, 88)
        self.assertFalse(any('ngân sách' in c for c in k.ly_do))

    def test_phong_cach_ti_le_khop_va_tong_100(self):
        # Khách chọn 3 phong cách -> tổng 100. Nền: 30 + 20 + 20 (ngân sách không giới hạn) = 70.
        khop_hai = self.tao_nag(cach=[self.s1, self.s2])            # +20*2/3 = 83,33 -> 83
        khong_khop = self.tao_nag(cach=[self.s4])                   # +0 -> 70
        khop_het = self.tao_nag(cach=[self.s1, self.s2, self.s3])   # +20 -> 90
        uv = self.uv(phong_cach=[self.s1.pk, self.s2.pk, self.s3.pk])
        self.assertEqual([uv[n.pk].phan_tram for n in (khop_hai, khong_khop, khop_het)], [83, 70, 90])

    def test_bo_qua_phong_cach_thi_tong_la_80(self):
        nag = self.tao_nag(cach=[self.s4])
        self.assertEqual(self.uv(phong_cach=[])[nag.pk].tong, 80)
        self.assertEqual(self.uv(phong_cach=[])[nag.pk].phan_tram, 88)    # 70/80, không phải 70/100
        self.assertEqual(self.uv(phong_cach=[self.s1.pk])[nag.pk].tong, 100)
        self.assertEqual(self.uv(phong_cach=[self.s1.pk])[nag.pk].phan_tram, 70)

    def test_chua_co_danh_gia_toi_da_90_va_co_chip(self):
        nag = self.tao_nag(cach=[self.s1])
        k = goi_y_nhiep_anh_gia(self.cau(phong_cach=[self.s1.pk]))[0]
        self.assertEqual(k.nhiep_anh_gia.pk, nag.pk)
        self.assertEqual(k.diem, 90)                      # 30+20+20+20, đánh giá 0 nhưng vẫn chia cho 100
        self.assertIsNone(k.diem_tb)
        self.assertEqual(k.so_danh_gia, 0)
        k2 = goi_y_nhiep_anh_gia(self.cau())[0]           # bỏ qua phong cách: chip chỉ còn 3 -> có "Chưa có đánh giá"
        self.assertEqual(k2.ly_do, ['Chụp Cưới', 'Hoạt động tại TP.HCM', 'Chưa có đánh giá'])

    def test_diem_danh_gia_trung_binh(self):
        self.tao_nag(danh_gia=[5, 4])                     # tb 4,5 -> (4,5/5) x 10 = 9 điểm
        k = goi_y_nhiep_anh_gia(self.cau())[0]
        self.assertEqual(k.diem, 99)                      # 30+20+20+9 = 79 trên tổng 80 -> 98,75 -> 99
        self.assertEqual(k.diem_tb, 4.5)
        self.assertEqual(k.so_danh_gia, 2)
        self.assertEqual(k.ly_do, ['Chụp Cưới', 'Hoạt động tại TP.HCM', 'Đánh giá 4.5/5'])

    def test_chip_ly_do_toi_da_3_theo_thu_tu_uu_tien(self):
        self.tao_nag(cach=[self.s1], goi=[(self.cuoi, 2000000, 60)], danh_gia=[5])
        k = goi_y_nhiep_anh_gia(self.cau(ngan_sach=D('2500000'), phong_cach=[self.s1.pk]))[0]
        # Có đủ 5 lý do (loại hình, khu vực, phong cách, ngân sách, đánh giá) nhưng chỉ lấy 3 đầu theo thứ tự ưu tiên.
        self.assertEqual(k.ly_do, ['Chụp Cưới', 'Hoạt động tại TP.HCM', 'Phong cách Tự nhiên phù hợp'])

    def test_chip_ngan_sach_trong_va_gan(self):
        self.tao_nag(goi=[(self.cuoi, 2000000, 60)])
        self.tao_nag(goi=[(self.cuoi, 2400000, 60)])
        k_trong, k_gan = goi_y_nhiep_anh_gia(self.cau(ngan_sach=D('2000000')))
        self.assertIn('Gói từ 2.000.000đ trong ngân sách', k_trong.ly_do)
        self.assertIn('Gói từ 2.400.000đ gần ngân sách', k_gan.ly_do)


# =====================================================================
# Tập gói áp dụng và khung giờ hợp lệ
# =====================================================================
class TapGoiVaKhungGioTest(GoiYTestCase):
    def test_tap_goi_dung_loai_hinh_bo_qua_goi_re_hon_cua_loai_khac(self):
        nag = self.tao_nag(loai=[self.cuoi, self.chan_dung],
                           goi=[(self.cuoi, 3000000, 60), (self.chan_dung, 1000000, 60)])
        self.assertEqual(self.uv()[nag.pk].gia_tu, D('3000000'))          # chọn Cưới: bỏ qua gói Chân dung 1.000.000
        self.assertEqual(self.uv(loai_hinh=self.chan_dung.pk)[nag.pk].gia_tu, D('1000000'))

    def test_khong_co_goi_dung_loai_thi_lay_moi_goi(self):
        nag = self.tao_nag(loai=[self.chan_dung], goi=[(self.chan_dung, 1500000, 60), (self.chan_dung, 1800000, 60)])
        self.assertEqual(self.uv()[nag.pk].gia_tu, D('1500000'))          # khách chọn Cưới nhưng người này chỉ có gói Chân dung

    def test_goi_ngung_ap_dung_khong_tinh(self):
        nag = self.tao_nag(goi=[(self.cuoi, 2000000, 60)])
        self.tao_goi(nag, self.cuoi, 500000, 60, trang_thai=TrangThaiGoi.NGUNG_AP_DUNG)
        self.assertEqual(self.uv()[nag.pk].gia_tu, D('2000000'))

    def test_khung_gio_ngan_hon_moi_goi_thi_loai(self):
        # Khung giờ 60 phút, nhưng gói duy nhất cần 120 phút -> không có khung giờ hợp lệ -> loại.
        nag = self.tao_nag(goi=[(self.cuoi, 2000000, 120)], slot=False)
        self.tao_slot(nag, bat_dau=time(9, 0), ket_thuc=time(10, 0))
        self.assertEqual(goi_y_nhiep_anh_gia(self.cau()), [])

    def test_khung_gio_du_dai_cho_it_nhat_mot_goi(self):
        nag = self.tao_nag(goi=[(self.cuoi, 3000000, 120), (self.cuoi, 2000000, 60)], slot=False)
        self.tao_slot(nag, bat_dau=time(9, 0), ket_thuc=time(10, 0))      # vừa gói 60 phút
        k = goi_y_nhiep_anh_gia(self.cau())[0]
        self.assertEqual(k.nhiep_anh_gia.pk, nag.pk)
        self.assertEqual(k.gia_tu, D('2000000'))

    def test_khung_gio_chi_lay_dung_ngay_con_trong_va_xep_theo_gio(self):
        nag = self.tao_nag(slot=False)
        chieu = self.tao_slot(nag, bat_dau=time(14, 0), ket_thuc=time(17, 0))
        sang = self.tao_slot(nag, bat_dau=time(9, 0), ket_thuc=time(12, 0))
        self.tao_slot(nag, ngay=self.ngay + timedelta(days=1))                              # sai ngày
        self.tao_slot(nag, bat_dau=time(18, 0), ket_thuc=time(20, 0), trang_thai=TrangThaiSlot.DANG_GIU)   # đang giữ
        self.tao_slot(nag, bat_dau=time(20, 30), ket_thuc=time(22, 0), trang_thai=TrangThaiSlot.DA_DAT)    # đã đặt
        k = goi_y_nhiep_anh_gia(self.cau())[0]
        self.assertEqual([lich.pk for lich in k.khung_gio], [sang.pk, chieu.pk])

    def test_khong_co_khung_gio_dung_ngay_thi_loai(self):
        self.tao_nag(slot=False)
        self.assertEqual(goi_y_nhiep_anh_gia(self.cau()), [])

    def test_chi_nhiep_anh_gia_cong_khai_va_co_goi(self):
        ok = self.tao_nag()
        self.tao_nag(trang_thai=TrangThaiHoSo.CHO_DUYET)
        self.tao_nag(trang_thai=TrangThaiHoSo.DA_TU_CHOI)
        self.tao_nag(hoat_dong=False)
        self.tao_nag(goi=[])                                   # không có gói đang áp dụng
        self.assertEqual(self.ids(goi_y_nhiep_anh_gia(self.cau())), [ok.pk])


# =====================================================================
# Ngưỡng, xếp hạng, giới hạn số lượng
# =====================================================================
class XepHangTest(GoiYTestCase):
    def test_nguong_so_voi_phan_tram_da_lam_tron(self):
        self.assertEqual(NGUONG_HIEN_THI, 60)
        cau = self.cau(phong_cach=[self.s1.pk, self.s2.pk, self.s3.pk])      # tổng 100
        # Sai loại hình (0) + khu vực đúng (20) + ngân sách không giới hạn (20) + khớp 2/3 phong cách (13,333) = 53,333.
        duoi = self.tao_nag(loai=[self.chan_dung], cach=[self.s1, self.s2], danh_gia=[3])               # +6 -> 59,333 -> 59
        tren = self.tao_nag(loai=[self.chan_dung], cach=[self.s1, self.s2], danh_gia=[3, 3, 3, 3, 4])   # tb 3,2 -> +6,4 -> 59,733 -> 60
        ket_qua = goi_y_nhiep_anh_gia(cau)
        self.assertEqual([(k.nhiep_anh_gia.pk, k.diem) for k in ket_qua], [(tren.pk, 60)])
        self.assertEqual(self.uv(phong_cach=cau['phong_cach'])[duoi.pk].phan_tram, 59)

    def test_xep_theo_phan_tram_chua_lam_tron(self):
        cau = self.cau(phong_cach=[self.s1.pk, self.s2.pk, self.s3.pk])      # tổng 100
        # Y tạo trước (mã nhỏ hơn) và có đánh giá, nhưng 76,5 < 76,667 của X: X phải đứng trước dù cả hai cùng hiện 77%.
        y = self.tao_nag(vuc=[self.da_lat], cach=[self.s1, self.s2, self.s3], danh_gia=[3, 3, 3, 4])   # 30+0+20+20+6,5 = 76,5
        x = self.tao_nag(cach=[self.s1])                                                             # 30+20+20+6,667 = 76,667
        ket_qua = goi_y_nhiep_anh_gia(cau)
        self.assertEqual([(k.nhiep_anh_gia.pk, k.diem) for k in ket_qua], [(x.pk, 77), (y.pk, 77)])

    def test_bang_diem_thi_diem_danh_gia_cao_hon_dung_truoc(self):
        cau = self.cau(ngan_sach=D('2500000'), phong_cach=[self.s1.pk])      # tổng 100
        # N tạo trước (mã nhỏ): 30+20+10 (gói đúng 120%)+20 (khớp phong cách) = 80, chưa có đánh giá.
        n = self.tao_nag(cach=[self.s1], goi=[(self.cuoi, 3000000, 60)])
        # M: 30+20+20+0 (không khớp phong cách)+10 (tb 5,0) = 80. Bằng 80 nhưng đánh giá cao hơn nên đứng trước.
        m = self.tao_nag(goi=[(self.cuoi, 2500000, 60)], danh_gia=[5])
        ket_qua = goi_y_nhiep_anh_gia(cau)
        self.assertEqual([(k.nhiep_anh_gia.pk, k.diem) for k in ket_qua], [(m.pk, 80), (n.pk, 80)])

    def test_bang_diem_va_danh_gia_thi_nhieu_luot_hon_dung_truoc(self):
        it = self.tao_nag(danh_gia=[4, 4])                  # tb 4,0
        nhieu = self.tao_nag(danh_gia=[4, 4, 4, 4])         # tb 4,0 nhưng nhiều lượt hơn
        self.assertEqual(self.ids(goi_y_nhiep_anh_gia(self.cau())), [nhieu.pk, it.pk])

    def test_bang_het_thi_theo_ma(self):
        a, b, c = self.tao_nag(), self.tao_nag(), self.tao_nag()
        self.assertEqual(self.ids(goi_y_nhiep_anh_gia(self.cau())), [a.pk, b.pk, c.pk])

    def test_toi_da_ket_qua(self):
        for _ in range(7):
            self.tao_nag()
        self.assertEqual(len(goi_y_nhiep_anh_gia(self.cau())), 5)               # mặc định 5
        self.assertEqual(len(goi_y_nhiep_anh_gia(self.cau(), toi_da=2)), 2)
        self.assertEqual(len(goi_y_nhiep_anh_gia(self.cau(), toi_da=None)), 7)
        self.assertEqual(goi_y_nhiep_anh_gia(self.cau(), toi_da=0), [])

    def test_ket_qua_co_dung_kieu_du_lieu(self):
        nag = self.tao_nag(danh_gia=[5])
        k = goi_y_nhiep_anh_gia(self.cau())[0]
        self.assertEqual(k.nhiep_anh_gia, nag)
        self.assertIsInstance(k.diem, int)
        self.assertIsInstance(k.diem_tb, float)
        self.assertIsInstance(k.gia_tu, Decimal)
        self.assertTrue(all(isinstance(lich, LichKhaDung) for lich in k.khung_gio))
        self.assertLessEqual(len(k.ly_do), 3)

    def test_khong_ghi_gi_vao_csdl(self):
        self.tao_nag(danh_gia=[5])
        so_lich, so_booking = LichKhaDung.objects.count(), Booking.objects.count()
        goi_y_nhiep_anh_gia(self.cau())
        goi_y_noi_tieu_chi(self.cau(ngay_chup=self.ngay + timedelta(days=3)))
        self.assertEqual((LichKhaDung.objects.count(), Booking.objects.count()), (so_lich, so_booking))


# =====================================================================
# Kiểm tra đầu vào (E1: ngày chụp hôm nay + 29 được, + 30 bị từ chối)
# =====================================================================
class DauVaoTest(GoiYTestCase):
    def test_ngay_chup_bien(self):
        hom_nay = timezone.localdate()
        kiem_tra_cau_tra_loi(self.cau(ngay_chup=hom_nay))                                   # hôm nay: được
        kiem_tra_cau_tra_loi(self.cau(ngay_chup=hom_nay + timedelta(days=29)))             # hôm nay + 29: được
        with self.assertRaises(ValidationError):
            kiem_tra_cau_tra_loi(self.cau(ngay_chup=hom_nay + timedelta(days=30)))         # hôm nay + 30: bị từ chối
        with self.assertRaises(ValidationError):
            kiem_tra_cau_tra_loi(self.cau(ngay_chup=hom_nay - timedelta(days=1)))          # quá khứ

    def test_ngay_chup_phai_la_date_khong_phai_datetime(self):
        with self.assertRaises(ValidationError):
            kiem_tra_cau_tra_loi(self.cau(ngay_chup=datetime.now()))
        with self.assertRaises(ValidationError):
            kiem_tra_cau_tra_loi(self.cau(ngay_chup='2026-11-20'))

    def test_thieu_hoac_sai_cac_cau_bat_buoc(self):
        for sai in (dict(loai_hinh=None), dict(loai_hinh=9999), dict(khu_vuc=None), dict(khu_vuc=9999),
                    dict(ngay_chup=None), dict(ngan_sach=D('0')), dict(ngan_sach=D('-5')),
                    dict(phong_cach=[self.s1.pk, self.s2.pk, self.s3.pk, self.s4.pk]), dict(phong_cach=[9999])):
            with self.subTest(sai=sai), self.assertRaises(ValidationError):
                kiem_tra_cau_tra_loi(self.cau(**sai))
        with self.assertRaises(ValidationError):
            kiem_tra_cau_tra_loi(None)

    def test_dau_vao_hop_le_duoc_doi_kieu(self):
        c = kiem_tra_cau_tra_loi(self.cau(ngan_sach=3000000, phong_cach=[self.s1.pk, self.s1.pk, str(self.s2.pk)]))
        self.assertEqual(c.ngan_sach, D('3000000'))
        self.assertEqual([p.pk for p in c.phong_cach], [self.s1.pk, self.s2.pk])      # bỏ trùng, giữ thứ tự

    def test_phong_cach_none_hoac_rong_la_bo_qua(self):
        self.assertEqual(kiem_tra_cau_tra_loi(self.cau(phong_cach=None)).phong_cach, [])
        self.assertEqual(kiem_tra_cau_tra_loi(self.cau(phong_cach=[])).phong_cach, [])

    def test_hang_so_ngay_khop_trang_lich(self):
        # Nếu trang lịch đổi số ngày hiển thị thì test này nhắc cập nhật SO_NGAY_CHON_TOI_DA.
        self.assertEqual(SO_NGAY_CHON_TOI_DA, SO_NGAY_HIEN_THI_LICH)
        self.assertIs(goi_y.SO_NGAY_CHON_TOI_DA, SO_NGAY_CHON_TOI_DA)


# =====================================================================
# Gợi ý nới tiêu chí khi kết quả rỗng
# =====================================================================
class GoiYNoiTieuChiTest(GoiYTestCase):
    def test_con_ket_qua_thi_khong_goi_y(self):
        self.tao_nag()
        self.assertEqual(goi_y_noi_tieu_chi(self.cau()), [])

    def test_khong_ai_co_lich_dung_ngay_thi_goi_y_doi_ngay(self):
        self.tao_nag()                                                  # chỉ có slot ở self.ngay
        cau = self.cau(ngay_chup=self.ngay + timedelta(days=3))
        self.assertEqual(goi_y_nhiep_anh_gia(cau), [])
        self.assertEqual(goi_y_noi_tieu_chi(cau), ['Thử chọn ngày khác'])

    def test_bo_ngan_sach_thi_co_ket_qua_thi_goi_y_nang_ngan_sach(self):
        # Người này chỉ sai ngân sách: 30+20+0+0(không khớp phong cách) = 50/100 -> bị loại; bỏ giới hạn ngân sách: 70 -> hiện.
        self.tao_nag(goi=[(self.cuoi, 5000000, 60)])
        cau = self.cau(ngan_sach=D('2000000'), phong_cach=[self.s1.pk])
        self.assertEqual(goi_y_nhiep_anh_gia(cau), [])
        self.assertEqual(goi_y_noi_tieu_chi(cau), ['Thử nâng ngân sách hoặc chọn “Không giới hạn”'])

    def test_con_lai_thi_goi_y_doi_khu_vuc_hoac_loai_hinh(self):
        self.tao_nag(loai=[self.chan_dung], vuc=[self.da_lat])          # có lịch đúng ngày nhưng sai loại hình và khu vực
        cau = self.cau()
        self.assertEqual(goi_y_nhiep_anh_gia(cau), [])
        self.assertEqual(goi_y_noi_tieu_chi(cau), ['Thử chọn khu vực khác', 'Thử chọn loại hình khác'])
        # Đã không giới hạn ngân sách rồi thì không gợi ý nâng ngân sách nữa.
        self.assertEqual(goi_y_noi_tieu_chi(self.cau(ngan_sach=None)), ['Thử chọn khu vực khác', 'Thử chọn loại hình khác'])

    def test_khong_co_nhiep_anh_gia_nao_thi_goi_y_doi_ngay(self):
        self.assertEqual(goi_y_noi_tieu_chi(self.cau()), ['Thử chọn ngày khác'])

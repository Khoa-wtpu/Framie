# profiles/tests_goi.py - K6: quản lý gói dịch vụ (UC1.4). Chạy: python manage.py test profiles
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from core.constants import LoaiHauKy, TrangThaiBooking, TrangThaiGoi as TG, TrangThaiHoSo, VaiTro
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()


class GoiDichVuTestCase(TestCase):
    def setUp(self):
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.nhom_khach, _ = Group.objects.get_or_create(name=VaiTro.KHACH_HANG)
        self.dem = 0
        self.user, self.nag = self.tao_nag('nag1')
        self.user2, self.nag2 = self.tao_nag('nag2')
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.client.force_login(self.user)
        self.url_ds = reverse('service_packages')

    # ---- dữ liệu mẫu ----
    def tao_nag(self, ten, trang_thai=TrangThaiHoSo.DA_DUYET, co_ho_so=True):
        self.dem += 1
        user = User.objects.create_user(ten, f'{ten}@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09300000{self.dem:02d}')
        user.groups.add(self.nhom_nag)
        user.trang_thai_ho_so = trang_thai
        user.save()
        nag = None
        if co_ho_so:
            nag = NhiepAnhGia.objects.create(
                MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='x',
                NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        return user, nag

    def tao_goi(self, nag=None, ten='Gói cưới', trang_thai=TG.DANG_AP_DUNG, gia=1500000, so_anh=15):
        return GoiDichVu.objects.create(
            MaNhiepAnhGia=nag or self.nag, MaLoaiHinh=self.cuoi, TenGoi=ten, MoTa='Quyền lợi',
            Gia=Decimal(gia), ThoiLuongChup=90,
            LoaiHauKy=LoaiHauKy.GIOI_HAN if so_anh else LoaiHauKy.TOAN_BO,
            SoAnhHauKyToiDa=so_anh, TrangThai=trang_thai)

    def tao_booking(self, goi):
        khach = User.objects.create_user('khach', 'khach@example.com', 'Matkhau@123', so_dien_thoai='0988888888')
        khach.groups.add(self.nhom_khach)
        lich = LichKhaDung.objects.create(
            MaNhiepAnhGia=goi.MaNhiepAnhGia, Ngay=timezone.localdate() + timedelta(days=30),
            GioBatDau=time(9, 0), GioKetThuc=time(10, 0))
        return Booking.objects.create(
            MaKhachHang=khach, MaNhiepAnhGia=goi.MaNhiepAnhGia, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
            Concept='c', TrangThai=TrangThaiBooking.HOAN_THANH)

    def du_lieu(self, **doi):
        data = {'TenGoi': 'Gói chân dung', 'MaLoaiHinh': self.chan_dung.pk, 'MoTa': 'Chụp 1 giờ, 10 ảnh',
                'Gia': '1500000', 'ThoiLuongChup': '90', 'LoaiHauKy': LoaiHauKy.GIOI_HAN,
                'SoAnhHauKyToiDa': '15', 'TrangThai': TG.DANG_AP_DUNG}
        data.update(doi)
        return data

    def tin_nhan(self, res):
        return [str(m) for m in get_messages(res.wsgi_request)]

    def hanh_dong(self, goi, ten, **kw):
        return self.client.post(reverse('goi_hanh_dong', args=[goi.pk, ten]), **kw)

    # ---- quyền truy cập ----
    def test_chua_dang_nhap_bi_chuyen_ve_dang_nhap(self):
        self.client.logout()
        res = self.client.get(self.url_ds)
        self.assertEqual(res.status_code, 302)
        self.assertIn('dang-nhap', res.url)

    def test_khach_hang_bi_chan(self):
        khach = User.objects.create_user('khach', 'khach@example.com', 'Matkhau@123', so_dien_thoai='0988888888')
        khach.groups.add(self.nhom_khach)
        self.client.force_login(khach)
        for url in (self.url_ds, reverse('goi_them')):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_ho_so_chua_duyet_khong_vao_duoc(self):
        for trang_thai in (TrangThaiHoSo.CHO_DUYET, TrangThaiHoSo.DA_TU_CHOI):
            user, _ = self.tao_nag(f'u_{trang_thai[:3]}{self.dem}', trang_thai=trang_thai)
            self.client.force_login(user)
            res = self.client.get(self.url_ds)
            self.assertEqual(res.status_code, 302)
            self.assertIn('chưa được duyệt', self.tin_nhan(res)[0])
            self.assertEqual(self.client.post(reverse('goi_them'), self.du_lieu()).status_code, 302)
        self.assertEqual(GoiDichVu.objects.count(), 0)

    def test_chua_co_ho_so(self):
        user, _ = self.tao_nag('khongho', co_ho_so=False)
        self.client.force_login(user)
        res = self.client.get(self.url_ds)
        self.assertEqual(res.status_code, 302)
        self.assertIn('chưa có hồ sơ', self.tin_nhan(res)[0])

    # ---- danh sách và bộ lọc ----
    def test_danh_sach_tat_ca_hien_ca_goi_da_an_va_xep_thu_tu(self):
        self.tao_goi(ten='Gói ngừng', trang_thai=TG.NGUNG_AP_DUNG)
        self.tao_goi(ten='Gói ẩn', trang_thai=TG.DA_AN)
        self.tao_goi(ten='Gói đang')
        res = self.client.get(self.url_ds)
        self.assertContains(res, 'Hiển thị 3 gói dịch vụ')
        ten = [g.TenGoi for g in res.context['cac_goi']]
        self.assertEqual(ten, ['Gói đang', 'Gói ẩn', 'Gói ngừng'])      # Ngừng áp dụng nằm cuối cùng

    def test_goi_ngung_ap_dung_bi_gach_ten(self):
        self.tao_goi(ten='Gói ngừng', trang_thai=TG.NGUNG_AP_DUNG)
        self.assertContains(self.client.get(self.url_ds), 'class="gv__gach"')
        GoiDichVu.objects.update(TrangThai=TG.DANG_AP_DUNG)
        self.assertNotContains(self.client.get(self.url_ds), 'class="gv__gach"')

    def test_loc_theo_trang_thai(self):
        self.tao_goi(ten='Gói A')
        self.tao_goi(ten='Gói B', trang_thai=TG.NGUNG_AP_DUNG)
        self.tao_goi(ten='Gói C', trang_thai=TG.DA_AN)
        res = self.client.get(self.url_ds, {'trang_thai': 'da-an'})
        self.assertContains(res, 'Gói C')
        self.assertNotContains(res, 'Gói A')
        self.assertContains(res, 'Hiển thị 1 gói dịch vụ')
        res = self.client.get(self.url_ds, {'trang_thai': 'dang-ap-dung'})
        self.assertContains(res, 'Gói A')
        self.assertNotContains(res, 'Gói B')

    def test_loc_gia_tri_la_dung_mac_dinh(self):
        self.tao_goi(ten='Gói A')
        res = self.client.get(self.url_ds, {'trang_thai': 'abc'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Gói A')

    def test_chi_thay_goi_cua_minh(self):
        self.tao_goi(ten='Gói của tôi')
        self.tao_goi(nag=self.nag2, ten='Gói người khác')
        res = self.client.get(self.url_ds)
        self.assertContains(res, 'Gói của tôi')
        self.assertNotContains(res, 'Gói người khác')

    def test_hien_thi_gia_thoi_luong_va_hau_ky(self):
        self.tao_goi(ten='Gói A', gia=1500000, so_anh=15)
        self.tao_goi(ten='Gói B', so_anh=None)
        res = self.client.get(self.url_ds)
        self.assertContains(res, '1.500.000đ')
        self.assertContains(res, '90 phút')
        self.assertContains(res, 'Giới hạn 15 ảnh')
        self.assertContains(res, 'Hậu kỳ toàn bộ ảnh')

    def test_danh_sach_trong(self):
        res = self.client.get(self.url_ds)
        self.assertContains(res, 'chưa có gói dịch vụ nào')
        self.assertContains(res, 'Hiển thị 0 gói dịch vụ')

    def test_nut_thao_tac_theo_trang_thai(self):
        dang = self.tao_goi(ten='A')
        ngung = self.tao_goi(ten='B', trang_thai=TG.NGUNG_AP_DUNG)
        an = self.tao_goi(ten='C', trang_thai=TG.DA_AN)
        res = self.client.get(self.url_ds, {'trang_thai': 'da-an'})
        self.assertContains(res, reverse('goi_hanh_dong', args=[an.pk, 'hien-lai']))
        res = self.client.get(self.url_ds)
        self.assertContains(res, reverse('goi_hanh_dong', args=[dang.pk, 'ngung']))
        self.assertContains(res, reverse('goi_hanh_dong', args=[dang.pk, 'an']))       # đang áp dụng cũng ẩn được
        self.assertNotContains(res, reverse('goi_hanh_dong', args=[dang.pk, 'ap-dung-lai']))
        self.assertContains(res, reverse('goi_hanh_dong', args=[ngung.pk, 'ap-dung-lai']))
        self.assertContains(res, reverse('goi_hanh_dong', args=[ngung.pk, 'an']))

    # ---- thêm gói ----
    def test_mo_form_them(self):
        res = self.client.get(reverse('goi_them'))
        self.assertContains(res, 'Thêm gói dịch vụ')
        self.assertContains(res, 'Nhập thông tin gói dịch vụ hiển thị cho Khách hàng khi đặt lịch.')

    def test_them_goi_hop_le(self):
        res = self.client.post(reverse('goi_them'), self.du_lieu())
        self.assertRedirects(res, self.url_ds)
        goi = GoiDichVu.objects.get()
        self.assertEqual(goi.MaNhiepAnhGia, self.nag)
        self.assertEqual((goi.TenGoi, goi.Gia, goi.ThoiLuongChup, goi.SoAnhHauKyToiDa),
                         ('Gói chân dung', 1500000, 90, 15))
        self.assertEqual(goi.TrangThai, TG.DANG_AP_DUNG)
        self.assertIn('Đã thêm gói', self.tin_nhan(res)[0])

    def test_them_goi_hau_ky_toan_bo_xoa_so_anh(self):
        self.client.post(reverse('goi_them'),
                         self.du_lieu(LoaiHauKy=LoaiHauKy.TOAN_BO, SoAnhHauKyToiDa='20'))
        goi = GoiDichVu.objects.get()
        self.assertEqual(goi.LoaiHauKy, LoaiHauKy.TOAN_BO)
        self.assertIsNone(goi.SoAnhHauKyToiDa)

    def test_them_thieu_truong_bat_buoc(self):
        res = self.client.post(reverse('goi_them'), {})
        self.assertEqual(res.status_code, 200)
        for ten in ('TenGoi', 'MaLoaiHinh', 'MoTa', 'Gia', 'ThoiLuongChup', 'LoaiHauKy'):
            self.assertIn(ten, res.context['form'].errors)
        self.assertEqual(GoiDichVu.objects.count(), 0)

    def kiem_tra_loi(self, truong, **doi):
        so_goi_truoc = GoiDichVu.objects.count()
        res = self.client.post(reverse('goi_them'), self.du_lieu(**doi))
        self.assertEqual(res.status_code, 200)
        self.assertIn(truong, res.context['form'].errors)
        self.assertEqual(GoiDichVu.objects.count(), so_goi_truoc)      # không tạo thêm gói nào

    def test_gia_khong_hop_le(self):
        for gia in ('0', '-5', 'abc', '1500000.5'):
            self.kiem_tra_loi('Gia', Gia=gia)

    def test_thoi_luong_khong_hop_le(self):
        for phut in ('0', '-1', '1441', 'x'):
            self.kiem_tra_loi('ThoiLuongChup', ThoiLuongChup=phut)

    def test_gioi_han_phai_co_so_anh_duong(self):
        for so in ('', '0', '-3', '10001', 'abc'):
            self.kiem_tra_loi('SoAnhHauKyToiDa', SoAnhHauKyToiDa=so)

    def test_mo_ta_qua_dai(self):
        self.kiem_tra_loi('MoTa', MoTa='a' * 2001)

    def test_trang_thai_da_an_khong_chon_duoc_khi_them(self):
        self.kiem_tra_loi('TrangThai', TrangThai=TG.DA_AN)

    def test_trung_ten_goi_cua_cung_nhiep_anh_gia(self):
        self.tao_goi(ten='Gói chân dung')
        self.kiem_tra_loi('TenGoi', TenGoi='  gói CHÂN dung ')
        # nhưng chỉ tính trong gói của chính mình
        self.client.force_login(self.user2)
        res = self.client.post(reverse('goi_them'), self.du_lieu())
        self.assertRedirects(res, self.url_ds)

    def test_ten_goi_duoc_chuan_hoa_khoang_trang(self):
        self.client.post(reverse('goi_them'), self.du_lieu(TenGoi='  Gói   mới  '))
        self.assertEqual(GoiDichVu.objects.get().TenGoi, 'Gói mới')

    # ---- sửa gói ----
    def test_mo_form_sua_co_san_du_lieu(self):
        goi = self.tao_goi(ten='Gói cũ')
        res = self.client.get(reverse('goi_sua', args=[goi.pk]))
        self.assertContains(res, 'Chỉnh sửa gói dịch vụ')
        self.assertContains(res, 'Gói cũ')

    def test_sua_goi(self):
        goi = self.tao_goi(ten='Gói cũ')
        res = self.client.post(reverse('goi_sua', args=[goi.pk]),
                               self.du_lieu(TenGoi='Gói mới', Gia='2000000', TrangThai=TG.NGUNG_AP_DUNG))
        self.assertRedirects(res, self.url_ds)
        goi.refresh_from_db()
        self.assertEqual((goi.TenGoi, goi.Gia, goi.TrangThai), ('Gói mới', 2000000, TG.NGUNG_AP_DUNG))

    def test_sua_giu_nguyen_ten_khong_bi_bao_trung(self):
        goi = self.tao_goi(ten='Gói chân dung')
        res = self.client.post(reverse('goi_sua', args=[goi.pk]), self.du_lieu(Gia='999000'))
        self.assertRedirects(res, self.url_ds)

    def test_sua_goi_da_an_van_giu_trang_thai(self):
        goi = self.tao_goi(trang_thai=TG.DA_AN)
        res = self.client.post(reverse('goi_sua', args=[goi.pk]), self.du_lieu(TrangThai=TG.DA_AN))
        self.assertRedirects(res, self.url_ds)
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.DA_AN)

    def test_khong_sua_duoc_goi_cua_nguoi_khac(self):
        goi = self.tao_goi(nag=self.nag2, ten='Của người khác')
        self.assertEqual(self.client.get(reverse('goi_sua', args=[goi.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('goi_sua', args=[goi.pk]), self.du_lieu()).status_code, 404)
        goi.refresh_from_db()
        self.assertEqual(goi.TenGoi, 'Của người khác')

    # ---- đổi trạng thái ----
    def test_trang_xac_nhan_hien_dung_noi_dung(self):
        goi = self.tao_goi()
        res = self.client.get(reverse('goi_hanh_dong', args=[goi.pk, 'ngung']))
        self.assertContains(res, 'Xác nhận ngừng áp dụng')
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.DANG_AP_DUNG)       # mở trang xác nhận chưa đổi gì

    def test_ngung_ap_dung_roi_ap_dung_lai(self):
        goi = self.tao_goi()
        res = self.hanh_dong(goi, 'ngung')
        self.assertRedirects(res, self.url_ds)
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.NGUNG_AP_DUNG)
        self.assertIn('Đã ngừng áp dụng', self.tin_nhan(res)[0])
        self.hanh_dong(goi, 'ap-dung-lai')
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.DANG_AP_DUNG)

    def test_an_roi_hien_lai_ve_dung_trang_thai_cu(self):
        for truoc in (TG.DANG_AP_DUNG, TG.NGUNG_AP_DUNG):
            goi = self.tao_goi(ten=f'Gói {truoc}', trang_thai=truoc)
            self.hanh_dong(goi, 'an')
            goi.refresh_from_db()
            self.assertEqual(goi.TrangThai, TG.DA_AN)
            self.assertEqual(goi.TrangThaiTruocKhiAn, truoc)
            res = self.hanh_dong(goi, 'hien-lai')
            goi.refresh_from_db()
            self.assertEqual(goi.TrangThai, truoc)                       # về đúng trạng thái trước khi ẩn
            self.assertIsNone(goi.TrangThaiTruocKhiAn)
            self.assertIn(f'(trạng thái "{truoc}")', self.tin_nhan(res)[-1])   # thông báo mới nhất, không phải thông báo Ẩn còn tồn

    def test_hien_lai_goi_khong_ro_trang_thai_cu_thi_ve_ngung_ap_dung(self):
        goi = self.tao_goi(trang_thai=TG.DA_AN)                          # dữ liệu cũ, chưa ghi nhớ
        self.hanh_dong(goi, 'hien-lai')
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.NGUNG_AP_DUNG)

    def test_popup_hien_lai_noi_ro_trang_thai_se_ve(self):
        goi = self.tao_goi(trang_thai=TG.DANG_AP_DUNG)
        self.hanh_dong(goi, 'an')
        res = self.client.get(reverse('goi_hanh_dong', args=[goi.pk, 'hien-lai']))
        self.assertContains(res, TG.DANG_AP_DUNG)

    def test_popup_ngung_ap_dung_noi_ve_cuoi_danh_sach(self):
        self.tao_goi()
        self.assertContains(self.client.get(self.url_ds), 'chuyển xuống cuối danh sách')

    def test_chuyen_trang_thai_khong_hop_le(self):
        goi = self.tao_goi()                                     # đang áp dụng: không "áp dụng lại" được
        res = self.hanh_dong(goi, 'ap-dung-lai')
        self.assertRedirects(res, self.url_ds)
        self.assertIn('Không thể thực hiện', self.tin_nhan(res)[0])
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.DANG_AP_DUNG)
        res = self.client.get(reverse('goi_hanh_dong', args=[goi.pk, 'hien-lai']))
        self.assertEqual(res.status_code, 302)

    def test_hanh_dong_la_khong_ton_tai(self):
        goi = self.tao_goi()
        self.assertEqual(self.client.get(reverse('goi_hanh_dong', args=[goi.pk, 'bay-ba'])).status_code, 404)

    def test_khong_doi_trang_thai_goi_cua_nguoi_khac(self):
        goi = self.tao_goi(nag=self.nag2)
        for ten in ('ngung', 'xoa'):
            self.assertEqual(self.hanh_dong(goi, ten).status_code, 404)
        goi.refresh_from_db()
        self.assertEqual(goi.TrangThai, TG.DANG_AP_DUNG)

    # ---- xóa ----
    def test_trang_xac_nhan_xoa(self):
        goi = self.tao_goi()
        res = self.client.get(reverse('goi_hanh_dong', args=[goi.pk, 'xoa']))
        self.assertContains(res, 'Xóa gói dịch vụ')
        self.assertContains(res, 'Xác nhận xóa')
        self.assertTrue(GoiDichVu.objects.filter(pk=goi.pk).exists())

    def test_xoa_goi_chua_co_booking(self):
        goi = self.tao_goi()
        res = self.hanh_dong(goi, 'xoa')
        self.assertRedirects(res, self.url_ds)
        self.assertFalse(GoiDichVu.objects.filter(pk=goi.pk).exists())
        self.assertIn('Đã xóa gói', self.tin_nhan(res)[0])

    def test_xoa_goi_da_co_booking_thi_chuyen_sang_da_an(self):
        goi = self.tao_goi()
        self.tao_booking(goi)
        res = self.client.get(reverse('goi_hanh_dong', args=[goi.pk, 'xoa']))
        self.assertContains(res, 'đã có Booking')
        res = self.hanh_dong(goi, 'xoa')
        self.assertRedirects(res, self.url_ds)
        goi.refresh_from_db()                                    # vẫn còn trong CSDL
        self.assertEqual(goi.TrangThai, TG.DA_AN)
        self.assertEqual(goi.TrangThaiTruocKhiAn, TG.DANG_AP_DUNG)       # hiện lại vẫn về được trạng thái cũ
        self.assertIn('đã có Booking', self.tin_nhan(res)[0])
        self.assertEqual(Booking.objects.count(), 1)

    # ---- tìm kiếm trong danh sách ----
    def test_tim_theo_ten_khong_can_dau_va_hoa_thuong(self):
        self.tao_goi(ten='Chân dung cơ bản')
        self.tao_goi(ten='Gói cưới cao cấp')
        res = self.client.get(self.url_ds, {'q': 'CHAN dung'})
        self.assertContains(res, 'Chân dung cơ bản')
        self.assertNotContains(res, 'Gói cưới cao cấp')
        self.assertContains(res, 'Hiển thị 1 gói dịch vụ')

    def test_tim_theo_loai_hinh(self):
        self.tao_goi(ten='Gói A')                                # loại hình Cưới
        res = self.client.get(self.url_ds, {'q': 'cuoi'})
        self.assertContains(res, 'Gói A')

    def test_tim_ket_hop_bo_loc_va_khong_co_ket_qua(self):
        self.tao_goi(ten='Gói A')
        self.tao_goi(ten='Gói A ngừng', trang_thai=TG.NGUNG_AP_DUNG)
        res = self.client.get(self.url_ds, {'q': 'gói a', 'trang_thai': 'ngung-ap-dung'})
        self.assertContains(res, 'Hiển thị 1 gói dịch vụ')
        res = self.client.get(self.url_ds, {'q': 'không có đâu'})
        self.assertContains(res, 'Không tìm thấy gói dịch vụ nào phù hợp')
        self.assertContains(res, 'Xóa bộ lọc')

    def test_tim_khong_lo_goi_cua_nguoi_khac(self):
        self.tao_goi(nag=self.nag2, ten='Bí mật')
        self.assertNotContains(self.client.get(self.url_ds, {'q': 'bí mật'}), 'Bí mật')

    # ---- popup xác nhận ----
    def test_nut_mang_noi_dung_popup(self):
        goi = self.tao_goi(ten='Gói A')
        res = self.client.get(self.url_ds)
        self.assertContains(res, 'data-xac-nhan')
        self.assertContains(res, 'id="gv-popup"')
        self.assertContains(res, 'Xác nhận ngừng áp dụng')
        self.assertContains(res, 'Xác nhận xóa')
        self.assertContains(res, 'Xóa gói dịch vụ')

    def test_popup_xoa_canh_bao_khi_co_booking(self):
        goi = self.tao_goi(ten='Gói A')
        self.tao_booking(goi)
        self.assertContains(self.client.get(self.url_ds), 'đã có Booking')

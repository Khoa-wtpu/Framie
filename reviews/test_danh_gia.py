# Chạy: python manage.py test reviews.test_danh_gia      (N11: UC6.1 Đánh giá nhiếp ảnh gia)
import itertools
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from bookings.models import Booking
from core.constants import LoaiHauKy, TrangThaiBooking as TT, TrangThaiHoSo, VaiTro
from notifications.models import ThongBao
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from reviews import services
from reviews.models import DanhGia
from schedule.models import LichKhaDung

User = get_user_model()
HOP_THU_GIA = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}   # email chỉ vào mail.outbox, không gửi thật (P12)
urlpatterns = [path('', include('reviews.urls')),              # bảng đường dẫn riêng cho test (không phụ thuộc config/urls.py)
               path('bookings/', include('bookings.theo_doi')),    # thêm tên 'chi_tiet_booking' để redirect của view tìm thấy
               path('bookings/', include('bookings.tiep_nhan')),   # thêm tên 'chi_tiet_yeu_cau_booking' cho Nhiếp ảnh gia
               path('dang-nhap/', lambda request: HttpResponse('dang nhap'), name='login')]   # LOGIN_URL = 'login' cần có tên này
NGAY_KE_TIEP = itertools.count(1)                              # mỗi Booking một ngày khác nhau để khung giờ không trùng


def _tao_nag(ten, sdt, so_tk):                                 # tạo Nhiếp ảnh gia đã duyệt
    user = User.objects.create_user(ten, f'{ten}@x.vn', 'p', so_dien_thoai=sdt)
    user.groups.add(Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)[0])
    user.trang_thai_ho_so = TrangThaiHoSo.DA_DUYET
    user.save(update_fields=['trang_thai_ho_so'])
    return NhiepAnhGia.objects.create(MaTaiKhoan=user, AnhDaiDien='a.jpg', GioiThieu='x',
                                      NganHang='B', SoTaiKhoan=so_tk, ChuTaiKhoan='N', AnhMaQR='q.jpg')


@override_settings(ROOT_URLCONF='reviews.test_danh_gia')
class _Nen(TestCase):                                          # dữ liệu nền + hàm tạo Booking (không có test riêng)
    @classmethod
    def setUpTestData(cls):
        cls.kh = User.objects.create_user('kh', 'kh@x.vn', 'p', so_dien_thoai='0900000001', first_name='An', last_name='Nguyễn')
        cls.kh2 = User.objects.create_user('kh2', 'kh2@x.vn', 'p', so_dien_thoai='0900000004')
        cls.nag = _tao_nag('nag', '0900000002', '1')
        cls.nag_user = cls.nag.MaTaiKhoan
        cls.nag_khac = _tao_nag('nag2', '0900000003', '2')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        cls.goi = GoiDichVu.objects.create(MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G1', Gia=1000000,
                                           ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)

    def tao_booking(self, trang_thai=TT.HOAN_THANH, khach=None):   # Booking ở trạng thái mong muốn
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=10 + next(NGAY_KE_TIEP)),
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0))
        bk = Booking.objects.create(MaKhachHang=khach or self.kh, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,
                                    NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
                                    Concept='c', TongGiaTri=self.goi.Gia)
        Booking.objects.filter(pk=bk.pk).update(TrangThai=trang_thai)
        bk.refresh_from_db()
        return bk


class DanhGiaServiceTests(_Nen):                               # nghiệp vụ của UC6.1
    def test_danh_gia_thanh_cong_luu_dung_nhiep_anh_gia_cua_booking(self):
        bk = self.tao_booking()
        dg = services.tao_danh_gia(bk.pk, self.kh, 5, '  Chụp rất đẹp  ')
        dg.refresh_from_db()
        self.assertEqual((dg.Diem, dg.NhanXet, dg.MaNhiepAnhGia_id), (5, 'Chụp rất đẹp', self.nag.pk))

    def test_nhan_xet_khong_bat_buoc(self):
        bk = self.tao_booking()
        dg = services.tao_danh_gia(bk.pk, self.kh, 3, '   ')
        self.assertIsNone(dg.NhanXet)                          # rỗng/toàn dấu cách -> NULL

    def test_diem_phai_tu_1_den_5(self):
        bk = self.tao_booking()
        for xau in (0, 6, -1, None, '', 'abc'):
            with self.assertRaises(services.LoiDanhGia):
                services.tao_danh_gia(bk.pk, self.kh, xau, 'x')
        self.assertFalse(DanhGia.objects.exists())

    def test_nhan_xet_toi_da_500_ky_tu(self):
        bk = self.tao_booking()
        with self.assertRaises(services.LoiDanhGia):
            services.tao_danh_gia(bk.pk, self.kh, 4, 'a' * 501)
        self.assertFalse(DanhGia.objects.exists())
        services.tao_danh_gia(bk.pk, self.kh, 4, 'a' * 500)    # đúng 500 thì được
        self.assertEqual(DanhGia.objects.count(), 1)

    def test_chi_booking_hoan_thanh_moi_danh_gia_duoc(self):
        for tt in (TT.CHO_XAC_NHAN_THANH_TOAN, TT.CHO_KH_KIEM_TRA, TT.DA_HUY, TT.DA_CHUP):
            bk = self.tao_booking(tt)
            self.assertIn('Hoàn thành', services.ly_do_khong_danh_gia_duoc(bk))
            with self.assertRaises(services.LoiDanhGia):
                services.tao_danh_gia(bk.pk, self.kh, 5, 'x')
        self.assertFalse(DanhGia.objects.exists())

    def test_moi_booking_chi_danh_gia_mot_lan(self):
        bk = self.tao_booking()
        services.tao_danh_gia(bk.pk, self.kh, 5, 'x')
        self.assertIn('một lần', services.ly_do_khong_danh_gia_duoc(bk))
        with self.assertRaises(services.LoiDanhGia):
            services.tao_danh_gia(bk.pk, self.kh, 1, 'y')
        self.assertEqual(DanhGia.objects.filter(MaBooking=bk).count(), 1)
        self.assertEqual(DanhGia.objects.get(MaBooking=bk).Diem, 5)   # đánh giá đầu tiên giữ nguyên

    def test_khach_khac_khong_danh_gia_duoc(self):
        bk = self.tao_booking()
        with self.assertRaises(services.LoiDanhGia):
            services.tao_danh_gia(bk.pk, self.kh2, 5, 'x')
        self.assertFalse(DanhGia.objects.exists())

    def test_thong_ke_diem_trung_binh(self):
        self.assertEqual(services.thong_ke_danh_gia(self.nag), {   # chưa có đánh giá
            'diem_tb': None, 'so_danh_gia': 0,
            'phan_bo': [{'sao': s, 'so': 0, 'phan_tram': 0} for s in (5, 4, 3, 2, 1)]})
        services.tao_danh_gia(self.tao_booking().pk, self.kh, 5, '')
        services.tao_danh_gia(self.tao_booking().pk, self.kh, 4, '')
        tk = services.thong_ke_danh_gia(self.nag)
        self.assertEqual((tk['diem_tb'], tk['so_danh_gia']), (4.5, 2))
        self.assertEqual({d['sao']: d['so'] for d in tk['phan_bo']}, {5: 1, 4: 1, 3: 0, 2: 0, 1: 0})
        self.assertEqual(services.thong_ke_danh_gia(self.nag_khac)['so_danh_gia'], 0)   # không lẫn sang người khác


class NhacDanhGiaTests(_Nen):                                  # "Gửi thông báo nhắc đánh giá khi Booking Hoàn thành"
    def test_nhac_khi_hoan_thanh_va_chi_nhac_mot_lan(self):
        bk = self.tao_booking()
        tb = services.gui_nhac_danh_gia(bk)
        self.assertIsNotNone(tb)
        self.assertEqual((tb.MaNguoiNhan, tb.MaBooking, tb.TieuDe), (self.kh, bk, services.TIEU_DE_NHAC_DANH_GIA))
        self.assertIsNone(services.gui_nhac_danh_gia(bk))      # gọi lần 2: không nhắc trùng
        self.assertEqual(ThongBao.objects.filter(MaBooking=bk).count(), 1)

    def test_khong_nhac_khi_chua_hoan_thanh_hoac_da_danh_gia(self):
        bk = self.tao_booking(TT.CHO_XAC_NHAN_THANH_TOAN)
        self.assertIsNone(services.gui_nhac_danh_gia(bk))
        bk2 = self.tao_booking()
        services.tao_danh_gia(bk2.pk, self.kh, 5, '')
        self.assertIsNone(services.gui_nhac_danh_gia(bk2))
        self.assertFalse(ThongBao.objects.exists())


    @override_settings(MAILERS=HOP_THU_GIA)
    def test_nhac_danh_gia_gui_ca_email(self):                       # P12: mời đánh giá -> web + email (TO-BE 12.1)
        bk = self.tao_booking()
        with self.captureOnCommitCallbacks(execute=True):
            services.gui_nhac_danh_gia(bk)
        self.assertEqual([m.to for m in mail.outbox], [['kh@x.vn']])
        self.assertEqual(mail.outbox[0].subject, services.TIEU_DE_NHAC_DANH_GIA)


class DanhGiaViewTests(_Nen):                                  # trang web
    def url(self, bk):
        return reverse('danh_gia_booking', args=[bk.pk])

    def test_chua_dang_nhap_bi_chuyen_ve_trang_dang_nhap(self):
        r = self.client.get(self.url(self.tao_booking()))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/dang-nhap/', r['Location'])

    def test_nhiep_anh_gia_khong_vao_duoc(self):
        self.client.force_login(self.nag_user)
        self.assertEqual(self.client.get(self.url(self.tao_booking())).status_code, 403)

    def test_booking_cua_nguoi_khac_la_404(self):
        self.client.force_login(self.kh2)
        self.assertEqual(self.client.get(self.url(self.tao_booking())).status_code, 404)

    def test_hien_form_khi_booking_hoan_thanh(self):
        self.client.force_login(self.kh)
        r = self.client.get(self.url(self.tao_booking()))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'name="diem"')
        self.assertContains(r, 'Gửi đánh giá')

    def test_booking_chua_hoan_thanh_hien_loi_khong_co_form(self):
        self.client.force_login(self.kh)
        bk = self.tao_booking(TT.CHO_KH_KIEM_TRA)
        r = self.client.get(self.url(bk))
        self.assertContains(r, 'Chỉ Booking ở trạng thái')
        self.assertNotContains(r, 'name="diem"')
        self.client.post(self.url(bk), {'diem': '5', 'nhan_xet': 'x'})
        self.assertFalse(DanhGia.objects.exists())

    def test_gui_thanh_cong_chuyen_huong_va_chi_xem_lai(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'diem': '4', 'nhan_xet': 'Tốt'})
        self.assertRedirects(r, self.url(bk), fetch_redirect_response=False)
        dg = DanhGia.objects.get(MaBooking=bk)
        self.assertEqual((dg.Diem, dg.NhanXet), (4, 'Tốt'))
        r = self.client.get(self.url(bk))                      # lần sau chỉ xem lại, không còn form
        self.assertContains(r, 'Đánh giá của bạn')
        self.assertNotContains(r, 'name="diem"')

    def test_thieu_so_sao_bao_loi_va_giu_nhan_xet(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'nhan_xet': 'Nhận xét đã gõ'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vui lòng chọn số sao')
        self.assertContains(r, 'Nhận xét đã gõ')
        self.assertFalse(DanhGia.objects.exists())

    def test_nhan_xet_qua_500_ky_tu_bao_loi(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'diem': '5', 'nhan_xet': 'a' * 501})
        self.assertContains(r, 'tối đa 500 ký tự')
        self.assertFalse(DanhGia.objects.exists())

    def test_xuong_dong_windows_tinh_la_1_ky_tu(self):          # trình duyệt gửi \r\n; chuẩn hóa thành \n trước khi đếm
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        self.client.post(self.url(bk), {'diem': '5', 'nhan_xet': 'a\r\n' * 249 + 'a'})   # 249*2 + 1 = 499 ký tự sau chuẩn hóa
        self.assertEqual(DanhGia.objects.count(), 1)

    def test_so_sao_ngoai_1_den_5_bi_tu_choi(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        for diem in ('0', '6', 'abc'):
            self.client.post(self.url(bk), {'diem': diem})
        self.assertFalse(DanhGia.objects.exists())


class DanhGiaCongKhaiTests(_Nen):                              # hiển thị công khai trên hồ sơ nhiếp ảnh gia
    def test_hien_diem_trung_binh_va_danh_gia_khong_can_dang_nhap(self):
        services.tao_danh_gia(self.tao_booking().pk, self.kh, 5, 'Rất hài lòng')
        services.tao_danh_gia(self.tao_booking().pk, self.kh, 4, 'Ổn')
        r = self.client.get(reverse('photographer_reviews', args=[self.nag.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '4.5')
        self.assertContains(r, '2 lượt đánh giá')
        self.assertContains(r, 'Rất hài lòng')
        self.assertContains(r, 'Nguyễn')                       # tên khách hiện công khai
        self.assertNotContains(r, 'kh@x.vn')                   # nhưng không lộ email

    def test_thanh_phan_bo_sao_dung_the_progress_khong_dung_style_inline(self):   # thanh phân bố sao: <progress>, không còn <span style="width:...">
        services.tao_danh_gia(self.tao_booking().pk, self.kh, 5, '')   # 1 đánh giá 5 sao
        services.tao_danh_gia(self.tao_booking().pk, self.kh, 4, '')   # 1 đánh giá 4 sao -> mỗi mức chiếm 50%
        r = self.client.get(reverse('photographer_reviews', args=[self.nag.pk]))
        self.assertContains(r, '<progress class="dg-phan-bo__thanh"', count=5)   # đủ 5 thanh, từ 5 sao đến 1 sao
        self.assertContains(r, 'max="100" value="50" aria-label="5 sao"')        # 5 sao: 1/2 = 50%
        self.assertContains(r, 'max="100" value="0" aria-label="1 sao"')         # 1 sao: chưa có = 0%
        self.assertNotContains(r, 'style="width')                                # không còn style inline

    def test_chua_co_danh_gia(self):
        r = self.client.get(reverse('photographer_reviews', args=[self.nag.pk]))
        self.assertContains(r, 'chưa có đánh giá nào')

    def test_ho_so_chua_duyet_la_404(self):
        User.objects.filter(pk=self.nag_user.pk).update(trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)
        self.assertEqual(self.client.get(reverse('photographer_reviews', args=[self.nag.pk])).status_code, 404)

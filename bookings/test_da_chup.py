# =====================================================================
# bookings/test_da_chup.py - Test cho bookings/da_chup.py (T8: Nhiếp ảnh gia bấm "Đã chụp")
# Chạy:  python manage.py test bookings.test_da_chup
# Mỗi hàm test_... là MỘT tình huống; test chạy trên cơ sở dữ liệu tạm, không đụng dữ liệu thật.
# =====================================================================
from datetime import timedelta  # timedelta: một khoảng thời gian (ví dụ 2 ngày, 1 giờ)

from django.test import override_settings  # cho phép đổi cài đặt chỉ trong lúc chạy test
from django.urls import reverse  # từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # lấy giờ hiện tại có múi giờ
from django.utils.html import escape  # đổi dấu " thành &quot; để so với HTML trả về

from bookings import da_chup as uc  # file đang được test (uc = use case)
from bookings import test_tiep_nhan as nen  # dùng lại lớp nền của UC4.3 (có sẵn khách, Nhiếp ảnh gia, gói, hàm tao_booking)
from bookings.models import LichSuTrangThaiBooking  # bảng lịch sử đổi trạng thái
from core.constants import BenThucHien, LoaiHauKy, TrangThaiBooking as BK  # hằng số dùng chung (BK = tên viết tắt)
from profiles.models import GoiDichVu  # bảng gói dịch vụ


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # dùng thuật toán băm mật khẩu nhanh để test chạy nhanh
class DaChupTest(nen.TiepNhanBase):  # nhóm test T8, kế thừa dữ liệu mẫu của UC4.3
    def setUp(self):  # chạy TRƯỚC mỗi test: chuẩn bị dữ liệu mẫu
        super().setUp()                                                      # dựng dữ liệu nền: đã đăng nhập bằng Nhiếp ảnh gia 'nag'; self.goi = gói Hậu kỳ toàn bộ
        self.goi_gioi_han = GoiDichVu.objects.create(  # tạo thêm một gói kiểu "Giới hạn số lượng ảnh" để thử nhánh còn lại
            MaNhiepAnhGia=self.nag, MaLoaiHinh=self.loai, TenGoi='Gói giới hạn', Gia=1000000,  # thuộc Nhiếp ảnh gia 'nag', giá 1 triệu
            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.GIOI_HAN, SoLuongAnhToiDa=20) if _co_cot_so_luong() else \
            GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.loai, TenGoi='Gói giới hạn',  # nếu bảng không có cột số lượng ảnh thì tạo bản không có cột đó
                                     Gia=1000000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.GIOI_HAN)

    def booking_chot(self, goi=None, da_qua_gio=True, **kw):  # hàm trợ giúp: tạo nhanh một Booking "Chốt Booking"
        """Booking 'Chốt Booking'; mặc định buổi chụp đã diễn ra (1 giờ trước, Booking tạo từ 2 ngày trước)."""
        bay_gio = timezone.now()  # giờ hiện tại
        gio_chup = bay_gio - timedelta(hours=1) if da_qua_gio else bay_gio + timedelta(days=2)  # đã qua: 1 giờ trước; chưa tới: 2 ngày nữa
        return self.tao_booking(goi=goi, trang_thai=BK.CHOT_BOOKING, NgayGioChup=gio_chup,  # tạo Booking ở trạng thái "Chốt Booking" với giờ chụp vừa tính
                                NgayTao=bay_gio - timedelta(days=2), **kw)  # ngày tạo lùi 2 ngày để giờ chụp luôn sau ngày tạo (luật của bảng)

    def bam(self, bk, **kw):  # hàm trợ giúp: giả lập Nhiếp ảnh gia bấm nút "Đã chụp"
        return self.client.post(reverse('da_chup_booking', kwargs={'ma_booking': bk.pk}), **kw)  # gửi POST tới địa chỉ nút "Đã chụp" của Booking đó

    def test_goi_gioi_han_dung_o_da_chup_cho_tai_anh(self):  # tình huống: gói Giới hạn -> dừng ở "Đã chụp"
        bk = self.booking_chot(goi=self.goi_gioi_han)  # Booking chốt, gói Giới hạn
        res = self.bam(bk)  # bấm "Đã chụp"
        self.assertRedirects(res, reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}))  # kết quả: được chuyển về trang chi tiết
        bk.refresh_from_db()  # đọc lại Booking từ cơ sở dữ liệu để thấy giá trị mới
        self.assertEqual(bk.TrangThai, BK.DA_CHUP)  # trạng thái phải là "Đã chụp"
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk, TrangThaiMoi=BK.DA_CHUP).count(), 1)  # lịch sử ghi đúng 1 dòng "Đã chụp"

    def test_goi_hau_ky_toan_bo_di_thang_sang_cho_hau_ky(self):  # tình huống: gói Hậu kỳ toàn bộ -> nhảy sang "Chờ hậu kỳ"
        bk = self.booking_chot(goi=self.goi)  # Booking chốt, gói Hậu kỳ toàn bộ (gói mặc định của lớp nền)
        self.bam(bk)  # bấm "Đã chụp"
        bk.refresh_from_db()  # đọc lại từ cơ sở dữ liệu
        self.assertEqual(bk.TrangThai, BK.CHO_HAU_KY)  # trạng thái cuối phải là "Chờ hậu kỳ"
        cac_buoc = list(LichSuTrangThaiBooking.objects.filter(MaBooking=bk).values_list('TrangThaiCu', 'TrangThaiMoi', 'BenThucHien'))  # lấy các dòng lịch sử (cũ, mới, ai đổi)
        self.assertEqual(cac_buoc, [(BK.CHOT_BOOKING, BK.DA_CHUP, BenThucHien.NHIEP_ANH_GIA),  # dòng 1: Chốt -> Đã chụp, do Nhiếp ảnh gia
                                    (BK.DA_CHUP, BK.CHO_HAU_KY, BenThucHien.NHIEP_ANH_GIA)])  # dòng 2: Đã chụp -> Chờ hậu kỳ, do Nhiếp ảnh gia

    def test_buoi_chup_chua_dien_ra_khong_bam_duoc(self):  # tình huống: chưa tới giờ chụp -> bị từ chối
        bk = self.booking_chot(da_qua_gio=False)  # Booking có giờ chụp 2 ngày nữa
        res = self.bam(bk, follow=True)  # bấm "Đã chụp" và đi theo trang được chuyển tới
        self.assertContains(res, escape(uc.TB_CHUA_DEN_GIO_CHUP))  # trang phải hiện câu "chưa diễn ra" (dấu " trong câu được HTML đổi thành &quot;)
        bk.refresh_from_db()  # đọc lại từ cơ sở dữ liệu
        self.assertEqual(bk.TrangThai, BK.CHOT_BOOKING)  # trạng thái giữ nguyên "Chốt Booking"

    def test_chi_bam_duoc_khi_dang_chot_booking(self):  # tình huống: các trạng thái khác "Chốt Booking" đều không bấm được
        for tt in (BK.CHO_XAC_NHAN, BK.CHO_DAT_COC, BK.DA_CHUP, BK.HOAN_THANH, BK.DA_HUY):  # thử lần lượt từng trạng thái
            bk = self.tao_booking(trang_thai=tt, gio=f'{BK.ALL.index(tt):02d}:00',  # mỗi Booking một khung giờ riêng để không trùng slot
                                  NgayGioChup=timezone.now() - timedelta(hours=1), NgayTao=timezone.now() - timedelta(days=2))  # giờ chụp đã qua
            self.bam(bk)  # bấm "Đã chụp"
            bk.refresh_from_db()  # đọc lại từ cơ sở dữ liệu
            self.assertEqual(bk.TrangThai, tt)  # trạng thái không đổi

    def test_bam_hai_lan_khong_ghi_lich_su_hai_lan(self):  # tình huống: bấm lặp (bấm đúp) không làm lịch sử bị ghi trùng
        bk = self.booking_chot(goi=self.goi_gioi_han)  # Booking chốt, gói Giới hạn
        self.bam(bk)  # bấm lần 1
        self.bam(bk)  # bấm lần 2 (Booking đã "Đã chụp" nên bị từ chối)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk, TrangThaiMoi=BK.DA_CHUP).count(), 1)  # vẫn chỉ 1 dòng lịch sử

    def test_booking_cua_nag_khac_tra_404_va_khong_doi(self):  # tình huống: bấm Booking của Nhiếp ảnh gia khác
        bk = self.booking_chot(nag=self.nag_khac)  # Booking thuộc Nhiếp ảnh gia khác
        self.assertEqual(self.bam(bk).status_code, 404)  # phải trả 404 (không tiết lộ là có tồn tại)
        bk.refresh_from_db()  # đọc lại từ cơ sở dữ liệu
        self.assertEqual(bk.TrangThai, BK.CHOT_BOOKING)  # trạng thái giữ nguyên

    def test_khach_hang_khong_bam_duoc(self):  # tình huống: Khách hàng cố bấm
        bk = self.booking_chot()  # Booking chốt
        self.client.force_login(self.khach)  # đăng nhập bằng tài khoản Khách hàng
        self.assertEqual(self.bam(bk).status_code, 403)  # phải bị chặn (403 = không đủ quyền)

    def test_chi_nhan_post(self):  # tình huống: mở link bằng GET (gõ trên thanh địa chỉ)
        bk = self.booking_chot()  # Booking chốt
        res = self.client.get(reverse('da_chup_booking', kwargs={'ma_booking': bk.pk}))  # mở bằng GET thay vì POST
        self.assertEqual(res.status_code, 405)  # phải bị từ chối (405 = sai phương thức)

    def test_trang_chi_tiet_hien_nut_da_chup_dung_luc(self):  # tình huống: nút chỉ hiện khi đã tới giờ chụp
        sau = self.booking_chot()  # Booking đã qua giờ chụp
        truoc = self.booking_chot(da_qua_gio=False, gio='15:00')  # Booking chưa tới giờ chụp (khung giờ khác để không trùng slot)
        url_nut = lambda b: reverse('da_chup_booking', kwargs={'ma_booking': b.pk})  # hàm nhỏ: địa chỉ nút "Đã chụp" của một Booking
        self.assertContains(self.client.get(reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': sau.pk})), url_nut(sau))  # Booking đã qua giờ: trang có chứa địa chỉ nút
        self.assertNotContains(self.client.get(reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': truoc.pk})), url_nut(truoc))  # Booking chưa tới giờ: trang KHÔNG có nút


def _co_cot_so_luong():  # hàm phụ: kiểm tra bảng gói có cột "số lượng ảnh tối đa" không
    """Gói giới hạn có thể bắt buộc cột số lượng ảnh (tùy models của Khoa); kiểm tra để test không phụ thuộc phiên bản."""
    return any(f.name == 'SoLuongAnhToiDa' for f in GoiDichVu._meta.get_fields())  # True nếu bảng có cột đó

# =====================================================================
# bookings/test_theo_doi.py - Test cho bookings/theo_doi.py (T7 / UC4.7 Theo dõi trạng thái Booking)
# Chạy:  python manage.py test bookings.test_theo_doi
# Mỗi hàm test_... là MỘT tình huống; test chạy trên cơ sở dữ liệu tạm, không đụng dữ liệu thật.
# =====================================================================
from django.test import override_settings  # cho phép đổi cài đặt chỉ trong lúc chạy test
from django.urls import reverse  # từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # lấy giờ hiện tại có múi giờ

from bookings import test_tiep_nhan as nen             # dùng lại dữ liệu mẫu của UC4.3 (khách, Nhiếp ảnh gia, gói, tao_booking)
from bookings import theo_doi as uc  # file đang được test (uc = use case)
from bookings.models import LichSuTrangThaiBooking  # bảng lịch sử đổi trạng thái
from bookings.services import chuyen_trang_thai_booking  # hàm chung đổi trạng thái (dùng để tạo lịch sử thật)
from core.constants import BenThucHien, LoaiThanhToan, TrangThaiBooking as BK, TrangThaiThanhToan as TT, VaiTro  # hằng số dùng chung
from core.status_tones import TONE_BY_STATUS  # bảng "trạng thái -> màu" của nhóm
from payments.models import ThanhToan, tinh_so_tien  # bảng thanh toán + hàm chia tiền 40/60


class TheoDoiBase(nen.TiepNhanBase):  # lớp nền cho mọi test T7: thêm Quản trị viên và vài hàm trợ giúp
    def setUp(self):  # chạy TRƯỚC mỗi test
        super().setUp()  # dựng dữ liệu nền của UC4.3
        self.admin = nen.tao_user('qtv', VaiTro.QUAN_TRI_VIEN)  # tạo một tài khoản Quản trị viên
        self.client.logout()  # đăng xuất để mỗi test tự chọn người đăng nhập

    def dang_nhap(self, user):  # hàm trợ giúp: đăng nhập nhanh bằng một tài khoản
        self.client.force_login(user)  # đăng nhập không cần gõ mật khẩu

    def tao_thanh_toan(self, bk, loai, trang_thai):  # hàm trợ giúp: tạo một khoản thanh toán cho Booking
        da_xn = trang_thai in (TT.DA_DAT_COC, TT.DA_THANH_TOAN)  # khoản đã được xác nhận chưa
        return ThanhToan.objects.create(  # ghi khoản thanh toán vào cơ sở dữ liệu tạm
            MaBooking=bk, LoaiThanhToan=loai, SoTien=tinh_so_tien(bk.TongGiaTri, loai), TrangThai=trang_thai,  # thuộc Booking nào, loại gì, số tiền 40%/60%, trạng thái
            NgayXacNhan=timezone.now() if da_xn else None)  # đã xác nhận thì ghi giờ xác nhận


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class UC47KhachHang(TheoDoiBase):  # nhóm test: Khách hàng xem "Booking của tôi"
    url = property(lambda self: reverse('my_bookings'))  # địa chỉ trang danh sách "Booking của tôi"

    def test_khach_chi_thay_booking_cua_minh_kem_trang_thai(self):          # bước 2 + BR4.7-1
        cua_minh = self.tao_booking(gio='09:00')  # Booking của Khách này, "Chờ xác nhận"
        da_chap = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)  # Booking khác của Khách này, "Chờ đặt cọc"
        cua_khach_b = self.tao_booking(gio='16:00', MaKhachHang=self.khach_b)  # Booking của Khách KHÁC
        self.dang_nhap(self.khach)  # đăng nhập bằng Khách hàng
        res = self.client.get(self.url)  # mở trang "Booking của tôi"
        self.assertEqual(res.status_code, 200)  # trang mở được
        ds = list(res.context['page_obj'])  # danh sách Booking mà trang đưa ra
        self.assertCountEqual(ds, [cua_minh, da_chap])  # phải đúng 2 Booking của mình (không cần đúng thứ tự)
        self.assertNotIn(cua_khach_b, ds)  # Booking của Khách khác không được lọt vào
        self.assertContains(res, BK.CHO_XAC_NHAN)  # trang có chữ trạng thái "Chờ xác nhận"
        self.assertContains(res, BK.CHO_DAT_COC)  # trang có chữ trạng thái "Chờ đặt cọc"

    def test_chua_co_booking_nao(self):                                      # ngoại lệ 1a
        self.dang_nhap(self.khach)  # Khách chưa đặt gì
        self.assertContains(self.client.get(self.url), uc.TB_CHUA_CO_BOOKING)  # trang phải hiện "Chưa có Booking nào"

    def test_loc_theo_trang_thai(self):                                      # luồng 2a
        moi = self.tao_booking(gio='09:00')  # Booking "Chờ xác nhận"
        coc = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)  # Booking "Chờ đặt cọc"
        self.dang_nhap(self.khach)  # đăng nhập Khách
        res = self.client.get(self.url, {'trang_thai': BK.CHO_DAT_COC})  # lọc theo "Chờ đặt cọc"
        self.assertEqual(list(res.context['page_obj']), [coc])  # chỉ còn đúng Booking "Chờ đặt cọc"
        res = self.client.get(self.url, {'trang_thai': 'gõ_bậy'})            # giá trị lạ trên thanh địa chỉ
        self.assertCountEqual(list(res.context['page_obj']), [moi, coc])  # coi như "tất cả", không lỗi

    def test_loc_ra_rong_bao_theo_bo_loc_khong_phai_chua_co_booking(self):  # tình huống: có Booking nhưng lọc ra rỗng
        self.tao_booking()  # Khách có 1 Booking "Chờ xác nhận"
        self.dang_nhap(self.khach)  # đăng nhập Khách
        res = self.client.get(self.url, {'trang_thai': BK.HOAN_THANH})  # lọc "Hoàn thành" -> không có cái nào
        self.assertContains(res, uc.TB_KHONG_KHOP_BO_LOC)  # phải hiện "Không có Booking nào khớp bộ lọc."
        self.assertNotContains(res, uc.TB_CHUA_CO_BOOKING)  # KHÔNG được hiện "Chưa có Booking nào" (vì Khách có Booking)

    def test_chi_tiet_co_dong_thoi_gian_lich_su(self):                       # bước 3-4
        bk = self.tao_booking()  # Booking mới
        chuyen_trang_thai_booking(bk, BK.CHO_DAT_COC, BenThucHien.NHIEP_ANH_GIA)  # Nhiếp ảnh gia chấp nhận -> tạo 1 dòng lịch sử thật
        self.dang_nhap(self.khach)  # đăng nhập Khách
        res = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))  # mở trang chi tiết
        self.assertEqual(res.status_code, 200)  # trang mở được
        self.assertEqual(list(res.context['lich_su']), list(LichSuTrangThaiBooking.objects.filter(MaBooking=bk)))  # lịch sử trên trang = lịch sử trong cơ sở dữ liệu
        self.assertContains(res, 'Lịch sử trạng thái')  # có tiêu đề khối lịch sử
        self.assertContains(res, 'td-timeline')  # có khung dòng thời gian (tên class CSS)
        self.assertContains(res, BenThucHien.NHIEP_ANH_GIA)  # hiện ai là người đổi trạng thái

    def test_khong_xem_duoc_booking_cua_nguoi_khac(self):                    # BR4.7-1
        bk = self.tao_booking(MaKhachHang=self.khach_b)  # Booking của Khách khác
        self.dang_nhap(self.khach)  # đăng nhập Khách này
        self.assertEqual(self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk})).status_code, 404)  # mở chi tiết -> 404

    def test_chua_dang_nhap_ve_trang_dang_nhap(self):  # tình huống: chưa đăng nhập
        self.assertEqual(self.client.get(self.url).status_code, 302)  # bị chuyển (302) sang trang đăng nhập

    def test_khach_khong_vao_trang_quan_tri(self):  # tình huống: Khách cố vào trang Quản trị viên
        self.dang_nhap(self.khach)  # đăng nhập Khách
        self.assertEqual(self.client.get(reverse('admin_bookings')).status_code, 403)  # bị chặn (403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class UC47NhiepAnhGia(TheoDoiBase):  # nhóm test: Nhiếp ảnh gia xem Booking của mình
    def test_nag_chi_thay_booking_gui_den_minh(self):  # tình huống: chỉ thấy Booking gửi tới mình
        cua_minh = self.tao_booking()  # Booking gửi tới Nhiếp ảnh gia 'nag'
        cua_nag_khac = self.tao_booking(nag=self.nag_khac, gio='13:00')  # Booking gửi tới Nhiếp ảnh gia khác
        self.dang_nhap(self.nag.MaTaiKhoan)  # đăng nhập bằng tài khoản của 'nag'
        res = self.client.get(reverse('my_bookings'))  # mở danh sách
        self.assertEqual(list(res.context['page_obj']), [cua_minh])  # chỉ có Booking của mình
        self.assertEqual(self.client.get(  # mở chi tiết Booking của Nhiếp ảnh gia khác
            reverse('chi_tiet_booking', kwargs={'ma_booking': cua_nag_khac.pk})).status_code, 404)  # -> 404

    def test_nag_chi_tiet_co_link_xu_ly_khi_cho_xac_nhan(self):  # tình huống: Booking còn việc phải xử lý
        bk = self.tao_booking()  # Booking "Chờ xác nhận"
        self.dang_nhap(self.nag.MaTaiKhoan)  # đăng nhập Nhiếp ảnh gia
        res = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))  # mở chi tiết
        self.assertContains(res, reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}))  # trang có link sang màn xử lý (T5)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class UC47QuanTriVien(TheoDoiBase):  # nhóm test: Quản trị viên tra cứu
    def test_quan_tri_thay_tat_ca_va_tim_kiem(self):  # tình huống: thấy tất cả + tìm được
        a = self.tao_booking(gio='09:00')  # Booking của Khách A
        b = self.tao_booking(nag=self.nag_khac, gio='13:00', MaKhachHang=self.khach_b)  # Booking của Khách B, gửi Nhiếp ảnh gia khác
        self.dang_nhap(self.admin)  # đăng nhập Quản trị viên
        res = self.client.get(reverse('admin_bookings'))  # mở danh sách của Quản trị
        self.assertCountEqual(list(res.context['page_obj']), [a, b])  # thấy cả 2 Booking
        res = self.client.get(reverse('admin_bookings'), {'q': 'khach_b'})  # tìm theo tên đăng nhập 'khach_b'
        self.assertEqual(list(res.context['page_obj']), [b])  # chỉ còn Booking của Khách B
        res = self.client.get(reverse('admin_bookings'), {'q': f'#{a.pk}'})  # tìm theo mã Booking, ví dụ #5
        self.assertEqual(list(res.context['page_obj']), [a])  # chỉ còn đúng Booking đó
        self.assertEqual(self.client.get(reverse('admin_booking_detail', kwargs={'ma_booking': b.pk})).status_code, 200)  # mở chi tiết Booking bất kỳ -> được

    def test_nag_khong_vao_trang_quan_tri(self):  # tình huống: Nhiếp ảnh gia cố vào trang Quản trị
        self.dang_nhap(self.nag.MaTaiKhoan)  # đăng nhập Nhiếp ảnh gia
        self.assertEqual(self.client.get(reverse('admin_bookings')).status_code, 403)  # bị chặn (403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class UC47DongBoThanhToan(TheoDoiBase):                                      # BR4.7-2: trạng thái khớp dữ liệu thanh toán
    def test_khop_thi_khong_canh_bao(self):  # tình huống: mọi thứ khớp
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)  # Booking "Chốt Booking"
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)  # cọc đã xác nhận (đúng với "Chốt Booking")
        self.assertEqual(uc.doi_chieu_thanh_toan(bk), [])  # không có chỗ lệch

    def test_chot_booking_ma_coc_chua_xac_nhan_la_lech(self):  # tình huống: Booking đã chốt nhưng cọc chưa xác nhận
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)  # Booking "Chốt Booking"
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.CHO_XAC_NHAN_COC)  # cọc còn "Chờ xác nhận cọc"
        self.assertEqual(len(uc.doi_chieu_thanh_toan(bk)), 1)  # phải báo đúng 1 chỗ lệch

    def test_coc_da_xac_nhan_ma_booking_van_cho_dat_coc_la_lech(self):  # tình huống: cọc xong mà Booking chưa tiến lên
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC)  # Booking vẫn "Chờ đặt cọc"
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)  # nhưng cọc đã "Đã đặt cọc"
        self.assertEqual(len(uc.doi_chieu_thanh_toan(bk)), 1)  # phải báo đúng 1 chỗ lệch

    def test_hoan_thanh_phai_co_60_da_thanh_toan(self):  # tình huống: "Hoàn thành" thì phải thu đủ 60%
        bk = self.tao_booking(trang_thai=BK.HOAN_THANH)  # Booking "Hoàn thành"
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)  # chỉ mới có cọc
        self.assertEqual(len(uc.doi_chieu_thanh_toan(bk)), 1)                # thiếu khoản 60% -> 1 chỗ lệch
        self.tao_thanh_toan(bk, LoaiThanhToan.PHAN_CON_LAI, TT.DA_THANH_TOAN)  # bổ sung khoản 60% đã thanh toán
        self.assertEqual(uc.doi_chieu_thanh_toan(bk), [])  # giờ khớp, không còn cảnh báo

    def test_chi_quan_tri_thay_canh_bao_lech(self):  # tình huống: chỉ Quản trị viên được thấy cảnh báo lệch
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)                     # chưa có khoản cọc nào -> đang lệch
        url_kh = reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk})  # địa chỉ chi tiết dành cho Khách
        self.dang_nhap(self.khach)  # đăng nhập Khách
        self.assertNotContains(self.client.get(url_kh), 'không khớp dữ liệu thanh toán')  # Khách KHÔNG thấy cảnh báo
        self.dang_nhap(self.admin)  # đăng nhập Quản trị viên
        res = self.client.get(reverse('admin_booking_detail', kwargs={'ma_booking': bk.pk}))  # mở chi tiết của Quản trị
        self.assertContains(res, 'không khớp dữ liệu thanh toán')  # Quản trị viên THẤY cảnh báo

    def test_chi_tiet_hien_khoan_thanh_toan_canh_trang_thai(self):  # tình huống: trang chi tiết hiện kèm thanh toán
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)  # Booking "Chốt Booking"
        self.tao_thanh_toan(bk, LoaiThanhToan.TIEN_COC, TT.DA_DAT_COC)  # cọc đã xác nhận
        self.dang_nhap(self.khach)  # đăng nhập Khách
        res = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))  # mở chi tiết
        self.assertContains(res, TT.DA_DAT_COC)  # có nhãn trạng thái thanh toán "Đã đặt cọc"
        self.assertContains(res, LoaiThanhToan.TIEN_COC)  # có tên khoản "Tiền cọc"


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class UC47NhanVaMau(TheoDoiBase):  # nhóm test: nhãn và màu trạng thái thống nhất
    def test_moi_trang_thai_booking_co_mau_khai_bao_ro_rang(self):  # tình huống: không trạng thái nào bị quên màu
        for tt in BK.ALL:  # duyệt qua cả 13 trạng thái
            self.assertIn(tt, TONE_BY_STATUS, f'"{tt}" chưa có màu trong core/status_tones.py')  # phải có trong bảng màu, thiếu thì báo tên trạng thái

    def test_danh_sach_va_chi_tiet_dung_cung_mot_mau_cho_cung_trang_thai(self):  # tình huống: danh sách và chi tiết cùng một màu
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC)  # Booking "Chờ đặt cọc"
        tone = TONE_BY_STATUS[BK.CHO_DAT_COC]  # màu quy định cho trạng thái này
        self.dang_nhap(self.khach)  # đăng nhập Khách
        ds = self.client.get(reverse('my_bookings'))  # trang danh sách
        ct = self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))  # trang chi tiết
        for res in (ds, ct):  # kiểm tra cả hai trang
            self.assertContains(res, f'badge badge--{tone}')  # cả hai đều dùng đúng class màu đó

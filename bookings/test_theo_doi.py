# =====================================================================
# bookings/test_theo_doi.py - Test cho bookings/theo_doi.py (T7 / UC4.7 Theo dõi trạng thái Booking)
# Chạy:  python manage.py test bookings.test_theo_doi
# Mỗi hàm test_... là MỘT tình huống; test chạy trên cơ sở dữ liệu tạm, không đụng dữ liệu thật.
# =====================================================================
from unittest import mock  # mock: giả lập tạm một hàm trong lúc test

from django.test import override_settings  # cho phép đổi cài đặt chỉ trong lúc chạy test
from django.urls import NoReverseMatch, reverse  # NoReverseMatch: lỗi khi tên url chưa tồn tại; reverse: từ TÊN url suy ra địa chỉ thật
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
        self.assertContains(res, 'ct-timeline')  # có khung dòng thời gian (tên class CSS)
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
        # C5: Nhiếp ảnh gia được chuyển thẳng sang màn xử lý (T5) - nơi có đủ nút - thay vì ở lại trang chung thiếu nút
        self.assertRedirects(res, reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)


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

    def test_quan_tri_tab_loc_nhieu_trang_thai_va_sap_xep(self):  # tình huống: bố cục giống trang Duyệt hồ sơ (tab + bộ lọc chọn nhiều)
        a = self.tao_booking(gio='09:00')  # "Chờ xác nhận" (đang xử lý)
        b = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)  # "Chờ đặt cọc" (đang xử lý)
        c = self.tao_booking(gio='16:00', trang_thai=BK.DA_HUY)  # "Đã hủy" (đã kết thúc)
        self.dang_nhap(self.admin)  # đăng nhập Quản trị viên
        url = reverse('admin_bookings')  # trang "Tất cả Booking"
        res = self.client.get(url)  # không tham số: tab "Tất cả", mới nhất trước
        self.assertEqual(list(res.context['page_obj']), [c, b, a])  # đủ 3 Booking, cái tạo sau lên đầu
        self.assertEqual((res.context['so_tat_ca'], res.context['so_dang_xu_ly'], res.context['so_ket_thuc']), (3, 2, 1))  # số trên 3 tab
        self.assertContains(res, 'abk__tabs')  # có hàng tab (tên class CSS)
        res = self.client.get(url, {'tab': 'ket_thuc'})  # tab "Đã kết thúc"
        self.assertEqual(list(res.context['page_obj']), [c])  # chỉ còn Booking đã kết thúc
        res = self.client.get(url, {'tab': 'dang_xu_ly'})  # tab "Đang xử lý"
        self.assertEqual(list(res.context['page_obj']), [b, a])  # loại Booking đã kết thúc
        res = self.client.get(url, {'trang_thai': [BK.CHO_XAC_NHAN, BK.DA_HUY]})  # chọn NHIỀU trạng thái cùng lúc
        self.assertEqual(list(res.context['page_obj']), [c, a])  # giữ đúng 2 trạng thái đã chọn
        self.assertEqual(res.context['so_bo_loc'], 2)  # nút "Bộ lọc" hiện số 2
        res = self.client.get(url, {'sap_xep': 'cu'})  # cũ nhất trước
        self.assertEqual(list(res.context['page_obj']), [a, b, c])  # thứ tự đảo lại
        res = self.client.get(url, {'tu_ngay': 'khong-phai-ngay', 'trang_thai': 'gõ_bậy'})  # giá trị lạ trên thanh địa chỉ
        self.assertEqual(res.status_code, 200)  # không gây lỗi trang
        self.assertCountEqual(list(res.context['page_obj']), [a, b, c])  # coi như không lọc

    def test_quan_tri_tim_nhieu_tu_khoa(self):  # tình huống: gõ nhiều từ, mỗi từ phải khớp (như trang Duyệt hồ sơ)
        a = self.tao_booking(gio='09:00')  # Booking của Khách A gửi Nhiếp ảnh gia 'nag'
        self.tao_booking(nag=self.nag_khac, gio='13:00', MaKhachHang=self.khach_b)  # Booking của Khách B
        self.dang_nhap(self.admin)  # đăng nhập Quản trị viên
        res = self.client.get(reverse('admin_bookings'), {'q': f'#{a.pk} {self.khach.username}'})  # mã Booking + tên đăng nhập của khách
        self.assertEqual(list(res.context['page_obj']), [a])  # cả hai từ khóa đều khớp Booking a
        res = self.client.get(reverse('admin_bookings'), {'q': f'#{a.pk} khach_b'})  # mã của a nhưng tên của khách b
        self.assertEqual(list(res.context['page_obj']), [])  # không Booking nào khớp cả hai
        self.assertContains(res, uc.TB_KHONG_KHOP_BO_LOC)  # hiện "Không có Booking nào khớp bộ lọc."

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


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class UC47NutBanGiaoAnh(TheoDoiBase):  # nhóm test: nút dẫn sang các trang xử lý ảnh của Nguyên (N4-N6)
    NHAN_CHON_ANH = 'Chọn ảnh cần hậu kỳ'  # chữ trên nút của Khách hàng
    NHAN_TAI_ANH = 'Tải ảnh lên hệ thống'  # chữ trên nút tải ảnh sau khi đã bắt đầu hậu kỳ
    NHAN_BAT_DAU = 'Bắt đầu hậu kỳ'

    def mo_chi_tiet(self, user, bk):  # hàm trợ giúp: đăng nhập rồi mở trang chi tiết Booking
        self.dang_nhap(user)  # đăng nhập bằng tài khoản truyền vào
        ten_url = 'admin_booking_detail' if user == self.admin else 'chi_tiet_booking'  # Quản trị viên có trang chi tiết riêng
        return self.client.get(reverse(ten_url, kwargs={'ma_booking': bk.pk}))  # mở chi tiết

    def url_chon_anh(self, bk):  # địa chỉ trang Khách chọn ảnh (N6)
        return reverse('chon_anh_hau_ky', kwargs={'ma_booking': bk.pk})

    def url_tai_anh(self, bk):  # địa chỉ trang Nhiếp ảnh gia tải ảnh / hậu kỳ (N4, N5)
        return reverse('tai_anh_len', kwargs={'ma_booking': bk.pk})

    # ---- Khách hàng
    def test_khach_thay_nut_chon_anh_khi_cho_khach_lua_chon_anh(self):  # tình huống: Khách phải chọn ảnh
        bk = self.tao_booking(trang_thai=BK.CHO_KH_CHON_ANH)  # Booking "Chờ Khách hàng lựa chọn ảnh"
        res = self.mo_chi_tiet(self.khach, bk)  # Khách mở chi tiết
        self.assertEqual(res.context['url_chon_anh'], self.url_chon_anh(bk))  # view đưa đúng địa chỉ vào context
        self.assertContains(res, self.NHAN_CHON_ANH)  # có chữ trên nút
        self.assertContains(res, f'href="{self.url_chon_anh(bk)}"')  # nút trỏ đúng tới chon_anh_hau_ky
        self.assertNotContains(res, self.NHAN_TAI_ANH)  # Khách không thấy nút của Nhiếp ảnh gia

    def test_khach_khong_thay_nut_chon_anh_o_trang_thai_khac(self):  # tình huống: chưa tới / đã qua bước chọn ảnh
        for trang_thai in (BK.CHOT_BOOKING, BK.DA_CHUP, BK.CHO_HAU_KY, BK.DANG_HAU_KY, BK.CHO_KH_KIEM_TRA):  # các trạng thái không phải "Chờ Khách hàng lựa chọn ảnh"
            with self.subTest(trang_thai=trang_thai):  # báo lỗi riêng cho từng trạng thái
                bk = self.tao_booking(trang_thai=trang_thai, gio={BK.CHOT_BOOKING: '07:00', BK.DA_CHUP: '09:00', BK.CHO_HAU_KY: '11:00',
                                                                  BK.DANG_HAU_KY: '13:00', BK.CHO_KH_KIEM_TRA: '15:00'}[trang_thai])  # mỗi Booking một khung giờ riêng để không trùng slot
                res = self.mo_chi_tiet(self.khach, bk)  # Khách mở chi tiết
                self.assertIsNone(res.context['url_chon_anh'])  # không có địa chỉ
                self.assertNotContains(res, self.NHAN_CHON_ANH)  # không có nút

    # ---- Nhiếp ảnh gia
    def test_nag_thay_nut_tai_anh_khi_da_chup_cho_hau_ky_hoac_dang_hau_ky(self):  # tình huống: Nhiếp ảnh gia còn việc với ảnh
        gio = {BK.DA_CHUP: '07:00', BK.DANG_HAU_KY: '13:00'}  # mỗi Booking một khung giờ riêng
        for trang_thai in uc.TRANG_THAI_NAG_XU_LY_ANH:  # "Đã chụp", "Đang hậu kỳ"
            with self.subTest(trang_thai=trang_thai):  # báo lỗi riêng cho từng trạng thái
                bk = self.tao_booking(trang_thai=trang_thai, gio=gio[trang_thai])  # Booking ở trạng thái đang thử
                res = self.mo_chi_tiet(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia mở chi tiết
                self.assertEqual(res.context['url_tai_anh'], self.url_tai_anh(bk))  # view đưa đúng địa chỉ vào context
                self.assertContains(res, self.NHAN_TAI_ANH)  # có chữ trên nút
                self.assertContains(res, f'href="{self.url_tai_anh(bk)}"')  # nút trỏ đúng tới tai_anh_len
                self.assertNotContains(res, self.NHAN_CHON_ANH)  # Nhiếp ảnh gia không thấy nút của Khách

    def test_nag_thay_nut_bat_dau_hau_ky_rieng(self):
        bk = self.tao_booking(trang_thai=BK.CHO_HAU_KY, gio='10:00')
        res = self.mo_chi_tiet(self.nag.MaTaiKhoan, bk)
        self.assertEqual(res.context['url_bat_dau_hau_ky'], reverse('bat_dau_hau_ky', kwargs={'ma_booking': bk.pk}))
        self.assertContains(res, self.NHAN_BAT_DAU)
        self.assertContains(res, 'method="post"')
        self.assertNotContains(res, f'href="{self.url_tai_anh(bk)}"')

    def test_nag_khong_thay_nut_tai_anh_o_trang_thai_khac(self):  # tình huống: chưa chụp xong / đã giao ảnh cho Khách
        gio = {BK.CHOT_BOOKING: '07:00', BK.CHO_KH_CHON_ANH: '10:00', BK.CHO_KH_KIEM_TRA: '13:00', BK.HOAN_THANH: '16:00'}  # mỗi Booking một khung giờ riêng
        for trang_thai, g in gio.items():  # các trạng thái không thuộc nhóm của Nhiếp ảnh gia
            with self.subTest(trang_thai=trang_thai):  # báo lỗi riêng cho từng trạng thái
                bk = self.tao_booking(trang_thai=trang_thai, gio=g)  # Booking ở trạng thái đang thử
                res = self.mo_chi_tiet(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia mở chi tiết
                if res.status_code == 302:  # C5: "Chốt Booking" được chuyển sang trang xử lý riêng; trang đó cũng không có nút tải ảnh
                    res = self.client.get(res['Location'])  # đi theo link chuyển hướng
                    self.assertNotContains(res, self.NHAN_TAI_ANH)  # không có nút
                    continue  # sang trạng thái kế tiếp
                self.assertIsNone(res.context['url_tai_anh'])  # không có địa chỉ
                self.assertNotContains(res, self.NHAN_TAI_ANH)  # không có nút

    # ---- Quản trị viên
    def test_quan_tri_khong_thay_ca_hai_nut(self):  # tình huống: Quản trị viên chỉ tra cứu, không xử lý ảnh
        for trang_thai, g in ((BK.CHO_KH_CHON_ANH, '07:00'), (BK.DA_CHUP, '10:00')):  # một trạng thái của mỗi bên
            with self.subTest(trang_thai=trang_thai):  # báo lỗi riêng cho từng trạng thái
                bk = self.tao_booking(trang_thai=trang_thai, gio=g)  # Booking ở trạng thái đang thử
                res = self.mo_chi_tiet(self.admin, bk)  # Quản trị viên mở chi tiết
                self.assertNotContains(res, self.NHAN_CHON_ANH)  # không có nút chọn ảnh
                self.assertNotContains(res, self.NHAN_TAI_ANH)  # không có nút tải ảnh

    # ---- Trang của Nguyên chưa có trên máy
    def test_ten_url_chua_ton_tai_thi_an_nut_khong_bao_loi(self):  # tình huống: chưa merge N4-N6
        khach_bk = self.tao_booking(trang_thai=BK.CHO_KH_CHON_ANH, gio='07:00')  # Booking cần Khách chọn ảnh
        nag_bk = self.tao_booking(trang_thai=BK.DA_CHUP, gio='10:00')  # Booking cần Nhiếp ảnh gia tải ảnh
        goc = reverse  # giữ hàm reverse thật để các tên url khác vẫn chạy bình thường

        def reverse_thieu_trang_cua_nguyen(ten, *a, **kw):  # giả lập: hai tên url của Nguyên chưa tồn tại
            if ten in ('chon_anh_hau_ky', 'tai_anh_len'):  # đúng hai tên url cần thử
                raise NoReverseMatch(ten)  # báo "không có tên url này"
            return goc(ten, *a, **kw)  # tên khác: chạy như thường

        with mock.patch.object(uc, 'reverse', side_effect=reverse_thieu_trang_cua_nguyen):  # thay reverse trong theo_doi.py bằng bản giả lập
            res_khach = self.mo_chi_tiet(self.khach, khach_bk)  # Khách mở chi tiết
            res_nag = self.mo_chi_tiet(self.nag.MaTaiKhoan, nag_bk)  # Nhiếp ảnh gia mở chi tiết
        self.assertEqual(res_khach.status_code, 200)  # trang vẫn mở được (không lỗi 500)
        self.assertEqual(res_nag.status_code, 200)  # trang vẫn mở được
        self.assertNotContains(res_khach, self.NHAN_CHON_ANH)  # nút bị ẩn
        self.assertNotContains(res_nag, self.NHAN_TAI_ANH)  # nút bị ẩn

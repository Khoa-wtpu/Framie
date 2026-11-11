# =====================================================================
# bookings/test_cai_tien_booking.py - kiểm thử các sửa lỗi C1, C3, C4, C5 và đề xuất UX trong file "CỐT QUÉT - GIAI ĐOẠN 4-5 (Extended)"
#   C1  Khách hủy được khi Booking còn "Chờ xác nhận" (rút yêu cầu trước khi Nhiếp ảnh gia phản hồi).
#   C3  Nhiếp ảnh gia hủy được khi "Chờ đặt cọc" (có nút trên trang xử lý riêng).
#   C4  Nhiếp ảnh gia hủy được khi "Chốt Booking" (có nút trên trang xử lý riêng).
#   C5  Nhiếp ảnh gia luôn về MỘT trang đủ nút; thanh đếm ngược hạn đặt cọc; nút "Xem minh chứng đặt cọc" sau khi đã tải lên.
# Chạy:  python manage.py test bookings.test_cai_tien_booking
# =====================================================================
from datetime import timedelta  # khoảng thời gian (vd 1 ngày) để đặt hạn đặt cọc

from django.test import override_settings  # đổi cài đặt riêng cho test
from django.urls import reverse  # từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # lấy giờ hiện tại có múi giờ

from bookings.models import LichSuTrangThaiBooking, YeuCauHuy  # bảng Lịch sử trạng thái và Yêu cầu hủy
from bookings.services import dem_nguoc_han_dat_coc  # hàm tính dữ liệu thanh đếm ngược
from bookings.test_huy_booking import LY_DO, HuyBase  # lớp nền dựng dữ liệu mẫu + lý do hủy mẫu của nhóm
from core.constants import (BenThucHien, LoaiThanhToan, TrangThaiBooking as BK, TrangThaiSlot as SL,  # hằng số dùng chung, đặt tên ngắn
                            TrangThaiThanhToan, XuLyTienCoc as XL)  # trạng thái thanh toán; cách xử lý tiền cọc
from notifications.models import ThongBao  # bảng thông báo web
from payments.models import ThanhToan  # bảng thanh toán (minh chứng cọc)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class CaiTienBase(HuyBase):  # lớp nền: thêm hàm tiện ích dùng chung cho các nhóm test bên dưới
    def cho_dat_coc(self):  # tạo Booking "Chờ đặt cọc" có hạn đặt cọc 1 ngày kể từ bây giờ (giống lúc Nhiếp ảnh gia chấp nhận)
        bk = self.tao_booking(BK.CHO_DAT_COC)  # Booking ở "Chờ đặt cọc"
        bk.HanDatCoc = timezone.now() + timedelta(days=1)  # hạn đặt cọc = bây giờ + 1 ngày
        bk.save(update_fields=['HanDatCoc'])  # chỉ lưu cột hạn
        return bk  # trả Booking

    def mo(self, user, ten_url, bk, **kw):  # đăng nhập rồi mở một trang của Booking
        self.client.force_login(user)  # đăng nhập thẳng bằng tài khoản
        return self.client.get(reverse(ten_url, kwargs={'ma_booking': bk.pk}), **kw)  # mở trang, trả phản hồi


class C1KhachHuyKhiChoXacNhan(CaiTienBase):  # nhóm test C1
    def test_khach_thay_nut_huy_va_loi_nhac_o_cho_xac_nhan(self):  # Khách thấy nút Hủy + lời nhắc "vẫn hủy được"
        bk = self.tao_booking(BK.CHO_XAC_NHAN)  # Booking vừa gửi
        res = self.mo(self.khach, 'chi_tiet_booking', bk)  # Khách mở chi tiết
        self.assertEqual(res.status_code, 200)  # Khách ở lại trang chung (không bị chuyển hướng)
        self.assertContains(res, self.url_huy(bk))  # có nút Hủy Booking
        self.assertContains(res, 'Đang chờ Nhiếp ảnh gia phản hồi')  # có lời nhắc

    def test_nag_khong_thay_nut_huy_o_cho_xac_nhan(self):  # Nhiếp ảnh gia dùng Từ chối chứ không Hủy
        bk = self.tao_booking(BK.CHO_XAC_NHAN)  # Booking vừa gửi
        res = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_yeu_cau_booking', bk)  # trang xử lý của Nhiếp ảnh gia
        self.assertEqual(res.status_code, 200)  # mở được
        self.assertNotContains(res, self.url_huy(bk))  # không có nút Hủy
        self.assertContains(res, reverse('tu_choi_booking', kwargs={'ma_booking': bk.pk}))  # có nút Từ chối

    def test_khach_huy_thanh_cong_day_du(self):  # hủy xong: trạng thái, slot, lịch sử, thông báo hai bên
        bk = self.tao_booking(BK.CHO_XAC_NHAN)  # Booking vừa gửi
        res = self.huy(self.khach, bk)  # Khách gửi form hủy kèm lý do
        self.assertRedirects(res, reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)  # về trang chi tiết
        bk.refresh_from_db()  # nạp lại Booking
        bk.MaLich.refresh_from_db()  # nạp lại slot
        self.assertEqual(bk.TrangThai, BK.DA_HUY)  # Booking "Đã hủy"
        self.assertEqual(bk.MaLich.TrangThai, SL.TRONG)  # slot về "Lịch trống" => đặt lại được
        yc = YeuCauHuy.objects.get(MaBooking=bk)  # Yêu cầu hủy được ghi
        self.assertEqual((yc.BenYeuCau, yc.LyDo, yc.TrangThaiBookingLucHuy, yc.XuLyTienCoc),  # bên hủy, lý do, trạng thái lúc hủy, tiền cọc
                         (BenThucHien.KHACH_HANG, LY_DO, BK.CHO_XAC_NHAN, XL.KHONG_PHAT_SINH))
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk, TrangThaiMoi=BK.DA_HUY)  # dòng lịch sử chuyển sang "Đã hủy"
        self.assertEqual((ls.TrangThaiCu, ls.BenThucHien, ls.LyDo), (BK.CHO_XAC_NHAN, BenThucHien.KHACH_HANG, LY_DO))  # ghi đúng cũ/bên/lý do
        for nguoi in (self.khach, self.nag.MaTaiKhoan):  # cả hai bên đều nhận thông báo web
            self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=nguoi, MaBooking=bk).exists(), nguoi.username)

    def test_khach_huy_thieu_ly_do_bi_chan(self):  # ngoại lệ 4a: không nhập lý do
        bk = self.tao_booking(BK.CHO_XAC_NHAN)  # Booking vừa gửi
        res = self.huy(self.khach, bk, ly_do='   ')  # chỉ toàn dấu cách
        self.assertContains(res, 'Vui lòng nhập lý do hủy')  # hiện câu báo lỗi
        bk.refresh_from_db()  # nạp lại
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)  # không đổi

    def test_khach_khac_khong_huy_duoc_booking_nguoi_khac(self):  # an toàn: Booking của người khác -> 404
        bk = self.tao_booking(BK.CHO_XAC_NHAN)  # Booking của khach_a
        self.client.force_login(self.khach_b)  # đăng nhập khach_b
        self.assertEqual(self.client.post(self.url_huy(bk), {'ly_do': LY_DO}).status_code, 404)  # không lộ là có tồn tại
        bk.refresh_from_db()  # nạp lại
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)  # không đổi


class C3C4NagHuyKhiChoCocVaChot(CaiTienBase):  # nhóm test C3 + C4
    def test_nag_thay_nut_huy_o_trang_xu_ly_khi_cho_dat_coc(self):  # C3
        bk = self.cho_dat_coc()  # "Chờ đặt cọc"
        res = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_yeu_cau_booking', bk)  # trang xử lý /quan-ly/<mã>/
        self.assertEqual(res.status_code, 200)  # mở được
        self.assertContains(res, self.url_huy(bk))  # có nút Hủy Booking

    def test_nag_thay_nut_huy_o_trang_xu_ly_khi_chot_booking(self):  # C4
        bk = self.tao_booking(BK.CHOT_BOOKING)  # "Chốt Booking"
        res = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_yeu_cau_booking', bk)  # trang xử lý
        self.assertContains(res, self.url_huy(bk))  # có nút Hủy Booking

    def test_nag_huy_truoc_coc_dung_nhu_case_c3(self):  # đúng "Mong đợi" của case C3 trong file
        bk = self.cho_dat_coc()  # "Chờ đặt cọc"
        res = self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia hủy kèm lý do
        self.assertRedirects(res, reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)  # về trang chi tiết (rồi tới trang xử lý)
        bk.refresh_from_db()  # nạp lại
        bk.MaLich.refresh_from_db()  # nạp lại slot
        self.assertEqual(bk.TrangThai, BK.DA_HUY)  # "Đã hủy"
        self.assertEqual(bk.MaLich.TrangThai, SL.TRONG)  # trả khung giờ về lịch trống
        yc = YeuCauHuy.objects.get(MaBooking=bk)  # Yêu cầu hủy
        self.assertEqual((yc.BenYeuCau, yc.LyDo, yc.XuLyTienCoc), (BenThucHien.NHIEP_ANH_GIA, LY_DO, XL.KHONG_PHAT_SINH))  # ghi bên hủy + lý do; không mất/hoàn cọc
        self.assertIsNone(yc.TrangThaiHoanTien)  # không có theo dõi hoàn tiền
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag.MaTaiKhoan, MaBooking=bk).exists())  # Nhiếp ảnh gia nhận thông báo
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.khach, MaBooking=bk).exists())  # Khách cũng nhận thông báo
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk, TrangThaiMoi=BK.DA_HUY)  # lịch sử
        self.assertEqual((ls.BenThucHien, ls.LyDo), (BenThucHien.NHIEP_ANH_GIA, LY_DO))  # ghi bên hủy và lý do
        res = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_booking', bk)  # sau khi hủy Nhiếp ảnh gia xem lại
        self.assertContains(res, 'Thông tin hủy')  # thấy khối "Thông tin hủy"
        # slot đặt lại được: một Booking mới dùng lại cùng slot không bị chặn (ràng buộc "mỗi slot một Booking còn hiệu lực")
        from bookings.models import Booking  # import trong hàm cho gọn
        Booking.objects.create(MaKhachHang=self.khach_b, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=bk.MaLich,
                               NgayGioChup=bk.NgayGioChup, DiaDiem='Hồ Gươm', SoNguoi=1, Concept='Mới')

    def test_nag_huy_khi_chot_booking_ghi_hoan_coc(self):  # C4: đã cọc -> Nhiếp ảnh gia hủy phải hoàn cọc
        bk = self.tao_booking(BK.CHOT_BOOKING)  # "Chốt Booking"
        self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia hủy
        yc = YeuCauHuy.objects.get(MaBooking=bk)  # Yêu cầu hủy
        self.assertEqual((yc.XuLyTienCoc, yc.TrangThaiHoanTien), (XL.HOAN_COC, 'Chờ hoàn tiền'))  # ghi nghĩa vụ hoàn cọc, đang chờ hoàn

    def test_nag_khac_khong_huy_duoc(self):  # an toàn: Nhiếp ảnh gia khác -> 404
        bk = self.cho_dat_coc()  # Booking của self.nag
        self.client.force_login(self.nag_khac.MaTaiKhoan)  # đăng nhập Nhiếp ảnh gia khác
        self.assertEqual(self.client.post(self.url_huy(bk), {'ly_do': LY_DO}).status_code, 404)  # 404
        bk.refresh_from_db()  # nạp lại
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)  # không đổi


class C5MotTrangChoNag(CaiTienBase):  # nhóm test C5: Nhiếp ảnh gia luôn về MỘT trang đủ nút
    def test_cua_toi_chuyen_sang_trang_xu_ly_voi_nag(self):  # 3 trạng thái có trang xử lý riêng
        for tt in (BK.CHO_XAC_NHAN, BK.CHO_DAT_COC, BK.CHOT_BOOKING):  # từng trạng thái
            with self.subTest(trang_thai=tt):  # báo lỗi riêng
                bk = self.tao_booking(tt)  # Booking ở trạng thái đang thử
                res = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_booking', bk)  # mở /cua-toi/<mã>/
                self.assertRedirects(res, reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)  # -> /quan-ly/<mã>/

    def test_khong_bao_gio_lap_chuyen_huong(self):  # mọi trạng thái: theo link tối đa 1 lần chuyển, kết thúc ở 200
        for tt in BK.ALL:  # cả 13 trạng thái
            with self.subTest(trang_thai=tt):  # báo lỗi riêng
                bk = self.tao_booking(tt)  # Booking ở trạng thái đang thử
                res = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_booking', bk, follow=True)  # đi theo mọi chuyển hướng
                self.assertEqual(res.status_code, 200)  # kết thúc ở trang hiển thị được
                self.assertLessEqual(len(res.redirect_chain), 1)  # tối đa một lần chuyển (không vòng lặp)

    def test_khach_khong_bi_chuyen_huong(self):  # Khách luôn ở trang chung
        bk = self.cho_dat_coc()  # "Chờ đặt cọc"
        self.assertEqual(self.mo(self.khach, 'chi_tiet_booking', bk).status_code, 200)  # 200

    def test_booking_nag_khac_van_404(self):  # chuyển hướng không làm lộ Booking của người khác
        bk = self.cho_dat_coc()  # Booking của self.nag
        res = self.mo(self.nag_khac.MaTaiKhoan, 'chi_tiet_booking', bk)  # Nhiếp ảnh gia khác mở
        self.assertEqual(res.status_code, 404)  # 404, không phải 302


class DemNguocHanCoc(CaiTienBase):  # nhóm test thanh đếm ngược hạn đặt cọc
    def test_ham_tinh_con_lai(self):  # hàm service
        bk = self.cho_dat_coc()  # hạn = bây giờ + 1 ngày
        kq = dem_nguoc_han_dat_coc(bk)  # tính
        self.assertEqual(kq['tong'], 86400)  # tổng 1 ngày = 86400 giây
        self.assertTrue(86390 <= kq['con_lai'] <= 86400)  # còn xấp xỉ 1 ngày

    def test_qua_han_thi_con_lai_bang_0(self):  # quá hạn không âm
        bk = self.cho_dat_coc()  # "Chờ đặt cọc"
        bk.HanDatCoc = timezone.now() - timedelta(hours=1)  # đã quá hạn 1 giờ
        self.assertEqual(dem_nguoc_han_dat_coc(bk)['con_lai'], 0)  # 0

    def test_trang_thai_khac_khong_co_dem_nguoc(self):  # chỉ "Chờ đặt cọc" có thanh
        for tt in (BK.CHO_XAC_NHAN, BK.CHOT_BOOKING, BK.DA_HUY):  # vài trạng thái khác
            self.assertIsNone(dem_nguoc_han_dat_coc(self.tao_booking(tt)), tt)  # None

    def test_ca_hai_trang_deu_co_thanh_dem_nguoc(self):  # trang Khách và trang Nhiếp ảnh gia
        bk = self.cho_dat_coc()  # "Chờ đặt cọc"
        khach = self.mo(self.khach, 'chi_tiet_booking', bk)  # trang của Khách
        nag = self.mo(self.nag.MaTaiKhoan, 'chi_tiet_yeu_cau_booking', bk)  # trang xử lý của Nhiếp ảnh gia
        for res in (khach, nag):  # cả hai
            self.assertContains(res, 'id="han-coc"')  # có khối đếm ngược
            self.assertContains(res, 'han_dat_coc.js')  # có nạp JS
        self.assertContains(khach, 'Bạn cần đặt cọc')  # chữ viết cho Khách
        self.assertContains(nag, 'Khách hàng cần đặt cọc')  # chữ viết cho Nhiếp ảnh gia

    def test_khong_co_thanh_dem_nguoc_o_trang_thai_khac(self):  # ẩn khi không "Chờ đặt cọc"
        bk = self.tao_booking(BK.CHOT_BOOKING)  # "Chốt Booking"
        self.assertNotContains(self.mo(self.khach, 'chi_tiet_booking', bk), 'id="han-coc"')  # không có


class NhanNutMinhChung(CaiTienBase):  # nhóm test: chữ trên nút minh chứng của Khách
    def tao_khoan(self, bk, ly_do=None):  # tạo khoản cọc Khách đã gửi minh chứng
        return ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.TIEN_COC, SoTien=600000,
                                        TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_COC, NgayThanhToan=timezone.now(), LyDoTuChoi=ly_do)

    def nhan(self, bk):  # lấy chữ trên nút từ context của trang Khách
        return self.mo(self.khach, 'chi_tiet_booking', bk).context['nhan_tai_minh_chung']

    def test_chua_gui_la_tai(self):  # chưa gửi
        self.assertEqual(self.nhan(self.cho_dat_coc()), 'Tải minh chứng đặt cọc')

    def test_da_gui_la_xem(self):  # đã gửi, chờ Nhiếp ảnh gia xác nhận
        bk = self.cho_dat_coc()
        self.tao_khoan(bk)
        self.assertEqual(self.nhan(bk), 'Xem minh chứng đặt cọc')

    def test_bi_yeu_cau_bo_sung_la_tai_lai(self):  # Nhiếp ảnh gia yêu cầu bổ sung -> Khách phải tải lại
        bk = self.cho_dat_coc()
        self.tao_khoan(bk, ly_do='Ảnh mờ')
        self.assertEqual(self.nhan(bk), 'Tải minh chứng đặt cọc')


class GiaoDienMau(CaiTienBase):  # nhóm test: trang chi tiết có thẻ phân màu (không dùng mã màu cứng)
    def test_the_co_mau_rieng(self):  # trang Khách và trang Nhiếp ảnh gia
        bk = self.cho_dat_coc()
        for res in (self.mo(self.khach, 'chi_tiet_booking', bk), self.mo(self.nag.MaTaiKhoan, 'chi_tiet_yeu_cau_booking', bk)):
            self.assertContains(res, 'ct__the--mau')  # có thẻ phân màu
            self.assertContains(res, 'ct__o--ngay')  # dải thông tin phân màu

    def test_css_moi_khong_go_ma_mau(self):  # quy ước README_GIAO_DIEN: CHỈ dùng biến, không gõ mã màu
        import re  # tìm mã màu bằng biểu thức chính quy
        from pathlib import Path  # đọc file
        goc = Path(__file__).resolve().parent / 'static' / 'bookings' / 'css'  # thư mục CSS của bookings
        phan_moi = (goc / 'chi_tiet_booking.css').read_text(encoding='utf-8').split('C2 + C5: THANH ĐẾM NGƯỢC')[1]  # phần CSS mới thêm
        phan_moi += (goc / 'bookings.css').read_text(encoding='utf-8').split('.goi-chi-tiet {')[1]  # phần CSS form mới
        self.assertIsNone(re.search(r'#[0-9A-Fa-f]{3,8}\b', phan_moi))  # không có mã #RRGGBB nào

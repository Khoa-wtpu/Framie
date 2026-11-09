# =====================================================================
# bookings/test_huy_booking.py - Test cho bookings/huy_booking.py (T9 / UC4.6)
# Chạy:  python manage.py test bookings.test_huy_booking
# =====================================================================
from unittest import mock  # mock: thay thế tạm một hàm để dựng tình huống hai thao tác chạm nhau
from datetime import timedelta  # timedelta: một khoảng thời gian (vd: 3 ngày) để cộng vào ngày

from django.core import mail  # mail.outbox: hộp thư giả khi chạy test, để kiểm tra Email đã "gửi"
from django.test import TestCase, override_settings  # TestCase: lớp test có CSDL tạm; override_settings: đổi cài đặt riêng cho test
from django.urls import reverse  # từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # lấy ngày giờ có múi giờ

from bookings import huy_booking as hb  # module nghiệp vụ hủy (để mock lay_booking_cua_ben)
from bookings.services import chuyen_trang_thai_booking  # hàm đổi trạng thái chung (dùng để giả lập Nhiếp ảnh gia xác nhận cọc)
from bookings.models import Booking, LichSuTrangThaiBooking, YeuCauHuy  # 3 bảng cần kiểm tra: Booking, Lịch sử trạng thái, Yêu cầu hủy
from bookings.test_tiep_nhan import tao_nag, tao_user          # dựng tài khoản / Nhiếp ảnh gia mẫu của nhóm
from core.constants import (BenThucHien, LoaiHauKy, TrangThaiBooking as BK, TrangThaiSlot as SL,  # các hằng số dùng chung, đặt tên ngắn: BK = trạng thái Booking, SL = trạng thái slot
                            VaiTro, XuLyTienCoc as XL, TrangThaiHoanTien as HT)  # VaiTro; XL = xử lý tiền cọc; HT = trạng thái hoàn tiền
from notifications.models import ThongBao  # bảng thông báo web
from core.constants import LoaiThanhToan, TrangThaiThanhToan  # loại / trạng thái thanh toán (minh chứng cọc đang chờ)
from payments.models import ThanhToan  # bảng thanh toán
from profiles.models import GoiDichVu, LoaiHinhChup  # bảng Gói dịch vụ và Loại hình chụp
from schedule.models import LichKhaDung  # bảng lịch khả dụng (các slot giờ chụp)

LY_DO = 'Em bận việc đột xuất.'  # lý do hủy mẫu dùng chung cho mọi test


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # dùng cách mã hóa mật khẩu nhanh để test chạy nhanh hơn
class HuyBase(TestCase):  # lớp nền: dựng dữ liệu mẫu chung, các lớp test khác kế thừa
    def setUp(self):  # chạy TRƯỚC mỗi test: tạo dữ liệu mẫu
        self.khach = tao_user('khach_a', VaiTro.KHACH_HANG, first_name='An', last_name='Nguyễn')  # Khách hàng chính "khach_a"
        self.khach_b = tao_user('khach_b', VaiTro.KHACH_HANG)  # Khách hàng thứ hai (dùng để thử "Booking của người khác")
        self.nag = tao_nag('nag')  # Nhiếp ảnh gia chính
        self.nag_khac = tao_nag('nag_khac')  # Nhiếp ảnh gia khác (dùng để thử truy cập trái phép)
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')  # tạo loại hình chụp "Chân dung"
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='Gói cơ bản',  # tạo gói dịch vụ của self.nag...
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)  # ...giá 1.500.000, chụp 60 phút, hậu kỳ toàn bộ
        self.ngay = timezone.localdate() + timedelta(days=3)  # ngày chụp mẫu = 3 ngày sau hôm nay
        self._gio = 7  # bộ đếm giờ bắt đầu, để mỗi Booking dùng một slot khác nhau (không trùng)

    def tao_booking(self, trang_thai=BK.CHO_DAT_COC):  # hàm tiện ích: tạo nhanh một Booking ở trạng thái mong muốn
        """Booking của self.khach gửi self.nag. Slot: Chờ đặt cọc = Đang giữ chỗ; các trạng thái sau = Đã đặt lịch."""
        self._gio += 1  # tăng giờ để slot mới không trùng slot cũ
        gio = f'{self._gio:02d}:00'  # giờ bắt đầu dạng "08:00" (02d = đủ 2 chữ số)
        slot = SL.DANG_GIU if trang_thai in (BK.CHO_XAC_NHAN, BK.CHO_DAT_COC) else SL.DA_DAT  # trạng thái sớm -> slot "Đang giữ chỗ"; còn lại -> "Đã đặt"
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay, GioBatDau=gio,  # tạo một slot lịch của nhiếp ảnh gia: ngày, giờ bắt đầu...
                                          GioKetThuc=f'{self._gio + 2:02d}:00', TrangThai=slot)  # ...giờ kết thúc (+2 tiếng) và trạng thái slot
        gio_chup = timezone.make_aware(timezone.datetime.combine(self.ngay, timezone.datetime.strptime(gio, '%H:%M').time()))  # ghép ngày + giờ thành một mốc thời gian có múi giờ
        return Booking.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,  # tạo Booking: khách, nhiếp ảnh gia, gói, slot
                                      NgayGioChup=gio_chup, DiaDiem='Hồ Gươm', SoNguoi=2, Concept='Vintage',  # giờ chụp, địa điểm, số người, concept
                                      TrangThai=trang_thai,  # trạng thái theo tham số
                                      LyDoTuChoi='Trùng lịch' if trang_thai == BK.DA_TU_CHOI else None)   # CHECK ck_booking_lydotuchoi

    def url_huy(self, bk):  # địa chỉ trang hủy của một Booking
        return reverse('huy_booking', kwargs={'ma_booking': bk.pk})  # suy ra URL từ tên 'huy_booking'

    def url_hoan(self, bk):  # địa chỉ nút xác nhận hoàn tiền của một Booking
        return reverse('xac_nhan_hoan_tien', kwargs={'ma_booking': bk.pk})  # suy ra URL từ tên 'xac_nhan_hoan_tien'

    def huy(self, user, bk, ly_do=LY_DO):  # mô phỏng: một người dùng gửi form hủy
        self.client.force_login(user)  # đăng nhập thẳng bằng tài khoản này (không cần gõ mật khẩu)
        with self.captureOnCommitCallbacks(execute=True):  # cho phép các việc "sau khi lưu xong" (gửi Email) chạy thật trong test
            return self.client.post(self.url_huy(bk), {'ly_do': ly_do})  # gửi POST kèm lý do tới trang hủy, trả về phản hồi


# ---------------------------------------------------------------------
# Hủy thành công: 4 tổ hợp (trạng thái lúc hủy x bên hủy)
# ---------------------------------------------------------------------
class HuyThanhCong(HuyBase):  # nhóm test: các trường hợp hủy thành công
    def kiem_tra_chung(self, bk, ben, xu_ly):  # phần kiểm tra chung cho mọi trường hợp hủy thành công
        bk.refresh_from_db()  # nạp lại Booking từ CSDL để thấy giá trị mới
        self.assertEqual(bk.TrangThai, BK.DA_HUY)  # Booking phải đã sang "Đã hủy"
        bk.MaLich.refresh_from_db()  # nạp lại slot từ CSDL
        self.assertEqual(bk.MaLich.TrangThai, SL.TRONG)                      # slot được nhả
        ls = LichSuTrangThaiBooking.objects.filter(MaBooking=bk).last()      # Lịch sử: bên hủy + lý do
        self.assertEqual((ls.TrangThaiMoi, ls.BenThucHien, ls.LyDo), (BK.DA_HUY, ben, LY_DO))  # dòng lịch sử cuối phải ghi: trạng thái mới, bên hủy, lý do
        yc = YeuCauHuy.objects.get(MaBooking=bk)  # lấy Yêu cầu hủy của Booking
        self.assertEqual((yc.BenYeuCau, yc.LyDo, yc.XuLyTienCoc), (ben, LY_DO, xu_ly))  # kiểm tra bên hủy, lý do, cách xử lý tiền cọc đều đúng
        return yc  # trả yêu cầu hủy để test con kiểm tra thêm

    def test_khach_huy_cho_dat_coc_khong_phat_sinh(self):  # Khách hủy khi chưa cọc
        bk = self.tao_booking(BK.CHO_DAT_COC)  # tạo Booking "Chờ đặt cọc"
        res = self.huy(self.khach, bk)  # Khách gửi hủy
        self.assertRedirects(res, reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)  # phải được chuyển về trang chi tiết Booking
        yc = self.kiem_tra_chung(bk, BenThucHien.KHACH_HANG, XL.KHONG_PHAT_SINH)  # kiểm tra chung: bên hủy = Khách, tiền cọc = Không phát sinh
        self.assertIsNone(yc.TrangThaiHoanTien)  # chưa cọc nên không có theo dõi hoàn tiền
        self.assertEqual(yc.TrangThaiBookingLucHuy, BK.CHO_DAT_COC)  # ghi nhận trạng thái lúc hủy là "Chờ đặt cọc"

    def test_nag_huy_cho_dat_coc_khong_phat_sinh(self):  # Nhiếp ảnh gia hủy khi chưa cọc
        bk = self.tao_booking(BK.CHO_DAT_COC)  # tạo Booking "Chờ đặt cọc"
        self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia gửi hủy
        yc = self.kiem_tra_chung(bk, BenThucHien.NHIEP_ANH_GIA, XL.KHONG_PHAT_SINH)  # bên hủy = Nhiếp ảnh gia, tiền cọc = Không phát sinh
        self.assertIsNone(yc.TrangThaiHoanTien)  # không có theo dõi hoàn tiền

    def test_khach_huy_chot_booking_mat_coc(self):  # Khách hủy sau khi cọc
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking "Chốt Booking" (đã cọc)
        self.huy(self.khach, bk)  # Khách gửi hủy
        yc = self.kiem_tra_chung(bk, BenThucHien.KHACH_HANG, XL.MAT_COC)  # bên hủy = Khách, tiền cọc = Mất cọc
        self.assertIsNone(yc.TrangThaiHoanTien)                              # mất cọc thì không có theo dõi hoàn tiền
        self.assertEqual(yc.TrangThaiBookingLucHuy, BK.CHOT_BOOKING)  # ghi nhận trạng thái lúc hủy là "Chốt Booking"

    def test_nag_huy_chot_booking_hoan_coc_cho_hoan_tien(self):  # Nhiếp ảnh gia hủy sau khi cọc
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking "Chốt Booking"
        self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia gửi hủy
        yc = self.kiem_tra_chung(bk, BenThucHien.NHIEP_ANH_GIA, XL.HOAN_COC)  # bên hủy = Nhiếp ảnh gia, tiền cọc = Hoàn cọc
        self.assertEqual(yc.TrangThaiHoanTien, HT.CHO_HOAN_TIEN)  # trạng thái hoàn tiền = "Chờ hoàn tiền"
        self.assertIsNone(yc.ThoiDiemXacNhanHoanTien)  # Khách chưa xác nhận nên chưa có thời điểm

    def test_thong_bao_web_va_email_cho_ca_hai_ben(self):  # cả hai bên đều nhận thông báo + Email
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking "Chốt Booking"
        self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia hủy
        for user in (self.khach, self.nag.MaTaiKhoan):  # lần lượt kiểm tra Khách rồi Nhiếp ảnh gia
            tb = ThongBao.objects.get(MaNguoiNhan=user, MaBooking=bk)  # lấy thông báo gửi cho người này về Booking này
            self.assertIn(LY_DO, tb.NoiDung)  # nội dung phải có lý do hủy
            self.assertIn('hoàn lại 40% tiền cọc', tb.NoiDung)  # và có câu về việc hoàn 40% cọc
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([self.khach.email, self.nag.MaTaiKhoan.email]))  # hộp thư giả phải có đúng 2 Email, gửi tới Khách và Nhiếp ảnh gia

    def test_noi_dung_thong_bao_mat_coc_va_khong_phat_sinh(self):  # nội dung thông báo khác nhau theo hệ quả tiền cọc
        bk = self.tao_booking(BK.CHOT_BOOKING)  # Booking đã cọc
        self.huy(self.khach, bk)  # Khách hủy -> mất cọc
        self.assertIn('mất 40% tiền cọc', ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan, MaBooking=bk).NoiDung)  # thông báo gửi Nhiếp ảnh gia có câu "mất 40% tiền cọc"
        bk2 = self.tao_booking(BK.CHO_DAT_COC)  # Booking chưa cọc
        self.huy(self.khach, bk2)  # Khách hủy -> không phát sinh
        self.assertIn('không phát sinh', ThongBao.objects.get(MaNguoiNhan=self.khach, MaBooking=bk2).NoiDung)  # thông báo có câu "không phát sinh"

    def test_slot_duoc_dat_lai_sau_khi_huy(self):  # slot phải được nhả sau khi hủy
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.huy(self.khach, bk)  # Khách hủy
        bk.MaLich.refresh_from_db()  # nạp lại slot
        self.assertEqual(bk.MaLich.TrangThai, SL.TRONG)  # slot về "Lịch trống" -> người khác đặt lại được


# ---------------------------------------------------------------------
# Lý do (ngoại lệ 4a) và trang xác nhận
# ---------------------------------------------------------------------
class LyDoVaTrangXacNhan(HuyBase):  # nhóm test: kiểm tra lý do và trang xác nhận
    def test_thieu_ly_do_khong_huy(self):  # không nhập lý do thì không hủy
        for ly_do in ('', '   '):  # thử hai trường hợp: rỗng và toàn dấu cách
            bk = self.tao_booking(BK.CHO_DAT_COC)  # tạo Booking mới cho mỗi lần thử
            res = self.huy(self.khach, bk, ly_do)  # gửi hủy với lý do thiếu
            self.assertContains(res, 'Vui lòng nhập lý do hủy')  # trang phản hồi phải có câu báo lỗi
            bk.refresh_from_db()  # nạp lại Booking
            self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)  # trạng thái vẫn là "Chờ đặt cọc" (chưa hủy)
            self.assertFalse(YeuCauHuy.objects.filter(MaBooking=bk).exists())  # và không có Yêu cầu hủy nào được tạo

    def test_ly_do_qua_dai_khong_huy(self):  # lý do quá 255 ký tự thì không hủy
        bk = self.tao_booking(BK.CHO_DAT_COC)  # tạo Booking
        res = self.huy(self.khach, bk, 'x' * 256)  # gửi lý do dài 256 ký tự (vượt 1)
        self.assertContains(res, 'Lý do tối đa 255 ký tự')  # phải hiện câu báo giới hạn
        bk.refresh_from_db()  # nạp lại Booking
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)  # vẫn chưa bị hủy

    def test_get_chi_hien_trang_xac_nhan_chua_huy(self):  # mở trang (GET) chỉ hiện form, chưa hủy
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.client.force_login(self.khach)  # đăng nhập bằng Khách
        res = self.client.get(self.url_huy(bk))  # mở trang hủy bằng GET
        self.assertTemplateUsed(res, 'bookings/huy_xac_nhan.html')  # phải dùng đúng template xác nhận
        self.assertContains(res, 'mất 40% tiền cọc')  # trang có giải thích hệ quả mất cọc
        self.assertContains(res, 'Xác nhận hủy Booking')  # trang có nút xác nhận
        bk.refresh_from_db()  # nạp lại Booking
        self.assertEqual(bk.TrangThai, BK.CHOT_BOOKING)  # Booking vẫn nguyên trạng thái cũ

    def test_trang_xac_nhan_noi_ro_he_qua_theo_tung_truong_hop(self):  # lời giải thích hệ quả đúng theo từng trường hợp
        cho_coc, chot = self.tao_booking(BK.CHO_DAT_COC), self.tao_booking(BK.CHOT_BOOKING)  # tạo 2 Booking: chưa cọc và đã chốt
        self.client.force_login(self.khach)  # đăng nhập Khách
        self.assertContains(self.client.get(self.url_huy(cho_coc)), 'không phát sinh mất hoặc hoàn tiền cọc')  # Booking chưa cọc -> câu "không phát sinh"
        self.assertContains(self.client.get(self.url_huy(chot)), 'bạn sẽ mất 40% tiền cọc')  # Booking đã chốt, Khách hủy -> câu "mất 40%"
        self.client.force_login(self.nag.MaTaiKhoan)  # đổi sang đăng nhập Nhiếp ảnh gia
        res = self.client.get(self.url_huy(chot))  # Nhiếp ảnh gia mở trang hủy Booking đã chốt
        self.assertContains(res, 'có trách nhiệm hoàn lại 40% tiền cọc')  # câu nói Nhiếp ảnh gia phải hoàn cọc
        self.assertContains(res, 'FRAMIE không trực tiếp hoàn tiền')  # và câu nhắc FRAMIE không giữ tiền


# ---------------------------------------------------------------------
# Trạng thái không được hủy; hủy hai lần
# ---------------------------------------------------------------------
class KhongHuyDuoc(HuyBase):  # nhóm test: các trường hợp không được hủy
    def test_tu_da_chup_tro_di_va_cac_trang_thai_khac_khong_huy_duoc(self):  # mọi trạng thái ngoài 2 trạng thái cho phép đều bị chặn
        for tt in (BK.CHO_XAC_NHAN, BK.DA_CHUP, BK.CHO_KH_CHON_ANH, BK.CHO_HAU_KY, BK.DANG_HAU_KY, BK.CHO_KH_KIEM_TRA,  # danh sách các trạng thái không được hủy (phần 1)
                   BK.CHO_XAC_NHAN_THANH_TOAN, BK.HOAN_THANH, BK.DA_TU_CHOI, BK.HET_THOI_HAN_DAT_COC, BK.DA_HUY):  # (phần 2)
            with self.subTest(trang_thai=tt):  # mỗi trạng thái là một "test con", lỗi sẽ chỉ rõ trạng thái nào
                bk = self.tao_booking(tt)  # tạo Booking ở trạng thái đang thử
                for user in (self.khach, self.nag.MaTaiKhoan):  # thử với cả Khách và Nhiếp ảnh gia
                    self.client.force_login(user)  # đăng nhập người này
                    self.assertRedirects(self.client.get(self.url_huy(bk)),  # mở trang hủy -> phải bị chuyển hướng...
                                         reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)  # ...về trang chi tiết Booking
                    self.client.post(self.url_huy(bk), {'ly_do': LY_DO})  # cố gửi hủy bằng POST
                bk.refresh_from_db()  # nạp lại Booking
                self.assertEqual(bk.TrangThai, tt)                            # không đổi
                self.assertFalse(YeuCauHuy.objects.filter(MaBooking=bk).exists())  # không có Yêu cầu hủy nào được tạo

    def test_huy_hai_lan_chi_ghi_mot_yeu_cau(self):  # hủy lần 2 không ghi thêm gì
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.huy(self.khach, bk)  # Khách hủy lần 1
        res = self.huy(self.nag.MaTaiKhoan, bk)                               # lần 2 (đã Đã hủy)
        self.assertRedirects(res, reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}), fetch_redirect_response=False)  # lần 2 bị chuyển về trang chi tiết
        self.assertEqual(YeuCauHuy.objects.filter(MaBooking=bk).count(), 1)  # vẫn chỉ có 1 Yêu cầu hủy
        self.assertEqual(YeuCauHuy.objects.get(MaBooking=bk).BenYeuCau, BenThucHien.KHACH_HANG)  # và bên hủy vẫn là Khách (lần đầu)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk, TrangThaiMoi=BK.DA_HUY).count(), 1)  # Lịch sử chỉ có 1 dòng chuyển sang "Đã hủy"


# ---------------------------------------------------------------------
# Quyền truy cập
# ---------------------------------------------------------------------
class Quyen(HuyBase):  # nhóm test: quyền truy cập
    def test_chua_dang_nhap_ve_trang_dang_nhap(self):  # chưa đăng nhập thì bị đẩy về trang đăng nhập
        bk = self.tao_booking()  # tạo Booking
        res = self.client.post(self.url_huy(bk), {'ly_do': LY_DO})  # gửi hủy khi CHƯA đăng nhập
        self.assertRedirects(res, f"{reverse('login')}?next={self.url_huy(bk)}", fetch_redirect_response=False)  # phải chuyển tới trang đăng nhập, nhớ trang cũ để quay lại (?next=)
        bk.refresh_from_db()  # nạp lại Booking
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)  # Booking không đổi

    def test_booking_cua_nguoi_khac_la_404_va_khong_doi(self):  # Booking của người khác -> 404
        bk = self.tao_booking()  # Booking của self.khach và self.nag
        for user in (self.khach_b, self.nag_khac.MaTaiKhoan):  # hai người "ngoài cuộc"
            self.client.force_login(user)  # đăng nhập người này
            self.assertEqual(self.client.get(self.url_huy(bk)).status_code, 404)  # mở trang hủy -> 404
            self.assertEqual(self.client.post(self.url_huy(bk), {'ly_do': LY_DO}).status_code, 404)  # gửi hủy -> 404
        bk.refresh_from_db()  # nạp lại Booking
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)  # Booking không đổi

    def test_quan_tri_vien_khong_huy_duoc(self):  # Quản trị viên không có quyền hủy
        bk = self.tao_booking()  # tạo Booking
        self.client.force_login(tao_user('qt', VaiTro.QUAN_TRI_VIEN))  # đăng nhập bằng một Quản trị viên mới tạo
        self.assertEqual(self.client.post(self.url_huy(bk), {'ly_do': LY_DO}).status_code, 403)  # gửi hủy -> 403 (cấm)
        bk.refresh_from_db()  # nạp lại Booking
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)  # Booking không đổi

    def test_khong_nhan_get_o_nut_xac_nhan_hoan_tien(self):  # nút xác nhận hoàn tiền chỉ nhận POST
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia hủy -> phát sinh hoàn cọc
        self.client.force_login(self.khach)  # đăng nhập Khách
        self.assertEqual(self.client.get(self.url_hoan(bk)).status_code, 405)  # mở bằng GET -> 405 (không cho phép phương thức này)


# ---------------------------------------------------------------------
# Khách xác nhận đã nhận lại tiền cọc
# ---------------------------------------------------------------------
class XacNhanHoanTien(HuyBase):  # nhóm test: Khách xác nhận đã nhận lại cọc
    def setUp(self):  # chạy trước mỗi test của nhóm này
        super().setUp()  # chạy phần dựng dữ liệu của lớp nền
        self.bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.huy(self.nag.MaTaiKhoan, self.bk)                                # NAG hủy -> Hoàn cọc, Chờ hoàn tiền

    def xac_nhan(self, user, bk=None):  # mô phỏng một người bấm nút "Tôi đã nhận lại tiền cọc"
        self.client.force_login(user)  # đăng nhập người này
        with self.captureOnCommitCallbacks(execute=True):  # cho các việc sau commit (Email) chạy thật
            return self.client.post(self.url_hoan(bk or self.bk))  # gửi POST tới nút xác nhận (mặc định dùng self.bk)

    def test_khach_xac_nhan_thanh_da_hoan_tien(self):  # xác nhận thành công
        res = self.xac_nhan(self.khach)  # Khách bấm xác nhận
        self.assertRedirects(res, reverse('chi_tiet_booking', kwargs={'ma_booking': self.bk.pk}), fetch_redirect_response=False)  # được chuyển về trang chi tiết
        yc = YeuCauHuy.objects.get(MaBooking=self.bk)  # lấy lại Yêu cầu hủy
        self.assertEqual(yc.TrangThaiHoanTien, HT.DA_HOAN_TIEN)  # trạng thái hoàn tiền = "Đã hoàn tiền"
        self.assertIsNotNone(yc.ThoiDiemXacNhanHoanTien)  # đã ghi thời điểm xác nhận
        self.assertGreaterEqual(yc.ThoiDiemXacNhanHoanTien, yc.ThoiDiemYeuCau)  # thời điểm xác nhận không thể sớm hơn thời điểm hủy
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag.MaTaiKhoan, MaBooking=self.bk,  # có thông báo gửi Nhiếp ảnh gia về Booking này...
                                                TieuDe__contains='đã nhận lại tiền cọc').exists())  # ...với tiêu đề chứa "đã nhận lại tiền cọc"

    def test_bam_lan_hai_khong_ghi_de(self):  # bấm lần 2 không ghi đè thời điểm
        self.xac_nhan(self.khach)  # bấm lần 1
        gio_dau = YeuCauHuy.objects.get(MaBooking=self.bk).ThoiDiemXacNhanHoanTien  # ghi nhớ thời điểm của lần 1
        res = self.client.post(self.url_hoan(self.bk), follow=True)  # bấm lần 2 và đi theo chuyển hướng để đọc trang kết quả
        self.assertContains(res, 'đã xác nhận nhận lại tiền cọc')  # trang hiện câu "đã xác nhận... rồi"
        self.assertEqual(YeuCauHuy.objects.get(MaBooking=self.bk).ThoiDiemXacNhanHoanTien, gio_dau)  # thời điểm vẫn là của lần 1

    def test_nag_khong_xac_nhan_duoc(self):  # Nhiếp ảnh gia không được bấm xác nhận thay Khách
        self.assertEqual(self.xac_nhan(self.nag.MaTaiKhoan).status_code, 403)  # bị chặn 403
        self.assertEqual(YeuCauHuy.objects.get(MaBooking=self.bk).TrangThaiHoanTien, HT.CHO_HOAN_TIEN)  # trạng thái vẫn "Chờ hoàn tiền"

    def test_khach_khac_la_404(self):  # Khách khác không được xác nhận Booking không phải của mình
        self.assertEqual(self.xac_nhan(self.khach_b).status_code, 404)  # bị 404
        self.assertEqual(YeuCauHuy.objects.get(MaBooking=self.bk).TrangThaiHoanTien, HT.CHO_HOAN_TIEN)  # trạng thái vẫn "Chờ hoàn tiền"

    def test_khong_co_hoan_coc_thi_bao_loi(self):  # không có khoản hoàn cọc thì báo lỗi
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt khác
        self.huy(self.khach, bk)                                              # Khách hủy -> Mất cọc, không có hoàn tiền
        res = self.client.post(self.url_hoan(bk), follow=True)  # Khách bấm xác nhận hoàn tiền
        self.assertContains(res, 'không có khoản cọc nào cần hoàn lại')  # phải hiện câu báo không có gì để hoàn
        chua_huy = self.tao_booking(BK.CHOT_BOOKING)                          # chưa hủy -> không có yêu cầu hủy
        self.assertContains(self.client.post(self.url_hoan(chua_huy), follow=True), 'không có khoản cọc nào cần hoàn lại')  # Booking chưa hủy cũng báo câu tương tự


# ---------------------------------------------------------------------
# Giao diện trang chi tiết (nút Hủy, khối Thông tin hủy)
# ---------------------------------------------------------------------
class GiaoDienChiTiet(HuyBase):  # nhóm test: giao diện trang chi tiết
    def chi_tiet(self, user, bk):  # mô phỏng: một người mở trang chi tiết Booking
        self.client.force_login(user)  # đăng nhập người này
        return self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))  # mở trang chi tiết, trả về phản hồi

    def test_nut_huy_hien_dung_trang_thai(self):  # nút Hủy chỉ hiện ở đúng trạng thái
        for tt, co in ((BK.CHO_DAT_COC, True), (BK.CHOT_BOOKING, True), (BK.DA_CHUP, False),  # (trạng thái, có nút hay không): 2 trạng thái đầu có nút...
                       (BK.HOAN_THANH, False), (BK.DA_HUY, False)):  # ...các trạng thái còn lại không có
            bk = self.tao_booking(tt)  # tạo Booking ở trạng thái đang thử
            for user in (self.khach, self.nag.MaTaiKhoan):  # thử với cả Khách và Nhiếp ảnh gia
                res = self.chi_tiet(user, bk)  # mở trang chi tiết
                self.assertEqual(self.url_huy(bk) in res.content.decode(), co, (tt, user.username))  # link hủy có trong trang đúng khi mong đợi (nội dung kèm theo giúp biết ca nào sai)

    def test_quan_tri_khong_thay_nut_huy(self):  # Quản trị viên không thấy nút Hủy
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.client.force_login(tao_user('qt', VaiTro.QUAN_TRI_VIEN))  # đăng nhập Quản trị viên
        res = self.client.get(reverse('admin_booking_detail', kwargs={'ma_booking': bk.pk}))  # mở trang chi tiết dành cho Quản trị
        self.assertNotContains(res, self.url_huy(bk))  # trang không được chứa link hủy

    def test_khoi_thong_tin_huy_va_nut_hoan_tien(self):  # khối "Thông tin hủy" và nút xác nhận hoàn tiền
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.huy(self.nag.MaTaiKhoan, bk)  # Nhiếp ảnh gia hủy -> Hoàn cọc, Chờ hoàn tiền
        res = self.chi_tiet(self.khach, bk)  # Khách mở trang chi tiết
        self.assertContains(res, 'Thông tin hủy')  # có khối "Thông tin hủy"
        self.assertContains(res, LY_DO)  # hiện lý do hủy
        self.assertContains(res, XL.HOAN_COC)  # hiện cách xử lý tiền cọc "Hoàn cọc"
        self.assertContains(res, HT.CHO_HOAN_TIEN)  # hiện trạng thái "Chờ hoàn tiền"
        self.assertContains(res, self.url_hoan(bk))                           # Khách thấy nút xác nhận
        self.assertNotContains(self.chi_tiet(self.nag.MaTaiKhoan, bk), self.url_hoan(bk))   # Nhiếp ảnh gia không thấy
        self.client.force_login(self.khach)  # đăng nhập lại Khách
        self.client.post(self.url_hoan(bk))  # Khách bấm xác nhận đã nhận lại tiền
        res = self.chi_tiet(self.khach, bk)  # mở lại trang chi tiết
        self.assertContains(res, HT.DA_HOAN_TIEN)  # giờ hiện "Đã hoàn tiền"
        self.assertNotContains(res, self.url_hoan(bk))                        # xác nhận xong thì ẩn nút

    def test_booking_chua_huy_khong_co_khoi_thong_tin_huy(self):  # Booking chưa hủy thì không có khối thông tin hủy
        self.assertNotContains(self.chi_tiet(self.khach, self.tao_booking(BK.CHO_DAT_COC)), 'Thông tin hủy')  # trang không chứa chữ "Thông tin hủy"

    def test_trang_xu_ly_cua_nag_co_nut_huy_khi_chot_booking(self):  # trang xử lý của Nhiếp ảnh gia có nút Hủy khi đã chốt
        bk = self.tao_booking(BK.CHOT_BOOKING)  # tạo Booking đã chốt
        self.client.force_login(self.nag.MaTaiKhoan)  # đăng nhập Nhiếp ảnh gia
        res = self.client.get(reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk}))  # mở trang xử lý yêu cầu của Nhiếp ảnh gia
        self.assertContains(res, self.url_huy(bk))  # trang phải chứa link hủy


# ---------------------------------------------------------------------
# Hai thao tác chạm nhau: Nhiếp ảnh gia xác nhận cọc đúng lúc Khách hủy (phải đọc trạng thái SAU khi khóa dòng Booking)
# ---------------------------------------------------------------------
class HuyDuaTranhVoiXacNhanCoc(HuyBase):
    def test_khach_huy_dung_luc_nag_xac_nhan_coc_thi_ghi_mat_coc(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)                       # trong DB đang "Chờ đặt cọc"
        goc = hb.lay_booking_cua_ben

        def lay_roi_nag_xac_nhan_coc(user, vai_tro, ma_booking):    # Khách đọc được bản "Chờ đặt cọc" CŨ ...
            ban_cu = goc(user, vai_tro, ma_booking)
            chuyen_trang_thai_booking(ma_booking, BK.CHOT_BOOKING, BenThucHien.NHIEP_ANH_GIA)   # ... rồi NAG xác nhận cọc xong
            return ban_cu                                           # hàm vẫn trả bản cũ (TrangThai còn là "Chờ đặt cọc")

        with mock.patch.object(hb, 'lay_booking_cua_ben', side_effect=lay_roi_nag_xac_nhan_coc):
            with self.captureOnCommitCallbacks(execute=True):
                hb.huy_booking(self.khach, bk.pk, LY_DO)
        yc = YeuCauHuy.objects.get(MaBooking=bk)
        self.assertEqual(yc.TrangThaiBookingLucHuy, BK.CHOT_BOOKING)            # phải ghi trạng thái THẬT lúc hủy
        self.assertEqual(yc.XuLyTienCoc, XL.MAT_COC)                           # Khách hủy sau khi cọc -> mất cọc (không phải "Không phát sinh")
        self.assertIsNone(yc.TrangThaiHoanTien)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_HUY)
        self.assertIn('mất 40% tiền cọc', ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan, MaBooking=bk).NoiDung)

    def test_nag_huy_dung_luc_chot_thi_ghi_hoan_coc(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        goc = hb.lay_booking_cua_ben

        def lay_roi_chot(user, vai_tro, ma_booking):
            ban_cu = goc(user, vai_tro, ma_booking)
            chuyen_trang_thai_booking(ma_booking, BK.CHOT_BOOKING, BenThucHien.NHIEP_ANH_GIA)
            return ban_cu

        with mock.patch.object(hb, 'lay_booking_cua_ben', side_effect=lay_roi_chot):
            with self.captureOnCommitCallbacks(execute=True):
                hb.huy_booking(self.nag.MaTaiKhoan, bk.pk, LY_DO)
        yc = YeuCauHuy.objects.get(MaBooking=bk)
        self.assertEqual((yc.TrangThaiBookingLucHuy, yc.XuLyTienCoc, yc.TrangThaiHoanTien),
                         (BK.CHOT_BOOKING, XL.HOAN_COC, HT.CHO_HOAN_TIEN))


# ---------------------------------------------------------------------
# Hủy khi "Chờ đặt cọc" nhưng Khách đã tải minh chứng cọc (đang chờ Nhiếp ảnh gia xác nhận): vẫn cho hủy,
# XuLyTienCoc giữ "Không phát sinh", chỉ đổi câu hiển thị / thông báo
# ---------------------------------------------------------------------
class HuyKhiCoMinhChungDangCho(HuyBase):
    CAU_KHACH = 'Booking có minh chứng cọc đang chờ xác nhận. Nếu bạn đã chuyển khoản, hãy liên hệ Nhiếp ảnh gia để xử lý hoàn tiền.'

    def tao_minh_chung_dang_cho(self, bk, ly_do_bo_sung=None):
        return ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.TIEN_COC, SoTien=600000,
                                        TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_COC,
                                        NgayThanhToan=timezone.now(), LyDoTuChoi=ly_do_bo_sung)

    def test_trang_xac_nhan_cua_khach_hien_cau_minh_chung_dang_cho(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        self.tao_minh_chung_dang_cho(bk)
        self.client.force_login(self.khach)
        res = self.client.get(self.url_huy(bk))
        self.assertContains(res, self.CAU_KHACH)
        self.assertNotContains(res, 'Booking chưa đặt cọc nên')

    def test_trang_xac_nhan_cua_nag_hien_cau_danh_cho_nag(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        self.tao_minh_chung_dang_cho(bk)
        self.client.force_login(self.nag.MaTaiKhoan)
        res = self.client.get(self.url_huy(bk))
        self.assertContains(res, 'Booking có minh chứng cọc đang chờ xác nhận. Nếu Khách hàng đã chuyển khoản')

    def test_khong_chan_huy_va_xu_ly_tien_coc_van_la_khong_phat_sinh(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        self.tao_minh_chung_dang_cho(bk)
        self.huy(self.khach, bk)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_HUY)                              # không bị chặn
        yc = YeuCauHuy.objects.get(MaBooking=bk)
        self.assertEqual((yc.XuLyTienCoc, yc.TrangThaiHoanTien, yc.TrangThaiBookingLucHuy),
                         (XL.KHONG_PHAT_SINH, None, BK.CHO_DAT_COC))

    def test_thong_bao_ca_hai_ben_neu_ro_minh_chung_dang_cho(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        self.tao_minh_chung_dang_cho(bk)
        self.huy(self.khach, bk)
        nd_khach = ThongBao.objects.get(MaNguoiNhan=self.khach, MaBooking=bk).NoiDung
        nd_nag = ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan, MaBooking=bk).NoiDung
        self.assertIn(self.CAU_KHACH, nd_khach)
        self.assertIn('Booking có minh chứng cọc đang chờ xác nhận. Nếu Khách hàng đã chuyển khoản', nd_nag)   # Nhiếp ảnh gia cũng được báo rõ
        for nd in (nd_khach, nd_nag):
            self.assertNotIn('chưa đặt cọc nên không phát sinh', nd)

    def test_nag_da_yeu_cau_bo_sung_van_hien_canh_bao(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        self.tao_minh_chung_dang_cho(bk, ly_do_bo_sung='Ảnh mờ')                # Khách có thể đã chuyển khoản trước đó
        self.client.force_login(self.khach)
        self.assertContains(self.client.get(self.url_huy(bk)), self.CAU_KHACH)

    def test_khong_co_minh_chung_thi_giu_cau_cu(self):
        bk = self.tao_booking(BK.CHO_DAT_COC)
        self.client.force_login(self.khach)
        res = self.client.get(self.url_huy(bk))
        self.assertContains(res, 'Booking chưa đặt cọc nên việc hủy không phát sinh mất hoặc hoàn tiền cọc.')
        self.assertNotContains(res, 'minh chứng cọc đang chờ')

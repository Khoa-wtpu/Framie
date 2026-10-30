# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from datetime import datetime, timedelta
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from unittest import mock

# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from django.contrib.auth import get_user_model
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from django.contrib.auth.models import Group
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from django.core import mail
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from django.test import TestCase
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from django.urls import reverse
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from django.utils import timezone

# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from bookings import giu_cho as uc41
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from bookings import gui_booking as uc
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from bookings.models import Booking, GiuCho, LichSuTrangThaiBooking
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from core.constants import (
    # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
    BenThucHien, LoaiHauKy, TrangThaiBooking as BK, TrangThaiGiuCho as GC, TrangThaiGoi,
    # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
    TrangThaiGuiEmail, TrangThaiHoSo, TrangThaiSlot as SL, VaiTro,
# Đóng lời gọi hàm hoặc nhóm tham số đang được khai báo ở phía trên.
)
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from notifications.models import ThongBao
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
# Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
from schedule.models import LichKhaDung

# Lấy model User đang được cấu hình trong dự án Django.
User = get_user_model()


# Hàm tiện ích tạo tài khoản người dùng phục vụ dữ liệu kiểm thử.
def tao_user(ten, nhom=None, **kw):
    # Tạo tài khoản người dùng kiểm thử với tên đăng nhập, email, mật khẩu và số điện thoại.
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                 so_dien_thoai=f'09{abs(hash(ten)) % 10**8:08d}', **kw)
    # Kiểm tra điều kiện trước khi thực hiện khối lệnh bên dưới.
    if nhom:
        # Gán tài khoản vào nhóm vai trò tương ứng.
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    # Trả kết quả của hàm về nơi gọi.
    return u


# Hàm tiện ích tạo tài khoản và hồ sơ nhiếp ảnh gia đã được duyệt.
def tao_nag(ten):
    # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
    user = tao_user(ten, VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
    # Trả kết quả của hàm về nơi gọi.
    return NhiepAnhGia.objects.create(MaTaiKhoan=user, AnhDaiDien='a.jpg', GioiThieu='g', NganHang='b',
                                      # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                      SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')


# Khai báo lớp kiểm thử UC42, kế thừa TestCase của Django.
class UC42(TestCase):
    # Hàm setUp chạy trước mỗi test để tạo dữ liệu kiểm thử ban đầu.
    def setUp(self):
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.b = tao_user('khach_b', VaiTro.KHACH_HANG)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.nag = tao_nag('nag')
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.nag_khac = tao_nag('nag_khac')
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.chan_dung, TenGoi='Gói cơ bản',
                                            # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.goi_cuoi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.cuoi, TenGoi='Gói cưới',
                                                 # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                                 Gia=9000000, ThoiLuongChup=240, LoaiHauKy=LoaiHauKy.GIOI_HAN,
                                                 # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                                 SoAnhHauKyToiDa=50)
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.goi_ngung = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.chan_dung,
                                                  # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                                  TenGoi='Gói cũ', Gia=1000000, ThoiLuongChup=60,
                                                  # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                                  LoaiHauKy=LoaiHauKy.TOAN_BO, TrangThai=TrangThaiGoi.NGUNG_AP_DUNG)
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.goi_nguoi_khac = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag_khac, MaLoaiHinh=self.chan_dung,
                                                       # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                                       TenGoi='Gói người khác', Gia=2000000, ThoiLuongChup=60,
                                                       # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                                       LoaiHauKy=LoaiHauKy.TOAN_BO)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.ngay = timezone.localdate() + timedelta(days=2)
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay,
                                             # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                             GioBatDau='09:00', GioKetThuc='11:00')
        # Tạo dữ liệu mẫu trong cơ sở dữ liệu cho trường hợp kiểm thử.
        self.s2 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay,
                                             # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                             GioBatDau='13:00', GioKetThuc='15:00')

    # ---- tiện ích ----
    # Hàm hỗ trợ tạo lượt giữ chỗ bằng chức năng UC4.1.
    def giu(self, user, slot):
        # Gọi chức năng giữ chỗ của UC4.1 và trả về lượt giữ chỗ được tạo.
        return uc41.giu_cho_slot(user, slot.pk)

    # Hàm tạo URL trang gửi Booking theo mã lượt giữ chỗ.
    def url(self, giu_cho):
        # Dùng tên URL để tạo đường dẫn, đồng thời truyền mã lượt giữ chỗ.
        return reverse('gui_booking', kwargs={'ma_giu_cho': giu_cho.pk})

    # Hàm tạo bộ dữ liệu mẫu để gửi lên form Booking.
    def du_lieu(self, **ghi_de):
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        d = {'loai_hinh': self.chan_dung.pk, 'goi': self.goi.pk, 'ngay_gio_chup': f'{self.ngay:%Y-%m-%d}T09:30',
             # Khai báo giá trị chuỗi được sử dụng trong dữ liệu kiểm thử.
             'dia_diem': 'Hồ Gươm, Hà Nội', 'so_nguoi': 2, 'concept': 'Vintage', 'yeu_cau_rieng': 'Mang theo phụ kiện'}
        # Ghi đè các giá trị mặc định bằng dữ liệu bổ sung được truyền vào.
        d.update(ghi_de)
        # Trả về bộ dữ liệu form đã được chuẩn bị.
        return d

    # Hàm hỗ trợ đăng nhập và gửi request POST tạo Booking.
    def gui(self, user, giu_cho, **ghi_de):
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(user)
        # Bắt và thực thi các callback on_commit trong quá trình kiểm thử.
        with self.captureOnCommitCallbacks(execute=True):
            # Gửi yêu cầu POST đến URL Booking cùng dữ liệu form; follow=True tự theo các redirect.
            return self.client.post(self.url(giu_cho), self.du_lieu(**ghi_de), follow=True)

    # Hàm lấy trạng thái hiện tại của slot từ cơ sở dữ liệu.
    def slot(self, slot):
        # Trả kết quả của hàm về nơi gọi.
        return LichKhaDung.objects.get(pk=slot.pk).TrangThai

    # Hàm giả lập lượt giữ chỗ đã quá thời hạn.
    def lam_het_han(self, giu_cho):
        # Lấy thời điểm hiện tại làm mốc để tính thời gian giữ chỗ đã hết hạn.
        bay_gio = timezone.now()    # lùi cả giờ giữ lẫn giờ hết hạn (ràng buộc: hết hạn phải sau giờ giữ)
        # Cập nhật trực tiếp thời điểm giữ và thời điểm hết hạn trong cơ sở dữ liệu.
        GiuCho.objects.filter(pk=giu_cho.pk).update(ThoiDiemGiu=bay_gio - timedelta(minutes=6),
                                                    # Thiết lập hoặc tính toán mốc thời gian phục vụ tình huống kiểm thử.
                                                    ThoiDiemHetHan=bay_gio - timedelta(minutes=1))

    # ---- Basic flow ----
    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_luong_chinh(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(r.status_code, 200)

        # Lấy Booking vừa được tạo từ cơ sở dữ liệu.
        b = Booking.objects.get()
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual((b.MaKhachHang, b.MaNhiepAnhGia, b.MaGoi, b.MaLich), (self.a, self.nag, self.goi, self.s1))
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(b.TrangThai, BK.CHO_XAC_NHAN)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(b.TongGiaTri, self.goi.Gia)                               # tổng giá trị = giá gói
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual((b.DiaDiem, b.SoNguoi, b.Concept), ('Hồ Gươm, Hà Nội', 2, 'Vintage'))
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(b.YeuCauRieng, 'Mang theo phụ kiện')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(timezone.localtime(b.NgayGioChup).strftime('%H:%M'), '09:30')

        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.DA_HOAN_TAT)           # lượt giữ chỗ hoàn tất
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.slot(self.s1), SL.DANG_GIU)                          # slot vẫn giữ cho tới khi NAG xử lý
        # Kiểm tra nội dung phản hồi HTTP có chứa chuỗi mong đợi.
        self.assertContains(r, 'Yêu cầu Booking đã được gửi')                      # bước 8

        # Lấy bản ghi lịch sử thay đổi trạng thái Booking.
        ls = LichSuTrangThaiBooking.objects.get()                                  # dòng lịch sử đầu tiên
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual((ls.MaBooking, ls.TrangThaiCu, ls.TrangThaiMoi, ls.BenThucHien),
                         # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                         (b, None, BK.CHO_XAC_NHAN, BenThucHien.KHACH_HANG))

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_thong_bao_web_va_email(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.a, g)
        # Lấy Booking vừa được tạo từ cơ sở dữ liệu.
        b = Booking.objects.get()
        # Lấy thông báo tương ứng từ cơ sở dữ liệu để kiểm tra nội dung.
        tb_nag = ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual((tb_nag.TieuDe, tb_nag.MaBooking), ('Yêu cầu Booking mới', b))
        # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
        self.assertIn('Gói cơ bản', tb_nag.NoiDung)
        # Lấy thông báo tương ứng từ cơ sở dữ liệu để kiểm tra nội dung.
        tb_khach = ThongBao.objects.get(MaNguoiNhan=self.a)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(tb_khach.TieuDe, 'Yêu cầu Booking đã được gửi')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(len(mail.outbox), 1)                                      # Email cho Nhiếp ảnh gia
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(mail.outbox[0].to, [self.nag.MaTaiKhoan.email])
        # Lấy thông báo tương ứng từ cơ sở dữ liệu để kiểm tra nội dung.
        tb_nag.refresh_from_db()
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(tb_nag.TrangThaiGuiEmail, TrangThaiGuiEmail.THANH_CONG)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_gui_email_loi_thi_booking_van_tao(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thay thế tạm thời hàm gửi email hoặc xử lý hết hạn để mô phỏng tình huống kiểm thử.
        with mock.patch.object(uc, 'send_mail', side_effect=OSError('smtp down')):
            # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
            self.gui(self.a, g)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 1)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(ThongBao.objects.get(MaNguoiNhan=self.nag.MaTaiKhoan).TrangThaiGuiEmail,
                         # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                         TrangThaiGuiEmail.THAT_BAI)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_yeu_cau_rieng_de_trong_thi_luu_null(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.gui(self.a, g, yeu_cau_rieng='   ')
        # Xác nhận giá trị nhận được là None (tương ứng NULL trong cơ sở dữ liệu).
        self.assertIsNone(Booking.objects.get().YeuCauRieng)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_trang_hien_dung_form(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.a)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.client.get(self.url(g))
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(r.status_code, 200)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertContains(r, 'id="dem-nguoc"')
        # Lấy danh sách mã các gói dịch vụ được phép hiển thị trong form.
        ds_goi = [o.pk for o in r.context['form'].fields['goi'].queryset]
        # So sánh hai tập hợp phần tử, không phụ thuộc thứ tự.
        self.assertCountEqual(ds_goi, [self.goi.pk, self.goi_cuoi.pk])              # chỉ gói Đang áp dụng của NAG này
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual([o.pk for o in r.context['form'].fields['loai_hinh'].queryset],
                         # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                         [self.chan_dung.pk, self.cuoi.pk])                        # xếp theo tên: Chân dung, Cưới

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_man_hinh_giu_cho_co_nut_tiep_tuc(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.a)
        # Dùng tên URL để tạo đường dẫn, đồng thời truyền mã lượt giữ chỗ.
        r = self.client.get(reverse('man_hinh_giu_cho', args=[g.pk]))
        # Kiểm tra nội dung phản hồi HTTP có chứa chuỗi mong đợi.
        self.assertContains(r, self.url(g))                                        # link 'gui_booking' của UC4.1 hoạt động

    # ---- 1a: thông tin không hợp lệ ----
    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_thieu_truong_bat_buoc(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.a)
        # Gửi yêu cầu POST đến URL Booking cùng dữ liệu form; follow=True tự theo các redirect.
        r = self.client.post(self.url(g), {})
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(r.status_code, 200)
        # Lấy danh sách lỗi validation của form từ response.
        loi = r.context['form'].errors
        # Lặp qua từng phần tử trong danh sách để kiểm tra nhiều trường hợp.
        for ten in ('loai_hinh', 'goi', 'ngay_gio_chup', 'dia_diem', 'so_nguoi', 'concept'):
            # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
            self.assertIn(ten, loi)
        # Kiểm tra một giá trị không xuất hiện trong tập dữ liệu hoặc thông báo lỗi.
        self.assertNotIn('yeu_cau_rieng', loi)                                     # không bắt buộc
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.DANG_GIU)              # vẫn giữ chỗ, được sửa tiếp

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_sua_loi_roi_gui_lai_thanh_cong(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g, dia_diem='   ')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)
        # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
        self.assertIn('dia_diem', r.context['form'].errors)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 1)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_gio_chup_ngoai_khung_gio_cua_slot(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Lặp qua từng phần tử trong danh sách để kiểm tra nhiều trường hợp.
        for gio in ('08:59', '11:00', '12:00'):
            # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
            r = self.gui(self.a, g, ngay_gio_chup=f'{self.ngay:%Y-%m-%d}T{gio}')
            # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
            self.assertIn('ngay_gio_chup', r.context['form'].errors, gio)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g, ngay_gio_chup=f'{self.ngay + timedelta(days=1):%Y-%m-%d}T09:30')   # sai ngày
        # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
        self.assertIn('ngay_gio_chup', r.context['form'].errors)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g, ngay_gio_chup=f'{self.ngay:%Y-%m-%d}T09:00')                         # đúng giờ bắt đầu slot
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 1)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_goi_ngung_ap_dung_hoac_cua_nguoi_khac_bi_chan(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Lặp qua từng phần tử trong danh sách để kiểm tra nhiều trường hợp.
        for goi in (self.goi_ngung, self.goi_nguoi_khac):
            # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
            r = self.gui(self.a, g, goi=goi.pk)
            # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
            self.assertIn('goi', r.context['form'].errors, goi.TenGoi)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_goi_khong_khop_loai_hinh(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g, loai_hinh=self.cuoi.pk)            # gói cơ bản là Chân dung
        # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
        self.assertIn('goi', r.context['form'].errors)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_so_nguoi_khong_hop_le(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Lặp qua từng phần tử trong danh sách để kiểm tra nhiều trường hợp.
        for v in ('0', '-1', 'abc'):
            # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
            r = self.gui(self.a, g, so_nguoi=v)
            # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
            self.assertIn('so_nguoi', r.context['form'].errors, v)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_service_loi_clean_cua_booking_ve_dung_o_nhap_va_khong_dong_giu_cho(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Xác nhận đoạn xử lý bên trong phải phát sinh ngoại lệ được chỉ định.
        with self.assertRaises(uc.GuiBookingLoi) as ctx:           # bỏ qua form: đưa thẳng gói đã ngừng vào service
            # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
            uc.gui_yeu_cau_booking(self.a, g.pk, self.goi_ngung.pk,
                                   # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                   timezone.make_aware(datetime.combine(self.ngay, datetime.strptime('09:30', '%H:%M').time())),
                                   # Khai báo giá trị chuỗi được sử dụng trong dữ liệu kiểm thử.
                                   'x', 1, 'y')
        # Kiểm tra một giá trị có nằm trong tập dữ liệu hoặc thông báo lỗi hay không.
        self.assertIn('MaGoi', ctx.exception.loi_truong)
        # Xác nhận kết quả là False.
        self.assertFalse(ctx.exception.het_han)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.DANG_GIU)   # rollback: lượt giữ chỗ không bị đóng

    # ---- 4a / BR4.2-1 / BR4.2-2: hết thời gian giữ chỗ ----
    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_het_5_phut_khi_gui(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.lam_het_han(g)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g)
        # Kiểm tra nội dung phản hồi HTTP có chứa chuỗi mong đợi.
        self.assertContains(r, 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại')
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(r.redirect_chain[-1][0], reverse('lich_chon_slot', args=[self.nag.pk]))
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.slot(self.s1), SL.TRONG)                             # slot được giải phóng (BR4.2-1)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(ThongBao.objects.count(), 0)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(len(mail.outbox), 0)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_het_5_phut_khi_mo_trang(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.lam_het_han(g)
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.a)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.client.get(self.url(g), follow=True)
        # Kiểm tra nội dung phản hồi HTTP có chứa chuỗi mong đợi.
        self.assertContains(r, 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.slot(self.s1), SL.TRONG)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_het_han_dung_luc_service_chay_van_nha_slot(self):
        # Hết hạn đúng khoảng giữa lúc mở view và lúc service chạy (bỏ qua bước quét sớm): slot phải được nhả thật.
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.lam_het_han(g)
        # Thay thế tạm thời hàm gửi email hoặc xử lý hết hạn để mô phỏng tình huống kiểm thử.
        with mock.patch.object(uc, 'giai_phong_giu_cho_het_han'):
            # Xác nhận đoạn xử lý bên trong phải phát sinh ngoại lệ được chỉ định.
            with self.assertRaises(uc.GuiBookingLoi) as ctx:
                # Thiết lập hoặc tính toán mốc thời gian phục vụ tình huống kiểm thử.
                uc.gui_yeu_cau_booking(self.a, g.pk, self.goi.pk, timezone.now() + timedelta(days=2),
                                       # Khai báo giá trị chuỗi được sử dụng trong dữ liệu kiểm thử.
                                       'x', 1, 'y')
        # Xác nhận điều kiện kiểm thử là True.
        self.assertTrue(ctx.exception.het_han)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(str(ctx.exception), 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.slot(self.s1), SL.TRONG)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_chon_lai_sau_khi_het_han_lam_lai_duoc_uc41(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.lam_het_han(g)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.a, g)
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g2 = self.giu(self.b, self.s1)                              # slot đã trống, người khác chọn được
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(g2.TrangThai, GC.DANG_GIU)

    # ---- BR4.2-3 / gửi trùng ----
    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_gui_hai_lan_chi_tao_mot_booking(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.a, g)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.a, g)
        # Kiểm tra nội dung phản hồi HTTP có chứa chuỗi mong đợi.
        self.assertContains(r, 'Lượt giữ chỗ này đã được dùng để gửi yêu cầu Booking.')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 1)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.nag.MaTaiKhoan).count(), 1)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_slot_da_gan_booking_con_hieu_luc_khong_tao_them(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.a, g)
        # Giả lập dữ liệu lệch: một lượt giữ mới trên slot đã có Booking còn hiệu lực.
        # Lấy thời điểm hiện tại để thiết lập dữ liệu thời gian giả lập.
        now = timezone.now()
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g2 = GiuCho.objects.create(MaKhachHang=self.b, MaLich=self.s1, ThoiDiemGiu=now,
                                   # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                                   ThoiDiemHetHan=now + uc41.THOI_GIAN_GIU_CHO)
        # Gửi yêu cầu hoặc lưu phản hồi HTTP để kiểm tra kết quả.
        r = self.gui(self.b, g2)
        # Kiểm tra nội dung phản hồi HTTP có chứa chuỗi mong đợi.
        self.assertContains(r, 'đã gắn với một Booking đang có hiệu lực')
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 1)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(GiuCho.objects.get(pk=g2.pk).TrangThai, GC.DANG_GIU)       # không đóng lượt giữ khi lỗi

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_slot_cua_booking_da_tu_choi_dat_lai_duoc(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.a, g)
        # Nạp thư viện hoặc thành phần cần dùng trong kiểm thử.
        from bookings.services import chuyen_trang_thai_booking
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        chuyen_trang_thai_booking(Booking.objects.get(), BK.DA_TU_CHOI, BenThucHien.NHIEP_ANH_GIA, ly_do='Bận')
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g2 = self.giu(self.b, self.s1)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.b, g2)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 2)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(Booking.objects.filter(MaLich=self.s1).exclude(TrangThai=BK.DA_TU_CHOI).count(), 1)

    # ---- Quyền ----
    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_chi_xem_va_gui_duoc_luot_giu_cua_chinh_minh(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.b)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.client.get(self.url(g)).status_code, 404)
        # Gửi yêu cầu POST đến URL Booking cùng dữ liệu form; follow=True tự theo các redirect.
        self.assertEqual(self.client.post(self.url(g), self.du_lieu()).status_code, 404)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 0)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_chua_dang_nhap_va_sai_vai_tro(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.client.get(self.url(g)).status_code, 302)             # sang trang đăng nhập
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.nag.MaTaiKhoan)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.client.get(self.url(g)).status_code, 403)

    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_chi_nhan_get_va_post(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        g = self.giu(self.a, self.s1)
        # Đăng nhập trực tiếp tài khoản kiểm thử vào Django test client.
        self.client.force_login(self.a)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(self.client.delete(self.url(g)).status_code, 405)

    # ---- Ghi nhận booking đầu tiên của hai khách ở hai slot ----
    # Khai báo một trường hợp kiểm thử cho UC4.2.
    def test_hai_khach_hai_slot_doc_lap(self):
        # Tạo một hoặc nhiều lượt giữ chỗ để sử dụng trong kịch bản kiểm thử.
        ga, gb = self.giu(self.a, self.s1), self.giu(self.b, self.s2)
        # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
        self.gui(self.a, ga)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.gui(self.b, gb, ngay_gio_chup=f'{self.ngay:%Y-%m-%d}T13:30', goi=self.goi_cuoi.pk,
                 # Thực hiện bước xử lý hoặc thiết lập dữ liệu cho trường hợp kiểm thử.
                 loai_hinh=self.cuoi.pk)
        # Lưu dữ liệu hoặc kết quả vào thuộc tính của đối tượng kiểm thử.
        self.assertEqual(Booking.objects.get(MaKhachHang=self.b).TongGiaTri, self.goi_cuoi.Gia)
        # So sánh giá trị thực tế với giá trị mong đợi để xác nhận kết quả kiểm thử.
        self.assertEqual(Booking.objects.count(), 2)


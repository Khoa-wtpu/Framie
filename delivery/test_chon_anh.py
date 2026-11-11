# Chạy: python manage.py test delivery.test_chon_anh      (N6: UC5.4 Khách hàng lựa chọn ảnh cần hậu kỳ + NAG bắt đầu hậu kỳ)
import re                                                      # dùng regex để đếm đúng các ô input đã tick
import tempfile                                                # tạo thư mục tạm để test không đụng private_media thật
from datetime import timedelta                                 # khoảng thời gian (2 ngày, 3 ngày...)
from unittest import mock                                      # giả lập đồng hồ để thử trường hợp quá hạn

from django.contrib.auth import get_user_model                 # model User của dự án
from django.test import override_settings                       # đổi cấu hình riêng cho test
from django.urls import reverse                                # đổi tên URL thành đường dẫn
from django.utils import timezone                              # giờ hiện tại có múi giờ

from bookings.models import Booking, LichSuTrangThaiBooking   # Booking và lịch sử đổi trạng thái
from core.constants import BenThucHien, LoaiAnh, TrangThaiBooking as TT   # hằng số dùng chung
from delivery import services                                  # hàm nghiệp vụ cần kiểm tra
from delivery.models import Anh                                # bảng ảnh
from delivery.tests import _NenAnh, tep_anh                             # lớp nền có sẵn của N4/N5 (tạo Khách, Nhiếp ảnh gia, gói, hàm tao_booking, tao_anh)
from notifications.models import ThongBao                      # bảng thông báo

User = get_user_model()                                        # lấy model User


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(), ROOT_URLCONF='delivery.tests')   # thư mục tạm riêng + bảng URL riêng của test
class _NenChonAnh(_NenAnh):                                    # lớp nền riêng của N6 (không có test riêng)
    def tao_booking_cho_chon(self, so_anh=7, goi=None):        # Booking ở "Chờ Khách hàng lựa chọn ảnh" có sẵn so_anh ảnh chưa hậu kỳ
        bk = self.tao_booking(goi or self.goi_gh, TT.CHO_KH_CHON_ANH)   # tạo Booking đúng trạng thái
        self.ds_anh = [self.tao_anh(bk, f'a{i}.jpg') for i in range(1, so_anh + 1)]   # tạo ảnh a1.jpg, a2.jpg...
        return bk                                              # trả Booking

    def ma(self, *chi_so):                                     # đổi số thứ tự ảnh (1, 2...) thành mã ảnh thật
        return [self.ds_anh[i - 1].pk for i in chi_so]         # a1 là phần tử đầu tiên

    def so_duoc_chon(self, bk):                                # đếm ảnh đang được đánh dấu "được chọn hậu kỳ"
        return Anh.objects.filter(MaBooking=bk, DuocChonHauKy=1).count()  # trả kết quả


class ChonAnhServiceTests(_NenChonAnh):                        # nghiệp vụ của UC5.4
    def test_luu_lua_chon_danh_dau_dung_anh(self):             # bước 3-4: ghi nhận ảnh được chọn
        bk = self.tao_booking_cho_chon()                       # gói tối đa 5 ảnh, có 7 ảnh
        so = services.luu_lua_chon(bk.pk, self.kh, self.ma(1, 3))   # chọn a1 và a3
        self.assertEqual(so, 2)                                # số ảnh đã chọn
        self.assertEqual(set(Anh.objects.filter(MaBooking=bk, DuocChonHauKy=1).values_list('TenAnh', flat=True)), {'a1.jpg', 'a3.jpg'})  # kiểm tra hai giá trị bằng nhau
        bk.refresh_from_db()                                   # Booking chưa đổi trạng thái (mới chỉ lưu)
        self.assertEqual(bk.TrangThai, TT.CHO_KH_CHON_ANH)  # kiểm tra hai giá trị bằng nhau

    def test_luu_lai_thay_the_lua_chon_cu(self):               # lưu lần 2 thì thay hẳn lần 1
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        services.luu_lua_chon(bk.pk, self.kh, self.ma(1, 2))   # lần 1: a1, a2
        services.luu_lua_chon(bk.pk, self.kh, self.ma(2, 4))   # lần 2: a2, a4
        self.assertEqual(set(Anh.objects.filter(MaBooking=bk, DuocChonHauKy=1).values_list('TenAnh', flat=True)), {'a2.jpg', 'a4.jpg'})  # kiểm tra hai giá trị bằng nhau

    def test_chon_vuot_gioi_han_bi_chan_va_khong_doi_gi(self):  # ngoại lệ 4b
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        services.luu_lua_chon(bk.pk, self.kh, self.ma(1))      # đã lưu a1 trước
        with self.assertRaises(services.LoiChonAnh) as ctx:    # chọn 6 ảnh > 5
            services.luu_lua_chon(bk.pk, self.kh, self.ma(1, 2, 3, 4, 5, 6))  # gọi hàm lưu lựa chọn ảnh
        self.assertIn('vượt quá', str(ctx.exception))          # câu báo có chữ "vượt quá"
        self.assertEqual(self.so_duoc_chon(bk), 1)             # lựa chọn cũ giữ nguyên

    def test_ma_anh_la_hoac_cua_booking_khac_bi_chan(self):    # không tin mã ảnh gửi lên
        bk = self.tao_booking_cho_chon(so_anh=2)  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        ds_cua_bk = self.ds_anh                                # ảnh của Booking 1
        bk2 = self.tao_booking_cho_chon(so_anh=2)              # Booking 2 (ảnh a1.jpg, a2.jpg khác mã)
        with self.assertRaises(services.LoiChonAnh):  # mong đợi hàm này báo lỗi
            services.luu_lua_chon(bk2.pk, self.kh, [ds_cua_bk[0].pk])   # lấy mã ảnh của Booking 1 chọn cho Booking 2
        with self.assertRaises(services.LoiChonAnh):  # mong đợi hàm này báo lỗi
            services.luu_lua_chon(bk.pk, self.kh, [999999])    # mã không tồn tại
        self.assertEqual(self.so_duoc_chon(bk), 0)  # kiểm tra hai giá trị bằng nhau

    def test_khach_khac_khong_chon_duoc(self):                 # Booking phải là của chính Khách
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        khach_khac = User.objects.create_user('kh2', 'kh2@x.vn', 'p', so_dien_thoai='0900000077')  # tạo thêm một tài khoản để thử người khác
        with self.assertRaises(services.LoiChonAnh):  # mong đợi hàm này báo lỗi
            services.luu_lua_chon(bk.pk, khach_khac, self.ma(1))  # gọi hàm lưu lựa chọn ảnh

    def test_sai_trang_thai_bi_chan(self):                     # Booking chưa đến / đã qua bước chọn
        bk = self.tao_booking(self.goi_gh, TT.CHO_HAU_KY)      # đã gửi danh sách rồi
        self.assertIn('đã được gửi', services.ly_do_khong_chon_duoc(bk))  # kiểm tra câu báo có chứa đoạn chữ mong đợi
        with self.assertRaises(services.LoiChonAnh):  # mong đợi hàm này báo lỗi
            services.luu_lua_chon(bk.pk, self.kh, [])  # gọi hàm lưu lựa chọn ảnh
        bk2 = self.tao_booking(self.goi_gh, TT.DA_CHUP)        # chưa đến bước chọn
        self.assertIn('chưa đến lúc', services.ly_do_khong_chon_duoc(bk2))  # kiểm tra câu báo có chứa đoạn chữ mong đợi

    def test_khong_gioi_han_thoi_gian_chon_anh(self):          # Khách chọn ảnh hậu kỳ không còn hạn 2 ngày
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.assertIsNone(bk.HanChonAnh)                       # hệ thống không còn gán hạn chọn ảnh
        sau_lau = timezone.now() + timedelta(days=30)          # giả lập đã qua 30 ngày
        with mock.patch('delivery.services.timezone.now', return_value=sau_lau):  # giả lập giờ hiện tại rất xa sau đó
            self.assertIsNone(services.ly_do_khong_chon_duoc(bk))  # vẫn được chọn ảnh bình thường
            self.assertEqual(services.luu_lua_chon(bk.pk, self.kh, self.ma(1)), 1)  # lưu lựa chọn thành công
            services.gui_danh_sach_hau_ky(bk.pk, self.kh)      # Khách xác nhận gửi cho Nhiếp ảnh gia thành công
        bk.refresh_from_db()                                   # đọc lại trạng thái mới nhất
        self.assertEqual(bk.TrangThai, TT.CHO_HAU_KY)          # hệ thống tự chuyển sang giai đoạn tiếp theo

    def test_goi_hau_ky_toan_bo_khong_co_buoc_chon(self):      # chỉ gói giới hạn mới có bước chọn
        bk = self.tao_booking(self.goi_tb, TT.CHO_HAU_KY)  # tạo Booking ở trạng thái cần thử
        self.assertIn('hậu kỳ toàn bộ', services.ly_do_khong_chon_duoc(bk))  # kiểm tra câu báo có chứa đoạn chữ mong đợi

    def test_gui_danh_sach_chuyen_cho_hau_ky_va_bao_nhiep_anh_gia(self):   # bước 5-6
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        services.luu_lua_chon(bk.pk, self.kh, self.ma(1, 2))  # gọi hàm lưu lựa chọn ảnh
        kq = services.gui_danh_sach_hau_ky(bk.pk, self.kh)  # gọi hàm gửi danh sách ảnh cho Nhiếp ảnh gia
        self.assertEqual(kq['so_anh'], 2)  # kiểm tra hai giá trị bằng nhau
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_HAU_KY)          # Booking thành Chờ hậu kỳ
        self.assertTrue(LichSuTrangThaiBooking.objects.filter(  # hàm của Tuyền tự ghi lịch sử, bên thực hiện là Khách hàng
            MaBooking=bk, TrangThaiCu=TT.CHO_KH_CHON_ANH, TrangThaiMoi=TT.CHO_HAU_KY, BenThucHien=BenThucHien.KHACH_HANG).exists())  # điều kiện lọc lịch sử: Khách hàng là bên thực hiện
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).exists())   # Nhiếp ảnh gia được báo
        self.assertEqual(self.so_duoc_chon(bk), 2)             # danh sách ảnh lưu trong Booking

    def test_gui_khi_chua_chon_anh_nao_bi_chan(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        with self.assertRaises(services.LoiChonAnh):  # mong đợi hàm này báo lỗi
            services.gui_danh_sach_hau_ky(bk.pk, self.kh)  # gọi hàm gửi danh sách ảnh cho Nhiếp ảnh gia
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_CHON_ANH)     # không đổi trạng thái
        self.assertFalse(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).exists())  # kiểm tra điều kiện sai

    def test_gui_hai_lan_lan_hai_bi_chan(self):                # bấm gửi lần 2 (F5, hai tab) không gây đổi trạng thái lần nữa
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        services.luu_lua_chon(bk.pk, self.kh, self.ma(1))  # gọi hàm lưu lựa chọn ảnh
        services.gui_danh_sach_hau_ky(bk.pk, self.kh)  # gọi hàm gửi danh sách ảnh cho Nhiếp ảnh gia
        with self.assertRaises(services.LoiChonAnh):  # mong đợi hàm này báo lỗi
            services.gui_danh_sach_hau_ky(bk.pk, self.kh)  # gọi hàm gửi danh sách ảnh cho Nhiếp ảnh gia
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).count(), 1)  # kiểm tra hai giá trị bằng nhau

    def test_luong_day_du_chon_bat_dau_hau_ky_va_chi_hau_ky_anh_da_chon(self):   # nối N6 với N4
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        services.luu_lua_chon(bk.pk, self.kh, self.ma(2, 5))  # gọi hàm lưu lựa chọn ảnh
        services.gui_danh_sach_hau_ky(bk.pk, self.kh)  # gọi hàm gửi danh sách ảnh cho Nhiếp ảnh gia
        services.bat_dau_hau_ky(bk.pk, self.nag_user)          # NAG bấm bắt đầu
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)  # kiểm tra hai giá trị bằng nhau
        self.assertAlmostEqual((bk.HanHauKy - timezone.now()).total_seconds(), 3 * 86400, delta=120)   # hạn 3 ngày
        self.assertEqual({a.TenAnh for a in services.anh_can_hau_ky(bk)}, {'a2.jpg', 'a5.jpg'})   # N4 chỉ đòi hậu kỳ đúng ảnh Khách chọn

    def test_bat_dau_hau_ky_nag_khac_hoac_sai_trang_thai_bi_chan(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking(self.goi_gh, TT.CHO_HAU_KY)  # tạo Booking ở trạng thái cần thử
        with self.assertRaises(services.LoiBatDauHauKy):  # mong đợi hàm này báo lỗi
            services.bat_dau_hau_ky(bk.pk, self.nag_khac)      # không phải Booking của NAG này
        bk2 = self.tao_booking(self.goi_gh, TT.CHO_KH_CHON_ANH)  # tạo Booking ở trạng thái cần thử
        with self.assertRaises(services.LoiBatDauHauKy):  # mong đợi hàm này báo lỗi
            services.bat_dau_hau_ky(bk2.pk, self.nag_user)     # Khách chưa chọn xong thì chưa hậu kỳ được
        bk2.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk2.TrangThai, TT.CHO_KH_CHON_ANH)  # kiểm tra hai giá trị bằng nhau

    def test_goi_toan_bo_bat_dau_hau_ky_duoc(self):            # gói toàn bộ: bắt đầu hậu kỳ rồi tải trực tiếp ảnh đã hậu kỳ
        bk = self.tao_booking(self.goi_tb, TT.CHO_HAU_KY)       # T8 đưa gói toàn bộ vào Chờ hậu kỳ, chưa có ảnh gốc
        services.bat_dau_hau_ky(bk.pk, self.nag_user)          # NAG bấm "Bắt đầu hậu kỳ"
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)

        ket_qua = services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('anh-hoan-thien.jpg')])
        bk.refresh_from_db()
        anh = Anh.objects.get(MaBooking=bk)
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)
        self.assertEqual(ket_qua['trang_thai_moi'], TT.CHO_KH_KIEM_TRA)
        self.assertEqual((anh.LoaiAnh, anh.PhienBanAnh, anh.CoWatermark),
                         (LoaiAnh.DA_HAU_KY, 1, 1))


class ChonAnhViewTests(_NenChonAnh):                           # trang web của UC5.4
    def url(self, bk):                                         # đường dẫn trang chọn ảnh
        return reverse('chon_anh_hau_ky', args=[bk.pk])  # trả kết quả

    def test_get_khach_200_va_nguoi_khac_bi_chan(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.get(self.url(bk))  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(phan_hoi, 'name="anh"')            # có ô tick ảnh
        self.assertContains(phan_hoi, 'tối đa <strong>5</strong> ảnh')   # hiện số ảnh tối đa của gói
        khach_khac = User.objects.create_user('kh3', 'kh3@x.vn', 'p', so_dien_thoai='0900000078')  # tạo thêm một tài khoản để thử người khác
        self.client.force_login(khach_khac)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)   # Booking của người khác
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)   # Nhiếp ảnh gia không phải Khách hàng
        self.client.logout()  # đăng xuất
        self.assertEqual(self.client.get(self.url(bk)).status_code, 302)   # chưa đăng nhập -> trang đăng nhập

    def test_post_luu_chuyen_trang_va_luu_dung(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'luu', 'anh': self.ma(1, 2)})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 302)  # kiểm tra hai giá trị bằng nhau
        self.assertEqual(self.so_duoc_chon(bk), 2)  # kiểm tra hai giá trị bằng nhau
        trang = self.client.get(self.url(bk))                  # mở lại: 2 ô đã tick sẵn
        self.assertEqual(len(re.findall(r'<input[^>]*\bchecked\b', trang.content.decode())), 2)  # chỉ đếm ô input đã tick, bỏ qua aria-checked
        self.assertContains(trang, 'Đã chọn: <strong id="so-da-chon">2</strong>')  # kiểm tra trang có hiện đoạn chữ mong đợi

    def test_gui_chua_du_so_luong_hien_hop_hoi_4a_roi_gui_xac_nhan(self):   # luồng 4a
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'gui', 'anh': self.ma(1, 2)})   # 2 < 5
        self.assertEqual(phan_hoi.status_code, 200)            # chưa chuyển trang: đang hỏi
        self.assertContains(phan_hoi, 'Bạn có thể chọn thêm ảnh vì chưa đạt số lượng tối đa')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(phan_hoi, 'Có, bổ sung thêm ảnh')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(phan_hoi, 'Không, gửi danh sách ảnh đã chọn cho Nhiếp ảnh gia')  # kiểm tra trang có hiện đoạn chữ mong đợi
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_CHON_ANH)     # chưa gửi
        self.assertEqual(self.so_duoc_chon(bk), 2)             # nhưng lựa chọn đã được lưu
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'gui_xac_nhan'})   # 4a-2
        self.assertEqual(phan_hoi.status_code, 302)  # kiểm tra hai giá trị bằng nhau
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_HAU_KY)  # kiểm tra hai giá trị bằng nhau

    def test_gui_dung_so_luong_toi_da_gui_luon(self):          # đủ 5/5 thì không hỏi nữa
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'gui', 'anh': self.ma(1, 2, 3, 4, 5)})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 302)  # kiểm tra hai giá trị bằng nhau
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_HAU_KY)  # kiểm tra hai giá trị bằng nhau

    def test_gui_vuot_gioi_han_hien_loi_4b_va_giu_o_tick(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'gui', 'anh': self.ma(1, 2, 3, 4, 5, 6)})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(phan_hoi, 'vượt quá giới hạn 5 ảnh')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertEqual(len(re.findall(r'<input[^>]*\bchecked\b', phan_hoi.content.decode())), 6)   # vẫn giữ 6 ô Khách vừa tick để bỏ bớt
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_CHON_ANH)  # kiểm tra hai giá trị bằng nhau

    def test_gui_khong_chon_anh_nao_hien_loi(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'gui'})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(phan_hoi, 'Vui lòng chọn ít nhất một ảnh')  # kiểm tra trang có hiện đoạn chữ mong đợi

    def test_sau_khi_gui_trang_chi_cho_xem_anh_da_chon(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        self.client.post(self.url(bk), {'hanh_dong': 'gui', 'anh': self.ma(1, 2, 3, 4, 5)})  # gửi yêu cầu tới trang
        trang = self.client.get(self.url(bk))  # gửi yêu cầu tới trang
        self.assertContains(trang, 'đã được gửi cho Nhiếp ảnh gia')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertNotContains(trang, 'name="anh"')            # không còn ô tick
        self.assertContains(trang, 'Ảnh bạn đã chọn (5)')  # kiểm tra trang có hiện đoạn chữ mong đợi

    def test_nut_phong_to_dang_bieu_tuong_thay_chu_xem_lon(self):   # nút zoom dạng biểu tượng, không còn chữ "Xem lớn"
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        trang = self.client.get(self.url(bk))  # mở trang chọn ảnh
        self.assertContains(trang, 'xal-nut-zoom--tren-anh')   # có nút biểu tượng phóng to đè trên ảnh
        self.assertContains(trang, 'aria-label="Phóng to ảnh')   # nút có nhãn cho người dùng đọc màn hình
        self.assertNotContains(trang, 'Xem lớn')               # không còn chữ "Xem lớn"

    def test_hanh_dong_la_hien_thong_bao_loi(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'xoa_het'})  # gửi yêu cầu tới trang
        self.assertContains(phan_hoi, 'Thao tác không hợp lệ')  # kiểm tra trang có hiện đoạn chữ mong đợi


class BatDauHauKyViewTests(_NenChonAnh):                       # nút "Bắt đầu hậu kỳ" của Nhiếp ảnh gia
    def test_goi_toan_bo_hien_huong_dan_tai_anh_da_hau_ky(self):
        bk = self.tao_booking(self.goi_tb, TT.CHO_HAU_KY)
        self.client.force_login(self.nag_user)
        trang = self.client.get(reverse('tai_anh_len', args=[bk.pk]))
        self.assertEqual(trang.status_code, 200)
        self.assertContains(trang, 'Bắt đầu hậu kỳ')                # trang nhắc bấm nút Bắt đầu hậu kỳ (khớp template hiện tại)
        self.assertContains(trang, 'chuyển thẳng đến giao diện tải ảnh')   # câu hướng dẫn trong template hiện tại

    def test_trang_tai_anh_hien_nut_khi_cho_hau_ky(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_chon()  # tạo Booking ở Chờ Khách hàng lựa chọn ảnh, kèm sẵn các ảnh mẫu
        services.luu_lua_chon(bk.pk, self.kh, self.ma(1, 2))  # gọi hàm lưu lựa chọn ảnh
        services.gui_danh_sach_hau_ky(bk.pk, self.kh)  # gọi hàm gửi danh sách ảnh cho Nhiếp ảnh gia
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        trang = self.client.get(reverse('tai_anh_len', args=[bk.pk]))  # gửi yêu cầu tới trang
        self.assertEqual(trang.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(trang, 'Bắt đầu hậu kỳ')  # hướng dẫn người dùng bắt đầu từ Booking detail
        self.assertNotContains(trang, 'a1.jpg, a2.jpg')  # không còn trang trung gian liệt kê ảnh trước khi bắt đầu

    def test_post_bat_dau_chuyen_dang_hau_ky(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking(self.goi_gh, TT.CHO_HAU_KY)  # tạo Booking ở trạng thái cần thử
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(reverse('bat_dau_hau_ky', args=[bk.pk]))  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 302)  # chuyển hướng sau khi cập nhật trạng thái
        self.assertEqual(phan_hoi.url, reverse('tai_anh_len', args=[bk.pk]))  # vào thẳng trang tải ảnh, không quay về Booking detail
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)  # kiểm tra hai giá trị bằng nhau

    def test_get_khong_duoc_va_nag_khac_404_va_khach_403(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking(self.goi_gh, TT.CHO_HAU_KY)  # tạo Booking ở trạng thái cần thử
        url = reverse('bat_dau_hau_ky', args=[bk.pk])  # đường dẫn cần thử
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(url).status_code, 405)    # chỉ nhận POST
        self.client.force_login(self.nag_khac)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.post(url).status_code, 404)   # Booking của NAG khác
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.post(url).status_code, 403)   # Khách hàng không được bắt đầu hậu kỳ
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_HAU_KY)  # kiểm tra hai giá trị bằng nhau

    def test_sai_trang_thai_hien_loi_khong_doi(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking(self.goi_gh, TT.CHO_KH_CHON_ANH)  # tạo Booking ở trạng thái cần thử
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(reverse('bat_dau_hau_ky', args=[bk.pk]), follow=True)  # gửi yêu cầu tới trang
        self.assertContains(phan_hoi, 'Không thể chuyển Booking')  # kiểm tra trang có hiện đoạn chữ mong đợi
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_CHON_ANH)  # kiểm tra hai giá trị bằng nhau

# notifications/tests_hanh_dong.py - P12: kiểm tra nút hành động trong thông báo. Chạy: python manage.py test notifications.tests_hanh_dong
from datetime import date, time, timedelta  # ngày giờ để dựng slot, hạn đặt cọc, thời điểm duyệt

from django.contrib.auth import get_user_model  # model User của project
from django.contrib.auth.models import Group  # nhóm quyền: dùng để cho một User thành Nhiếp ảnh gia
from django.test import TestCase, override_settings  # TestCase dùng DB tạm; override_settings đổi cấu hình trong test
from django.urls import reverse  # đổi tên URL thành địa chỉ để so sánh
from django.utils import timezone  # giờ hiện tại có múi giờ

from bookings.models import Booking, YeuCauHuy  # Booking và Yêu cầu hủy của Tuyền
from core.constants import (BenThucHien, DinhDangTep, KetQuaDuyetHoSo, LoaiAnh, LoaiHauKy, LoaiThanhToan,  # hằng số, không tự gõ chữ tiếng Việt
                            TrangThaiBooking, TrangThaiSlot, TrangThaiThanhToan, VaiTro, XuLyTienCoc)
from delivery.models import Anh  # ảnh bàn giao của Nguyên
from notifications.services import gui_thong_bao, hanh_dong_thong_bao  # hàm gửi thông báo và hàm dựng nút cần thử
from payments.models import MinhChungThanhToan, ThanhToan  # thanh toán và minh chứng của Nguyên
from profiles.models import DuyetHoSo, GoiDichVu, LoaiHinhChup, NhiepAnhGia  # hồ sơ, gói, lượt duyệt của Khoa
from reviews.models import DanhGia  # đánh giá của Nguyên
from schedule.models import LichKhaDung  # khung giờ

User = get_user_model()  # gán tên User


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class HanhDongBase(TestCase):  # dữ liệu chung cho các test nút hành động
    def setUp(self):  # chạy trước mỗi test
        self.khach = User.objects.create_user('kh_hd', 'kh_hd@example.com', 'Matkhau@123', so_dien_thoai='0900000021')  # Khách hàng (không nhóm = Khách hàng)
        self.nag_user = User.objects.create_user('nag_hd', 'nag_hd@example.com', 'Matkhau@123', so_dien_thoai='0900000022')  # tài khoản Nhiếp ảnh gia
        nhom, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)  # nhóm Nhiếp ảnh gia
        self.nag_user.groups.add(nhom)  # cho tài khoản này thuộc nhóm Nhiếp ảnh gia để get_role nhận ra
        self.admin = User.objects.create_user('ad_hd', 'ad_hd@example.com', 'Matkhau@123', so_dien_thoai='0900000023')  # tài khoản Quản trị viên
        User.objects.filter(pk=self.admin.pk).update(is_superuser=True)  # superuser luôn là Quản trị viên (core/navigation.py)
        self.admin.refresh_from_db()  # đọc lại để có is_superuser mới
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=self.nag_user, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',  # hồ sơ Nhiếp ảnh gia tối thiểu
                                              SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')  # các cột bắt buộc còn lại
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')  # loại hình chụp
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='G', Gia=1000000,  # gói dịch vụ
                                            ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)  # hậu kỳ toàn bộ
        self.bay_gio = timezone.now()  # giờ chuẩn của test
        self.dem = 0  # bộ đếm slot

    def booking(self, trang_thai):  # dựng một Booking ở trạng thái cho trước (cách làm giống bookings/test_qua_han.py)
        self.dem += 1  # slot mới mỗi lần gọi
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=10 + self.dem),  # slot vài ngày sau
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0), TrangThai=TrangThaiSlot.DANG_GIU)  # đang giữ chỗ
        bk = Booking.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,  # tạo Booking
                                    NgayGioChup=self.bay_gio + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,  # ngày chụp xa
                                    Concept='c', TongGiaTri=1000000)  # tổng giá trị
        Booking.objects.filter(pk=bk.pk).update(TrangThai=trang_thai, NgayTao=self.bay_gio - timedelta(days=10))  # đặt trạng thái bằng UPDATE, lùi NgayTao
        bk.refresh_from_db()  # đọc lại từ DB
        return bk  # trả về Booking

    def nut(self, nguoi, bk):  # tiện: gửi thông báo gắn Booking cho nguoi rồi trả về danh sách nút
        tb = gui_thong_bao(nguoi, 'Tiêu đề bất kỳ', 'Nội dung', booking=bk)  # tiêu đề không ảnh hưởng đến nút
        return hanh_dong_thong_bao(tb, nguoi)  # các nút

    def tao_coc(self, bk, co_minh_chung=True, ly_do=None):  # dựng khoản cọc, có thể kèm minh chứng và lý do yêu cầu bổ sung
        tt = ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.TIEN_COC, SoTien=400000,  # khoản cọc 40%
                                      TrangThai=TrangThaiThanhToan.CHO_XAC_NHAN_COC, LyDoTuChoi=ly_do)  # đang chờ xác nhận
        if co_minh_chung:  # Khách đã tải minh chứng
            MinhChungThanhToan.objects.create(MaThanhToan=tt, TenTep='a.png', DuongDanTep='a.png',  # một minh chứng
                                              DinhDangTep=DinhDangTep.PNG, KichThuocTep=10)  # định dạng và kích thước hợp lệ
        return tt  # trả về khoản cọc


class NutQuanTriVienVaHoSo(HanhDongBase):  # nút cho thông báo hồ sơ
    def test_quan_tri_vien_duyet_ho_so_dan_dung_ho_so(self):  # còn chờ duyệt: nút Duyệt hồ sơ, đúng lượt
        luot = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag)  # lượt nộp đầu, chưa có kết quả
        tb = gui_thong_bao(self.admin, 'Có hồ sơ mới', 'Nội dung', duyet_ho_so=luot)  # thông báo gắn lượt duyệt
        nut = hanh_dong_thong_bao(tb, self.admin)  # các nút
        self.assertEqual(len(nut), 1)  # đúng 1 nút
        self.assertEqual(nut[0]['nhan'], 'Duyệt hồ sơ')  # đúng chữ
        self.assertEqual(nut[0]['url'], reverse('duyet_ho_so_chi_tiet', kwargs={'ma_duyet': luot.pk}))  # đúng lượt duyệt

    def test_da_xu_ly_thi_chi_xem_ho_so(self):  # đã có kết quả: đổi thành Xem hồ sơ
        luot = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag)  # lượt nộp đầu
        luot.MaQuanTriVien = self.admin  # có kết quả thì phải có người duyệt (CHECK của bảng)
        luot.KetQua = KetQuaDuyetHoSo.DA_DUYET  # đã duyệt
        luot.ThoiDiemDuyet = luot.ThoiDiemNop + timedelta(minutes=1)  # CHECK: thời điểm duyệt >= thời điểm nộp
        luot.save()  # lưu (đồng bộ trạng thái hồ sơ của Khoa)
        tb = gui_thong_bao(self.admin, 'Có hồ sơ mới', 'Nội dung', duyet_ho_so=luot)  # thông báo gắn lượt duyệt
        self.assertEqual(hanh_dong_thong_bao(tb, self.admin)[0]['nhan'], 'Xem hồ sơ')  # chữ đổi theo trạng thái

    def test_nguoi_khong_phai_quan_tri_khong_co_nut_duyet(self):  # Khách mở thông báo gắn lượt duyệt thì không có nút
        luot = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag)  # lượt nộp đầu
        tb = gui_thong_bao(self.khach, 'x', 'y', duyet_ho_so=luot)  # gắn lượt duyệt nhưng người nhận là Khách
        self.assertEqual(hanh_dong_thong_bao(tb, self.khach), [])  # không có nút

    def test_nag_duoc_yeu_cau_chinh_sua_thi_nut_chinh_sua(self):  # thông báo hồ sơ của Nhiếp ảnh gia
        luot = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag)  # lượt nộp đầu
        luot.MaQuanTriVien = self.admin  # người duyệt
        luot.KetQua = KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA  # yêu cầu chỉnh sửa
        luot.NoiDungPhanHoi = 'Bổ sung ảnh'  # CHECK: bắt buộc có nội dung phản hồi
        luot.ThoiDiemDuyet = luot.ThoiDiemNop + timedelta(minutes=1)  # CHECK thời điểm duyệt
        luot.save()  # lưu
        tb = gui_thong_bao(self.nag_user, 'Hồ sơ cần chỉnh sửa', 'Nội dung')  # không gắn Booking
        nut = hanh_dong_thong_bao(tb, self.nag_user)  # các nút
        self.assertEqual((nut[0]['nhan'], nut[0]['url']), ('Chỉnh sửa hồ sơ', reverse('cap_nhat_ho_so')))  # dẫn tới trang cập nhật hồ sơ

    def test_nag_duoc_duyet_thi_nut_xem_ho_so_cua_toi(self):  # các trường hợp còn lại
        tb = gui_thong_bao(self.nag_user, 'Hồ sơ đã duyệt', 'Nội dung')  # không gắn Booking
        nut = hanh_dong_thong_bao(tb, self.nag_user)  # các nút
        self.assertEqual((nut[0]['nhan'], nut[0]['url']), ('Xem hồ sơ của tôi', reverse('photographer_profile')))  # dẫn tới Hồ sơ của tôi


class NutBooking(HanhDongBase):  # nút theo trạng thái Booking
    def test_khach_cho_dat_coc_chua_tai_minh_chung_thi_nut_dat_coc(self):  # chưa tải minh chứng
        bk = self.booking(TrangThaiBooking.CHO_DAT_COC)  # Booking chờ đặt cọc
        nut = self.nut(self.khach, bk)  # nút của Khách
        self.assertEqual((nut[0]['nhan'], nut[0]['url']), ('Đặt cọc', reverse('tai_len_minh_chung', kwargs={'ma_booking': bk.pk})))  # dẫn tới trang tải minh chứng

    def test_khach_da_tai_minh_chung_thi_chi_xem_booking(self):  # đang chờ Nhiếp ảnh gia xác nhận
        bk = self.booking(TrangThaiBooking.CHO_DAT_COC)  # Booking chờ đặt cọc
        self.tao_coc(bk)  # đã có minh chứng
        self.assertEqual(self.nut(self.khach, bk)[0]['nhan'], 'Xem Booking')  # không còn nút Đặt cọc

    def test_khach_bi_yeu_cau_bo_sung_thi_nut_tai_lai(self):  # Nhiếp ảnh gia đã yêu cầu bổ sung
        bk = self.booking(TrangThaiBooking.CHO_DAT_COC)  # Booking chờ đặt cọc
        self.tao_coc(bk, ly_do='Sai số tiền')  # có lý do yêu cầu bổ sung
        self.assertEqual(self.nut(self.khach, bk)[0]['nhan'], 'Tải lại minh chứng')  # nút tải lại

    def test_nag_co_minh_chung_coc_thi_nut_xac_nhan(self):  # Nhiếp ảnh gia cần xác nhận cọc
        bk = self.booking(TrangThaiBooking.CHO_DAT_COC)  # Booking chờ đặt cọc
        self.tao_coc(bk)  # Khách đã tải minh chứng
        nut = self.nut(self.nag_user, bk)  # nút của Nhiếp ảnh gia
        self.assertEqual((nut[0]['nhan'], nut[0]['url']), ('Xác nhận thanh toán cọc', reverse('xac_nhan_thanh_toan_coc', kwargs={'ma_booking': bk.pk})))  # dẫn tới trang xác nhận cọc

    def test_nag_booking_moi_thi_nut_xu_ly(self):  # Booking mới gửi
        bk = self.booking(TrangThaiBooking.CHO_XAC_NHAN)  # chờ xác nhận
        self.assertEqual(self.nut(self.nag_user, bk)[0]['nhan'], 'Xử lý Booking')  # nút xử lý

    def test_nag_da_chup_thi_nut_tai_anh_len(self):  # đã chụp xong
        bk = self.booking(TrangThaiBooking.DA_CHUP)  # đã chụp
        self.assertEqual(self.nut(self.nag_user, bk)[0]['nhan'], 'Tải ảnh lên')  # nút tải ảnh

    def test_khach_cho_chon_anh_thi_nut_chon_anh(self):  # chờ Khách chọn ảnh
        bk = self.booking(TrangThaiBooking.CHO_KH_CHON_ANH)  # chờ chọn ảnh
        self.assertEqual(self.nut(self.khach, bk)[0]['nhan'], 'Chọn ảnh')  # nút chọn ảnh

    def test_khach_bi_nag_huy_va_cho_hoan_tien_thi_nut_xac_nhan_hoan_tien(self):  # hủy sau cọc do Nhiếp ảnh gia
        bk = self.booking(TrangThaiBooking.DA_HUY)  # đã hủy
        YeuCauHuy.objects.create(MaBooking=bk, BenYeuCau=BenThucHien.NHIEP_ANH_GIA, LyDo='Bận',  # yêu cầu hủy do Nhiếp ảnh gia
                                 TrangThaiBookingLucHuy=TrangThaiBooking.CHOT_BOOKING, XuLyTienCoc=XuLyTienCoc.HOAN_COC)  # hoàn cọc (tự mặc định Chờ hoàn tiền)
        nut = self.nut(self.khach, bk)  # nút của Khách
        self.assertEqual((nut[0]['nhan'], nut[0]['url']), ('Xác nhận đã nhận lại cọc', reverse('xac_nhan_hoan_tien', kwargs={'ma_booking': bk.pk})))  # dẫn tới trang của Tuyền

    def test_hoan_thanh_con_anh_va_chua_danh_gia_thi_hai_nut(self):  # Hoàn thành: Tải ảnh (chính) và Đánh giá (phụ)
        bk = self.booking(TrangThaiBooking.HOAN_THANH)  # hoàn thành
        Anh.objects.create(MaBooking=bk, TenAnh='x.jpg', DuongDanAnh='x.jpg', DinhDangAnh=DinhDangTep.JPG, KichThuocAnh=3,  # ảnh hoàn chỉnh còn lưu
                           LoaiAnh=LoaiAnh.HOAN_CHINH, CoWatermark=0)  # hoàn chỉnh thì không watermark
        nut = self.nut(self.khach, bk)  # nút của Khách
        self.assertEqual([(n['nhan'], n['chinh']) for n in nut], [('Tải ảnh', True), ('Đánh giá', False)])  # Tải ảnh là nút chính

    def test_hoan_thanh_khong_con_anh_thi_chi_nut_danh_gia_va_het_nut_khi_da_danh_gia(self):  # ảnh đã xóa, rồi đã đánh giá
        bk = self.booking(TrangThaiBooking.HOAN_THANH)  # hoàn thành, không có ảnh nào
        nut = self.nut(self.khach, bk)  # nút của Khách
        self.assertEqual([(n['nhan'], n['chinh']) for n in nut], [('Đánh giá', True)])  # Đánh giá thành nút chính
        DanhGia.objects.create(MaBooking=bk, MaNhiepAnhGia=self.nag, Diem=5)  # Khách đã đánh giá
        self.assertEqual(self.nut(self.khach, bk)[0]['nhan'], 'Xem Booking')  # chỉ còn nút mặc định

    def test_quan_tri_vien_khong_co_nut_booking(self):  # Quản trị viên chưa có trang Booking
        bk = self.booking(TrangThaiBooking.CHO_XAC_NHAN)  # một Booking bất kỳ
        self.assertEqual(self.nut(self.admin, bk), [])  # không có nút


class TrangChiTiet(HanhDongBase):  # kiểm tra nút hiện thật trong trang chi tiết
    def test_trang_chi_tiet_hien_nut_duyet_ho_so(self):  # Quản trị viên mở thông báo hồ sơ mới
        luot = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag)  # lượt nộp đầu
        tb = gui_thong_bao(self.admin, 'Có hồ sơ mới', 'Nội dung', duyet_ho_so=luot)  # thông báo gắn lượt duyệt
        self.client.force_login(self.admin)  # đăng nhập Quản trị viên
        phan_hoi = self.client.get(reverse('chi_tiet_thong_bao', args=[tb.pk]))  # mở trang chi tiết
        self.assertContains(phan_hoi, 'Duyệt hồ sơ')  # có chữ trên nút
        self.assertContains(phan_hoi, reverse('duyet_ho_so_chi_tiet', kwargs={'ma_duyet': luot.pk}))  # có đúng địa chỉ

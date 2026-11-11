# =====================================================================
# accounts/test_quan_tri.py  -  B7: kiểm thử trang tổng quan Quản trị
# Chạy:  python manage.py test accounts.test_quan_tri
# =====================================================================
from datetime import time, timedelta  # time: giờ trong ngày của khung giờ; timedelta: khoảng thời gian cộng vào ngày
from django.contrib.auth.models import Group  # bảng nhóm quyền (vai trò)
from django.test import TestCase  # mỗi test chạy trên database tạm
from django.urls import reverse  # đổi tên URL thành đường dẫn
from django.utils import timezone  # giờ hiện tại có múi giờ

from accounts.models import User  # model User, để lấy lại tài khoản đã tạo
from accounts.quan_tri import thong_ke_tong_quan, NHOM_BOOKING  # hàm đếm số liệu và danh sách 5 nhóm
from accounts.services import tao_tai_khoan  # hàm tạo tài khoản của P4
from bookings.models import Booking  # bảng Booking, để tạo dữ liệu đếm
from core.constants import (  # tên các trạng thái, không tự gõ chữ tiếng Việt
    LoaiHauKy, LoaiThanhToan, TrangThaiBooking, TrangThaiHoSo, TrangThaiThanhToan, VaiTro,
)
from payments.models import ThanhToan  # bảng thanh toán, để tạo dữ liệu đếm
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia  # hồ sơ, gói dịch vụ, loại hình: dữ liệu nền của một Booking
from schedule.models import LichKhaDung  # khung giờ, mỗi Booking còn hiệu lực cần một khung giờ riêng


class TongQuanQuanTriTests(TestCase):  # nhóm test của B7
    def setUp(self):  # chạy trước mỗi test
        self.admin = tao_tai_khoan('Quản Trị', 'admin@example.com', '0900000001', 'Matkhau!2026', vai_tro=VaiTro.QUAN_TRI_VIEN)  # tài khoản Quản trị viên
        self.khach = tao_tai_khoan('Khách Hàng', 'khach@example.com', '0900000002', 'Matkhau!2026')  # tài khoản Khách hàng (vai trò mặc định)
        self.url = reverse('admin_dashboard')  # đường dẫn trang tổng quan

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):  # người lạ không vào được
        r = self.client.get(self.url)  # mở trang khi chưa đăng nhập
        self.assertEqual(r.status_code, 302)  # bị chuyển trang
        self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_khach_hang_bi_403(self):  # sai vai trò
        self.client.force_login(self.khach)  # đăng nhập bằng Khách hàng
        self.assertEqual(self.client.get(self.url).status_code, 403)  # bị từ chối

    def test_quan_tri_vien_vao_duoc_va_dem_dung(self):  # đúng vai trò và số liệu đúng
        tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0900000003', 'Matkhau!2026',  # tạo 1 Nhiếp ảnh gia
                      vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)  # hồ sơ đang chờ duyệt
        self.client.force_login(self.admin)  # đăng nhập bằng Quản trị viên
        r = self.client.get(self.url)  # mở trang
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertEqual(r.context['thong_ke']['ho_so_cho_duyet'], 1)  # đếm đúng 1 hồ sơ chờ duyệt
        self.assertEqual(len(r.context['thong_ke']['booking_theo_trang_thai']), 13)  # luôn đủ 13 trạng thái
        self.assertContains(r, 'Tổng quan')  # có chữ Tổng quan (menu và tiêu đề)

    def test_nhiep_anh_gia_bi_403_du_da_duyet_hay_chua(self):  # feedback B7-8: chỉ Quản trị viên vào được, Nhiếp ảnh gia thì không
        for ten, trang_thai in (('cho', TrangThaiHoSo.CHO_DUYET), ('duyet', TrangThaiHoSo.DA_DUYET)):  # hai kiểu Nhiếp ảnh gia
            with self.subTest(trang_thai=trang_thai):  # báo riêng từng kiểu nếu lỗi
                nag = tao_tai_khoan('Nhiếp Ảnh', f'{ten}@example.com', '09000001' + ('11' if ten == 'cho' else '22'), 'Matkhau!2026',  # tạo tài khoản
                                    vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=trang_thai)  # gán vai trò và trạng thái hồ sơ
                self.client.force_login(nag)  # đăng nhập bằng Nhiếp ảnh gia
                self.assertEqual(self.client.get(self.url).status_code, 403)  # bị từ chối


class ThongKeTongQuanTests(TestCase):  # feedback B7-8: kiểm tra hàm đếm thong_ke_tong_quan bằng dữ liệu thật
    def setUp(self):  # chạy trước mỗi test
        self.dem = 0  # bộ đếm để mỗi lần tạo dữ liệu có số điện thoại, email, ngày không trùng nhau
        self.khach = tao_tai_khoan('Khách Hàng', 'khach@example.com', '0900000002', 'Matkhau!2026')  # 1 Khách hàng
        user_nag = tao_tai_khoan('Nhiếp Ảnh', 'nag@example.com', '0900000003', 'Matkhau!2026',  # 1 Nhiếp ảnh gia
                                 vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)  # hồ sơ đã duyệt (không tính vào hồ sơ chờ duyệt)
        self.nag = NhiepAnhGia.objects.create(  # hồ sơ Nhiếp ảnh gia, Booking cần trỏ tới
            MaTaiKhoan=user_nag, AnhDaiDien='avatars/a.png', GioiThieu='x',  # ảnh chỉ là đường dẫn, không cần file thật
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')  # thông tin ngân hàng
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')  # một loại hình chụp
        self.goi = GoiDichVu.objects.create(  # một gói dịch vụ
            MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='G', Gia=1000000, ThoiLuongChup=60,  # thông tin gói
            LoaiHauKy=LoaiHauKy.TOAN_BO)  # hậu kỳ toàn bộ ảnh

    def tao_booking(self, trang_thai):  # tạo một Booking ở trạng thái cho trước
        self.dem += 1  # mỗi Booking một khung giờ riêng (luật: một slot chỉ gắn một Booking còn hiệu lực)
        lich = LichKhaDung.objects.create(  # khung giờ của Booking này
            MaNhiepAnhGia=self.nag, Ngay=timezone.localdate() + timedelta(days=30 + self.dem),  # ngày khác nhau cho mỗi Booking
            GioBatDau=time(9, 0), GioKetThuc=time(10, 0))  # 9h đến 10h
        return Booking.objects.create(  # tạo Booking
            MaKhachHang=self.khach, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,  # khóa ngoại
            NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2, Concept='c',  # thông tin buổi chụp
            TrangThai=trang_thai)  # trạng thái cần đếm

    def tao_thanh_toan(self, booking, loai, trang_thai, da_xac_nhan=False):  # tạo một khoản thanh toán
        return ThanhToan.objects.create(  # tạo khoản thanh toán
            MaBooking=booking, LoaiThanhToan=loai, SoTien=400000, TrangThai=trang_thai,  # thông tin chính
            NgayXacNhan=timezone.now() if da_xac_nhan else None)  # đã xác nhận thì phải có ngày xác nhận (ràng buộc CSDL)

    def test_he_thong_trong_thi_moi_so_deu_bang_khong(self):  # chưa có Booking, thanh toán: các số Booking và thanh toán bằng 0
        tk = thong_ke_tong_quan()  # tính số liệu
        self.assertEqual(tk['tong_booking'], 0)  # chưa có Booking
        self.assertEqual(tk['thanh_toan_cho_xac_nhan'], 0)  # chưa có thanh toán
        self.assertEqual(tk['ho_so_cho_duyet'], 0)  # chưa có hồ sơ chờ duyệt (Nhiếp ảnh gia ở setUp đã duyệt)
        self.assertEqual(tk['tong_tai_khoan'], 2)  # 2 tài khoản tạo ở setUp
        self.assertEqual(len(tk['booking_theo_trang_thai']), 13)  # luôn đủ 13 trạng thái
        self.assertTrue(all(m['so_luong'] == 0 for m in tk['booking_theo_trang_thai']))  # và đều bằng 0

    def test_dem_booking_theo_tung_trang_thai(self):  # mỗi trạng thái đếm đúng số Booking của nó
        for trang_thai in (TrangThaiBooking.CHO_XAC_NHAN, TrangThaiBooking.CHO_XAC_NHAN, TrangThaiBooking.HOAN_THANH):  # 2 Booking chờ xác nhận, 1 hoàn thành
            self.tao_booking(trang_thai)  # tạo từng Booking
        tk = thong_ke_tong_quan()  # tính số liệu
        so_luong = {m['ten']: m['so_luong'] for m in tk['booking_theo_trang_thai']}  # đổi danh sách thành từ điển cho dễ so
        self.assertEqual(tk['tong_booking'], 3)  # tổng 3 Booking
        self.assertEqual(so_luong[TrangThaiBooking.CHO_XAC_NHAN], 2)  # 2 Booking chờ xác nhận
        self.assertEqual(so_luong[TrangThaiBooking.HOAN_THANH], 1)  # 1 Booking hoàn thành
        self.assertEqual(so_luong[TrangThaiBooking.DA_HUY], 0)  # trạng thái không có Booking vẫn hiện số 0
        self.assertEqual(sum(so_luong.values()), 3)  # cộng 13 trạng thái phải bằng tổng

    def test_ho_so_cho_duyet_chi_dem_dung_trang_thai(self):  # chỉ đếm hồ sơ Chờ duyệt, không đếm Đã duyệt, Đã từ chối hay Khách hàng
        tao_tai_khoan('A', 'a1@example.com', '0900000011', 'Matkhau!2026', vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)  # chờ duyệt, tính
        tao_tai_khoan('B', 'b1@example.com', '0900000012', 'Matkhau!2026', vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)  # chờ duyệt, tính
        tao_tai_khoan('C', 'c1@example.com', '0900000013', 'Matkhau!2026', vai_tro=VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_TU_CHOI)  # bị từ chối, không tính
        tk = thong_ke_tong_quan()  # tính số liệu
        self.assertEqual(tk['ho_so_cho_duyet'], 2)  # đúng 2 hồ sơ chờ duyệt
        self.assertEqual(tk['tong_tai_khoan'], 5)  # 2 tài khoản ở setUp cộng 3 tài khoản vừa tạo

    def test_thanh_toan_cho_xac_nhan_chi_dem_hai_trang_thai_cho(self):  # chỉ đếm cọc 40% và 60% còn lại đang chờ xác nhận
        b1 = self.tao_booking(TrangThaiBooking.CHO_DAT_COC)  # Booking 1: khoản cọc đang chờ xác nhận
        self.tao_thanh_toan(b1, LoaiThanhToan.TIEN_COC, TrangThaiThanhToan.CHO_XAC_NHAN_COC)  # tính
        b2 = self.tao_booking(TrangThaiBooking.CHO_XAC_NHAN_THANH_TOAN)  # Booking 2: cọc đã xác nhận, 60% đang chờ
        self.tao_thanh_toan(b2, LoaiThanhToan.TIEN_COC, TrangThaiThanhToan.DA_DAT_COC, da_xac_nhan=True)  # đã đặt cọc, không tính
        self.tao_thanh_toan(b2, LoaiThanhToan.PHAN_CON_LAI, TrangThaiThanhToan.CHO_XAC_NHAN_60)  # 60% chờ xác nhận, tính
        self.assertEqual(thong_ke_tong_quan()['thanh_toan_cho_xac_nhan'], 2)  # đúng 2 khoản đang chờ

    def test_trang_tong_quan_hien_dung_so_trong_html(self):  # con số tính được phải thật sự hiện ra trang
        tao_tai_khoan('Quản Trị', 'admin@example.com', '0900000001', 'Matkhau!2026', vai_tro=VaiTro.QUAN_TRI_VIEN)  # tài khoản vào trang
        self.tao_booking(TrangThaiBooking.CHO_XAC_NHAN)  # 1 Booking
        self.client.force_login(User.objects.get(email='admin@example.com'))  # đăng nhập bằng Quản trị viên
        res = self.client.get(reverse('admin_dashboard'))  # mở trang tổng quan
        self.assertEqual(res.context['thong_ke']['tong_booking'], 1)  # view truyền đúng số
        self.assertContains(res, 'admin-stat__value')  # và có các thẻ số liệu trong HTML

    def test_booking_theo_nhom_phu_du_13_trang_thai_khong_trung(self):  # 5 nhóm phải chứa đủ 13 trạng thái, mỗi trạng thái đúng một lần
        tk = thong_ke_tong_quan()  # tính số liệu
        ten_trong_nhom = [m['ten'] for nhom in tk['booking_theo_nhom'] for m in nhom['muc']]  # gộp tên trạng thái của mọi nhóm
        self.assertEqual(len(tk['booking_theo_nhom']), 5)  # có 5 nhóm
        self.assertEqual(len(ten_trong_nhom), 13)  # đủ 13 trạng thái
        self.assertEqual(set(ten_trong_nhom), set(TrangThaiBooking.ALL))  # không thiếu, không thừa, không trùng (13 phần tử mà tập đủ 13)

    def test_booking_theo_nhom_dung_nhom_va_tong(self):  # trạng thái rơi đúng nhóm và tổng nhóm đúng
        for trang_thai in (TrangThaiBooking.CHO_XAC_NHAN, TrangThaiBooking.CHO_HAU_KY, TrangThaiBooking.CHO_DAT_COC, TrangThaiBooking.HOAN_THANH, TrangThaiBooking.DA_HUY):  # 5 Booking ở 5 trạng thái (không dùng Đã từ chối vì Booking đó bắt buộc có lý do từ chối)
            self.tao_booking(trang_thai)  # tạo từng Booking
        nhom = {n['ma']: n for n in thong_ke_tong_quan()['booking_theo_nhom']}  # đổi danh sách nhóm thành từ điển theo mã
        self.assertEqual(nhom['cho-nag']['tong'], 2)  # Chờ xác nhận và Chờ hậu kỳ
        self.assertEqual(nhom['cho-kh']['tong'], 1)  # Chờ đặt cọc
        self.assertEqual(nhom['dang-dien-ra']['tong'], 0)  # chưa có Booking nào đang diễn ra
        self.assertEqual(nhom['hoan-tat']['tong'], 1)  # Hoàn thành
        self.assertEqual(nhom['khong-thanh-cong']['tong'], 1)  # chỉ Đã hủy

    def test_5_nhom_phu_dung_13_trang_thai(self):  # 5 nhóm phải chứa đúng 13 trạng thái, không thiếu không trùng
        trong_nhom = [t for n in NHOM_BOOKING for t in n['trang_thai']]  # gộp trạng thái của mọi nhóm
        self.assertCountEqual(trong_nhom, TrangThaiBooking.ALL)  # so với danh sách gốc trong core/constants.py

    def test_phan_tram_theo_nhom(self):  # % trên tổng Booking tính đúng
        self.tao_booking(TrangThaiBooking.CHO_XAC_NHAN)  # 1 Booking nhóm Chờ Nhiếp ảnh gia
        self.tao_booking(TrangThaiBooking.HOAN_THANH)  # 1 Booking nhóm Hoàn tất
        nhom = {n['ten']: n for n in thong_ke_tong_quan()['booking_theo_nhom']}  # đổi danh sách thành từ điển theo tên nhóm
        self.assertEqual(nhom['Chờ Nhiếp ảnh gia']['phan_tram'], 50.0)  # 1 trên 2 = 50%
        self.assertEqual(nhom['Hoàn tất']['phan_tram'], 50.0)  # 1 trên 2 = 50%
        self.assertEqual(nhom['Chờ Khách hàng']['phan_tram'], 0)  # nhóm không có Booking thì 0%

    def test_khong_co_booking_thi_phan_tram_la_0(self):  # tổng 0 không được lỗi chia cho 0
        self.assertTrue(all(n['phan_tram'] == 0 for n in thong_ke_tong_quan()['booking_theo_nhom']))  # mọi nhóm đều 0%
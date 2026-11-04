# Chạy: python manage.py test delivery.test_yeu_cau_chinh_sua      (N7: UC5.5 Khách hàng yêu cầu chỉnh sửa ảnh)
from datetime import timedelta                                 # khoảng thời gian (3 ngày...)
from unittest import mock                                      # giả lập lỗi database / lỗi thông báo

from django.contrib.auth import get_user_model                 # model User của dự án
from django.db import DatabaseError                            # lỗi database để giả lập
from django.urls import reverse                                # đổi tên URL thành đường dẫn
from django.utils import timezone                              # giờ hiện tại có múi giờ

from bookings.models import Booking, LichSuTrangThaiBooking   # Booking và lịch sử đổi trạng thái
from core.constants import BenThucHien, LoaiAnh, TrangThaiBooking as TT   # hằng số dùng chung
from delivery import services                                  # hàm nghiệp vụ cần kiểm tra
from delivery.models import YeuCauChinhSua, YeuCauChinhSua_Anh   # bảng yêu cầu và chi tiết từng ảnh
from delivery.test_chon_anh import _NenChonAnh                 # lớp nền có sẵn (tạo Khách, Nhiếp ảnh gia, gói, thư mục tạm, bảng URL test)
from notifications.models import ThongBao                      # bảng thông báo

User = get_user_model()                                        # lấy model User


class _NenYeuCau(_NenChonAnh):                                 # lớp nền riêng của N7 (không có test riêng)
    def tao_booking_cho_kiem_tra(self, so_anh=3, goi=None):    # Booking ở "Chờ Khách hàng kiểm tra" có sẵn các ảnh ĐÃ hậu kỳ
        bk = self.tao_booking(goi or self.goi_gh, TT.CHO_KH_KIEM_TRA)   # tạo Booking đúng trạng thái
        self.ds_anh = [self.tao_anh(bk, f'a{i}.jpg', loai=LoaiAnh.DA_HAU_KY) for i in range(1, so_anh + 1)]   # tạo ảnh a1.jpg, a2.jpg... đã hậu kỳ
        return bk                                              # trả Booking

    def du_lieu(self, *chi_so, nhan_xet='Tông màu hơi tối'):    # dữ liệu POST/hàm: nhận xét chung + nội dung sửa cho các ảnh thứ chi_so
        return nhan_xet, {self.ds_anh[i - 1].pk: f'Sửa ảnh {i} sáng hơn' for i in chi_so}   # trả (nhận xét, {mã ảnh: nội dung})

    def them_yeu_cau_cu(self, bk, so_lan):                     # tạo sẵn so_lan yêu cầu cũ (để thử giới hạn 3 lần)
        for i in range(1, so_lan + 1):                         # lần 1..so_lan
            YeuCauChinhSua.objects.create(MaBooking=bk, NoiDung=f'Lần {i}', SoLanYeuCau=i)   # mỗi lần một dòng yêu cầu


class YeuCauChinhSuaServiceTests(_NenYeuCau):                  # nghiệp vụ của UC5.5
    def test_gui_thanh_cong_luu_yeu_cau_doi_trang_thai_va_bao_nag(self):   # bước 4-6
        bk = self.tao_booking_cho_kiem_tra()                   # 3 ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(1, 3)                      # sửa ảnh 1 và 3
        kq = services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)   # Khách gửi yêu cầu
        self.assertEqual((kq['so_lan'], kq['so_anh'], kq['da_bao_nag']), (1, 2, True))   # lần 1, 2 ảnh, đã báo
        yc = YeuCauChinhSua.objects.get(MaBooking=bk)          # yêu cầu vừa lưu
        self.assertEqual((yc.SoLanYeuCau, yc.NoiDung), (1, 'Tông màu hơi tối'))   # số lần và nhận xét tổng quát
        self.assertEqual(YeuCauChinhSua_Anh.objects.filter(MaYeuCauChinhSua=yc).count(), 2)   # 2 dòng chi tiết
        self.assertEqual(YeuCauChinhSua_Anh.objects.get(MaYeuCauChinhSua=yc, MaAnh=self.ds_anh[0]).NoiDungChinhSua, 'Sửa ảnh 1 sáng hơn')   # nội dung đúng ảnh
        bk.refresh_from_db()                                   # đọc lại Booking
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)         # Booking quay lại Đang hậu kỳ
        self.assertAlmostEqual((bk.HanHauKy - timezone.now()).total_seconds(), 3 * 86400, delta=120)   # hạn 3 ngày được tính lại
        self.assertTrue(LichSuTrangThaiBooking.objects.filter(  # hàm của Tuyền tự ghi lịch sử, bên thực hiện là Khách hàng
            MaBooking=bk, TrangThaiCu=TT.CHO_KH_KIEM_TRA, TrangThaiMoi=TT.DANG_HAU_KY, BenThucHien=BenThucHien.KHACH_HANG).exists())  # điều kiện lọc lịch sử: Khách hàng là bên thực hiện
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).exists())   # Nhiếp ảnh gia được báo

    def test_nhiep_anh_gia_chi_phai_tai_lai_dung_anh_khach_yeu_cau(self):   # nối N7 với N4
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(2)                         # chỉ sửa ảnh 2
        services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertEqual({a.TenAnh for a in services.anh_can_hau_ky(bk)}, {'a2.jpg'})   # N4 chỉ đòi tải lại a2

    def test_lan_hai_tang_so_lan_len_2(self):                  # Booking quay lại Chờ kiểm tra thì gửi được lần 2
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)   # lần 1
        Booking.objects.filter(pk=bk.pk).update(TrangThai=TT.CHO_KH_KIEM_TRA)   # giả lập Nhiếp ảnh gia đã tải bản mới
        kq = services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)   # lần 2
        self.assertEqual(kq['so_lan'], 2)                      # số lần là 2
        self.assertEqual(services.so_lan_chinh_sua_con_lai(bk), 1)   # còn 1 lần

    def test_da_dung_du_3_lan_bi_chan_khong_tao_them(self):    # luồng 2a + BR5.5-1
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.them_yeu_cau_cu(bk, 3)                            # đã dùng đủ 3 lần
        self.assertEqual(services.so_lan_chinh_sua_con_lai(bk), 0)   # không còn lần nào
        self.assertIn('03 lần', services.ly_do_khong_yeu_cau_duoc(bk))   # thông báo nhắc tối đa 03 lần
        nhan_xet, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        with self.assertRaises(services.LoiYeuCauChinhSua):    # gửi thêm bị chặn
            services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertEqual(YeuCauChinhSua.objects.filter(MaBooking=bk).count(), 3)   # không có lần thứ 4
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)     # trạng thái không đổi

    def test_chua_chon_anh_nao_bi_chan(self):                  # ngoại lệ 4a
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        with self.assertRaises(services.LoiYeuCauChinhSua) as ctx:  # mong đợi hàm này báo lỗi
            services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, 'Tổng quát', {})  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertIn('ít nhất một ảnh', str(ctx.exception))   # câu báo đúng
        self.assertEqual(YeuCauChinhSua.objects.count(), 0)    # không lưu gì

    def test_noi_dung_khong_hop_le_bi_chan_va_khong_doi_gi(self):   # ngoại lệ 4b
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        _, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        with self.assertRaises(services.LoiYeuCauChinhSua):    # nhận xét tổng quát trống
            services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, '   ', ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        with self.assertRaises(services.LoiYeuCauChinhSua):    # nhận xét quá 1000 ký tự
            services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, 'x' * 1001, ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        with self.assertRaises(services.LoiYeuCauChinhSua):    # ảnh đã chọn nhưng thiếu nội dung
            services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, 'Tổng quát', {self.ds_anh[0].pk: '  '})  # gọi hàm gửi yêu cầu chỉnh sửa
        with self.assertRaises(services.LoiYeuCauChinhSua):    # nội dung ảnh quá 500 ký tự
            services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, 'Tổng quát', {self.ds_anh[0].pk: 'y' * 501})  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertEqual(YeuCauChinhSua.objects.count(), 0)    # không lưu gì
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)     # trạng thái không đổi

    def test_ma_anh_la_hoac_anh_chua_hau_ky_bi_chan(self):     # không tin mã ảnh gửi lên
        bk = self.tao_booking_cho_kiem_tra(so_anh=1)  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        anh_goc = self.tao_anh(bk, 'goc.jpg', loai=LoaiAnh.CHUA_HAU_KY)   # ảnh chưa hậu kỳ
        bk2 = self.tao_booking_cho_kiem_tra(so_anh=1)          # Booking khác
        anh_khac = self.ds_anh[0]                              # ảnh của Booking 2
        for ma in (anh_goc.pk, anh_khac.pk, 999999):           # 3 loại mã không hợp lệ
            with self.assertRaises(services.LoiYeuCauChinhSua):  # mong đợi hàm này báo lỗi
                services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, 'Tổng quát', {ma: 'Sửa'})  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertEqual(YeuCauChinhSua.objects.count(), 0)  # kiểm tra hai giá trị bằng nhau

    def test_khach_khac_sai_trang_thai_va_da_ban_giao_bi_chan(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        khach_khac = User.objects.create_user('kh9', 'kh9@x.vn', 'p', so_dien_thoai='0900000099')   # tài khoản khác
        with self.assertRaises(services.LoiYeuCauChinhSua):    # Booking của người khác
            services.gui_yeu_cau_chinh_sua(bk.pk, khach_khac, nhan_xet, ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        bk2 = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)    # Nhiếp ảnh gia đang hậu kỳ
        self.assertIn('đang hậu kỳ', services.ly_do_khong_yeu_cau_duoc(bk2))  # kiểm tra câu báo có chứa đoạn chữ mong đợi
        bk3 = self.tao_booking(self.goi_gh, TT.CHO_XAC_NHAN_THANH_TOAN)   # đã bàn giao
        self.assertIn('bàn giao', services.ly_do_khong_yeu_cau_duoc(bk3))  # kiểm tra câu báo có chứa đoạn chữ mong đợi
        bk4 = self.tao_booking(self.goi_gh, TT.DA_CHUP)        # chưa có ảnh hậu kỳ
        self.assertIn('chưa đến lúc', services.ly_do_khong_yeu_cau_duoc(bk4))  # kiểm tra câu báo có chứa đoạn chữ mong đợi

    def test_loi_thong_bao_van_luu_yeu_cau_va_bao_da_bao_nag_false(self):   # ngoại lệ 6a
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        with mock.patch('delivery.services.gui_thong_bao', return_value=None), self.assertLogs('delivery.services', level='ERROR'):   # thông báo lỗi và có ghi log
            kq = services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertFalse(kq['da_bao_nag'])                     # báo cho view biết chưa gửi được thông báo
        self.assertEqual(YeuCauChinhSua.objects.filter(MaBooking=bk).count(), 1)   # yêu cầu vẫn được lưu
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)         # Booking vẫn chuyển Đang hậu kỳ

    def test_loi_database_khi_luu_hoan_tac_het(self):          # ngoại lệ 5a
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        with mock.patch.object(YeuCauChinhSua_Anh.objects, 'bulk_create', side_effect=DatabaseError('hỏng')):   # lỗi khi lưu chi tiết
            with self.assertRaises(services.LoiYeuCauChinhSua) as ctx:  # mong đợi hàm này báo lỗi
                services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, nhan_xet, ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        self.assertIn('thực hiện lại', str(ctx.exception))     # yêu cầu Khách làm lại
        self.assertEqual(YeuCauChinhSua.objects.count(), 0)    # yêu cầu chính cũng bị hoàn tác
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)     # trạng thái không đổi
        self.assertFalse(ThongBao.objects.filter(MaBooking=bk).exists())   # không gửi thông báo


class YeuCauChinhSuaViewTests(_NenYeuCau):                     # trang web của UC5.5
    def url(self, bk):                                         # đường dẫn trang yêu cầu chỉnh sửa
        return reverse('yeu_cau_chinh_sua', args=[bk.pk])  # trả kết quả

    def test_get_khach_200_va_nguoi_khac_bi_chan(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        trang = self.client.get(self.url(bk))  # gửi yêu cầu tới trang
        self.assertEqual(trang.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(trang, 'name="nhan_xet"')          # có ô nhận xét tổng quát
        self.assertContains(trang, 'name="anh"', count=3)      # có 3 ô tick ảnh
        self.assertContains(trang, 'Còn <strong>3</strong> lần')   # bước 2: hiện số lần còn lại
        khach_khac = User.objects.create_user('kh8', 'kh8@x.vn', 'p', so_dien_thoai='0900000098')  # tạo thêm một tài khoản để thử người khác
        self.client.force_login(khach_khac)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)   # Booking của người khác
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)   # Nhiếp ảnh gia không phải Khách hàng
        self.client.logout()  # đăng xuất
        self.assertEqual(self.client.get(self.url(bk)).status_code, 302)   # chưa đăng nhập -> trang đăng nhập

    def test_post_thanh_cong_chuyen_trang_va_doi_trang_thai(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        a1 = self.ds_anh[0].pk  # mã ảnh 1
        phan_hoi = self.client.post(self.url(bk), {'nhan_xet': 'Tổng quát', 'anh': [a1], f'noi_dung_{a1}': 'Làm sáng da'})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 302)            # chuyển trang để tránh gửi lại khi F5
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)  # kiểm tra hai giá trị bằng nhau
        trang = self.client.get(self.url(bk))                  # mở lại: hiện lịch sử và lý do không gửi tiếp được
        self.assertContains(trang, 'đang hậu kỳ')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(trang, 'Lần 1')                    # lịch sử lần 1
        self.assertNotContains(trang, 'name="nhan_xet"')       # không còn form

    def test_post_khong_chon_anh_hien_loi_va_giu_nhan_xet(self):   # ngoại lệ 4a trên giao diện
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'nhan_xet': 'Giữ dòng này'})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(phan_hoi, 'Vui lòng chọn ít nhất một ảnh')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(phan_hoi, 'Giữ dòng này')          # nhận xét vừa nhập không bị mất

    def test_post_thieu_noi_dung_anh_giu_lai_o_tick(self):     # ngoại lệ 4b trên giao diện
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        a1 = self.ds_anh[0].pk  # mã ảnh 1
        phan_hoi = self.client.post(self.url(bk), {'nhan_xet': 'Tổng quát', 'anh': [a1], f'noi_dung_{a1}': ''})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(phan_hoi, 'Nội dung yêu cầu không hợp lệ')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(phan_hoi, 'checked', count=1)      # ô đã tick vẫn được giữ
        self.assertEqual(YeuCauChinhSua.objects.count(), 0)  # kiểm tra hai giá trị bằng nhau

    def test_het_3_lan_hien_thong_bao_va_khong_con_form(self):   # luồng 2a trên giao diện
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.them_yeu_cau_cu(bk, 3)  # tạo sẵn 3 lần yêu cầu cũ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        trang = self.client.get(self.url(bk))  # gửi yêu cầu tới trang
        self.assertContains(trang, 'tối đa 03 lần yêu cầu chỉnh sửa')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertNotContains(trang, 'name="nhan_xet"')  # kiểm tra trang KHÔNG có đoạn chữ này
        phan_hoi = self.client.post(self.url(bk), {'nhan_xet': 'x', 'anh': [self.ds_anh[0].pk]})   # cố gửi trực tiếp
        self.assertEqual(YeuCauChinhSua.objects.filter(MaBooking=bk).count(), 3)   # vẫn chỉ 3 lần
        self.assertContains(phan_hoi, 'tối đa 03 lần')  # kiểm tra trang có hiện đoạn chữ mong đợi

    def test_loi_thong_bao_hien_canh_bao_cho_khach(self):      # ngoại lệ 6a trên giao diện
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        a1 = self.ds_anh[0].pk  # mã ảnh 1
        with mock.patch('delivery.services.gui_thong_bao', return_value=None), self.assertLogs('delivery.services', level='ERROR'):  # giả lập lỗi để thử
            phan_hoi = self.client.post(self.url(bk), {'nhan_xet': 'Tổng quát', 'anh': [a1], f'noi_dung_{a1}': 'Sửa'}, follow=True)  # gửi yêu cầu tới trang
        self.assertContains(phan_hoi, 'chưa gửi được thông báo')   # cảnh báo cho Khách
        self.assertEqual(YeuCauChinhSua.objects.filter(MaBooking=bk).count(), 1)  # kiểm tra hai giá trị bằng nhau

    def test_nhiep_anh_gia_thay_noi_dung_khach_yeu_cau_o_trang_tai_anh(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        nhan_xet, ds = self.du_lieu(1)  # lấy dữ liệu mẫu để gửi
        services.gui_yeu_cau_chinh_sua(bk.pk, self.kh, 'Màu hơi lạnh', ds)  # gọi hàm gửi yêu cầu chỉnh sửa
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        trang = self.client.get(reverse('tai_anh_len', args=[bk.pk]))  # gửi yêu cầu tới trang
        self.assertEqual(trang.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(trang, 'Khách hàng yêu cầu chỉnh sửa (lần 1/3)')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(trang, 'Màu hơi lạnh')             # nhận xét tổng quát
        self.assertContains(trang, 'Sửa ảnh 1 sáng hơn')       # nội dung sửa của ảnh

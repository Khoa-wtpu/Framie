# Chạy: python manage.py test delivery.test_xac_nhan_ban_giao      (N8: UC5.6 Khách hàng xác nhận hoàn tất bàn giao)
from datetime import timedelta                                 # khoảng thời gian (2 ngày...)
from decimal import Decimal                                    # số tiền chính xác
from unittest import mock                                      # giả lập lỗi database

from django.contrib.auth import get_user_model                 # model User của dự án
from django.db import DatabaseError                            # lỗi database để giả lập
from django.test import override_settings                       # đổi cấu hình riêng cho test
from django.urls import include, path, reverse                  # đổi tên URL thành đường dẫn và ghép bảng URL
from django.utils import timezone                              # giờ hiện tại có múi giờ

from bookings.models import LichSuTrangThaiBooking             # lịch sử đổi trạng thái
from core.constants import BenThucHien, LoaiThanhToan, TrangThaiBooking as TT, TrangThaiThanhToan   # hằng số dùng chung
from delivery import services                                  # hàm nghiệp vụ cần kiểm tra
from delivery.models import BanGiao                            # bảng Bàn giao
from delivery.test_yeu_cau_chinh_sua import _NenYeuCau         # lớp nền có sẵn (Booking Chờ kiểm tra kèm ảnh đã hậu kỳ)
from delivery.tests import urlpatterns as _url_delivery        # bảng URL test có sẵn của delivery
from notifications.models import ThongBao                      # bảng thông báo
from payments.models import ThanhToan                          # bảng Thanh toán

User = get_user_model()                                        # lấy model User

urlpatterns = _url_delivery + [path('', include('payments.urls'))]   # bảng URL test: thêm payments để trang có link sang tải minh chứng


class XacNhanBanGiaoServiceTests(_NenYeuCau):                  # nghiệp vụ của UC5.6
    def test_xac_nhan_thanh_cong_tao_ban_giao_khoan_60_doi_trang_thai_va_bao_hai_ben(self):   # bước 5-7
        bk = self.tao_booking_cho_kiem_tra()                   # Booking Chờ Khách hàng kiểm tra, tổng giá trị 1.000.000
        kq = services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)   # Khách xác nhận hoàn tất bàn giao
        self.assertEqual(kq['so_tien'], Decimal('600000'))     # số tiền còn lại là 60%
        bg = BanGiao.objects.get(MaBooking=bk)                 # bản ghi Bàn giao vừa tạo
        self.assertEqual(bg.TrangThaiBanGiao, 'Hoàn tất bàn giao')   # trạng thái bàn giao
        tt = ThanhToan.objects.get(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI)   # khoản thanh toán 60%
        self.assertEqual((tt.SoTien, tt.TrangThai), (Decimal('600000'), TrangThaiThanhToan.CHO_XAC_NHAN_60))   # đúng số tiền và đang chờ xác nhận
        bk.refresh_from_db()                                   # đọc lại Booking
        self.assertEqual(bk.TrangThai, TT.CHO_XAC_NHAN_THANH_TOAN)   # Booking sang Chờ xác nhận thanh toán
        self.assertAlmostEqual((bk.HanThanhToanConLai - timezone.now()).total_seconds(), 2 * 86400, delta=120)   # hạn thanh toán 2 ngày
        self.assertTrue(LichSuTrangThaiBooking.objects.filter(  # hàm của Tuyền tự ghi lịch sử, bên thực hiện là Khách hàng
            MaBooking=bk, TrangThaiCu=TT.CHO_KH_KIEM_TRA, TrangThaiMoi=TT.CHO_XAC_NHAN_THANH_TOAN, BenThucHien=BenThucHien.KHACH_HANG).exists())  # điều kiện lọc lịch sử
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())   # Khách được nhắc thanh toán
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).exists())   # Nhiếp ảnh gia được báo

    def test_so_tien_coc_va_con_lai_cong_lai_bang_tong(self):  # tổng giá trị lẻ thì hai khoản vẫn cộng đúng
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        from bookings.models import Booking                    # import cục bộ để cập nhật tổng giá trị
        Booking.objects.filter(pk=bk.pk).update(TongGiaTri=Decimal('1234567'))   # tổng giá trị lẻ
        kq = services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)  # gọi hàm xác nhận hoàn tất bàn giao
        self.assertEqual(kq['so_tien'], Decimal('1234567') - Decimal('493827'))   # cọc 40% làm tròn = 493.827, còn lại = tổng - cọc

    def test_bam_xac_nhan_lan_hai_bi_chan_khong_tao_trung(self):   # F5 hoặc hai tab
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)    # lần 1
        with self.assertRaises(services.LoiBanGiao):           # lần 2 bị chặn
            services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)  # gọi hàm xác nhận hoàn tất bàn giao
        self.assertEqual(BanGiao.objects.filter(MaBooking=bk).count(), 1)   # chỉ một bàn giao
        self.assertEqual(ThanhToan.objects.filter(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI).count(), 1)   # chỉ một khoản 60%
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).count(), 1)   # chỉ báo một lần

    def test_sai_trang_thai_va_khach_khac_bi_chan(self):  # tên test cho biết tình huống đang kiểm tra
        khach_khac = User.objects.create_user('kh7', 'kh7@x.vn', 'p', so_dien_thoai='0900000097')   # tài khoản khác
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        with self.assertRaises(services.LoiBanGiao):           # Booking của người khác
            services.xac_nhan_hoan_tat_ban_giao(bk.pk, khach_khac)  # gọi hàm xác nhận hoàn tất bàn giao
        bk2 = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)    # đang hậu kỳ
        self.assertIn('đang hậu kỳ', services.ly_do_khong_xac_nhan_duoc(bk2))  # kiểm tra câu báo có chứa đoạn chữ mong đợi
        bk3 = self.tao_booking(self.goi_gh, TT.DA_CHUP)        # chưa đến lúc
        self.assertIn('chưa đến lúc', services.ly_do_khong_xac_nhan_duoc(bk3))  # kiểm tra câu báo có chứa đoạn chữ mong đợi
        with self.assertRaises(services.LoiBanGiao):  # mong đợi hàm này báo lỗi
            services.xac_nhan_hoan_tat_ban_giao(bk3.pk, self.kh)  # gọi hàm xác nhận hoàn tất bàn giao
        self.assertEqual(BanGiao.objects.count(), 0)           # không tạo bàn giao nào

    def test_loi_cap_nhat_ban_giao_5a_hoan_tac_het(self):      # ngoại lệ 5a
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        with mock.patch.object(BanGiao.objects, 'create', side_effect=DatabaseError('hỏng')):   # lỗi khi tạo Bàn giao
            with self.assertRaises(services.LoiBanGiao) as ctx:  # mong đợi hàm này báo lỗi
                services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)  # gọi hàm xác nhận hoàn tất bàn giao
        self.assertIn('trạng thái bàn giao', str(ctx.exception))   # đúng câu 5a
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)     # trạng thái không đổi
        self.assertEqual(ThanhToan.objects.filter(MaBooking=bk).count(), 0)   # không có khoản 60%
        self.assertFalse(ThongBao.objects.filter(MaBooking=bk).exists())   # không thông báo

    def test_loi_cap_nhat_booking_6a_hoan_tac_ca_ban_giao_va_khoan_60(self):   # ngoại lệ 6a
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        with mock.patch('delivery.services.chuyen_trang_thai_booking', side_effect=DatabaseError('hỏng')):   # lỗi khi đổi trạng thái
            with self.assertRaises(services.LoiBanGiao) as ctx:  # mong đợi hàm này báo lỗi
                services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)  # gọi hàm xác nhận hoàn tất bàn giao
        self.assertIn('cập nhật Booking', str(ctx.exception))  # đúng câu 6a
        self.assertEqual(BanGiao.objects.count(), 0)           # Bàn giao đã tạo cũng bị hoàn tác
        self.assertEqual(ThanhToan.objects.filter(MaBooking=bk).count(), 0)   # khoản 60% cũng bị hoàn tác
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)  # kiểm tra hai giá trị bằng nhau


    def test_khach_tai_minh_chung_60_duoc_ngay_sau_khi_xac_nhan(self):   # nối N8 với N2: dùng đúng khoản 60% vừa tạo
        import io                                              # tạo ảnh PNG nhỏ trong bộ nhớ
        from django.core.files.uploadedfile import SimpleUploadedFile   # giả lập tệp Khách tải lên
        from PIL import Image                                  # tạo ảnh PNG
        from payments import services as dich_vu_tt            # hàm tải minh chứng của N2
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        services.xac_nhan_hoan_tat_ban_giao(bk.pk, self.kh)    # Khách xác nhận bàn giao
        dem = io.BytesIO()                                     # vùng nhớ chứa ảnh
        Image.new('RGB', (10, 10), 'white').save(dem, format='PNG')   # ảnh PNG trắng 10x10
        tep = SimpleUploadedFile('minhchung.png', dem.getvalue(), content_type='image/png')   # tệp minh chứng
        tt = dich_vu_tt.tai_len_minh_chung(bk.pk, self.kh, tep)   # tải minh chứng cho khoản 60%
        self.assertEqual(tt.LoaiThanhToan, LoaiThanhToan.PHAN_CON_LAI)   # đúng khoản phần còn lại
        self.assertEqual(ThanhToan.objects.filter(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI).count(), 1)   # dùng lại khoản N8 đã tạo, không tạo trùng


@override_settings(ROOT_URLCONF='delivery.test_xac_nhan_ban_giao')   # dùng bảng URL ở trên cho test trang web
class XacNhanBanGiaoViewTests(_NenYeuCau):                     # trang web của UC5.6
    def url(self, bk):                                         # đường dẫn trang xác nhận bàn giao
        return reverse('xac_nhan_ban_giao', args=[bk.pk])  # trả kết quả

    def test_get_khach_200_hien_anh_nut_va_link_chinh_sua(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        trang = self.client.get(self.url(bk))  # gửi yêu cầu tới trang
        self.assertEqual(trang.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(trang, 'Ảnh đã hậu kỳ (3)')        # bước 2: hiện 3 ảnh hậu kỳ
        self.assertContains(trang, 'Xác nhận hoàn tất bàn giao')   # có nút xác nhận
        self.assertContains(trang, '600.000 VNĐ')              # báo trước số tiền phải thanh toán
        self.assertContains(trang, reverse('yeu_cau_chinh_sua', args=[bk.pk]))   # nhánh 4a: link sang Yêu cầu chỉnh sửa
        self.assertContains(trang, 'còn 3 lần')                # còn 3 lần chỉnh sửa

    def test_quyen_truy_cap(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        khach_khac = User.objects.create_user('kh6', 'kh6@x.vn', 'p', so_dien_thoai='0900000096')  # tạo thêm một tài khoản để thử người khác
        self.client.force_login(khach_khac)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)   # Booking của người khác
        self.client.force_login(self.nag_user)  # đăng nhập bằng tài khoản cần thử
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)   # Nhiếp ảnh gia không phải Khách hàng
        self.client.logout()  # đăng xuất
        self.assertEqual(self.client.get(self.url(bk)).status_code, 302)   # chưa đăng nhập

    def test_bam_nut_dau_hien_hop_hoi_chua_ghi_gi(self):       # bước xác nhận
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'hoi'})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)            # chưa chuyển trang
        self.assertContains(phan_hoi, 'Bạn có chắc chắn đã hài lòng')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(phan_hoi, 'Có, xác nhận hoàn tất bàn giao')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertEqual(BanGiao.objects.count(), 0)           # chưa ghi gì
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)  # kiểm tra hai giá trị bằng nhau

    def test_xac_nhan_that_chuyen_trang_va_hien_thong_tin_thanh_toan(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'xac_nhan'})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 302)  # kiểm tra hai giá trị bằng nhau
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_XAC_NHAN_THANH_TOAN)  # kiểm tra hai giá trị bằng nhau
        trang = self.client.get(self.url(bk))                  # mở lại trang
        self.assertContains(trang, 'đã xác nhận hoàn tất bàn giao')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(trang, 'Thanh toán phần còn lại')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(trang, 'Hạn thanh toán')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertContains(trang, reverse('tai_len_minh_chung', args=[bk.pk]))   # link sang trang tải minh chứng của N2
        self.assertNotContains(trang, 'value="hoi"')           # không còn nút xác nhận

    def test_gui_xac_nhan_truc_tiep_khi_sai_trang_thai_hien_loi(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)  # tạo Booking ở trạng thái cần thử
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'xac_nhan'})  # gửi yêu cầu tới trang
        self.assertEqual(phan_hoi.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(phan_hoi, 'đang hậu kỳ')  # kiểm tra trang có hiện đoạn chữ mong đợi
        self.assertEqual(BanGiao.objects.count(), 0)  # kiểm tra hai giá trị bằng nhau

    def test_hanh_dong_la_hien_thong_bao_loi(self):  # tên test cho biết tình huống đang kiểm tra
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        self.assertContains(self.client.post(self.url(bk), {'hanh_dong': 'xoa'}), 'Thao tác không hợp lệ')  # kiểm tra trang có hiện đoạn chữ mong đợi

    def test_loi_tai_anh_2a_hien_thong_bao(self):              # ngoại lệ 2a
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        with mock.patch('delivery.views.services.anh_de_chinh_sua', side_effect=DatabaseError('hỏng')):  # giả lập lỗi database để thử
            trang = self.client.get(self.url(bk))  # gửi yêu cầu tới trang
        self.assertEqual(trang.status_code, 200)  # kiểm tra hai giá trị bằng nhau
        self.assertContains(trang, 'Không thể tải ảnh hậu kỳ')  # kiểm tra trang có hiện đoạn chữ mong đợi

    def test_loi_cap_nhat_5a_hien_thong_bao_va_giu_nguyen(self):   # ngoại lệ 5a trên giao diện
        bk = self.tao_booking_cho_kiem_tra()  # tạo Booking Chờ Khách hàng kiểm tra kèm ảnh đã hậu kỳ
        self.client.force_login(self.kh)  # đăng nhập bằng tài khoản cần thử
        with mock.patch.object(BanGiao.objects, 'create', side_effect=DatabaseError('hỏng')):  # giả lập lỗi database để thử
            phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'xac_nhan'})  # gửi yêu cầu tới trang
        self.assertContains(phan_hoi, 'Không thể cập nhật trạng thái bàn giao')  # kiểm tra trang có hiện đoạn chữ mong đợi
        bk.refresh_from_db()  # đọc lại dữ liệu mới nhất từ database
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)  # kiểm tra hai giá trị bằng nhau

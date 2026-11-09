# Chạy: python manage.py test bookings   # lệnh chạy toàn bộ test của app "bookings"
from datetime import date, time, timedelta  # date: ngày; time: giờ; timedelta: khoảng thời gian để cộng/trừ
from unittest import mock  # mock.patch: giả lập hàm bị lỗi trong test

from django.contrib.auth import get_user_model  # lấy class User mà dự án đang dùng (có thể là User tự tạo)
from django.core.exceptions import ValidationError  # loại lỗi mà hàm services ném ra, test sẽ bắt lỗi này
from django.test import TestCase  # lớp test của Django: mỗi test chạy trong transaction rồi tự rollback, DB luôn sạch
from django.utils import timezone  # lấy giờ hiện tại có múi giờ

from bookings.models import Booking, LichSuTrangThaiBooking  # 2 bảng cần tạo/kiểm tra
from bookings.services import CHUYEN_HOP_LE, chuyen_trang_thai_booking  # bảng chuyển hợp lệ + hàm đang được test
from core.constants import BenThucHien as BEN  # tên ngắn BEN cho 3 bên thực hiện (KHACH_HANG, NHIEP_ANH_GIA, HE_THONG)
from core.constants import LoaiHauKy, TrangThaiSlot  # loại hậu kỳ của gói; trạng thái slot
from core.constants import TrangThaiBooking as TT  # tên ngắn TT cho các trạng thái Booking
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia  # gói dịch vụ, loại hình chụp, hồ sơ nhiếp ảnh gia
from schedule.models import LichKhaDung  # slot lịch khả dụng của nhiếp ảnh gia

User = get_user_model()  # class User thực tế của dự án, dùng để tạo tài khoản


class ChuyenTrangThaiBookingTests(TestCase):  # nhóm test cho hàm chuyen_trang_thai_booking
    @classmethod  # chạy 1 lần cho cả class (không chạy lại từng test) -> nhanh hơn
    def setUpTestData(cls):  # chuẩn bị dữ liệu nền dùng chung cho mọi test
        cls.kh = User.objects.create_user('kh', 'kh@x.vn', 'p', so_dien_thoai='0900000001')  # tạo tài khoản Khách hàng (username, email, mật khẩu, SĐT)
        nag_user = User.objects.create_user('nag', 'nag@x.vn', 'p', so_dien_thoai='0900000002')  # tạo tài khoản dành cho Nhiếp ảnh gia
        cls.nag = NhiepAnhGia.objects.create(  # tạo hồ sơ Nhiếp ảnh gia gắn với tài khoản trên
            MaTaiKhoan=nag_user, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',  # tài khoản, ảnh, giới thiệu, ngân hàng (giá trị giả cho đủ trường)
            SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')  # số TK, chủ TK, ảnh QR (giá trị giả)
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')  # tạo loại hình chụp "Cưới"
        cls.goi_gioi_han = GoiDichVu.objects.create(  # gói loại "Giới hạn số lượng ảnh" (phải qua bước Khách chọn ảnh)
            MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G1', Gia=1000000, ThoiLuongChup=60,  # thuộc nhiếp ảnh gia, loại hình, tên, giá, thời lượng (phút)
            LoaiHauKy=LoaiHauKy.GIOI_HAN, SoAnhHauKyToiDa=10)  # hậu kỳ giới hạn, tối đa 10 ảnh
        cls.goi_toan_bo = GoiDichVu.objects.create(  # gói loại "Hậu kỳ toàn bộ" (bỏ qua bước chọn ảnh)
            MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G2', Gia=2000000, ThoiLuongChup=60,
            LoaiHauKy=LoaiHauKy.TOAN_BO)  # hậu kỳ toàn bộ nên không cần SoAnhHauKyToiDa

    def tao_booking(self, trang_thai=TT.CHO_XAC_NHAN, goi=None):  # hàm phụ: tạo nhanh 1 Booking ở trạng thái bất kỳ để test từng bước
        # Mỗi Booking một slot riêng (ngày khác nhau) để không đụng ràng buộc "một slot một Booking còn hiệu lực"
        self.__class__.dem = getattr(self.__class__, 'dem', 0) + 1  # biến đếm lưu ở class: lần đầu = 0, mỗi lần gọi +1 -> mỗi Booking có ngày khác nhau
        lich = LichKhaDung.objects.create(  # tạo 1 slot lịch riêng cho Booking này
            MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=10 + self.__class__.dem),  # ngày = hôm nay + 10 + số đếm (không trùng nhau)
            GioBatDau=time(8, 0), GioKetThuc=time(9, 0))  # khung giờ 8:00 - 9:00
        goi = goi or self.goi_gioi_han  # nếu không truyền gói thì mặc định dùng gói giới hạn
        bk = Booking.objects.create(  # tạo Booking (lúc này trạng thái là mặc định)
            MaKhachHang=self.kh, MaNhiepAnhGia=self.nag, MaGoi=goi, MaLich=lich,  # khách, nhiếp ảnh gia, gói, slot
            NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2, Concept='c',  # chụp sau 30 ngày, địa điểm, số người, concept
            TongGiaTri=goi.Gia)  # tổng giá trị = giá của gói
        # Đặt thẳng trạng thái để thử từng bước (test được phép, code thật thì không)
        # Slot đi kèm cho đúng thực tế: đang giữ trước khi chốt, đã đặt từ khi chốt, trống khi Booking kết thúc không thành
        if trang_thai in (TT.CHO_XAC_NHAN, TT.CHO_DAT_COC):  # chưa chốt -> slot đang được giữ chỗ
            slot = TrangThaiSlot.DANG_GIU
        elif trang_thai in (TT.DA_TU_CHOI, TT.HET_THOI_HAN_DAT_COC, TT.DA_HUY):  # kết thúc không thành -> slot được trả về trống
            slot = TrangThaiSlot.TRONG
        else:  # các trạng thái từ "Chốt Booking" trở đi -> slot đã đặt
            slot = TrangThaiSlot.DA_DAT
        LichKhaDung.objects.filter(pk=lich.pk).update(TrangThai=slot)  # ghi trạng thái slot thẳng vào DB (bỏ qua kiểm tra)
        Booking.objects.filter(pk=bk.pk).update(  # ghi trạng thái Booking thẳng vào DB, bỏ qua hàm services để dựng tình huống
            TrangThai=trang_thai,  # trạng thái muốn thử
            LyDoTuChoi='x' if trang_thai == TT.DA_TU_CHOI else None)  # DB có CHECK: "Đã từ chối" phải có lý do, trạng thái khác phải NULL
        bk.refresh_from_db()  # nạp lại đối tượng từ DB để có dữ liệu mới
        return bk  # trả Booking đã sẵn sàng để test

    def test_chuyen_hop_le_ghi_lich_su(self):  # test: chuyển đúng luật thì đổi trạng thái VÀ ghi lịch sử
        bk = self.tao_booking()  # Booking mặc định ở "Chờ xác nhận"
        kq = chuyen_trang_thai_booking(bk, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA)  # nhiếp ảnh gia chấp nhận
        self.assertEqual(kq.TrangThai, TT.CHO_DAT_COC)  # đối tượng trả về đã có trạng thái mới
        bk.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)  # DB cũng đã lưu trạng thái mới
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk)  # lấy dòng lịch sử (get = phải có đúng 1 dòng)
        self.assertEqual((ls.TrangThaiCu, ls.TrangThaiMoi, ls.BenThucHien),  # kiểm tra 3 thông tin trong lịch sử
                         (TT.CHO_XAC_NHAN, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA))  # cũ, mới, bên thực hiện
        self.assertIsNotNone(ls.ThoiDiemThayDoi)  # có ghi thời điểm thay đổi

    def test_nhan_ma_booking_thay_vi_doi_tuong(self):  # test: hàm nhận được cả mã số, không chỉ đối tượng
        bk = self.tao_booking()
        chuyen_trang_thai_booking(bk.pk, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA)  # truyền bk.pk (mã) thay vì bk
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)  # vẫn đổi đúng

    def test_buoc_khong_co_trong_bang_bi_cam_va_khong_ghi_gi(self):  # test: bước ngoài bảng bị cấm và không để lại dấu vết
        bk = self.tao_booking()
        with self.assertRaises(ValidationError):  # mong đợi hàm ném ValidationError
            chuyen_trang_thai_booking(bk, TT.HOAN_THANH, BEN.NHIEP_ANH_GIA)  # nhảy từ "Chờ xác nhận" thẳng "Hoàn thành" -> cấm
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_XAC_NHAN)  # trạng thái giữ nguyên
        self.assertEqual(LichSuTrangThaiBooking.objects.count(), 0)  # không có dòng lịch sử nào

    def test_sai_ben_thuc_hien(self):  # test: sai người làm thì bị từ chối
        bk = self.tao_booking()
        with self.assertRaises(ValidationError):   # Khách không được tự chấp nhận Booking
            chuyen_trang_thai_booking(bk, TT.CHO_DAT_COC, BEN.KHACH_HANG)

    def test_gia_tri_khong_hop_le(self):  # test: tham số rác đều bị bắt
        bk = self.tao_booking()
        with self.assertRaises(ValidationError):  # trạng thái mới không tồn tại
            chuyen_trang_thai_booking(bk, 'Trạng thái lạ', BEN.HE_THONG)
        with self.assertRaises(ValidationError):  # bên thực hiện không tồn tại
            chuyen_trang_thai_booking(bk, TT.CHO_DAT_COC, 'Quản trị viên')
        with self.assertRaises(ValidationError):  # mã Booking không tồn tại
            chuyen_trang_thai_booking(999999, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA)

    def test_tu_choi_can_ly_do_va_ghi_LyDoTuChoi(self):  # test: từ chối phải có lý do và lý do được lưu đúng chỗ
        bk = self.tao_booking()
        for ly_do in (None, '', '   '):  # 3 kiểu "không có lý do": None, rỗng, toàn dấu cách
            with self.assertRaises(ValidationError):  # đều phải bị từ chối
                chuyen_trang_thai_booking(bk, TT.DA_TU_CHOI, BEN.NHIEP_ANH_GIA, ly_do)
        kq = chuyen_trang_thai_booking(bk, TT.DA_TU_CHOI, BEN.NHIEP_ANH_GIA, '  Trùng lịch  ')  # lý do hợp lệ, có dấu cách thừa 2 đầu
        bk.refresh_from_db()
        self.assertEqual(bk.LyDoTuChoi, 'Trùng lịch')  # DB lưu lý do đã được cắt khoảng trắng
        self.assertEqual(kq.LyDoTuChoi, 'Trùng lịch')  # đối tượng trả về cũng có lý do đó
        self.assertEqual(LichSuTrangThaiBooking.objects.get().LyDo, 'Trùng lịch')  # lịch sử cũng ghi lý do (get() không tham số = bảng chỉ có đúng 1 dòng)

    def test_huy_can_ly_do_ca_hai_ben(self):  # test: hủy cần lý do, cả Khách và Nhiếp ảnh gia đều được hủy
        for trang_thai in (TT.CHO_DAT_COC, TT.CHOT_BOOKING):  # 2 trạng thái được phép hủy
            for ben in (BEN.KHACH_HANG, BEN.NHIEP_ANH_GIA):  # 2 bên được phép hủy
                bk = self.tao_booking(trang_thai)  # mỗi tổ hợp 1 Booking mới
                with self.assertRaises(ValidationError):  # hủy không lý do -> lỗi
                    chuyen_trang_thai_booking(bk, TT.DA_HUY, ben)
                chuyen_trang_thai_booking(bk, TT.DA_HUY, ben, 'Bận')  # hủy có lý do -> thành công
                bk.refresh_from_db()
                self.assertEqual(bk.TrangThai, TT.DA_HUY)  # đã ở "Đã hủy"
                self.assertIsNone(bk.LyDoTuChoi)  # LyDoTuChoi chỉ dành cho từ chối nên phải là None khi hủy

    def test_sau_khi_chup_khong_huy_duoc(self):  # test: từ "Đã chụp" trở đi không được hủy
        for trang_thai in (TT.DA_CHUP, TT.CHO_HAU_KY, TT.DANG_HAU_KY, TT.HOAN_THANH):
            bk = self.tao_booking(trang_thai)
            with self.assertRaises(ValidationError):  # hủy ở các trạng thái này đều bị cấm
                chuyen_trang_thai_booking(bk, TT.DA_HUY, BEN.KHACH_HANG, 'Bận')

    def test_trang_thai_ket_thuc_khong_di_tiep(self):  # test: trạng thái kết thúc là ngõ cụt
        for trang_thai in (TT.DA_TU_CHOI, TT.HET_THOI_HAN_DAT_COC, TT.DA_HUY, TT.HOAN_THANH):  # 4 trạng thái kết thúc
            bk = self.tao_booking(trang_thai)
            for moi in TT.ALL:  # thử đi sang MỌI trạng thái
                for ben in (BEN.KHACH_HANG, BEN.NHIEP_ANH_GIA, BEN.HE_THONG):  # bởi MỌI bên
                    with self.assertRaises(ValidationError):  # tất cả đều phải bị cấm
                        chuyen_trang_thai_booking(bk, moi, ben, 'x')

    def test_het_han_dat_coc_chi_he_thong(self):  # test: "Hết hạn đặt cọc" chỉ Hệ thống được làm
        bk = self.tao_booking(TT.CHO_DAT_COC)
        with self.assertRaises(ValidationError):  # Khách không được tự đánh dấu hết hạn
            chuyen_trang_thai_booking(bk, TT.HET_THOI_HAN_DAT_COC, BEN.KHACH_HANG)
        chuyen_trang_thai_booking(bk, TT.HET_THOI_HAN_DAT_COC, BEN.HE_THONG, 'Quá 1 ngày chưa đặt cọc')  # Hệ thống làm thì được
        self.assertEqual(LichSuTrangThaiBooking.objects.get().BenThucHien, BEN.HE_THONG)  # lịch sử ghi bên thực hiện là Hệ thống

    def test_cho_xac_nhan_chi_he_thong_tu_huy(self):  # test: "Chờ xác nhận -> Đã hủy" chỉ Hệ thống được làm (quá giờ chụp mà chưa xác nhận)
        bk = self.tao_booking(TT.CHO_XAC_NHAN)
        for ben in (BEN.KHACH_HANG, BEN.NHIEP_ANH_GIA):  # Khách và Nhiếp ảnh gia không được hủy ở bước này
            with self.assertRaises(ValidationError):
                chuyen_trang_thai_booking(bk, TT.DA_HUY, ben, 'Bận')
        chuyen_trang_thai_booking(bk, TT.DA_HUY, BEN.HE_THONG, 'Quá giờ chụp mà Nhiếp ảnh gia chưa xác nhận')  # Hệ thống làm thì được
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.DA_HUY)  # đã ở "Đã hủy"
        self.assertIsNone(bk.LyDoTuChoi)  # đây là hủy chứ không phải từ chối nên không lưu LyDoTuChoi
        self.assertEqual(LichSuTrangThaiBooking.objects.get().BenThucHien, BEN.HE_THONG)  # lịch sử ghi bên thực hiện là Hệ thống

    def test_goi_gioi_han_phai_qua_buoc_chon_anh(self):  # test: gói giới hạn không được bỏ qua bước chọn ảnh
        bk = self.tao_booking(TT.DA_CHUP, self.goi_gioi_han)
        with self.assertRaises(ValidationError):  # nhảy thẳng vào hậu kỳ -> cấm
            chuyen_trang_thai_booking(bk, TT.CHO_HAU_KY, BEN.NHIEP_ANH_GIA)
        chuyen_trang_thai_booking(bk, TT.CHO_KH_CHON_ANH, BEN.NHIEP_ANH_GIA)  # đi qua bước chọn ảnh -> được

    def test_goi_toan_bo_bo_qua_buoc_chon_anh(self):  # test: gói toàn bộ thì không có bước chọn ảnh
        bk = self.tao_booking(TT.DA_CHUP, self.goi_toan_bo)
        with self.assertRaises(ValidationError):  # đi vào bước chọn ảnh -> cấm
            chuyen_trang_thai_booking(bk, TT.CHO_KH_CHON_ANH, BEN.NHIEP_ANH_GIA)
        chuyen_trang_thai_booking(bk, TT.CHO_HAU_KY, BEN.NHIEP_ANH_GIA)  # vào thẳng hậu kỳ -> được

    def test_di_het_quy_trinh_goi_gioi_han(self):  # test: chạy trọn quy trình từ đầu đến "Hoàn thành"
        bk = self.tao_booking(TT.CHO_XAC_NHAN, self.goi_gioi_han)
        buoc = [(TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA), (TT.CHOT_BOOKING, BEN.NHIEP_ANH_GIA),  # danh sách (trạng thái mới, bên làm) theo thứ tự
                (TT.DA_CHUP, BEN.NHIEP_ANH_GIA), (TT.CHO_KH_CHON_ANH, BEN.NHIEP_ANH_GIA),
                (TT.CHO_HAU_KY, BEN.KHACH_HANG), (TT.DANG_HAU_KY, BEN.NHIEP_ANH_GIA),
                (TT.CHO_KH_KIEM_TRA, BEN.NHIEP_ANH_GIA), (TT.CHO_XAC_NHAN_THANH_TOAN, BEN.KHACH_HANG),
                (TT.HOAN_THANH, BEN.NHIEP_ANH_GIA)]
        for moi, ben in buoc:  # đi lần lượt từng bước
            chuyen_trang_thai_booking(bk, moi, ben)  # lỗi ở bước nào thì test fail ngay
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HOAN_THANH)  # cuối cùng phải là "Hoàn thành"
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk).count(), len(buoc))  # số dòng lịch sử = số bước đã đi

    def test_khach_yeu_cau_chinh_sua_quay_lai_hau_ky(self):  # test: Khách yêu cầu chỉnh sửa thì quay lại hậu kỳ
        bk = self.tao_booking(TT.CHO_KH_KIEM_TRA)
        for ben in (BEN.NHIEP_ANH_GIA, BEN.HE_THONG):  # chỉ Khách được yêu cầu chỉnh sửa
            with self.assertRaises(ValidationError):
                chuyen_trang_thai_booking(bk, TT.DANG_HAU_KY, ben)
        chuyen_trang_thai_booking(bk, TT.DANG_HAU_KY, BEN.KHACH_HANG, 'Chỉnh màu ảnh 3')  # Khách yêu cầu kèm lý do
        chuyen_trang_thai_booking(bk, TT.CHO_KH_KIEM_TRA, BEN.NHIEP_ANH_GIA)  # nhiếp ảnh gia sửa xong, gửi lại
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_KH_KIEM_TRA)  # lại về trạng thái chờ Khách kiểm tra

    def test_het_han_chon_anh_khong_tu_chuyen(self):  # test: quá hạn chọn ảnh KHÔNG tự chuyển (theo TO-BE)
        bk = self.tao_booking(TT.CHO_KH_CHON_ANH)
        with self.assertRaises(ValidationError):  # Hệ thống không được tự chuyển sang hậu kỳ
            chuyen_trang_thai_booking(bk, TT.CHO_HAU_KY, BEN.HE_THONG)

    def test_gan_han_theo_to_be(self):  # test: vào trạng thái nào thì gán đúng hạn chót và đúng số ngày
        cac_ca = [  # (trạng thái trước, gói, trạng thái mới, bên làm, tên cột hạn, số ngày)
            (TT.CHO_XAC_NHAN, None, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA, 'HanDatCoc', 1),  # chấp nhận -> hạn cọc 1 ngày
            (TT.DA_CHUP, self.goi_gioi_han, TT.CHO_KH_CHON_ANH, BEN.NHIEP_ANH_GIA, 'HanChonAnh', 2),  # chờ chọn ảnh -> hạn 2 ngày
            (TT.CHO_HAU_KY, None, TT.DANG_HAU_KY, BEN.NHIEP_ANH_GIA, 'HanHauKy', 3),  # hạn hậu kỳ tính từ lúc vào "Đang hậu kỳ"
            (TT.CHO_KH_KIEM_TRA, None, TT.DANG_HAU_KY, BEN.KHACH_HANG, 'HanHauKy', 3),  # Khách yêu cầu chỉnh sửa: tính lại 3 ngày
            (TT.CHO_KH_KIEM_TRA, None, TT.CHO_XAC_NHAN_THANH_TOAN, BEN.KHACH_HANG, 'HanThanhToanConLai', 2),  # chờ thanh toán 60% -> 2 ngày
        ]
        for truoc, goi, moi, ben, ten_han, ngay in cac_ca:
            bk = self.tao_booking(truoc, goi)
            self.assertIsNone(getattr(bk, ten_han))  # trước khi chuyển, cột hạn còn trống (getattr lấy field theo tên chuỗi)
            chuyen_trang_thai_booking(bk, moi, ben)
            bk.refresh_from_db()
            ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk)  # lấy thời điểm đổi từ lịch sử
            self.assertEqual(getattr(bk, ten_han), ls.ThoiDiemThayDoi + timedelta(days=ngay))  # hạn = thời điểm đổi + số ngày quy định

    def test_vao_cho_hau_ky_chua_gan_han_hau_ky(self):  # test: vào "Chờ hậu kỳ" thì CHƯA tính hạn 3 ngày (chỉ tính khi vào "Đang hậu kỳ")
        for truoc, goi, ben in ((TT.CHO_KH_CHON_ANH, None, BEN.KHACH_HANG),  # đường gói giới hạn: Khách chọn ảnh xong
                                (TT.DA_CHUP, self.goi_toan_bo, BEN.NHIEP_ANH_GIA)):  # đường gói toàn bộ: từ "Đã chụp"
            bk = self.tao_booking(truoc, goi)
            chuyen_trang_thai_booking(bk, TT.CHO_HAU_KY, ben)
            bk.refresh_from_db()
            self.assertIsNone(bk.HanHauKy)  # hạn hậu kỳ vẫn trống

    def test_slot_doi_theo_booking(self):  # test: slot đổi trạng thái đi kèm Booking
        cac_ca = [  # (trạng thái trước, trạng thái mới, bên làm, trạng thái slot mong đợi)
            (TT.CHO_XAC_NHAN, TT.DA_TU_CHOI, BEN.NHIEP_ANH_GIA, TrangThaiSlot.TRONG),  # từ chối -> slot trống
            (TT.CHO_DAT_COC, TT.CHOT_BOOKING, BEN.NHIEP_ANH_GIA, TrangThaiSlot.DA_DAT),  # chốt -> slot đã đặt
            (TT.CHO_DAT_COC, TT.HET_THOI_HAN_DAT_COC, BEN.HE_THONG, TrangThaiSlot.TRONG),  # hết hạn cọc -> slot trống
            (TT.CHO_DAT_COC, TT.DA_HUY, BEN.KHACH_HANG, TrangThaiSlot.TRONG),  # Khách hủy -> slot trống
            (TT.CHOT_BOOKING, TT.DA_HUY, BEN.NHIEP_ANH_GIA, TrangThaiSlot.TRONG),  # nhiếp ảnh gia hủy sau khi chốt -> slot trống
            (TT.CHO_XAC_NHAN, TT.DA_HUY, BEN.HE_THONG, TrangThaiSlot.TRONG),  # hệ thống tự hủy (quá giờ chụp chưa xác nhận) -> slot trống
            (TT.CHO_XAC_NHAN, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA, TrangThaiSlot.DANG_GIU),  # chấp nhận: slot vẫn giữ
        ]
        for truoc, moi, ben, slot_mong_doi in cac_ca:
            bk = self.tao_booking(truoc)
            chuyen_trang_thai_booking(bk, moi, ben, 'lý do')  # truyền 'lý do' cho đủ, bước không cần thì bị bỏ qua
            self.assertEqual(LichKhaDung.objects.get(pk=bk.MaLich_id).TrangThai, slot_mong_doi, (truoc, moi))  # so sánh slot thực tế; (truoc, moi) in ra khi fail để biết ca nào sai

    def test_slot_bi_nha_nham_duoc_tu_khoi_phuc_khi_chot(self):  # test: slot bị nhả nhầm (Trống) thì chốt Booking vẫn thành công
        bk = self.tao_booking(TT.CHO_DAT_COC)  # tạo Booking đang Chờ đặt cọc
        LichKhaDung.objects.filter(pk=bk.MaLich_id).update(TrangThai=TrangThaiSlot.TRONG)  # dữ liệu lệch: slot bị nhả về Trống
        chuyen_trang_thai_booking(bk, TT.CHOT_BOOKING, BEN.NHIEP_ANH_GIA)  # chốt Booking: hàm tự đặt slot lại Đang giữ rồi mới sang Đã đặt
        bk.refresh_from_db()  # nạp lại Booking từ database
        self.assertEqual(bk.TrangThai, TT.CHOT_BOOKING)  # Booking đã chuyển sang Chốt Booking
        self.assertEqual(LichKhaDung.objects.get(pk=bk.MaLich_id).TrangThai, TrangThaiSlot.DA_DAT)  # slot cuối cùng là Đã đặt lịch

    def test_slot_loi_thi_rollback_ca_booking(self):  # test: đổi slot báo lỗi thì hoàn tác cả Booking lẫn lịch sử
        bk = self.tao_booking(TT.CHO_DAT_COC)  # tạo Booking đang Chờ đặt cọc
        with mock.patch('bookings.services.doi_trang_thai_khung_gio',  # giả lập hàm đổi slot của Khoa bị lỗi
                        side_effect=ValidationError('Lỗi slot giả lập.')):  # hàm giả ném ValidationError
            with self.assertRaises(ValidationError):  # chốt Booking phải báo lỗi theo
                chuyen_trang_thai_booking(bk, TT.CHOT_BOOKING, BEN.NHIEP_ANH_GIA)  # thử chốt Booking
        bk.refresh_from_db()  # nạp lại Booking từ database
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)  # Booking vẫn như cũ (đã rollback)
        self.assertEqual(LichSuTrangThaiBooking.objects.count(), 0)  # lịch sử cũng không được ghi

    def test_ban_cu_trong_bo_nho_khong_qua_mat(self):  # test: chống ghi đè khi 2 người cầm cùng bản cũ
        # Hai người cùng cầm một bản Booking cũ: người thứ hai phải bị từ chối, không ghi đè.
        bk_a = self.tao_booking()
        bk_b = Booking.objects.get(pk=bk_a.pk)  # bản sao thứ hai, vẫn nghĩ trạng thái là "Chờ xác nhận"
        chuyen_trang_thai_booking(bk_a, TT.DA_TU_CHOI, BEN.NHIEP_ANH_GIA, 'Bận')  # người A từ chối trước
        with self.assertRaises(ValidationError):  # người B (bản cũ) chấp nhận -> phải lỗi vì DB đã là "Đã từ chối"
            chuyen_trang_thai_booking(bk_b, TT.CHO_DAT_COC, BEN.NHIEP_ANH_GIA)
        self.assertEqual(Booking.objects.get(pk=bk_a.pk).TrangThai, TT.DA_TU_CHOI)  # kết quả của A không bị B ghi đè

    def test_ly_do_qua_dai(self):  # test: lý do dài hơn 255 ký tự bị từ chối
        bk = self.tao_booking()
        with self.assertRaises(ValidationError):
            chuyen_trang_thai_booking(bk, TT.DA_TU_CHOI, BEN.NHIEP_ANH_GIA, 'x' * 256)  # 'x' * 256 = chuỗi 256 chữ x

    def test_bang_chuyen_chi_dung_trang_thai_co_that(self):  # test: bảng CHUYEN_HOP_LE không gõ nhầm tên trạng thái
        for (cu, moi), bens in CHUYEN_HOP_LE.items():  # duyệt từng dòng của bảng
            self.assertIn(cu, TT.ALL)  # trạng thái cũ phải có thật
            self.assertIn(moi, TT.ALL)  # trạng thái mới phải có thật
            self.assertTrue(bens)  # tập bên được phép không được rỗng
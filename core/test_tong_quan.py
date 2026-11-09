# core/test_tong_quan.py - B9: kiểm tra Trang tổng quan sau đăng nhập. Chạy: python manage.py test core.test_tong_quan
# Mỗi hàm test_... là MỘT tình huống; test chạy trên cơ sở dữ liệu tạm, không đụng dữ liệu thật.
from datetime import timedelta  # timedelta: một khoảng thời gian (ví dụ 3 ngày, 1 giờ)

from django.test import TestCase, override_settings  # TestCase: lớp test có cơ sở dữ liệu tạm; override_settings: đổi cài đặt chỉ trong lúc test
from django.urls import reverse  # từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # lấy giờ hiện tại có múi giờ

from accounts.permissions import url_trang_chu  # hàm cho biết trang đích sau đăng nhập của một người
from bookings.models import Booking  # bảng Booking
from bookings.test_tiep_nhan import tao_nag, tao_user          # hàm dựng tài khoản / Nhiếp ảnh gia mẫu của nhóm Booking
from core.constants import (KetQuaDuyetHoSo, LoaiHauKy, TrangThaiBooking as BK, TrangThaiDoc, TrangThaiHoSo,  # tên các kết quả / trạng thái dùng chung
                            TrangThaiSlot as SL, VaiTro)  # trạng thái khung giờ, vai trò
from notifications.models import ThongBao  # bảng thông báo
from profiles.models import DuyetHoSo, GoiDichVu, LoaiHinhChup  # bảng lượt duyệt hồ sơ, gói dịch vụ, loại hình chụp
from schedule.models import LichKhaDung  # bảng khung giờ khả dụng

URL = '/tong-quan/'  # địa chỉ trang đang được test


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # băm mật khẩu nhanh cho test
class TongQuanBase(TestCase):  # lớp nền: dựng dữ liệu mẫu dùng chung cho mọi nhóm test bên dưới
    def setUp(self):  # chạy TRƯỚC mỗi test: dựng lại dữ liệu từ đầu
        self.khach = tao_user('khach_a', VaiTro.KHACH_HANG, first_name='An', last_name='Nguyễn')  # Khách hàng chính
        self.khach_b = tao_user('khach_b', VaiTro.KHACH_HANG)  # Khách hàng khác (để kiểm tra Booking người khác không lọt vào)
        self.nag = tao_nag('nag')  # Nhiếp ảnh gia chính (hồ sơ Đã duyệt)
        self.nag_khac = tao_nag('nag_khac')  # Nhiếp ảnh gia khác
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')  # một loại hình chụp
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='Gói cơ bản',  # gói của Nhiếp ảnh gia chính
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)  # giá 1,5 triệu, chụp 60 phút, hậu kỳ toàn bộ
        self.goi_khac = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag_khac, MaLoaiHinh=loai,  # gói của Nhiếp ảnh gia khác
                                                 TenGoi='Gói người khác', Gia=2000000, ThoiLuongChup=60,  # giá 2 triệu, chụp 60 phút
                                                 LoaiHauKy=LoaiHauKy.TOAN_BO)  # hậu kỳ toàn bộ
        self.ngay = timezone.localdate() + timedelta(days=3)  # ngày chụp thử: 3 ngày nữa (để thuộc "lịch sắp tới")
        self._gio = 7  # bộ đếm giờ: mỗi Booking một khung giờ riêng, bắt đầu từ 7 giờ

    def tao_booking(self, nag=None, khach=None, trang_thai=BK.CHO_XAC_NHAN):  # hàm trợ giúp: tạo nhanh một Booking
        nag = nag or self.nag  # không truyền thì dùng Nhiếp ảnh gia chính
        goi = self.goi if nag == self.nag else self.goi_khac  # chọn gói đúng của Nhiếp ảnh gia đó
        self._gio += 1                                   # mỗi Booking một khung giờ riêng
        gio = f'{self._gio:02d}:00'  # đổi số giờ thành chữ, ví dụ 8 -> '08:00'
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=self.ngay, GioBatDau=gio,  # tạo khung giờ cho Booking
                                          GioKetThuc=f'{self._gio + 2:02d}:00', TrangThai=SL.DANG_GIU)  # dài 2 tiếng, đang được giữ chỗ
        return Booking.objects.create(  # tạo Booking trong cơ sở dữ liệu tạm và trả về
            MaKhachHang=khach or self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,  # Khách (mặc định Khách chính), Nhiếp ảnh gia, gói, khung giờ
            NgayGioChup=timezone.make_aware(timezone.datetime.combine(self.ngay, timezone.datetime.strptime(gio, '%H:%M').time())),  # giờ chụp = ngày chụp thử + giờ của khung
            DiaDiem='Hồ Gươm', SoNguoi=2, Concept='Vintage', TrangThai=trang_thai)  # thông tin mặc định + trạng thái truyền vào

    def mo(self, user):  # hàm trợ giúp: đăng nhập bằng một tài khoản rồi mở trang tổng quan
        self.client.force_login(user)  # đăng nhập không cần gõ mật khẩu
        return self.client.get(URL)  # mở trang và trả về kết quả


class TruyCap(TongQuanBase):  # nhóm test: ai được vào / bị chuyển đi đâu
    def test_chua_dang_nhap_chuyen_ve_dang_nhap(self):  # tình huống: chưa đăng nhập
        res = self.client.get(URL)  # mở trang khi chưa đăng nhập
        self.assertRedirects(res, f"{reverse('login')}?next={URL}", fetch_redirect_response=False)  # bị chuyển về đăng nhập, nhớ quay lại trang này sau đó

    def test_quan_tri_chuyen_sang_trang_quan_tri(self):  # tình huống: Quản trị viên vào trang này
        admin = tao_user('qt', VaiTro.QUAN_TRI_VIEN)  # tạo một Quản trị viên
        self.assertRedirects(self.mo(admin), reverse('admin_dashboard'), fetch_redirect_response=False)  # bị chuyển sang trang tổng quan riêng của Quản trị

    def test_trang_dich_sau_dang_nhap(self):  # tình huống: đăng nhập xong đi đâu
        self.assertEqual(reverse('dashboard'), URL)  # tên url 'dashboard' trỏ đúng /tong-quan/
        self.assertEqual(url_trang_chu(self.khach),
                         reverse('home'))  # Khách hàng về Trang chủ (B8), không vào Tổng quan
        self.assertEqual(url_trang_chu(self.nag.MaTaiKhoan), URL)  # Nhiếp ảnh gia vào Tổng quan


class KhachHang(TongQuanBase):  # nhóm test: trang của Khách hàng
    def test_chi_hien_booking_dang_xu_ly_cua_minh(self):  # tình huống: chỉ Booking đang xử lý của chính Khách
        dang = self.tao_booking(trang_thai=BK.CHO_DAT_COC)  # Booking đang xử lý của Khách
        self.tao_booking(trang_thai=BK.HOAN_THANH)  # đã hoàn thành -> không tính
        self.tao_booking(trang_thai=BK.DA_HUY)  # đã hủy -> không tính
        self.tao_booking(khach=self.khach_b)                          # của người khác
        res = self.mo(self.khach)  # Khách mở trang
        self.assertEqual(res.status_code, 200)  # trang mở được
        self.assertTemplateUsed(res, 'core/tong_quan.html')  # dùng đúng template
        self.assertEqual(res.context['khach']['so_dang_xu_ly'], 1)  # chỉ đếm 1 Booking
        self.assertEqual([b['ma'] for b in res.context['khach']['dang_xu_ly']], [dang.pk])  # và đúng Booking đó
        self.assertContains(res, reverse('chi_tiet_booking', args=[dang.pk]))  # trang có link sang chi tiết Booking
        self.assertContains(res, BK.CHO_DAT_COC)  # trang có chữ trạng thái "Chờ đặt cọc"

    def test_chua_co_booking_hien_cau_trong(self):  # tình huống: chưa có Booking nào
        res = self.mo(self.khach)  # Khách mở trang
        self.assertContains(res, 'Bạn chưa có Booking nào đang xử lý.')  # câu báo trống
        self.assertContains(res, 'Tìm nhiếp ảnh gia')  # nút gợi ý đi tìm Nhiếp ảnh gia

    def test_chi_hien_thong_bao_chua_doc_cua_minh(self):  # tình huống: chỉ thông báo chưa đọc của chính Khách
        ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe='Yêu cầu được chấp nhận', NoiDung='Hãy đặt cọc.')  # chưa đọc, của Khách
        ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe='Thông báo cũ', NoiDung='x', TrangThaiDoc=TrangThaiDoc.DA_DOC)  # đã đọc -> không hiện
        ThongBao.objects.create(MaNguoiNhan=self.khach_b, TieuDe='Của người khác', NoiDung='x')  # của Khách khác -> không hiện
        res = self.mo(self.khach)  # Khách mở trang
        self.assertContains(res, 'Yêu cầu được chấp nhận')  # thấy thông báo chưa đọc của mình
        self.assertNotContains(res, 'Thông báo cũ')  # không thấy thông báo đã đọc
        self.assertNotContains(res, 'Của người khác')  # không thấy thông báo của người khác
        self.assertEqual(res.context['khach']['so_thong_bao'], 1)  # số chưa đọc = 1

    def test_khong_co_thong_bao(self):  # tình huống: không có thông báo nào
        self.assertContains(self.mo(self.khach), 'Không có thông báo mới.')  # câu báo trống

    def test_thong_bao_moi_nhat_len_dau_roi_moi_cat_5(self):  # tình huống: thứ tự thông báo phải rõ ràng
        # Tạo từ MỚI nhất đến CŨ nhất, để mã (pk) ngược với thời gian: nếu chỉ dựa vào thứ tự tạo / mã thì sẽ lấy nhầm 5 cái cũ nhất.
        bay_gio = timezone.now()  # mốc thời gian để tính NgayTao
        for i in range(6, -1, -1):                                       # i = 6 là mới nhất, i = 0 là cũ nhất
            tb = ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe=f'TB{i}', NoiDung='x')  # tạo thông báo TB6, TB5, ... TB0
            ThongBao.objects.filter(pk=tb.pk).update(NgayTao=bay_gio - timedelta(hours=10 - i))   # NgayTao tự điền khi tạo, nên chỉnh lại bằng update: TB6 mới nhất
        res = self.mo(self.khach)  # Khách mở trang
        self.assertEqual([t['tieu_de'] for t in res.context['khach']['thong_bao']],  # tiêu đề các thông báo trang đưa ra
                         ['TB6', 'TB5', 'TB4', 'TB3', 'TB2'])            # 5 thông báo MỚI nhất, mới nhất lên đầu
        self.assertEqual(res.context['khach']['so_thong_bao'], 7)  # tổng số chưa đọc vẫn là 7 (không bị cắt)

    def test_chi_hien_toi_da_5_dong(self):  # tình huống: danh sách dài chỉ hiện 5 dòng
        for _ in range(7):  # tạo 7 Booking đang xử lý
            self.tao_booking()  # mỗi cái một khung giờ riêng
        res = self.mo(self.khach)  # Khách mở trang
        self.assertEqual(res.context['khach']['so_dang_xu_ly'], 7)  # số đếm vẫn là 7
        self.assertEqual(len(res.context['khach']['dang_xu_ly']), 5)  # nhưng chỉ đưa 5 dòng


class NhiepAnhGiaDaDuyet(TongQuanBase):  # nhóm test: trang của Nhiếp ảnh gia đã duyệt
    def test_yeu_cau_moi_va_lich_sap_toi(self):  # tình huống: phân đúng yêu cầu mới / lịch sắp tới, không lẫn người khác
        moi = self.tao_booking(trang_thai=BK.CHO_XAC_NHAN)  # yêu cầu mới
        chot = self.tao_booking(trang_thai=BK.CHOT_BOOKING)  # buổi chụp đã chốt, chưa tới giờ
        self.tao_booking(trang_thai=BK.HOAN_THANH)  # đã hoàn thành -> không vào hai nhóm trên
        self.tao_booking(nag=self.nag_khac)                           # Booking của Nhiếp ảnh gia khác
        res = self.mo(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia mở trang
        nag = res.context['nag']  # dữ liệu dành cho Nhiếp ảnh gia
        self.assertTrue(nag['da_duyet'])  # hồ sơ đã duyệt
        self.assertEqual(nag['so_yeu_cau_moi'], 1)  # 1 yêu cầu mới
        self.assertEqual([b['ma'] for b in nag['yeu_cau_moi']], [moi.pk])  # đúng Booking đó
        self.assertEqual(nag['so_lich_sap_toi'], 1)  # 1 buổi chụp sắp tới
        self.assertEqual([b['ma'] for b in nag['lich_sap_toi']], [chot.pk])  # đúng Booking đó
        self.assertContains(res, reverse('chi_tiet_yeu_cau_booking', args=[moi.pk]))  # có link sang màn xử lý
        self.assertContains(res, 'Yêu cầu Booking mới')  # có khối yêu cầu mới
        self.assertContains(res, 'Lịch sắp tới')  # có khối lịch sắp tới

    def test_dem_khung_gio_trong(self):  # tình huống: đếm khung giờ trống
        LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay, GioBatDau='06:00',  # tạo 1 khung giờ trống
                                   GioKetThuc='07:00', TrangThai=SL.TRONG)  # từ 6h đến 7h, còn trống
        self.assertEqual(self.mo(self.nag.MaTaiKhoan).context['nag']['so_khung_gio_trong'], 1)  # đếm được đúng 1

    def test_khong_co_gi(self):  # tình huống: chưa có yêu cầu / lịch nào
        res = self.mo(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia mở trang
        self.assertContains(res, 'Không có yêu cầu Booking mới.')  # câu báo trống 1
        self.assertContains(res, 'Chưa có buổi chụp nào sắp tới.')  # câu báo trống 2
        self.assertContains(res, TrangThaiHoSo.DA_DUYET)  # nhãn hồ sơ "Đã duyệt"


class NhiepAnhGiaChuaDuyet(TongQuanBase):  # nhóm test: Nhiếp ảnh gia chưa duyệt (chỉ thấy tình trạng hồ sơ)
    def _doi_trang_thai(self, trang_thai):  # hàm trợ giúp: đổi trạng thái hồ sơ trên tài khoản
        user = self.nag.MaTaiKhoan  # tài khoản của Nhiếp ảnh gia chính
        user.trang_thai_ho_so = trang_thai  # gán trạng thái mới
        user.save()  # lưu lại
        return user  # trả về tài khoản để đăng nhập

    def test_cho_duyet_chi_thay_tinh_trang_ho_so(self):  # tình huống: Chờ duyệt không thấy Booking
        self.tao_booking()  # có một Booking, nhưng không được hiện
        res = self.mo(self._doi_trang_thai(TrangThaiHoSo.CHO_DUYET))  # đổi sang Chờ duyệt rồi mở trang
        self.assertEqual(res.status_code, 200)  # trang vẫn mở được
        self.assertFalse(res.context['nag']['da_duyet'])  # chưa duyệt
        self.assertNotIn('yeu_cau_moi', res.context['nag'])  # không có dữ liệu Booking trong context
        self.assertContains(res, 'Tình trạng hồ sơ')  # có khối tình trạng hồ sơ
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')  # câu báo đang chờ
        self.assertNotContains(res, 'Yêu cầu Booking mới')  # không có khối yêu cầu mới
        self.assertNotContains(res, 'Lịch sắp tới')  # không có khối lịch

    def _tao_luot(self, lan, ket_qua=None, phan_hoi=None, cung_thoi_diem_nop=False):  # hàm trợ giúp: tạo một lượt duyệt hồ sơ
        """Tạo một lượt duyệt hồ sơ. ket_qua=None là lượt đang chờ duyệt (nộp / nộp lại).
        DuyetHoSo.save() tự đồng bộ User.trang_thai_ho_so theo lượt MỚI NHẤT (đúng như hệ thật).
        cung_thoi_diem_nop=True: mọi lượt cùng một ThoiDiemNop, để chỉ còn LanNop phân biệt lượt mới / cũ."""
        gio_nop = timezone.now() - timedelta(days=3) + (timedelta(0) if cung_thoi_diem_nop else timedelta(hours=lan))  # giờ nộp: 3 ngày trước (+ lan giờ nếu muốn lượt sau nộp muộn hơn)
        du_lieu = dict(MaNhiepAnhGia=self.nag, LanNop=lan, ThoiDiemNop=gio_nop)  # thông tin chung của mọi lượt
        if ket_qua:                                                     # ràng buộc DB: có kết quả thì có Quản trị viên + ThoiDiemDuyet >= ThoiDiemNop
            du_lieu.update(MaQuanTriVien=self.admin, ThoiDiemDuyet=timezone.now() - timedelta(days=1),  # người duyệt + giờ duyệt (1 ngày trước, sau giờ nộp)
                           KetQua=ket_qua, NoiDungPhanHoi=phan_hoi)  # kết quả + lý do
        return DuyetHoSo.objects.create(**du_lieu)  # lưu lượt duyệt vào cơ sở dữ liệu tạm

    def setUp(self):  # chạy trước mỗi test của nhóm này
        super().setUp()  # dựng dữ liệu nền
        self.admin = tao_user('qt', VaiTro.QUAN_TRI_VIEN)  # tạo Quản trị viên để ghi vào lượt duyệt

    def test_bi_tu_choi_hien_ly_do(self):  # tình huống: bị từ chối thì thấy lý do
        self._tao_luot(1, KetQuaDuyetHoSo.DA_TU_CHOI, 'Ảnh Portfolio chưa rõ nét.')       # save() đưa hồ sơ sang 'Đã từ chối'
        res = self.mo(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia mở trang
        self.assertContains(res, 'Ảnh Portfolio chưa rõ nét.')  # thấy lý do
        self.assertContains(res, TrangThaiHoSo.DA_TU_CHOI)  # thấy nhãn "Đã từ chối"
        self.assertFalse(res.context['nag']['can_chinh_sua'])  # không phải trường hợp "yêu cầu chỉnh sửa"

    def test_hai_luot_duyet_hien_ly_do_cua_luot_moi_nhat(self):  # tình huống: có 2 lượt duyệt, phải hiện lý do của lượt MỚI NHẤT
        # Hai lượt CÙNG ThoiDiemNop: chỉ LanNop phân biệt cũ / mới, nên chỉ đúng khi view sắp rõ ràng theo '-LanNop'.
        self._tao_luot(1, KetQuaDuyetHoSo.DA_TU_CHOI, 'Lý do của lượt cũ.', cung_thoi_diem_nop=True)  # lượt 1
        self._tao_luot(2, KetQuaDuyetHoSo.DA_TU_CHOI, 'Lý do của lượt mới nhất.', cung_thoi_diem_nop=True)  # lượt 2 (mới nhất)
        res = self.mo(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia mở trang
        self.assertEqual(res.context['nag']['phan_hoi'], 'Lý do của lượt mới nhất.')  # context mang lý do của lượt 2
        self.assertContains(res, 'Lý do của lượt mới nhất.')  # trang hiện lý do lượt 2
        self.assertNotContains(res, 'Lý do của lượt cũ.')  # không hiện lý do lượt 1

    def test_yeu_cau_chinh_sua_hien_ly_do_va_nut_cap_nhat(self):  # tình huống: Quản trị viên yêu cầu chỉnh sửa
        self._tao_luot(1, KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA, 'Bổ sung thêm 3 ảnh Portfolio.')  # lượt "Yêu cầu chỉnh sửa" kèm lý do
        user = self.nag.MaTaiKhoan  # tài khoản Nhiếp ảnh gia
        user.refresh_from_db()  # đọc lại từ cơ sở dữ liệu (save() của lượt duyệt đã đổi trạng thái)
        self.assertEqual(user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)  # quy ước nhóm: hồ sơ vẫn 'Chờ duyệt'
        res = self.mo(user)  # Nhiếp ảnh gia mở trang
        self.assertTrue(res.context['nag']['can_chinh_sua'])  # view nhận ra đây là "yêu cầu chỉnh sửa"
        self.assertContains(res, 'Quản trị viên yêu cầu chỉnh sửa hồ sơ')  # trang hiện câu yêu cầu
        self.assertContains(res, 'Bổ sung thêm 3 ảnh Portfolio.')  # kèm lý do
        self.assertContains(res, 'Cập nhật hồ sơ')                        # nút để sửa
        self.assertNotContains(res, 'đang chờ Quản trị viên duyệt')       # không hiện câu "đang chờ duyệt"
        self.assertNotContains(res, 'Yêu cầu Booking mới')                # vẫn chỉ thấy tình trạng hồ sơ

    def test_yeu_cau_chinh_sua_lan_dau_roi_nop_lai_hien_dang_cho_duyet(self):  # tình huống: đã nộp lại sau khi bị yêu cầu chỉnh sửa
        # Lượt 1: bị yêu cầu chỉnh sửa. Lượt 2: Nhiếp ảnh gia đã nộp lại, chưa có kết quả -> không được hiện lại lý do cũ.
        self._tao_luot(1, KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA, 'Lý do đã được xử lý.')  # lượt 1 có kết quả
        self._tao_luot(2)  # lượt 2: vừa nộp lại, chưa có kết quả
        res = self.mo(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia mở trang
        self.assertFalse(res.context['nag']['can_chinh_sua'])  # không còn là "yêu cầu chỉnh sửa"
        self.assertEqual(res.context['nag']['phan_hoi'], '')  # không còn lý do
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')  # hiện "đang chờ duyệt"
        self.assertNotContains(res, 'Lý do đã được xử lý.')  # không hiện lý do cũ
        self.assertNotContains(res, 'Quản trị viên yêu cầu chỉnh sửa hồ sơ')  # không hiện câu yêu cầu cũ

    def test_cho_duyet_lan_dau_khong_co_ly_do(self):  # tình huống: vừa nộp lần đầu
        self._tao_luot(1)                                               # vừa nộp lần đầu, chưa có kết quả
        res = self.mo(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia mở trang
        self.assertFalse(res.context['nag']['can_chinh_sua'])  # không phải "yêu cầu chỉnh sửa"
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')  # hiện "đang chờ duyệt"

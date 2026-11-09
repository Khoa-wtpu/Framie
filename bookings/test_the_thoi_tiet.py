# =====================================================================
# bookings/test_the_thoi_tiet.py - Test cho bookings/the_thoi_tiet.py (E8: thẻ "Dự báo thời tiết buổi chụp")
# Chạy:  python manage.py test bookings.test_the_thoi_tiet
# Dự báo được GIẢ LẬP (mock lay_du_bao_thoi_tiet của E7), KHÔNG gọi mạng thật.
# =====================================================================
from datetime import timedelta  # cộng/trừ ngày giờ
from unittest import mock  # giả lập hàm lấy dự báo

from django.urls import reverse  # từ TÊN url suy ra địa chỉ thật
from django.utils import timezone  # giờ hiện tại có múi giờ

from bookings import test_tiep_nhan as nen  # dùng lại dữ liệu mẫu: khách, Nhiếp ảnh gia, gói, tao_booking
from bookings import the_thoi_tiet as uc  # file đang được test
from chat.models import CuocTroChuyen  # cuộc trò chuyện Khách - Nhiếp ảnh gia
from core.constants import TrangThaiBooking as BK, VaiTro  # hằng số dùng chung
from profiles.models import KhuVuc, NhiepAnhGia_KhuVuc  # khu vực của Nhiếp ảnh gia

TIEU_DE = 'Dự báo thời tiết buổi chụp'  # tiêu đề thẻ
MOCK = 'bookings.the_thoi_tiet.lay_du_bao_thoi_tiet'  # chỗ cần giả lập


def du_bao(mua=20):  # một kết quả dự báo giả theo đúng khuôn của E7
    return {'nhiet_do': 29.5, 'xac_suat_mua': mua, 'mo_ta': 'Mưa rào nhẹ'}


class TheThoiTietBase(nen.TiepNhanBase):  # lớp nền: Nhiếp ảnh gia có khu vực Đà Nẵng
    def setUp(self):
        super().setUp()  # khách 'khach_a', Nhiếp ảnh gia 'nag' (đang đăng nhập), gói, ngày chụp = 3 ngày nữa
        NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=self.nag, MaKhuVuc=KhuVuc.objects.create(TenKhuVuc='Đà Nẵng'))

    def mo(self, bk, user):  # đăng nhập bằng user rồi mở trang chi tiết Booking
        self.client.force_login(user)
        return self.client.get(reverse('chi_tiet_booking', kwargs={'ma_booking': bk.pk}))


class TheThoiTietTest(TheThoiTietBase):
    def test_co_du_bao_hien_nhiet_do_mua_mo_ta_cho_khach_va_nag(self):  # trường hợp 1: có dự báo
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC)
        for user in (self.khach, self.nag.MaTaiKhoan):  # cả hai bên đều thấy
            with mock.patch(MOCK, return_value=du_bao(20)):
                res = self.mo(bk, user)
            self.assertContains(res, TIEU_DE)
            self.assertContains(res, 'Mưa rào nhẹ')
            self.assertContains(res, '29,5°C')  # nhiệt độ (định dạng số của Django theo ngôn ngữ vi)
            self.assertContains(res, '20%')
            self.assertNotContains(res, uc.TB_NHAC_DOI_LICH)  # mưa thấp: không nhắc đổi lịch
            self.assertNotContains(res, uc.TB_CHUA_CO_DU_BAO)

    def test_khong_co_du_bao_ghi_chua_co_du_bao(self):  # trường hợp 2: E7 trả rỗng
        bk = self.tao_booking()
        with mock.patch(MOCK, return_value={}):
            res = self.mo(bk, self.khach)
        self.assertContains(res, TIEU_DE)
        self.assertContains(res, 'Chưa có dự báo')
        self.assertNotContains(res, uc.TB_NHAC_DOI_LICH)

    def test_mua_cao_nhac_doi_lich_kem_nut_chat_cho_khach(self):  # trường hợp 3a: mưa cao, Khách có nút POST sang trò chuyện
        bk = self.tao_booking()
        with mock.patch(MOCK, return_value=du_bao(uc.NGUONG_MUA_CAO)):  # đúng ngưỡng cũng tính là cao
            res = self.mo(bk, self.khach)
        self.assertContains(res, uc.TB_NHAC_DOI_LICH)
        self.assertContains(res, reverse('khoi_tao_cuoc_tro_chuyen', kwargs={'ma_nhiep_anh_gia': self.nag.pk}))
        self.assertContains(res, 'Trao đổi qua trò chuyện')

    def test_mua_cao_nag_co_nut_chat_ke_ca_khi_chua_nhan_tin(self):  # trường hợp 3b: Nhiếp ảnh gia luôn có nút, bấm thì tạo cuộc trò chuyện
        bk = self.tao_booking()
        url = reverse('mo_tro_chuyen_booking', kwargs={'ma_booking': bk.pk})
        with mock.patch(MOCK, return_value=du_bao(90)):
            res = self.mo(bk, self.nag.MaTaiKhoan)  # hai bên chưa từng nhắn
        self.assertContains(res, uc.TB_NHAC_DOI_LICH)
        self.assertContains(res, 'Trao đổi qua trò chuyện')
        self.assertContains(res, url)
        self.assertFalse(CuocTroChuyen.objects.exists())  # mở trang chưa tạo gì
        res = self.client.post(url)  # bấm nút
        cuoc = CuocTroChuyen.objects.get(MaKhachHang=self.khach, MaNhiepAnhGia=self.nag)  # cuộc đã được tạo đúng cặp
        self.assertRedirects(res, reverse('chi_tiet_cuoc_tro_chuyen', kwargs={'ma_cuoc': cuoc.pk}), fetch_redirect_response=False)
        self.client.post(url)  # bấm lần nữa: mở lại cuộc cũ
        self.assertEqual(CuocTroChuyen.objects.count(), 1)  # vẫn chỉ một cuộc cho mỗi cặp

    def test_nut_chat_cua_nag_chi_dung_cho_booking_cua_minh(self):  # an toàn: sai người / sai vai trò / sai phương thức
        bk = self.tao_booking()
        url = reverse('mo_tro_chuyen_booking', kwargs={'ma_booking': bk.pk})
        self.client.force_login(self.nag_khac.MaTaiKhoan)  # Nhiếp ảnh gia khác
        self.assertEqual(self.client.post(url).status_code, 404)  # Booking của người khác -> 404, không tạo gì
        self.client.force_login(self.khach)  # Khách hàng
        self.assertEqual(self.client.post(url).status_code, 403)  # sai vai trò
        self.client.force_login(self.nag.MaTaiKhoan)
        self.assertEqual(self.client.get(url).status_code, 405)  # GET không được phép
        self.assertFalse(CuocTroChuyen.objects.exists())

    def test_booking_het_hieu_luc_khong_hien_the(self):  # ẩn: Đã từ chối / Hết thời hạn đặt cọc / Đã hủy
        cac_ca = [(BK.DA_TU_CHOI, {'LyDoTuChoi': 'Bận'}),  # từ chối bắt buộc có lý do (ràng buộc của database)
                  (BK.HET_THOI_HAN_DAT_COC, {}), (BK.DA_HUY, {})]
        for i, (trang_thai, them) in enumerate(cac_ca):
            bk = self.tao_booking(trang_thai=trang_thai, gio=f'{8 + i * 3:02d}:00', **them)  # mỗi Booking một giờ riêng
            with mock.patch(MOCK, return_value=du_bao()) as goi:
                res = self.mo(bk, self.khach)
            self.assertNotContains(res, TIEU_DE, msg_prefix=trang_thai)
            goi.assert_not_called()  # ẩn thì không gọi dự báo

    def test_buoi_chup_da_dien_ra_khong_hien_the(self):  # ẩn: giờ chụp đã qua
        bk = self.tao_booking(trang_thai=BK.CHOT_BOOKING)
        type(bk).objects.filter(pk=bk.pk).update(NgayGioChup=timezone.now() - timedelta(hours=2), NgayTao=timezone.now() - timedelta(days=5))
        with mock.patch(MOCK, return_value=du_bao()) as goi:
            res = self.mo(bk, self.khach)
        self.assertNotContains(res, TIEU_DE)
        goi.assert_not_called()

    def test_quan_tri_vien_khong_thay_the(self):  # ẩn: chỉ Khách và Nhiếp ảnh gia
        bk = self.tao_booking()
        qtv = nen.tao_user('qtv_tt', VaiTro.QUAN_TRI_VIEN)
        self.client.force_login(qtv)
        with mock.patch(MOCK, return_value=du_bao()):
            res = self.client.get(reverse('admin_booking_detail', kwargs={'ma_booking': bk.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, TIEU_DE)

    def test_dung_khu_vuc_khach_da_chon_trong_dia_diem(self):  # Khách chọn Hà Nội dù Nhiếp ảnh gia nhận cả Đà Nẵng và Hà Nội
        NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=self.nag, MaKhuVuc=KhuVuc.objects.create(TenKhuVuc='Hà Nội'))
        for dia_diem in ('Hà Nội', 'Hà Nội - 1 Tràng Tiền'):  # có và không có địa chỉ cụ thể
            bk = self.tao_booking(DiaDiem=dia_diem, gio='09:00' if dia_diem == 'Hà Nội' else '13:00')
            with mock.patch(MOCK, return_value=du_bao()) as goi:
                self.mo(bk, self.khach)
            goi.assert_called_once()  # chỉ tra đúng 1 khu vực
            self.assertEqual(goi.call_args.args[0].TenKhuVuc, 'Hà Nội')  # đúng khu vực Khách chọn

    def test_dia_diem_khong_khop_thi_dung_khu_vuc_cua_nag(self):  # Booking cũ / DiaDiem gõ tay: thử lần lượt khu vực Nhiếp ảnh gia khai
        NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=self.nag, MaKhuVuc=KhuVuc.objects.create(TenKhuVuc='Hà Nội'))
        bk = self.tao_booking(DiaDiem='Hồ Gươm')
        with mock.patch(MOCK, side_effect=[{}, du_bao(10)]) as goi:  # khu vực thứ nhất rỗng, thứ hai có dự báo
            res = self.mo(bk, self.khach)
        self.assertEqual(goi.call_count, 2)
        self.assertContains(res, 'Mưa rào nhẹ')

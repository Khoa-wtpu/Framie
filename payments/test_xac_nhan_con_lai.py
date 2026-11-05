# Chạy: python manage.py test payments.test_xac_nhan_con_lai      (N9: UC5.7 Nhiếp ảnh gia xác nhận thanh toán phần còn lại)
import tempfile
import unittest
from datetime import timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import DatabaseError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import LichSuTrangThaiBooking
from core.constants import (BenThucHien, LoaiAnh, LoaiThanhToan, TrangThaiBooking as TT,
                            TrangThaiThanhToan as TTT)
from delivery import services as dich_vu_anh
from delivery.models import Anh, BanGiao
from notifications.models import ThongBao
from payments import services as dich_vu_thanh_toan             # N2: Khách tải minh chứng
from payments import services_con_lai as services              # N9: hàm cần kiểm tra
from payments.models import ThanhToan
from payments.tests import _DuLieuNen, tep_anh                  # lớp nền và hàm tạo ảnh có sẵn của N2/N3

try:                                                           # N11 (reviews) có thể chưa được ghép vào project
    from reviews.services import gui_nhac_danh_gia             # noqa: F401
    CO_REVIEWS = True
except ImportError:
    CO_REVIEWS = False


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())      # ảnh test ghi vào thư mục tạm, không đụng private_media
class _NenConLai(_DuLieuNen):
    def booking_con_lai(self, minh_chung=True, trang_thai=TTT.CHO_XAC_NHAN_60, so_anh=0):   # Booking Chờ xác nhận thanh toán + khoản 60% (N8 đã tạo)
        bk = self.tao_booking(TT.CHO_XAC_NHAN_THANH_TOAN)
        BanGiao.objects.create(MaBooking=bk, NgayXacNhan=timezone.now() - timedelta(hours=1))
        tt = ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.PHAN_CON_LAI, SoTien=600001, TrangThai=trang_thai)
        if minh_chung:
            dich_vu_thanh_toan.tai_len_minh_chung(bk.pk, self.kh, tep_anh())   # Khách tải minh chứng (N2)
        kho = dich_vu_anh.kho_anh()
        for i in range(1, so_anh + 1):                         # ảnh Đã hậu kỳ, có cả bản gốc không watermark
            duong_dan = f'booking_{bk.pk}/a{i}.jpg'
            kho.save(duong_dan, ContentFile(b'co-watermark'))
            kho.save(dich_vu_anh.duong_dan_goc(duong_dan), ContentFile(b'khong-watermark'))
            Anh.objects.create(MaBooking=bk, TenAnh=f'a{i}.jpg', DuongDanAnh=duong_dan, DinhDangAnh='JPG', KichThuocAnh=100,
                               LoaiAnh=LoaiAnh.DA_HAU_KY, CoWatermark=1, DuocChonHauKy=0)
        tt.refresh_from_db()
        return bk, tt


class XacNhanConLaiServiceTests(_NenConLai):                   # nghiệp vụ UC5.7
    def test_xac_nhan_thanh_cong_doi_thanh_toan_booking_anh_ban_giao_va_bao_khach(self):   # bước 4-7
        bk, tt = self.booking_con_lai(so_anh=2)
        services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        tt.refresh_from_db()
        self.assertEqual(tt.TrangThai, TTT.DA_THANH_TOAN)
        self.assertIsNotNone(tt.NgayXacNhan)                   # CHECK của bảng
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HOAN_THANH)
        self.assertTrue(LichSuTrangThaiBooking.objects.filter(
            MaBooking=bk, TrangThaiCu=TT.CHO_XAC_NHAN_THANH_TOAN, TrangThaiMoi=TT.HOAN_THANH,
            BenThucHien=BenThucHien.NHIEP_ANH_GIA).exists())
        for a in Anh.objects.filter(MaBooking=bk):             # ảnh Đã hậu kỳ -> Hoàn chỉnh, không watermark
            self.assertEqual((a.LoaiAnh, a.CoWatermark), (LoaiAnh.HOAN_CHINH, 0))
        han = BanGiao.objects.get(MaBooking=bk).ThoiHanTaiAnh
        self.assertAlmostEqual((han - timezone.now()).total_seconds(), 3 * 86400, delta=120)   # tải ảnh trong 3 ngày
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk,
                                                TieuDe='Thanh toán phần còn lại đã được xác nhận').exists())

    @unittest.skipUnless(CO_REVIEWS, 'chưa có reviews.services.gui_nhac_danh_gia (N11)')
    def test_xac_nhan_xong_nhac_khach_danh_gia(self):          # nối với N11
        bk, _ = self.booking_con_lai()
        services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk, TieuDe='Hãy đánh giá nhiếp ảnh gia').exists())

    def test_qua_han_van_xac_nhan_thu_cong_khong_can_minh_chung(self):   # luồng 1b
        bk, tt = self.booking_con_lai(minh_chung=False, trang_thai=TTT.QUA_HAN)
        self.assertIsNone(services.ly_do_khong_xu_ly_duoc(bk, tt))
        services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        tt.refresh_from_db()
        bk.refresh_from_db()
        self.assertEqual((tt.TrangThai, bk.TrangThai), (TTT.DA_THANH_TOAN, TT.HOAN_THANH))

    def test_chua_co_minh_chung_thi_khong_xac_nhan_duoc(self):
        bk, _ = self.booking_con_lai(minh_chung=False)
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'Khách hàng chưa tải minh chứng thanh toán phần còn lại.'):
            services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)

    def test_nhiep_anh_gia_khac_khong_xac_nhan_duoc(self):
        bk, _ = self.booking_con_lai()
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'Booking không tồn tại hoặc không thuộc về bạn.'):
            services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag2_user)

    def test_booking_chua_den_buoc_thanh_toan_bi_chan(self):
        bk = self.tao_booking(TT.CHO_KH_KIEM_TRA)
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'không thể xác nhận thanh toán phần còn lại'):
            services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)

    def test_xac_nhan_lan_hai_bi_chan_khong_ghi_trung(self):
        bk, _ = self.booking_con_lai()
        services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        with self.assertRaises(services.LoiXacNhanConLai):
            services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk, TrangThaiMoi=TT.HOAN_THANH).count(), 1)
        self.assertEqual(ThongBao.objects.filter(MaNguoiNhan=self.kh, TieuDe='Thanh toán phần còn lại đã được xác nhận').count(), 1)

    def test_ham_doi_trang_thai_bao_loi_thi_hoan_tac_khoan_thanh_toan(self):
        bk, tt = self.booking_con_lai()
        with mock.patch('payments.services_con_lai.chuyen_trang_thai_booking', side_effect=ValidationError('x')):
            with self.assertRaises(services.LoiXacNhanConLai):
                services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        tt.refresh_from_db()
        self.assertEqual((tt.TrangThai, tt.NgayXacNhan), (TTT.CHO_XAC_NHAN_60, None))

    def test_loi_cap_nhat_thanh_toan_5a_hoan_tac_het(self):
        bk, tt = self.booking_con_lai()
        with mock.patch.object(ThanhToan, 'save', side_effect=DatabaseError('hỏng')):
            with self.assertRaisesMessage(services.LoiXacNhanConLai, 'trạng thái thanh toán'):
                services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_XAC_NHAN_THANH_TOAN)

    def test_loi_cap_nhat_booking_6a_hoan_tac_khoan_thanh_toan(self):
        bk, tt = self.booking_con_lai()
        with mock.patch('payments.services_con_lai.chuyen_trang_thai_booking', side_effect=DatabaseError('hỏng')):
            with self.assertRaisesMessage(services.LoiXacNhanConLai, 'Hoàn thành'):
                services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        tt.refresh_from_db()
        self.assertEqual(tt.TrangThai, TTT.CHO_XAC_NHAN_60)    # khoản thanh toán bị hoàn tác

    def test_khong_chuyen_duoc_anh_hoan_chinh_thi_hoan_tac_het(self):   # thiếu bản gốc không watermark
        bk, tt = self.booking_con_lai(so_anh=1)
        kho = dich_vu_anh.kho_anh()
        kho.delete(dich_vu_anh.duong_dan_goc(f'booking_{bk.pk}/a1.jpg'))
        with self.assertRaises(services.LoiXacNhanConLai):
            services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        tt.refresh_from_db()
        bk.refresh_from_db()
        self.assertEqual((tt.TrangThai, bk.TrangThai), (TTT.CHO_XAC_NHAN_60, TT.CHO_XAC_NHAN_THANH_TOAN))

    # ---------------- nhánh 4a ----------------
    def test_yeu_cau_bo_sung_giu_nguyen_trang_thai_roi_khach_nop_lai_thi_xac_nhan_duoc(self):
        bk, tt = self.booking_con_lai()
        services.yeu_cau_bo_sung_con_lai(bk.pk, self.nag_user, 'Số tiền chưa đủ')
        tt.refresh_from_db()
        self.assertEqual((tt.TrangThai, tt.LyDoTuChoi), (TTT.CHO_XAC_NHAN_60, 'Số tiền chưa đủ'))
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk, TieuDe='Nhiếp ảnh gia yêu cầu bổ sung minh chứng').exists())
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'Đang chờ Khách hàng bổ sung'):
            services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        dich_vu_thanh_toan.tai_len_minh_chung(bk.pk, self.kh, tep_anh('moi.png'))   # Khách nộp lại (N2 xóa yêu cầu cũ)
        services.xac_nhan_thanh_toan_con_lai(bk.pk, self.nag_user)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HOAN_THANH)

    def test_yeu_cau_bo_sung_phai_co_ly_do_va_toi_da_255_ky_tu(self):
        bk, _ = self.booking_con_lai()
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'Vui lòng nhập lý do'):
            services.yeu_cau_bo_sung_con_lai(bk.pk, self.nag_user, '   ')
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'tối đa 255'):
            services.yeu_cau_bo_sung_con_lai(bk.pk, self.nag_user, 'a' * 256)

    def test_khoan_da_qua_han_khong_yeu_cau_bo_sung_duoc(self):
        bk, _ = self.booking_con_lai(minh_chung=False, trang_thai=TTT.QUA_HAN)
        with self.assertRaisesMessage(services.LoiXacNhanConLai, 'quá hạn'):
            services.yeu_cau_bo_sung_con_lai(bk.pk, self.nag_user, 'x')

    def test_yeu_cau_bo_sung_khi_chua_co_minh_chung_bi_chan(self):
        bk, _ = self.booking_con_lai(minh_chung=False)
        with self.assertRaises(services.LoiXacNhanConLai):
            services.yeu_cau_bo_sung_con_lai(bk.pk, self.nag_user, 'x')


class XacNhanConLaiViewTests(_NenConLai):                      # view UC5.7
    NUT_XAC_NHAN = 'Xác nhận đã nhận đủ tiền'

    def url(self, bk):
        return reverse('xac_nhan_thanh_toan_con_lai', args=[bk.pk])

    def test_get_co_thong_tin_minh_chung_va_hai_nut(self):
        bk, tt = self.booking_con_lai()
        self.client.force_login(self.nag_user)
        r = self.client.get(self.url(bk))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Xác nhận thanh toán phần còn lại')
        self.assertContains(r, self.goi.TenGoi)
        self.assertContains(r, reverse('xem_minh_chung', args=[tt.minh_chungs.get().pk]))
        self.assertContains(r, self.NUT_XAC_NHAN)
        self.assertContains(r, 'Yêu cầu bổ sung')

    def test_get_qua_han_co_nut_xac_nhan_thu_cong_va_khong_co_yeu_cau_bo_sung(self):   # luồng 1b
        bk, _ = self.booking_con_lai(minh_chung=False, trang_thai=TTT.QUA_HAN)
        self.client.force_login(self.nag_user)
        r = self.client.get(self.url(bk))
        self.assertContains(r, 'Khoản thanh toán đã quá hạn')
        self.assertContains(r, self.NUT_XAC_NHAN)
        self.assertNotContains(r, 'Yêu cầu bổ sung')

    def test_get_chua_co_minh_chung_thi_an_nut_va_hien_canh_bao(self):
        bk, _ = self.booking_con_lai(minh_chung=False)
        self.client.force_login(self.nag_user)
        r = self.client.get(self.url(bk))
        self.assertContains(r, 'Khách hàng chưa tải minh chứng thanh toán phần còn lại.')
        self.assertNotContains(r, self.NUT_XAC_NHAN)

    def test_khach_hang_bi_403_chua_dang_nhap_bi_chuyen_trang_nhiep_anh_gia_khac_bi_404(self):
        bk, _ = self.booking_con_lai()
        self.client.force_login(self.kh)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)
        self.client.logout()
        r = self.client.get(self.url(bk))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/dang-nhap/', r['Location'])
        self.client.force_login(self.nag2_user)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)

    def test_post_xac_nhan_chuyen_trang_va_booking_hoan_thanh(self):
        bk, _ = self.booking_con_lai()
        self.client.force_login(self.nag_user)
        r = self.client.post(self.url(bk), {'hanh_dong': 'xac_nhan'}, follow=True)
        self.assertEqual(r.redirect_chain, [(self.url(bk), 302)])
        self.assertContains(r, 'Đã xác nhận thanh toán phần còn lại. Booking đã hoàn thành.')
        self.assertContains(r, 'Booking đã hoàn thành.')
        self.assertNotContains(r, self.NUT_XAC_NHAN)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.HOAN_THANH)

    def test_post_bo_sung_co_ly_do_thanh_cong(self):
        bk, tt = self.booking_con_lai()
        self.client.force_login(self.nag_user)
        r = self.client.post(self.url(bk), {'hanh_dong': 'bo_sung', 'ly_do': 'Ảnh bị mờ'}, follow=True)
        self.assertContains(r, 'Đã gửi yêu cầu bổ sung minh chứng cho Khách hàng.')
        self.assertContains(r, 'Ảnh bị mờ')
        self.assertNotContains(r, self.NUT_XAC_NHAN)           # đang chờ khách nộp lại
        tt.refresh_from_db()
        self.assertEqual(tt.LyDoTuChoi, 'Ảnh bị mờ')

    def test_post_bo_sung_thieu_ly_do_o_lai_trang_va_hien_loi(self):
        bk, tt = self.booking_con_lai()
        self.client.force_login(self.nag_user)
        r = self.client.post(self.url(bk), {'hanh_dong': 'bo_sung', 'ly_do': ''})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vui lòng nhập lý do yêu cầu bổ sung.')
        tt.refresh_from_db()
        self.assertIsNone(tt.LyDoTuChoi)

    def test_hanh_dong_la_hien_thong_bao_khong_hop_le(self):
        bk, _ = self.booking_con_lai()
        self.client.force_login(self.nag_user)
        r = self.client.post(self.url(bk), {'hanh_dong': 'xoa_het'})
        self.assertContains(r, 'Thao tác không hợp lệ.')

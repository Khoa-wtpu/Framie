# Chạy: python manage.py test payments      (N2: UC5.1 tải minh chứng; N3: UC5.2 xác nhận cọc)
import io
import tempfile
from datetime import date, time, timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone
from PIL import Image

from bookings.models import Booking, LichSuTrangThaiBooking
from core.constants import (BenThucHien, LoaiHauKy, LoaiThanhToan, TrangThaiBooking as TT,
                            TrangThaiHoSo, TrangThaiSlot, TrangThaiThanhToan, VaiTro)
from notifications.models import ThongBao
from payments import services
from payments.forms import MinhChungForm
from payments.models import MinhChungThanhToan, ThanhToan
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
from schedule.models import LichKhaDung

User = get_user_model()

urlpatterns = [path('', include('payments.urls')),                 # bảng đường dẫn riêng cho test (không phụ thuộc config/urls.py)
               path('dang-nhap/', lambda request: HttpResponse('dang nhap'), name='login')]   # LOGIN_URL = 'login' cần có tên này để chuyển hướng

CAU_SAI_DINH_DANG = 'Chỉ chấp nhận tệp JPG, JPEG hoặc PNG.'
CAU_QUA_DUNG_LUONG = 'Dung lượng tệp vượt quá 5 MB.'
CAU_KHONG_NHAN_THEM = 'Khoản thanh toán này không còn nhận thêm minh chứng.'


def tep_anh(ten='bien-lai.png', dinh_dang='PNG'):              # tạo tệp ảnh thật trong bộ nhớ
    bo_nho = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(bo_nho, dinh_dang)
    return SimpleUploadedFile(ten, bo_nho.getvalue())


def cac_tep_tren_dia(kho):                                     # danh sách mọi tệp đang nằm trong kho lưu tệp
    return [p for p in Path(kho.location).rglob('*') if p.is_file()]


@override_settings(MINH_CHUNG_ROOT=tempfile.mkdtemp(), ROOT_URLCONF='payments.tests')   # tệp test ghi vào thư mục tạm, không đụng private_media
class _DuLieuNen(TestCase):                                    # dữ liệu nền dùng chung (không có test riêng)
    @classmethod
    def setUpTestData(cls):
        nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        cls.kh = User.objects.create_user('kh', 'kh@x.vn', 'p', so_dien_thoai='0900000001')
        cls.kh2 = User.objects.create_user('kh2', 'kh2@x.vn', 'p', so_dien_thoai='0900000003')
        cls.quan_tri = User.objects.create_superuser('root', 'root@x.vn', 'p', so_dien_thoai='0900000008')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')

        def tao_nag(ten, sdt):                                 # một Nhiếp ảnh gia THẬT: có nhóm, hồ sơ Đã duyệt và NhiepAnhGia
            user = User.objects.create_user(ten, f'{ten}@x.vn', 'p', so_dien_thoai=sdt,
                                            trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
            user.groups.add(nhom_nag)
            return user, NhiepAnhGia.objects.create(MaTaiKhoan=user, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',
                                                    SoTaiKhoan='1', ChuTaiKhoan='N', AnhMaQR='q.jpg')
        cls.nag_user, cls.nag = tao_nag('nag', '0900000002')
        cls.nag2_user, cls.nag2 = tao_nag('nag2', '0900000004')   # Nhiếp ảnh gia KHÁC, không liên quan Booking
        cls.goi = GoiDichVu.objects.create(MaNhiepAnhGia=cls.nag, MaLoaiHinh=loai, TenGoi='G1', Gia=1000001,
                                           ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)

    def tao_booking(self, trang_thai=TT.CHO_DAT_COC, han=None):  # Booking ở trạng thái mong muốn
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=date.today() + timedelta(days=20),
                                          GioBatDau=time(8, 0), GioKetThuc=time(9, 0))
        bk = Booking.objects.create(MaKhachHang=self.kh, MaNhiepAnhGia=self.nag, MaGoi=self.goi, MaLich=lich,
                                    NgayGioChup=timezone.now() + timedelta(days=30), DiaDiem='HCM', SoNguoi=2,
                                    Concept='c', TongGiaTri=self.goi.Gia)
        cap_nhat = {'TrangThai': trang_thai}
        if trang_thai == TT.CHO_XAC_NHAN_THANH_TOAN:
            cap_nhat['HanThanhToanConLai'] = han or timezone.now() + timedelta(days=2)
        else:
            cap_nhat['HanDatCoc'] = han or timezone.now() + timedelta(days=1)
        Booking.objects.filter(pk=bk.pk).update(**cap_nhat)
        LichKhaDung.objects.filter(pk=lich.pk).update(TrangThai=TrangThaiSlot.DANG_GIU)   # slot đang được giữ như thực tế
        bk.refresh_from_db()
        return bk


# =====================================================================
# N2 / UC5.1: Khách hàng tải lên minh chứng
# =====================================================================
class MinhChungFormTests(TestCase):                            # bước 4 / ngoại lệ 4a: kiểm tra từng câu báo lỗi
    def loi(self, tep):                                        # trả về danh sách câu lỗi của ô 'tep'
        form = MinhChungForm({}, {'tep': tep} if tep is not None else {})
        self.assertFalse(form.is_valid())
        return form.errors['tep']

    def test_nhan_png_va_jpg(self):
        self.assertTrue(MinhChungForm({}, {'tep': tep_anh('a.png', 'PNG')}).is_valid())
        self.assertTrue(MinhChungForm({}, {'tep': tep_anh('a.jpg', 'JPEG')}).is_valid())
        self.assertTrue(MinhChungForm({}, {'tep': tep_anh('a.jpeg', 'JPEG')}).is_valid())

    def test_khong_chon_tep(self):
        self.assertEqual(self.loi(None), ['Vui lòng chọn tệp minh chứng.'])

    def test_sai_duoi_tep(self):
        self.assertEqual(self.loi(tep_anh('a.gif', 'GIF')), [CAU_SAI_DINH_DANG])

    def test_gif_doi_duoi_thanh_png(self):
        self.assertEqual(self.loi(tep_anh('a.png', 'GIF')), [CAU_SAI_DINH_DANG])

    def test_tep_khong_phai_anh(self):
        self.assertEqual(self.loi(SimpleUploadedFile('a.jpg', b'khong phai anh')), ['Tệp không phải ảnh hợp lệ.'])

    def test_qua_dung_luong(self):                             # dùng ảnh THẬT và hạ giới hạn xuống 10 byte để nhánh dung lượng thật sự chạy
        with mock.patch('payments.forms.DUNG_LUONG_TOI_DA', 10):
            self.assertEqual(self.loi(tep_anh('a.png', 'PNG')), [CAU_QUA_DUNG_LUONG])


class TaiLenMinhChungTests(_DuLieuNen):                        # nghiệp vụ UC5.1 (service)
    def test_tai_lan_dau_tao_khoan_coc_minh_chung_va_thong_bao(self):
        bk = self.tao_booking()
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual((tt.LoaiThanhToan, tt.SoTien, tt.TrangThai),
                         (LoaiThanhToan.TIEN_COC, 400000, TrangThaiThanhToan.CHO_XAC_NHAN_COC))  # 40% của 1.000.001, làm tròn
        self.assertEqual(MinhChungThanhToan.objects.filter(MaThanhToan=tt).count(), 1)
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.nag_user, MaBooking=bk).exists())

    def test_gui_lai_nhieu_lan_va_xoa_yeu_cau_bo_sung(self):
        bk = self.tao_booking()
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        ThanhToan.objects.filter(MaBooking=bk).update(LyDoTuChoi='Ảnh mờ')
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh('lan-2.png'))
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual(tt.minh_chungs.count(), 2)            # không tạo thêm khoản thanh toán
        self.assertIsNone(tt.LyDoTuChoi)                       # lý do cũ được xóa

    def test_khoan_phan_con_lai_60_phan_tram(self):            # (a) Booking ở Chờ xác nhận thanh toán -> khoản 60%
        bk = self.tao_booking(TT.CHO_XAC_NHAN_THANH_TOAN)
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual((tt.LoaiThanhToan, tt.TrangThai, tt.SoTien),
                         (LoaiThanhToan.PHAN_CON_LAI, TrangThaiThanhToan.CHO_XAC_NHAN_60, 600001))   # 1.000.001 - 400.000

    def test_khoan_da_xac_nhan_bi_chan(self):                  # (b)
        bk = self.tao_booking()
        ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=LoaiThanhToan.TIEN_COC, SoTien=400000,
                                 TrangThai=TrangThaiThanhToan.DA_DAT_COC, NgayXacNhan=timezone.now())
        with self.assertRaisesMessage(services.LoiTaiMinhChung, CAU_KHONG_NHAN_THEM):
            services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        self.assertFalse(MinhChungThanhToan.objects.exists())

    def test_booking_khong_o_giai_doan_thanh_toan_bi_chan(self):   # (c)
        bk = self.tao_booking(TT.CHOT_BOOKING)
        with self.assertRaisesMessage(services.LoiTaiMinhChung, 'Booking hiện không ở giai đoạn thanh toán.'):
            services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())

    def test_qua_han_bi_chan(self):
        bk = self.tao_booking()
        Booking.objects.filter(pk=bk.pk).update(                      # Booking tạo cách đây 2 ngày, hạn cọc đã qua 1 giờ
            NgayTao=timezone.now() - timedelta(days=2),               # DB có CHECK: HanDatCoc phải SAU NgayTao
            HanDatCoc=timezone.now() - timedelta(hours=1))
        with self.assertRaisesMessage(services.LoiTaiMinhChung, 'Đã quá hạn thanh toán, không thể tải minh chứng.'):
            services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        self.assertFalse(MinhChungThanhToan.objects.exists())

    def test_booking_cua_nguoi_khac_bi_chan(self):
        bk = self.tao_booking()
        with self.assertRaisesMessage(services.LoiTaiMinhChung, 'Booking không tồn tại.'):
            services.tai_len_minh_chung(bk.pk, self.kh2, tep_anh())

    def test_loi_database_khi_luu_khong_de_lai_tep_va_khoan_thanh_toan(self):   # (d) ngoại lệ 6a
        bk = self.tao_booking()
        with mock.patch.object(MinhChungThanhToan.objects, 'create', side_effect=DatabaseError('loi')):
            with self.assertRaisesMessage(services.LoiTaiMinhChung, 'Không thể lưu minh chứng thanh toán, vui lòng thử lại.'):
                services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        self.assertEqual(cac_tep_tren_dia(services.kho_minh_chung()), [])       # tệp đã lỡ ghi được xóa, không còn tệp mồ côi
        self.assertFalse(ThanhToan.objects.filter(MaBooking=bk).exists())       # khoản thanh toán tạo dở bị hoàn tác
        self.assertFalse(MinhChungThanhToan.objects.exists())


class TaiLenMinhChungViewTests(_DuLieuNen):                    # view UC5.1: phân quyền và luồng gửi
    def url(self, bk):
        return reverse('tai_len_minh_chung', args=[bk.pk])

    def test_booking_cua_nguoi_khac_tra_404(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh2)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)

    def test_nhiep_anh_gia_vao_bi_403(self):
        bk = self.tao_booking()
        self.client.force_login(self.nag_user)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)

    def test_chua_dang_nhap_bi_chuyen_trang_dang_nhap(self):
        bk = self.tao_booking()
        phan_hoi = self.client.get(self.url(bk))
        self.assertEqual(phan_hoi.status_code, 302)
        self.assertIn('/dang-nhap/', phan_hoi['Location'])

    def test_get_hien_so_tien_va_nut_gui(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        phan_hoi = self.client.get(self.url(bk))
        self.assertContains(phan_hoi, 'Gửi minh chứng')
        self.assertContains(phan_hoi, 'Tiền cọc')

    def test_post_hop_le_chuyen_trang_va_co_thong_bao_thanh_cong(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        phan_hoi = self.client.post(self.url(bk), {'tep': tep_anh('a.png', 'PNG')}, follow=True)
        self.assertEqual(phan_hoi.redirect_chain, [(self.url(bk), 302)])
        self.assertContains(phan_hoi, 'Đã gửi minh chứng')
        self.assertEqual(MinhChungThanhToan.objects.count(), 1)

    def test_post_file_sai_o_lai_trang_va_khong_tao_minh_chung(self):
        bk = self.tao_booking()
        self.client.force_login(self.kh)
        phan_hoi = self.client.post(self.url(bk), {'tep': tep_anh('a.gif', 'GIF')})
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertContains(phan_hoi, CAU_SAI_DINH_DANG)
        self.assertFalse(MinhChungThanhToan.objects.exists())


class XemMinhChungViewTests(_DuLieuNen):                       # trang xem ảnh chuyển khoản: phần bảo mật quan trọng nhất
    def minh_chung_da_tai(self):
        bk = self.tao_booking()
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh('bien-lai.png', 'PNG'))
        return MinhChungThanhToan.objects.get(MaThanhToan__MaBooking=bk)

    def test_chua_dang_nhap_bi_chuyen_trang_dang_nhap(self):
        mc = self.minh_chung_da_tai()
        phan_hoi = self.client.get(reverse('xem_minh_chung', args=[mc.pk]))
        self.assertEqual(phan_hoi.status_code, 302)
        self.assertIn('/dang-nhap/', phan_hoi['Location'])

    def test_khach_hang_khac_bi_403(self):
        mc = self.minh_chung_da_tai()
        self.client.force_login(self.kh2)
        self.assertEqual(self.client.get(reverse('xem_minh_chung', args=[mc.pk])).status_code, 403)

    def test_nhiep_anh_gia_khac_bi_403(self):
        mc = self.minh_chung_da_tai()
        self.client.force_login(self.nag2_user)
        self.assertEqual(self.client.get(reverse('xem_minh_chung', args=[mc.pk])).status_code, 403)

    def test_ba_loai_nguoi_duoc_xem_nhan_dung_loai_tep_va_nosniff(self):
        mc = self.minh_chung_da_tai()
        for nguoi in (self.kh, self.nag_user, self.quan_tri):  # chính Khách hàng, Nhiếp ảnh gia nhận Booking, Quản trị viên
            self.client.force_login(nguoi)
            phan_hoi = self.client.get(reverse('xem_minh_chung', args=[mc.pk]))
            self.assertEqual(phan_hoi.status_code, 200, nguoi.username)
            self.assertEqual(phan_hoi['Content-Type'], 'image/png')
            self.assertEqual(phan_hoi['X-Content-Type-Options'], 'nosniff')

    def test_ma_khong_ton_tai_tra_404(self):
        self.client.force_login(self.kh)
        self.assertEqual(self.client.get(reverse('xem_minh_chung', args=[99999])).status_code, 404)


# =====================================================================
# N3 / UC5.2: Nhiếp ảnh gia xác nhận thanh toán tiền cọc
# =====================================================================
class _NenXacNhanCoc(_DuLieuNen):
    def booking_da_co_minh_chung(self):                        # Booking Chờ đặt cọc, khách đã tải 1 minh chứng
        bk = self.tao_booking()
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh())
        return bk


class XacNhanCocTests(_NenXacNhanCoc):                         # nghiệp vụ UC5.2 (service)
    def test_xac_nhan_doi_ca_thanh_toan_booking_slot_lich_su_va_bao_khach(self):
        bk = self.booking_da_co_minh_chung()
        services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual(tt.TrangThai, TrangThaiThanhToan.DA_DAT_COC)
        self.assertIsNotNone(tt.NgayXacNhan)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHOT_BOOKING)
        self.assertEqual(bk.MaLich.TrangThai, TrangThaiSlot.DA_DAT)                       # slot -> Đã đặt lịch
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk)
        self.assertEqual((ls.TrangThaiCu, ls.TrangThaiMoi, ls.BenThucHien),
                         (TT.CHO_DAT_COC, TT.CHOT_BOOKING, BenThucHien.NHIEP_ANH_GIA))
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())

    def test_nhiep_anh_gia_khac_khong_xac_nhan_duoc(self):    # dùng một Nhiếp ảnh gia THẬT khác (có hồ sơ), không phải Khách hàng
        bk = self.booking_da_co_minh_chung()
        with self.assertRaisesMessage(services.LoiXacNhanCoc, 'Booking không tồn tại hoặc không thuộc về bạn.'):
            services.xac_nhan_thanh_toan_coc(bk.pk, self.nag2_user)

    def test_chua_co_minh_chung_thi_khong_xac_nhan_duoc(self):
        bk = self.tao_booking()
        with self.assertRaisesMessage(services.LoiXacNhanCoc, 'Khách hàng chưa tải minh chứng thanh toán tiền cọc.'):
            services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)

    def test_ham_doi_trang_thai_bao_loi_thi_hoan_tac_khoan_coc(self):   # (a) transaction hoàn tác
        bk = self.booking_da_co_minh_chung()
        with mock.patch('payments.services.chuyen_trang_thai_booking', side_effect=ValidationError('x')):
            with self.assertRaises(services.LoiXacNhanCoc):
                services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual(tt.TrangThai, TrangThaiThanhToan.CHO_XAC_NHAN_COC)               # vẫn chờ xác nhận
        self.assertIsNone(tt.NgayXacNhan)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)
        self.assertFalse(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())

    def test_xac_nhan_lan_hai_bi_chan(self):                   # (b)
        bk = self.booking_da_co_minh_chung()
        services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)
        with self.assertRaises(services.LoiXacNhanCoc):
            services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk).count(), 1)  # không ghi lịch sử lần hai

    def test_yeu_cau_bo_sung_giu_nguyen_trang_thai_roi_khach_nop_lai_thi_xac_nhan_duoc(self):
        bk = self.booking_da_co_minh_chung()
        services.yeu_cau_bo_sung_minh_chung(bk.pk, self.nag_user, 'Ảnh bị mờ, sai số tiền')
        tt = ThanhToan.objects.get(MaBooking=bk)
        self.assertEqual(tt.LyDoTuChoi, 'Ảnh bị mờ, sai số tiền')
        self.assertEqual(tt.TrangThai, TrangThaiThanhToan.CHO_XAC_NHAN_COC)               # trạng thái giữ nguyên
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)
        self.assertTrue(ThongBao.objects.filter(MaNguoiNhan=self.kh, MaBooking=bk).exists())
        with self.assertRaises(services.LoiXacNhanCoc):                                   # đang chờ khách nộp lại
            services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)
        services.tai_len_minh_chung(bk.pk, self.kh, tep_anh('lan-2.png'))                 # khách nộp lại (UC5.1)
        services.xac_nhan_thanh_toan_coc(bk.pk, self.nag_user)                            # giờ xác nhận được
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHOT_BOOKING)

    def test_yeu_cau_bo_sung_phai_co_ly_do(self):
        bk = self.booking_da_co_minh_chung()
        with self.assertRaisesMessage(services.LoiXacNhanCoc, 'Vui lòng nhập lý do yêu cầu bổ sung minh chứng.'):
            services.yeu_cau_bo_sung_minh_chung(bk.pk, self.nag_user, '   ')

    def test_ly_do_qua_255_ky_tu_bi_chan(self):                # (c)
        bk = self.booking_da_co_minh_chung()
        with self.assertRaisesMessage(services.LoiXacNhanCoc, 'Lý do tối đa 255 ký tự.'):
            services.yeu_cau_bo_sung_minh_chung(bk.pk, self.nag_user, 'a' * 256)
        self.assertIsNone(ThanhToan.objects.get(MaBooking=bk).LyDoTuChoi)

    def test_yeu_cau_bo_sung_khi_chua_co_minh_chung_bi_chan(self):   # (d)
        bk = self.tao_booking()
        with self.assertRaisesMessage(services.LoiXacNhanCoc, 'Khách hàng chưa tải minh chứng thanh toán tiền cọc.'):
            services.yeu_cau_bo_sung_minh_chung(bk.pk, self.nag_user, 'Cần bổ sung')


class XacNhanCocViewTests(_NenXacNhanCoc):                     # view UC5.2: dùng assertContains để template và view luôn khớp nhau
    NUT_XAC_NHAN = 'Xác nhận đã nhận cọc'

    def url(self, bk):
        return reverse('xac_nhan_thanh_toan_coc', args=[bk.pk])

    def test_get_dung_nhiep_anh_gia_co_thong_tin_minh_chung_va_nut_xac_nhan(self):   # (a)
        bk = self.booking_da_co_minh_chung()
        mc = MinhChungThanhToan.objects.get(MaThanhToan__MaBooking=bk)
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.get(self.url(bk))
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertContains(phan_hoi, 'Xác nhận thanh toán tiền cọc')
        self.assertContains(phan_hoi, f'#{bk.pk}')
        self.assertContains(phan_hoi, self.goi.TenGoi)
        self.assertContains(phan_hoi, reverse('xem_minh_chung', args=[mc.pk]))           # link xem minh chứng
        self.assertContains(phan_hoi, self.NUT_XAC_NHAN)
        self.assertContains(phan_hoi, 'Yêu cầu bổ sung')

    def test_get_chua_co_minh_chung_thi_an_nut_va_hien_canh_bao(self):
        bk = self.tao_booking()
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.get(self.url(bk))
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertContains(phan_hoi, 'Khách hàng chưa tải minh chứng thanh toán tiền cọc.')
        self.assertNotContains(phan_hoi, self.NUT_XAC_NHAN)

    def test_khach_hang_vao_bi_403(self):                      # (b)
        bk = self.booking_da_co_minh_chung()
        self.client.force_login(self.kh)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)

    def test_chua_dang_nhap_bi_chuyen_trang(self):
        bk = self.booking_da_co_minh_chung()
        phan_hoi = self.client.get(self.url(bk))
        self.assertEqual(phan_hoi.status_code, 302)
        self.assertIn('/dang-nhap/', phan_hoi['Location'])

    def test_nhiep_anh_gia_khac_da_duyet_nhan_404(self):
        bk = self.booking_da_co_minh_chung()
        self.client.force_login(self.nag2_user)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)

    def test_post_xac_nhan_chuyen_trang_va_booking_thanh_chot(self):   # (c)
        bk = self.booking_da_co_minh_chung()
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'xac_nhan'}, follow=True)
        self.assertEqual(phan_hoi.redirect_chain, [(self.url(bk), 302)])
        self.assertContains(phan_hoi, 'Đã xác nhận tiền cọc. Booking được chốt.')
        self.assertContains(phan_hoi, 'Booking đã được chốt.')                           # dòng thân thiện khi đã chốt
        self.assertNotContains(phan_hoi, self.NUT_XAC_NHAN)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHOT_BOOKING)

    def test_post_bo_sung_co_ly_do_thanh_cong(self):           # (d)
        bk = self.booking_da_co_minh_chung()
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'bo_sung', 'ly_do': 'Ảnh bị mờ'}, follow=True)
        self.assertEqual(phan_hoi.redirect_chain, [(self.url(bk), 302)])
        self.assertContains(phan_hoi, 'Đã gửi yêu cầu bổ sung minh chứng cho Khách hàng.')
        self.assertContains(phan_hoi, 'Ảnh bị mờ')                                       # hộp "Đã yêu cầu Khách hàng bổ sung"
        self.assertEqual(ThanhToan.objects.get(MaBooking=bk).LyDoTuChoi, 'Ảnh bị mờ')
        self.assertNotContains(phan_hoi, self.NUT_XAC_NHAN)                              # đang chờ khách nộp lại

    def test_post_bo_sung_thieu_ly_do_o_lai_trang_va_hien_loi(self):
        bk = self.booking_da_co_minh_chung()
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'bo_sung', 'ly_do': ''})
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertContains(phan_hoi, 'Vui lòng nhập lý do yêu cầu bổ sung.')
        self.assertIsNone(ThanhToan.objects.get(MaBooking=bk).LyDoTuChoi)

    def test_hanh_dong_la_hien_thong_bao_khong_hop_le(self):    # (e)
        bk = self.booking_da_co_minh_chung()
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.post(self.url(bk), {'hanh_dong': 'xoa_het'})
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertContains(phan_hoi, 'Thao tác không hợp lệ.')
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.CHO_DAT_COC)

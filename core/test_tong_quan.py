# core/test_tong_quan.py - B9: kiểm tra Trang tổng quan sau đăng nhập. Chạy: python manage.py test core.test_tong_quan
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import url_trang_chu
from bookings.models import Booking
from bookings.test_tiep_nhan import tao_nag, tao_user          # hàm dựng tài khoản / Nhiếp ảnh gia mẫu của nhóm Booking
from core.constants import (KetQuaDuyetHoSo, LoaiHauKy, TrangThaiBooking as BK, TrangThaiDoc, TrangThaiHoSo,
                            TrangThaiSlot as SL, VaiTro)
from notifications.models import ThongBao
from profiles.models import DuyetHoSo, GoiDichVu, LoaiHinhChup
from schedule.models import LichKhaDung

URL = '/tong-quan/'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TongQuanBase(TestCase):
    def setUp(self):
        self.khach = tao_user('khach_a', VaiTro.KHACH_HANG, first_name='An', last_name='Nguyễn')
        self.khach_b = tao_user('khach_b', VaiTro.KHACH_HANG)
        self.nag = tao_nag('nag')
        self.nag_khac = tao_nag('nag_khac')
        loai = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=loai, TenGoi='Gói cơ bản',
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.goi_khac = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag_khac, MaLoaiHinh=loai,
                                                 TenGoi='Gói người khác', Gia=2000000, ThoiLuongChup=60,
                                                 LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.ngay = timezone.localdate() + timedelta(days=3)
        self._gio = 7

    def tao_booking(self, nag=None, khach=None, trang_thai=BK.CHO_XAC_NHAN):
        nag = nag or self.nag
        goi = self.goi if nag == self.nag else self.goi_khac
        self._gio += 1                                   # mỗi Booking một khung giờ riêng
        gio = f'{self._gio:02d}:00'
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=self.ngay, GioBatDau=gio,
                                          GioKetThuc=f'{self._gio + 2:02d}:00', TrangThai=SL.DANG_GIU)
        return Booking.objects.create(
            MaKhachHang=khach or self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
            NgayGioChup=timezone.make_aware(timezone.datetime.combine(self.ngay, timezone.datetime.strptime(gio, '%H:%M').time())),
            DiaDiem='Hồ Gươm', SoNguoi=2, Concept='Vintage', TrangThai=trang_thai)

    def mo(self, user):
        self.client.force_login(user)
        return self.client.get(URL)


class TruyCap(TongQuanBase):
    def test_chua_dang_nhap_chuyen_ve_dang_nhap(self):
        res = self.client.get(URL)
        self.assertRedirects(res, f"{reverse('login')}?next={URL}", fetch_redirect_response=False)

    def test_quan_tri_chuyen_sang_trang_quan_tri(self):
        admin = tao_user('qt', VaiTro.QUAN_TRI_VIEN)
        self.assertRedirects(self.mo(admin), reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_trang_dich_sau_dang_nhap_la_tong_quan(self):
        self.assertEqual(reverse('dashboard'), URL)
        self.assertEqual(url_trang_chu(self.khach), URL)
        self.assertEqual(url_trang_chu(self.nag.MaTaiKhoan), URL)


class KhachHang(TongQuanBase):
    def test_chi_hien_booking_dang_xu_ly_cua_minh(self):
        dang = self.tao_booking(trang_thai=BK.CHO_DAT_COC)
        self.tao_booking(trang_thai=BK.HOAN_THANH)
        self.tao_booking(trang_thai=BK.DA_HUY)
        self.tao_booking(khach=self.khach_b)                          # của người khác
        res = self.mo(self.khach)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'core/tong_quan.html')
        self.assertEqual(res.context['khach']['so_dang_xu_ly'], 1)
        self.assertEqual([b['ma'] for b in res.context['khach']['dang_xu_ly']], [dang.pk])
        self.assertContains(res, reverse('chi_tiet_booking', args=[dang.pk]))
        self.assertContains(res, BK.CHO_DAT_COC)

    def test_chua_co_booking_hien_cau_trong(self):
        res = self.mo(self.khach)
        self.assertContains(res, 'Bạn chưa có Booking nào đang xử lý.')
        self.assertContains(res, 'Tìm nhiếp ảnh gia')

    def test_chi_hien_thong_bao_chua_doc_cua_minh(self):
        ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe='Yêu cầu được chấp nhận', NoiDung='Hãy đặt cọc.')
        ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe='Thông báo cũ', NoiDung='x', TrangThaiDoc=TrangThaiDoc.DA_DOC)
        ThongBao.objects.create(MaNguoiNhan=self.khach_b, TieuDe='Của người khác', NoiDung='x')
        res = self.mo(self.khach)
        self.assertContains(res, 'Yêu cầu được chấp nhận')
        self.assertNotContains(res, 'Thông báo cũ')
        self.assertNotContains(res, 'Của người khác')
        self.assertEqual(res.context['khach']['so_thong_bao'], 1)

    def test_khong_co_thong_bao(self):
        self.assertContains(self.mo(self.khach), 'Không có thông báo mới.')

    def test_thong_bao_moi_nhat_len_dau_roi_moi_cat_5(self):
        # Tạo từ MỚI nhất đến CŨ nhất, để mã (pk) ngược với thời gian: nếu chỉ dựa vào thứ tự tạo / mã thì sẽ lấy nhầm 5 cái cũ nhất.
        bay_gio = timezone.now()
        for i in range(6, -1, -1):                                       # i = 6 là mới nhất, i = 0 là cũ nhất
            tb = ThongBao.objects.create(MaNguoiNhan=self.khach, TieuDe=f'TB{i}', NoiDung='x')
            ThongBao.objects.filter(pk=tb.pk).update(NgayTao=bay_gio - timedelta(hours=10 - i))   # NgayTao tự điền khi tạo, nên chỉnh lại bằng update
        res = self.mo(self.khach)
        self.assertEqual([t['tieu_de'] for t in res.context['khach']['thong_bao']],
                         ['TB6', 'TB5', 'TB4', 'TB3', 'TB2'])            # 5 thông báo MỚI nhất, mới nhất lên đầu
        self.assertEqual(res.context['khach']['so_thong_bao'], 7)

    def test_chi_hien_toi_da_5_dong(self):
        for _ in range(7):
            self.tao_booking()
        res = self.mo(self.khach)
        self.assertEqual(res.context['khach']['so_dang_xu_ly'], 7)
        self.assertEqual(len(res.context['khach']['dang_xu_ly']), 5)


class NhiepAnhGiaDaDuyet(TongQuanBase):
    def test_yeu_cau_moi_va_lich_sap_toi(self):
        moi = self.tao_booking(trang_thai=BK.CHO_XAC_NHAN)
        chot = self.tao_booking(trang_thai=BK.CHOT_BOOKING)
        self.tao_booking(trang_thai=BK.HOAN_THANH)
        self.tao_booking(nag=self.nag_khac)                           # Booking của Nhiếp ảnh gia khác
        res = self.mo(self.nag.MaTaiKhoan)
        nag = res.context['nag']
        self.assertTrue(nag['da_duyet'])
        self.assertEqual(nag['so_yeu_cau_moi'], 1)
        self.assertEqual([b['ma'] for b in nag['yeu_cau_moi']], [moi.pk])
        self.assertEqual(nag['so_lich_sap_toi'], 1)
        self.assertEqual([b['ma'] for b in nag['lich_sap_toi']], [chot.pk])
        self.assertContains(res, reverse('chi_tiet_yeu_cau_booking', args=[moi.pk]))
        self.assertContains(res, 'Yêu cầu Booking mới')
        self.assertContains(res, 'Lịch sắp tới')

    def test_dem_khung_gio_trong(self):
        LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=self.ngay, GioBatDau='06:00',
                                   GioKetThuc='07:00', TrangThai=SL.TRONG)
        self.assertEqual(self.mo(self.nag.MaTaiKhoan).context['nag']['so_khung_gio_trong'], 1)

    def test_khong_co_gi(self):
        res = self.mo(self.nag.MaTaiKhoan)
        self.assertContains(res, 'Không có yêu cầu Booking mới.')
        self.assertContains(res, 'Chưa có buổi chụp nào sắp tới.')
        self.assertContains(res, TrangThaiHoSo.DA_DUYET)


class NhiepAnhGiaChuaDuyet(TongQuanBase):
    def _doi_trang_thai(self, trang_thai):
        user = self.nag.MaTaiKhoan
        user.trang_thai_ho_so = trang_thai
        user.save()
        return user

    def test_cho_duyet_chi_thay_tinh_trang_ho_so(self):
        self.tao_booking()
        res = self.mo(self._doi_trang_thai(TrangThaiHoSo.CHO_DUYET))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['nag']['da_duyet'])
        self.assertNotIn('yeu_cau_moi', res.context['nag'])
        self.assertContains(res, 'Tình trạng hồ sơ')
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')
        self.assertNotContains(res, 'Yêu cầu Booking mới')
        self.assertNotContains(res, 'Lịch sắp tới')

    def _tao_luot(self, lan, ket_qua=None, phan_hoi=None, cung_thoi_diem_nop=False):
        """Tạo một lượt duyệt hồ sơ. ket_qua=None là lượt đang chờ duyệt (nộp / nộp lại).
        DuyetHoSo.save() tự đồng bộ User.trang_thai_ho_so theo lượt MỚI NHẤT (đúng như hệ thật).
        cung_thoi_diem_nop=True: mọi lượt cùng một ThoiDiemNop, để chỉ còn LanNop phân biệt lượt mới / cũ."""
        gio_nop = timezone.now() - timedelta(days=3) + (timedelta(0) if cung_thoi_diem_nop else timedelta(hours=lan))
        du_lieu = dict(MaNhiepAnhGia=self.nag, LanNop=lan, ThoiDiemNop=gio_nop)
        if ket_qua:                                                     # ràng buộc DB: có kết quả thì có Quản trị viên + ThoiDiemDuyet >= ThoiDiemNop
            du_lieu.update(MaQuanTriVien=self.admin, ThoiDiemDuyet=timezone.now() - timedelta(days=1),
                           KetQua=ket_qua, NoiDungPhanHoi=phan_hoi)
        return DuyetHoSo.objects.create(**du_lieu)

    def setUp(self):
        super().setUp()
        self.admin = tao_user('qt', VaiTro.QUAN_TRI_VIEN)

    def test_bi_tu_choi_hien_ly_do(self):
        self._tao_luot(1, KetQuaDuyetHoSo.DA_TU_CHOI, 'Ảnh Portfolio chưa rõ nét.')       # save() đưa hồ sơ sang 'Đã từ chối'
        res = self.mo(self.nag.MaTaiKhoan)
        self.assertContains(res, 'Ảnh Portfolio chưa rõ nét.')
        self.assertContains(res, TrangThaiHoSo.DA_TU_CHOI)
        self.assertFalse(res.context['nag']['can_chinh_sua'])

    def test_hai_luot_duyet_hien_ly_do_cua_luot_moi_nhat(self):
        # Hai lượt CÙNG ThoiDiemNop: chỉ LanNop phân biệt cũ / mới, nên chỉ đúng khi view sắp rõ ràng theo '-LanNop'.
        self._tao_luot(1, KetQuaDuyetHoSo.DA_TU_CHOI, 'Lý do của lượt cũ.', cung_thoi_diem_nop=True)
        self._tao_luot(2, KetQuaDuyetHoSo.DA_TU_CHOI, 'Lý do của lượt mới nhất.', cung_thoi_diem_nop=True)
        res = self.mo(self.nag.MaTaiKhoan)
        self.assertEqual(res.context['nag']['phan_hoi'], 'Lý do của lượt mới nhất.')
        self.assertContains(res, 'Lý do của lượt mới nhất.')
        self.assertNotContains(res, 'Lý do của lượt cũ.')

    def test_yeu_cau_chinh_sua_hien_ly_do_va_nut_cap_nhat(self):
        self._tao_luot(1, KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA, 'Bổ sung thêm 3 ảnh Portfolio.')
        user = self.nag.MaTaiKhoan
        user.refresh_from_db()
        self.assertEqual(user.trang_thai_ho_so, TrangThaiHoSo.CHO_DUYET)  # quy ước nhóm: hồ sơ vẫn 'Chờ duyệt'
        res = self.mo(user)
        self.assertTrue(res.context['nag']['can_chinh_sua'])
        self.assertContains(res, 'Quản trị viên yêu cầu chỉnh sửa hồ sơ')
        self.assertContains(res, 'Bổ sung thêm 3 ảnh Portfolio.')
        self.assertContains(res, 'Cập nhật hồ sơ')                        # nút để sửa
        self.assertNotContains(res, 'đang chờ Quản trị viên duyệt')       # không hiện câu "đang chờ duyệt"
        self.assertNotContains(res, 'Yêu cầu Booking mới')                # vẫn chỉ thấy tình trạng hồ sơ

    def test_yeu_cau_chinh_sua_lan_dau_roi_nop_lai_hien_dang_cho_duyet(self):
        # Lượt 1: bị yêu cầu chỉnh sửa. Lượt 2: Nhiếp ảnh gia đã nộp lại, chưa có kết quả -> không được hiện lại lý do cũ.
        self._tao_luot(1, KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA, 'Lý do đã được xử lý.')
        self._tao_luot(2)
        res = self.mo(self.nag.MaTaiKhoan)
        self.assertFalse(res.context['nag']['can_chinh_sua'])
        self.assertEqual(res.context['nag']['phan_hoi'], '')
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')
        self.assertNotContains(res, 'Lý do đã được xử lý.')
        self.assertNotContains(res, 'Quản trị viên yêu cầu chỉnh sửa hồ sơ')

    def test_cho_duyet_lan_dau_khong_co_ly_do(self):
        self._tao_luot(1)                                               # vừa nộp lần đầu, chưa có kết quả
        res = self.mo(self.nag.MaTaiKhoan)
        self.assertFalse(res.context['nag']['can_chinh_sua'])
        self.assertContains(res, 'đang chờ Quản trị viên duyệt')

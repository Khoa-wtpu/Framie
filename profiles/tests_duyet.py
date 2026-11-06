# profiles/tests_duyet.py - K7: Duyệt hồ sơ Nhiếp ảnh gia (UC1.5). Chạy: python manage.py test profiles.tests_duyet
# Cần config/urls.py có include('profiles.urls_duyet') và đã có bookings.services (gui_email_sau_commit, của Tuyền).
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.constants import KetQuaDuyetHoSo as KQ, TrangThaiHoSo, VaiTro
from profiles import duyet_ho_so as dh
from profiles.models import DuyetHoSo, NhiepAnhGia

User = get_user_model()
GUI_TB = 'profiles.duyet_ho_so.gui_thong_bao'
GUI_EMAIL = 'profiles.duyet_ho_so.gui_email_sau_commit'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DuyetHoSoTestCase(TestCase):
    def setUp(self):
        self.dem = 0
        self.nhom_qtv, _ = Group.objects.get_or_create(name=VaiTro.QUAN_TRI_VIEN)
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.nhom_khach, _ = Group.objects.get_or_create(name=VaiTro.KHACH_HANG)
        self.qtv = self.tao_user('qtv', self.nhom_qtv)
        self.khach = self.tao_user('khach', self.nhom_khach)
        self.nag = self.tao_nag('Lê', 'Khôi')
        self.luot = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag)
        self.url_ds = reverse('admin_profile_review')
        self.url_ct = reverse('duyet_ho_so_chi_tiet', args=[self.luot.pk])

    # ---- dữ liệu mẫu ----
    def tao_user(self, ten_dang_nhap, nhom, **kw):
        self.dem += 1
        user = User.objects.create_user(ten_dang_nhap, f'{ten_dang_nhap}@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09300000{self.dem:02d}', **kw)
        user.groups.add(nhom)
        return user

    def tao_nag(self, ho, ten):
        self.dem += 1
        user = self.tao_user(f'nag{self.dem}', self.nhom_nag, first_name=ten, last_name=ho)
        user.trang_thai_ho_so = TrangThaiHoSo.CHO_DUYET
        user.save()
        return NhiepAnhGia.objects.create(
            MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='Chuyên ảnh cưới',
            NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')

    def trang_thai(self, nag=None):
        return User.objects.get(pk=(nag or self.nag).MaTaiKhoan_id).trang_thai_ho_so

    def quyet_dinh(self, hanh_dong, noi_dung='', luot=None, **kw):
        self.client.force_login(self.qtv)
        url = reverse('duyet_ho_so_chi_tiet', args=[(luot or self.luot).pk])
        return self.client.post(url, {'hanh_dong': hanh_dong, 'noi_dung': noi_dung}, **kw)

    def cac_thong_bao(self, r):
        return [(m.level_tag, str(m)) for m in r.context['messages']]

    # ---- quyền truy cập ----
    def test_khach_vang_lai_va_nguoi_khac_khong_vao_duoc(self):
        for url in (self.url_ds, self.url_ct):
            self.assertNotEqual(self.client.get(url).status_code, 200)           # chưa đăng nhập
            self.client.force_login(self.khach)
            self.assertNotEqual(self.client.get(url).status_code, 200)           # Khách hàng
            self.client.force_login(self.nag.MaTaiKhoan)
            self.assertNotEqual(self.client.get(url).status_code, 200)           # chính Nhiếp ảnh gia
            self.client.logout()

    def test_nguoi_khac_khong_gui_duoc_quyet_dinh(self):
        self.client.force_login(self.khach)
        self.client.post(self.url_ct, {'hanh_dong': dh.PHE_DUYET})
        self.luot.refresh_from_db()
        self.assertIsNone(self.luot.KetQua)
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.CHO_DUYET)

    # ---- danh sách ----
    def test_danh_sach_mac_dinh_la_tab_cho_xu_ly(self):
        self.client.force_login(self.qtv)
        r = self.client.get(self.url_ds)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['tab'], 'cho')
        self.assertEqual(list(r.context['cac_luot']), [self.luot])
        self.assertContains(r, 'Khôi')
        self.assertContains(r, 'Chờ xử lý (1)')
        self.assertContains(r, 'Đã xử lý (0)')

    def test_tab_la_va_page_sai_khong_gay_loi(self):
        self.client.force_login(self.qtv)
        r = self.client.get(self.url_ds, {'tab': '<script>', 'page': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['tab'], 'cho')
        self.assertEqual(self.client.get(self.url_ds, {'page': 999}).status_code, 200)

    def test_tab_da_xu_ly_chi_co_luot_da_co_ket_qua(self):
        self.quyet_dinh(dh.TU_CHOI, 'Ảnh đại diện mờ')
        nag2 = self.tao_nag('Trần', 'An')
        DuyetHoSo.objects.create(MaNhiepAnhGia=nag2)
        r = self.client.get(self.url_ds, {'tab': 'da_xu_ly'})
        self.assertEqual(list(r.context['cac_luot']), [self.luot])
        self.assertContains(r, KQ.DA_TU_CHOI)
        self.assertEqual(r.context['so_cho'], 1)
        self.assertEqual(r.context['so_da_xu_ly'], 1)

    def test_tab_cho_xep_cu_nhat_len_dau_va_phan_trang(self):
        cac_luot = [self.luot]
        for i in range(11):
            cac_luot.append(DuyetHoSo.objects.create(MaNhiepAnhGia=self.tao_nag('Họ', f'Tên{i}'),
                                                     ThoiDiemNop=timezone.now() + timedelta(minutes=i + 1)))
        self.client.force_login(self.qtv)
        trang_1 = self.client.get(self.url_ds).context
        self.assertEqual(len(trang_1['cac_luot']), 10)
        self.assertEqual(trang_1['cac_luot'][0], self.luot)                      # nộp sớm nhất
        trang_2 = self.client.get(self.url_ds, {'page': 2}).context
        self.assertEqual(len(trang_2['cac_luot']), 2)

    def test_danh_sach_trong(self):
        self.luot.delete()
        self.client.force_login(self.qtv)
        self.assertContains(self.client.get(self.url_ds), 'Không có hồ sơ nào đang chờ xử lý.')

    # ---- trang chi tiết ----
    def test_chi_tiet_luot_dang_cho_co_form_quyet_dinh(self):
        self.client.force_login(self.qtv)
        r = self.client.get(self.url_ct)
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.context['form'])
        self.assertContains(r, 'Chuyên ảnh cưới')
        self.assertContains(r, 'Xác nhận')

    def test_chi_tiet_luot_da_xu_ly_khong_con_form(self):
        self.quyet_dinh(dh.TU_CHOI, 'Thiếu thông tin')
        r = self.client.get(self.url_ct)
        self.assertIsNone(r.context['form'])
        self.assertContains(r, 'Thiếu thông tin')

    def test_chi_tiet_khong_ton_tai_tra_404(self):
        self.client.force_login(self.qtv)
        self.assertEqual(self.client.get(reverse('duyet_ho_so_chi_tiet', args=[99999])).status_code, 404)

    # ---- Phê duyệt ----
    @mock.patch(GUI_EMAIL)
    @mock.patch(GUI_TB)
    def test_phe_duyet(self, gui_tb, gui_email):
        r = self.quyet_dinh(dh.PHE_DUYET, follow=True)
        self.luot.refresh_from_db()
        self.assertEqual(self.luot.KetQua, KQ.DA_DUYET)
        self.assertEqual(self.luot.MaQuanTriVien, self.qtv)
        self.assertIsNotNone(self.luot.ThoiDiemDuyet)
        self.assertIsNone(self.luot.NoiDungPhanHoi)
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.DA_DUYET)
        gui_tb.assert_called_once()
        self.assertEqual(gui_tb.call_args.args[0], self.nag.MaTaiKhoan)
        gui_email.assert_called_once()                                          # Phê duyệt: có Email
        self.assertEqual(r.redirect_chain[-1][0], self.url_ds)
        self.assertIn('success', [m[0] for m in self.cac_thong_bao(r)])

    # ---- Yêu cầu chỉnh sửa ----
    @mock.patch(GUI_EMAIL)
    @mock.patch(GUI_TB)
    def test_yeu_cau_chinh_sua_giu_trang_thai_cho_duyet(self, gui_tb, gui_email):
        self.quyet_dinh(dh.YEU_CAU_CHINH_SUA, 'Bổ sung ảnh QR rõ hơn')
        self.luot.refresh_from_db()
        self.assertEqual(self.luot.KetQua, KQ.YEU_CAU_CHINH_SUA)
        self.assertEqual(self.luot.NoiDungPhanHoi, 'Bổ sung ảnh QR rõ hơn')
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.CHO_DUYET)
        self.assertIn('Bổ sung ảnh QR rõ hơn', gui_tb.call_args.args[2])
        gui_email.assert_called_once()                                            # chỉ Phê duyệt mới gửi Email

    # ---- Từ chối ----
    @mock.patch(GUI_EMAIL)
    @mock.patch(GUI_TB)
    def test_tu_choi(self, gui_tb, gui_email):
        self.quyet_dinh(dh.TU_CHOI, 'Không đúng lĩnh vực')
        self.luot.refresh_from_db()
        self.assertEqual(self.luot.KetQua, KQ.DA_TU_CHOI)
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.DA_TU_CHOI)
        self.assertIn('Không đúng lĩnh vực', gui_tb.call_args.args[2])
        gui_email.assert_called_once()

    # ---- dữ liệu không hợp lệ ----
    def test_thieu_noi_dung_khi_tu_choi_hoac_yeu_cau_chinh_sua(self):
        for hanh_dong in (dh.TU_CHOI, dh.YEU_CAU_CHINH_SUA):
            for noi_dung in ('', '    ', '\n\t'):
                with self.subTest(hanh_dong=hanh_dong, noi_dung=repr(noi_dung)):
                    r = self.quyet_dinh(hanh_dong, noi_dung)
                    self.assertEqual(r.status_code, 200)                          # ở lại trang, báo lỗi ở ô nội dung
                    self.assertIn('noi_dung', r.context['form'].errors)
                    self.luot.refresh_from_db()
                    self.assertIsNone(self.luot.KetQua)
                    self.assertEqual(self.trang_thai(), TrangThaiHoSo.CHO_DUYET)

    def test_quyet_dinh_la_hoac_trong_bi_tu_choi(self):
        for hanh_dong in ('', 'xoa', 'PHE_DUYET', 'Đã duyệt'):
            with self.subTest(hanh_dong=hanh_dong):
                r = self.quyet_dinh(hanh_dong)
                self.assertEqual(r.status_code, 200)
                self.assertIn('hanh_dong', r.context['form'].errors)
                self.luot.refresh_from_db()
                self.assertIsNone(self.luot.KetQua)

    def test_noi_dung_qua_1000_ky_tu_bi_chan(self):
        r = self.quyet_dinh(dh.TU_CHOI, 'a' * 1001)
        self.assertIn('noi_dung', r.context['form'].errors)
        self.luot.refresh_from_db()
        self.assertIsNone(self.luot.KetQua)

    def test_noi_dung_dung_1000_ky_tu_duoc_nhan(self):
        self.quyet_dinh(dh.TU_CHOI, 'a' * 1000)
        self.luot.refresh_from_db()
        self.assertEqual(self.luot.KetQua, KQ.DA_TU_CHOI)

    # ---- xử lý đồng thời / lượt cũ ----
    @mock.patch(GUI_TB)
    def test_luot_da_xu_ly_khong_nhan_quyet_dinh_thu_hai(self, gui_tb):
        self.quyet_dinh(dh.TU_CHOI, 'Lý do A')
        r = self.quyet_dinh(dh.PHE_DUYET, follow=True)                            # người bấm sau
        self.luot.refresh_from_db()
        self.assertEqual(self.luot.KetQua, KQ.DA_TU_CHOI)                         # kết quả của người trước giữ nguyên
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.DA_TU_CHOI)
        self.assertEqual(gui_tb.call_count, 1)
        self.assertIn('info', [m[0] for m in self.cac_thong_bao(r)])

    @mock.patch(GUI_TB)
    def test_luot_cu_khi_nag_da_nop_lai_bi_chan(self, gui_tb):
        moi = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag, LanNop=2)
        with self.assertRaises(dh.DuyetHoSoLoi):
            dh.xu_ly_duyet_ho_so(self.luot.pk, self.qtv, dh.PHE_DUYET)
        self.luot.refresh_from_db()
        self.assertIsNone(self.luot.KetQua)
        gui_tb.assert_not_called()
        dh.xu_ly_duyet_ho_so(moi.pk, self.qtv, dh.TU_CHOI, 'Lý do')             # lượt mới nhất xử lý được
        moi.refresh_from_db()
        self.assertEqual(moi.KetQua, KQ.DA_TU_CHOI)

    # ---- service ----
    @mock.patch(GUI_TB)
    def test_service_chi_nhan_quan_tri_vien(self, gui_tb):
        for user in (self.khach, self.nag.MaTaiKhoan):
            with self.assertRaises(dh.DuyetHoSoLoi):
                dh.xu_ly_duyet_ho_so(self.luot.pk, user, dh.PHE_DUYET)
        self.luot.refresh_from_db()
        self.assertIsNone(self.luot.KetQua)
        gui_tb.assert_not_called()

    def test_service_khong_co_luot(self):
        with self.assertRaises(dh.DuyetHoSoLoi):
            dh.xu_ly_duyet_ho_so(99999, self.qtv, dh.PHE_DUYET)

    @mock.patch(GUI_EMAIL)
    @mock.patch(GUI_TB, return_value=None)
    def test_ket_qua_van_luu_khi_khong_tao_duoc_thong_bao(self, gui_tb, gui_email):      # ngoại lệ 3d
        r = self.quyet_dinh(dh.PHE_DUYET, follow=True)
        self.luot.refresh_from_db()
        self.assertEqual(self.luot.KetQua, KQ.DA_DUYET)
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.DA_DUYET)
        self.assertIn('warning', [m[0] for m in self.cac_thong_bao(r)])

    def test_loi_database_bao_cho_quan_tri_vien_va_khong_doi_trang_thai(self):          # ngoại lệ 3c
        with mock.patch('profiles.views_duyet.xu_ly_duyet_ho_so', side_effect=DatabaseError):
            r = self.quyet_dinh(dh.PHE_DUYET)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Không thể cập nhật kết quả xử lý')
        self.luot.refresh_from_db()
        self.assertIsNone(self.luot.KetQua)
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.CHO_DUYET)

    @mock.patch(GUI_TB)
    def test_loi_giua_chung_rollback_ca_ket_qua(self, gui_tb):
        gui_tb.side_effect = DatabaseError('hỏng giữa chừng')
        with self.assertRaises(DatabaseError):
            dh.xu_ly_duyet_ho_so(self.luot.pk, self.qtv, dh.PHE_DUYET)
        self.luot.refresh_from_db()
        self.assertIsNone(self.luot.KetQua)                                       # transaction.atomic hoàn tác
        self.assertEqual(self.trang_thai(), TrangThaiHoSo.CHO_DUYET)

    # ---- lịch sử các lần duyệt ----
    @mock.patch(GUI_TB)
    def test_chi_tiet_hien_lan_duyet_truoc(self, gui_tb):
        self.quyet_dinh(dh.YEU_CAU_CHINH_SUA, 'Sửa phần giới thiệu')
        moi = DuyetHoSo.objects.create(MaNhiepAnhGia=self.nag, LanNop=2)
        r = self.client.get(reverse('duyet_ho_so_chi_tiet', args=[moi.pk]))
        self.assertContains(r, 'Các lần duyệt trước')
        self.assertContains(r, 'Sửa phần giới thiệu')

    # ---- tìm kiếm và bộ lọc ----
    def tao_luot(self, ho, ten, lan_nop=1, **kw):
        return DuyetHoSo.objects.create(MaNhiepAnhGia=self.tao_nag(ho, ten), LanNop=lan_nop, **kw)

    def ds(self, **params):
        self.client.force_login(self.qtv)
        r = self.client.get(self.url_ds, params)
        self.assertEqual(r.status_code, 200)
        return r, list(r.context['cac_luot'])

    def test_tim_theo_ten_email_va_nhieu_tu_khoa(self):
        an = self.tao_luot('Trần', 'An')
        _, kq = self.ds(q='an')                                                    # khớp tên của An (không phân biệt hoa thường)
        self.assertEqual(kq, [an])
        _, kq = self.ds(q='Lê Khôi')                                               # họ + tên: mỗi từ khớp một trường
        self.assertEqual(kq, [self.luot])
        _, kq = self.ds(q=an.MaNhiepAnhGia.MaTaiKhoan.email)
        self.assertEqual(kq, [an])
        _, kq = self.ds(q='Lê An')                                                 # họ của người này + tên người kia: không khớp ai
        self.assertEqual(kq, [])
        _, kq = self.ds(q='   ')
        self.assertEqual(len(kq), 2)                                               # chỉ dấu cách = không lọc

    def test_tim_kiem_khong_bi_loi_voi_ky_tu_dac_biet(self):
        for q in ("%", "_", "'; DROP TABLE x;--", "<script>", 'x' * 100):
            with self.subTest(q=q):
                self.ds(q=q)

    def test_loc_theo_lan_nop(self):
        lai = self.tao_luot('Phạm', 'Bình', lan_nop=2)
        _, kq = self.ds(lan_nop='dau')
        self.assertEqual(kq, [self.luot])
        _, kq = self.ds(lan_nop='nop_lai')
        self.assertEqual(kq, [lai])

    def test_loc_theo_thoi_diem_nop(self):
        cu = self.tao_luot('Cũ', 'Nam', ThoiDiemNop=timezone.now() - timedelta(days=10))
        gan_day = self.tao_luot('Gần', 'Đây', ThoiDiemNop=timezone.now() - timedelta(days=2))
        hom_nay = timezone.localdate()
        ngay = lambda d: (hom_nay - timedelta(days=d)).isoformat()
        _, kq = self.ds(tu_ngay=ngay(3))
        self.assertCountEqual(kq, [self.luot, gan_day])                            # từ 3 ngày trước đến nay
        _, kq = self.ds(den_ngay=ngay(5))
        self.assertEqual(kq, [cu])
        _, kq = self.ds(tu_ngay=ngay(10), den_ngay=ngay(10))                       # cả ngày đầu lẫn ngày cuối đều được tính
        self.assertEqual(kq, [cu])
        _, kq = self.ds(tu_ngay=ngay(3), den_ngay=ngay(1))
        self.assertEqual(kq, [gan_day])

    def test_ngay_sai_hoac_dao_nguoc_khong_gay_loi(self):
        hom_nay = timezone.localdate()
        r, kq = self.ds(tu_ngay='khong-phai-ngay', den_ngay='2025-13-45')          # bị bỏ qua
        self.assertEqual(kq, [self.luot])
        r, kq = self.ds(tu_ngay=hom_nay.isoformat(), den_ngay=(hom_nay - timedelta(days=5)).isoformat())
        self.assertContains(r, 'Ngày kết thúc phải sau hoặc cùng ngày bắt đầu.')   # báo trong bảng bộ lọc
        self.assertEqual(kq, [self.luot])                                          # chỉ áp dụng ngày bắt đầu

    @mock.patch(GUI_EMAIL)
    @mock.patch(GUI_TB)
    def test_loc_theo_trang_thai_ho_so(self, *_):
        khac = self.tao_luot('Đặng', 'Dũng')
        self.quyet_dinh(dh.PHE_DUYET, luot=khac)                                   # hồ sơ của Dũng -> Đã duyệt
        r, kq = self.ds(tab='da_xu_ly', trang_thai=TrangThaiHoSo.DA_DUYET)
        self.assertEqual(kq, [khac])
        _, kq = self.ds(tab='cho', trang_thai=TrangThaiHoSo.CHO_DUYET)
        self.assertEqual(kq, [self.luot])
        _, kq = self.ds(tab='cho', trang_thai=[TrangThaiHoSo.DA_DUYET, TrangThaiHoSo.DA_TU_CHOI])
        self.assertEqual(kq, [])

    def test_dem_so_bo_loc_gom_ca_khoang_ngay(self):
        hom_nay = timezone.localdate().isoformat()
        r, _ = self.ds(tu_ngay=hom_nay, trang_thai=[TrangThaiHoSo.CHO_DUYET], lan_nop='dau')
        self.assertEqual(r.context['so_bo_loc'], 3)                                # 1 khoảng ngày + 1 trạng thái + 1 lần nộp
        self.assertContains(r, 'class="duyet__so-loc">3<')

    def test_khong_con_bo_loc_loai_hinh(self):
        r, _ = self.ds()
        self.assertNotContains(r, 'Loại hình chụp')

    @mock.patch(GUI_TB)
    def test_loc_theo_ket_qua_chi_o_tab_da_xu_ly(self, _):
        khac = self.tao_luot('Đặng', 'Dũng')
        self.quyet_dinh(dh.TU_CHOI, 'Lý do')
        self.quyet_dinh(dh.YEU_CAU_CHINH_SUA, 'Sửa', luot=khac)
        _, kq = self.ds(tab='da_xu_ly', ket_qua=KQ.DA_TU_CHOI)
        self.assertEqual(kq, [self.luot])
        _, kq = self.ds(tab='da_xu_ly', ket_qua=KQ.YEU_CAU_CHINH_SUA)
        self.assertEqual(kq, [khac])
        cho = self.tao_luot('Bùi', 'Hà')                                           # một lượt đang chờ
        _, kq = self.ds(tab='cho', ket_qua=KQ.DA_TU_CHOI)                          # tab Chờ xử lý bỏ qua nhóm lọc Kết quả
        self.assertEqual(kq, [cho])

    @mock.patch(GUI_EMAIL)
    @mock.patch(GUI_TB)
    def test_chon_nhieu_muc_trong_mot_nhom_la_hoac(self, *_):
        khac = self.tao_luot('Đặng', 'Dũng')
        ba = self.tao_luot('Ngô', 'Bảo')
        self.quyet_dinh(dh.TU_CHOI, 'Lý do')
        self.quyet_dinh(dh.YEU_CAU_CHINH_SUA, 'Sửa', luot=khac)
        self.quyet_dinh(dh.PHE_DUYET, luot=ba)
        _, kq = self.ds(tab='da_xu_ly', ket_qua=[KQ.DA_TU_CHOI, KQ.YEU_CAU_CHINH_SUA])
        self.assertCountEqual(kq, [self.luot, khac])

    def test_chon_ca_hai_lan_nop_la_khong_loc(self):
        lai = self.tao_luot('Phạm', 'Bình', lan_nop=2)
        _, kq = self.ds(lan_nop=['dau', 'nop_lai'])
        self.assertCountEqual(kq, [self.luot, lai])

    def test_o_tim_kiem_co_nut_bo_loc_nam_trong_o(self):
        r, _ = self.ds()
        html = r.content.decode()
        self.assertContains(r, 'id="nut-bo-loc"')
        self.assertContains(r, 'id="bang-bo-loc"')
        # nút Bộ lọc nằm bên trong khối .duyet__pill (trước nút Tìm kiếm), không xuống hàng riêng
        pill = html[html.index('class="duyet__pill"'):html.index('id="bang-bo-loc"')]
        self.assertLess(pill.index('nut-bo-loc'), pill.index('duyet__gui'))
        self.assertNotIn('Kết quả', html[html.index('id="bang-bo-loc"'):html.index('duyet__ket-qua-dau')])   # tab Chờ xử lý: không có nhóm Kết quả

    def test_sap_xep_mac_dinh_va_dao_nguoc(self):
        moi = self.tao_luot('Hồ', 'Giang', ThoiDiemNop=timezone.now() + timedelta(hours=1))
        _, kq = self.ds()
        self.assertEqual(kq, [self.luot, moi])                                     # tab Chờ xử lý: cũ nhất trước
        _, kq = self.ds(sap_xep='moi')
        self.assertEqual(kq, [moi, self.luot])

    def test_gia_tri_loc_sai_duoc_bo_qua(self):
        r, kq = self.ds(trang_thai='xxx', lan_nop='xxx', ket_qua='xxx', sap_xep='xxx')
        self.assertEqual(kq, [self.luot])
        self.assertContains(r, 'Lê')                                               # trang vẫn hiển thị bình thường

    def test_so_tren_tab_khong_phu_thuoc_bo_loc_va_phan_trang_giu_bo_loc(self):
        for i in range(11):
            self.tao_luot('Họ', f'Lọc{i}')
        r, kq = self.ds(q='Lọc')
        self.assertEqual(r.context['so_cho'], 12)                                  # tổng, không phải số kết quả lọc
        self.assertEqual(r.context['so_ket_qua'], 11)
        self.assertEqual(len(kq), 10)
        self.assertContains(r, 'q=L%E1%BB%8Dc')                                    # liên kết sang trang 2 giữ từ khóa
        self.assertContains(r, 'Tìm thấy 11 hồ sơ.')

    def test_khong_khop_hien_thong_bao_rieng(self):
        r, _ = self.ds(q='khong-ai-ten-nhu-vay')
        self.assertContains(r, 'Không có hồ sơ nào khớp tìm kiếm và bộ lọc.')
        self.assertContains(r, 'Xóa bộ lọc')

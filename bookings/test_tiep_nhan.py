# =====================================================================
# CHÚ GIẢI CÁC LỆNH THƯỜNG GẶP TRONG FILE TEST (dành cho người không chuyên lập trình)
#   Test = chương trình nhỏ tự kiểm tra xem code chính có chạy đúng không. Mỗi hàm 'test_...' kiểm tra MỘT tình huống.
#   self.client.get(địa_chỉ)       : giả lập người dùng MỞ một trang.
#   self.client.post(địa_chỉ, ...) : giả lập người dùng BẤM NÚT / GỬI BIỂU MẪU.
#   self.client.force_login(tk)    : giả lập đã đăng nhập bằng tài khoản 'tk' (khỏi gõ mật khẩu).
#   bk.refresh_from_db()           : đọc lại Booking từ cơ sở dữ liệu để thấy giá trị mới nhất.
#   self.assertEqual(a, b)         : khẳng định a bằng b; nếu khác thì test báo THẤT BẠI.
#   self.assertContains(trang, chữ): khẳng định trang có hiện chữ đó.   assertNotContains: khẳng định KHÔNG hiện.
#   self.assertRedirects(...)      : khẳng định người dùng được chuyển sang đúng trang kia.
#   with self.captureOnCommitCallbacks(execute=True): cho các việc 'hẹn chạy sau khi lưu xong' (gửi Email) chạy thật trong test.
#   mail.outbox                    : hộp thư đi GIẢ của lúc test - dùng để kiểm tra Email đã gửi (không gửi mail thật).
#   Cơ sở dữ liệu dùng khi test là bản TẠM, xóa sau mỗi test, nên không ảnh hưởng dữ liệu thật.
# =====================================================================
# =====================================================================
# bookings/test_tiep_nhan.py - Test cho bookings/tiep_nhan.py (UC4.3, UC4.4, UC4.5)
# Chạy:  python manage.py test bookings.test_tiep_nhan
# =====================================================================
# timedelta: một khoảng thời gian (ví dụ 3 ngày) để cộng/trừ vào ngày giờ.
from datetime import timedelta
# count: bộ đếm tự tăng 1, 2, 3... dùng để tạo số điện thoại không bị trùng.
from itertools import count
# re: tìm đường link 'sang trang 2' trong HTML. unescape: đổi '&amp;' trong link HTML về '&' để giả lập bấm link.
import re
from html import unescape
# urljoin: ghép link với địa chỉ trang đang mở đúng như trình duyệt (link chỉ có '?page=2...' thì giữ đường dẫn trang hiện tại;
# link đã là đường dẫn đầy đủ thì dùng luôn đường dẫn đó).
from urllib.parse import urljoin
# mock: công cụ 'giả lập'; ở đây dùng để giả vờ máy chủ gửi mail bị hỏng.
from unittest import mock

# Lấy bảng tài khoản người dùng của dự án.
from django.contrib.auth import get_user_model
# Group: nhóm vai trò (Khách hàng, Nhiếp ảnh gia...).
from django.contrib.auth.models import Group
# mail: để xem hộp thư đi giả lúc test.
from django.core import mail
# TestCase: lớp nền để viết test. override_settings: đổi tạm cấu hình trong lúc test.
from django.test import TestCase, override_settings
# reverse: từ tên đường dẫn suy ra địa chỉ URL thật.
from django.urls import reverse
# timezone: lấy giờ hiện tại, đổi giờ theo múi giờ.
from django.utils import timezone

# giu_cho (UC4.1): dùng để kiểm tra khách khác có giữ chỗ lại được khung giờ vừa được trả.
from bookings import giu_cho as uc41
# File đang được kiểm thử (UC4.3 - UC4.5); gọi tắt là 'uc'.
from bookings import tiep_nhan as uc
# services: nơi chứa hàm gửi Email dùng chung (send_mail nằm ở đây nên mock phải trỏ tới module này).
from bookings import services
# Hai bảng: Booking và Lịch sử đổi trạng thái Booking.
from bookings.models import Booking, LichSuTrangThaiBooking
# Các hằng số trạng thái. Đặt tên ngắn: BK = trạng thái Booking, SL = trạng thái khung giờ (slot).
from core.constants import (
    BenThucHien, LoaiHauKy, LoaiThanhToan, TrangThaiBooking as BK, TrangThaiGuiEmail, TrangThaiHoSo, TrangThaiSlot as SL, VaiTro,
)
# Bảng thông báo trên web.
from notifications.models import ThongBao
# tinh_so_tien: hàm tính tiền cọc/phần còn lại dùng chung với module Thanh toán.
from payments.models import tinh_so_tien
# Các bảng: Nhiếp ảnh gia, Gói dịch vụ, Loại hình chụp.
from profiles.models import GoiDichVu, LoaiHinhChup, NhiepAnhGia
# LichKhaDung: bảng khung giờ (slot) trong lịch của Nhiếp ảnh gia.
from schedule.models import LichKhaDung

# Đặt tên 'User' cho bảng tài khoản để dùng ngắn gọn bên dưới.
User = get_user_model()
# Bộ đếm bắt đầu từ 1; mỗi tài khoản lấy một số kế tiếp làm số điện thoại (cột này không được trùng).
_so = count(1)   # đếm để mỗi tài khoản có số điện thoại riêng (cột so_dien_thoai là UNIQUE)


# Hàm tiện ích: tạo nhanh một tài khoản thử nghiệm với tên, vai trò và các thông tin phụ.
def tao_user(ten, nhom=None, **kw):
    # Tạo tài khoản với email, mật khẩu và số điện thoại riêng.
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 so_dien_thoai=f'09{next(_so):08d}', **kw)
    # Nếu có chỉ định vai trò thì thêm tài khoản vào nhóm vai trò đó.
    if nhom:
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    return u


# Hàm tiện ích: tạo một Nhiếp ảnh gia (mặc định hồ sơ 'Đã duyệt') kèm hồ sơ giả đủ các trường bắt buộc.
def tao_nag(ten, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET):
    user = tao_user(ten, VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=trang_thai_ho_so)
    return NhiepAnhGia.objects.create(MaTaiKhoan=user, AnhDaiDien='a.jpg', GioiThieu='g', NganHang='b',
                                      SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')


# Dùng cách băm mật khẩu nhanh trong lúc test để chạy nhanh hơn; KHÔNG ảnh hưởng website thật.
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])   # test nhanh hơn, không ảnh hưởng web thật
# LỚP NỀN: chuẩn bị sẵn dữ liệu mẫu dùng chung cho tất cả nhóm test bên dưới.
class TiepNhanBase(TestCase):
    # setUp tự chạy trước MỖI test: dựng lại dữ liệu thử nghiệm từ đầu.
    def setUp(self):
        # Hai khách hàng thử nghiệm.
        self.khach = tao_user('khach_a', VaiTro.KHACH_HANG, first_name='An', last_name='Nguyễn')
        self.khach_b = tao_user('khach_b', VaiTro.KHACH_HANG)
        # Hai Nhiếp ảnh gia: 'nag' (người đang thao tác) và 'nag_khac' (người ngoài, để kiểm tra hai bên không xem/sửa được Booking của nhau).
        self.nag = tao_nag('nag')
        self.nag_khac = tao_nag('nag_khac')
        # Một loại hình chụp, và hai gói dịch vụ (mỗi Nhiếp ảnh gia một gói).
        self.loai = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.goi = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag, MaLoaiHinh=self.loai, TenGoi='Gói cơ bản',
                                            Gia=1500000, ThoiLuongChup=60, LoaiHauKy=LoaiHauKy.TOAN_BO)
        self.goi_khac = GoiDichVu.objects.create(MaNhiepAnhGia=self.nag_khac, MaLoaiHinh=self.loai,
                                                 TenGoi='Gói người khác', Gia=2000000, ThoiLuongChup=60,
                                                 LoaiHauKy=LoaiHauKy.TOAN_BO)
        # Ngày chụp thử nghiệm: 3 ngày kể từ hôm nay.
        self.ngay = timezone.localdate() + timedelta(days=3)
        # Đăng nhập sẵn bằng tài khoản Nhiếp ảnh gia 'nag'.
        self.client.force_login(self.nag.MaTaiKhoan)

    # Hàm tiện ích: tạo một Booking giống như vừa được khách gửi xong (UC4.2): Booking 'Chờ xác nhận', khung giờ 'Đang giữ chỗ'.
    def tao_booking(self, nag=None, goi=None, gio='09:00', trang_thai=BK.CHO_XAC_NHAN, ngay=None, **kw):
        """Tạo Booking như sau khi Khách gửi (UC4.2): slot 'Đang giữ chỗ', Booking 'Chờ xác nhận'."""
        nag = nag or self.nag
        goi = goi or (self.goi if nag == self.nag else self.goi_khac)
        ngay = ngay or self.ngay   # mặc định ngày chụp thử nghiệm của lớp nền
        gio_bd = timezone.datetime.strptime(gio, '%H:%M')
        # Tạo khung giờ dài 2 tiếng, ở trạng thái 'Đang giữ chỗ' (đúng như thật sau khi khách gửi Booking).
        lich = LichKhaDung.objects.create(MaNhiepAnhGia=nag, Ngay=ngay, GioBatDau=gio,
                                          GioKetThuc=(gio_bd + timedelta(hours=2)).strftime('%H:%M'),
                                          TrangThai=SL.DANG_GIU)
        # Thông tin mặc định của Booking thử nghiệm (khách, gói, giờ chụp, địa điểm, concept...).
        mac_dinh = dict(MaKhachHang=self.khach, MaNhiepAnhGia=nag, MaGoi=goi, MaLich=lich,
                        NgayGioChup=timezone.make_aware(timezone.datetime.combine(ngay, gio_bd.time())),
                        DiaDiem='Hồ Gươm', SoNguoi=2, Concept='Vintage', YeuCauRieng='Mang phụ kiện',
                        TrangThai=trang_thai)
        # Cho phép từng test ghi đè một vài thông tin (ví dụ đổi trạng thái hoặc giờ chụp).
        mac_dinh.update(kw)
        # Lưu Booking vào cơ sở dữ liệu tạm và trả về.
        return Booking.objects.create(**mac_dinh)

    # Ba hàm nhỏ trả về địa chỉ: trang chi tiết, nút chấp nhận, trang từ chối của một Booking.
    def url_chi_tiet(self, bk):
        return reverse('chi_tiet_yeu_cau_booking', kwargs={'ma_booking': bk.pk})

    def url_chap_nhan(self, bk):
        return reverse('chap_nhan_booking', kwargs={'ma_booking': bk.pk})

    def url_tu_choi(self, bk):
        return reverse('tu_choi_booking', kwargs={'ma_booking': bk.pk})


# ---------------------------------------------------------------------
# UC4.3 Tiếp nhận yêu cầu Booking
# ---------------------------------------------------------------------
# ===== NHÓM TEST UC4.3: TIẾP NHẬN YÊU CẦU BOOKING (xem danh sách, lọc, sắp xếp, xem chi tiết, quyền truy cập) =====
class UC43TiepNhan(TiepNhanBase):
    # Địa chỉ trang Quản lý Booking.
    url = property(lambda self: reverse('manage_bookings'))

    # Kiểm tra: danh sách mặc định chỉ có Booking 'Chờ xác nhận' của chính mình; Booking đã chấp nhận hoặc của Nhiếp ảnh gia khác thì không hiện.
    def test_chi_thay_booking_cho_xac_nhan_cua_chinh_minh(self):          # Basic Flow bước 2 + BR4.3-1
        cua_minh = self.tao_booking(gio='09:00')
        da_chap = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)
        cua_nguoi_khac = self.tao_booking(nag=self.nag_khac, gio='09:00')
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        ds = list(res.context['page_obj'])
        self.assertEqual(ds, [cua_minh])                                  # mặc định chỉ "Chờ xác nhận"
        self.assertNotIn(da_chap, ds)
        self.assertNotIn(cua_nguoi_khac, ds)                              # không thấy Booking của người khác
        self.assertContains(res, 'Nguyễn An')                             # tên khách (họ + tên đệm trước)

    # Kiểm tra: chưa có yêu cầu nào thì hiện câu 'Không có yêu cầu Booking mới'.
    def test_khong_co_booking_moi(self):                                  # ngoại lệ 2b
        res = self.client.get(self.url)
        self.assertContains(res, uc.TB_KHONG_CO_YEU_CAU)

    # Kiểm tra: lọc theo từng trạng thái và lọc 'Tất cả trạng thái' đều cho kết quả đúng.
    def test_loc_theo_trang_thai(self):                                   # luồng 2a
        moi = self.tao_booking(gio='09:00')
        da_chap = self.tao_booking(gio='13:00', trang_thai=BK.CHO_DAT_COC)
        res = self.client.get(self.url, {'trang_thai': BK.CHO_DAT_COC})
        self.assertEqual(list(res.context['page_obj']), [da_chap])
        res = self.client.get(self.url, {'trang_thai': uc.LOC_TAT_CA})
        self.assertCountEqual(list(res.context['page_obj']), [moi, da_chap])

    # Kiểm tra: 11 Booking 'Chờ đặt cọc' (+ 1 'Chờ xác nhận' làm mồi) -> lọc 'Chờ đặt cọc', sắp xếp 'Ngày chụp gần nhất',
    # sang trang 2 (bằng cách mở ?page=2 VÀ bằng cách bấm đúng đường link phân trang trên trang 1) vẫn giữ bộ lọc + sắp xếp.
    def test_chuyen_trang_giu_bo_loc_va_sap_xep(self):
        coc = []
        for i in range(11):   # mỗi khung giờ dài 2 tiếng, nối tiếp nhau trong ngày: 00:00, 02:00, ... 20:00
            coc.append(self.tao_booking(gio=f'{i * 2:02d}:00', trang_thai=BK.CHO_DAT_COC,
                                        HanDatCoc=timezone.now() + timedelta(days=1)))
        moi = self.tao_booking(gio='09:00', ngay=self.ngay + timedelta(days=1))   # 'Chờ xác nhận' - không được lọt vào kết quả
        loc = {'trang_thai': BK.CHO_DAT_COC, 'sap_xep': 'chup_gan'}

        # Cách 1: mở thẳng ?page=2 kèm bộ lọc.
        res = self.client.get(self.url, {**loc, 'page': 2})
        self.assertEqual(list(res.context['page_obj']), coc[10:])        # còn đúng 1 dòng: Booking chụp xa nhất
        self.assertNotIn(moi, list(res.context['page_obj']))
        self.assertEqual(res.context['trang_thai'], BK.CHO_DAT_COC)
        self.assertEqual(res.context['sap_xep'], 'chup_gan')

        # Cách 2: bấm link 'sang trang 2' do includes/pagination.html sinh ra trên trang 1 -> bộ lọc không được mất.
        trang1 = self.client.get(self.url, loc)
        self.assertEqual(list(trang1.context['page_obj']), coc[:10])
        link = re.search(r'href="([^"]*page=2[^"]*)"', trang1.content.decode())
        self.assertIsNotNone(link, 'Trang 1 phải có link sang trang 2')
        trang2 = self.client.get(urljoin(self.url, unescape(link.group(1))))   # link thường chỉ có phần '?...': trình duyệt ghép vào trang hiện tại
        self.assertEqual(list(trang2.context['page_obj']), coc[10:])      # nếu link làm rơi bộ lọc, trang 2 sẽ sai
        self.assertEqual(trang2.context['trang_thai'], BK.CHO_DAT_COC)
        self.assertEqual(trang2.context['sap_xep'], 'chup_gan')


    # Kiểm tra: lọc trạng thái khác mà rỗng thì báo 'không khớp bộ lọc', không báo nhầm 'không có yêu cầu mới'.
    def test_loc_ra_rong_khong_hien_cau_yeu_cau_moi(self):
        self.tao_booking()
        res = self.client.get(self.url, {'trang_thai': BK.HOAN_THANH})
        self.assertNotContains(res, uc.TB_KHONG_CO_YEU_CAU)               # câu 2b chỉ dành cho danh sách yêu cầu mới
        self.assertContains(res, 'Không có Booking nào khớp bộ lọc')

    # Kiểm tra: gõ bậy giá trị lên thanh địa chỉ thì trang không lỗi mà quay về chế độ mặc định.
    def test_gia_tri_la_tren_url_quay_ve_mac_dinh(self):
        bk = self.tao_booking()
        res = self.client.get(self.url, {'trang_thai': 'abc', 'sap_xep': 'xyz'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context['page_obj']), [bk])
        self.assertEqual(res.context['sap_xep'], uc.SAP_XEP_MAC_DINH)

    # Kiểm tra: 4 kiểu sắp xếp (mới nhất, cũ nhất, chụp gần nhất, chụp xa nhất) cho thứ tự đúng.
    def test_sap_xep_theo_thoi_gian(self):                                # luồng 2a
        som = self.tao_booking(gio='09:00', NgayTao=timezone.now() - timedelta(hours=5))
        muon = self.tao_booking(gio='13:00', NgayTao=timezone.now() - timedelta(hours=1))
        ds = lambda s: list(self.client.get(self.url, {'sap_xep': s}).context['page_obj'])
        self.assertEqual(ds('moi_nhat'), [muon, som])                     # theo lúc gửi yêu cầu
        self.assertEqual(ds('cu_nhat'), [som, muon])
        self.assertEqual(ds('chup_gan'), [som, muon])                     # theo ngày giờ chụp (09:00 trước 13:00)
        self.assertEqual(ds('chup_xa'), [muon, som])

    # Kiểm tra: trang chi tiết hiện đủ khách, gói, giờ, địa điểm, concept, yêu cầu riêng, giá và hai nút xử lý.
    def test_chi_tiet_day_du_thong_tin(self):                             # Basic Flow bước 3-4
        bk = self.tao_booking(Concept='Phong cách cổ điển', YeuCauRieng='Mang theo váy đỏ')
        res = self.client.get(self.url_chi_tiet(bk))
        self.assertEqual(res.status_code, 200)
        for chu in ('Nguyễn An', 'Chân dung', 'Gói cơ bản', 'Hồ Gươm', 'Phong cách cổ điển',
                    'Mang theo váy đỏ', '1.500.000', 'Chấp nhận Booking', 'Từ chối Booking'):
            self.assertContains(res, chu)

    # Kiểm tra: mở chi tiết Booking của Nhiếp ảnh gia khác -> báo 404 (BR4.3-1).
    def test_chi_tiet_booking_nguoi_khac_la_404(self):                    # BR4.3-1
        cua_nguoi_khac = self.tao_booking(nag=self.nag_khac)
        self.assertEqual(self.client.get(self.url_chi_tiet(cua_nguoi_khac)).status_code, 404)

    # Kiểm tra: Booking đã chấp nhận rồi thì không còn nút Chấp nhận / Từ chối.
    def test_chi_tiet_booking_da_xu_ly_khong_con_nut(self):
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC, HanDatCoc=timezone.now() + timedelta(days=1))
        res = self.client.get(self.url_chi_tiet(bk))
        self.assertNotContains(res, 'Chấp nhận Booking')
        self.assertNotContains(res, 'Từ chối Booking')

    # Kiểm tra quyền: chưa đăng nhập -> đưa về trang đăng nhập; Khách hàng và Nhiếp ảnh gia chưa được duyệt -> bị chặn (403).
    def test_phan_quyen(self):
        bk = self.tao_booking()
        self.client.logout()
        res = self.client.get(self.url)                                   # chưa đăng nhập -> trang đăng nhập
        self.assertEqual(res.status_code, 302)
        self.assertIn('dang-nhap', res['Location'])
        self.client.force_login(self.khach)                               # Khách hàng -> 403
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url_chi_tiet(bk)).status_code, 403)
        cho_duyet = tao_nag('nag_cho_duyet', TrangThaiHoSo.CHO_DUYET)     # tiền điều kiện: tài khoản "Đã duyệt"
        self.client.force_login(cho_duyet.MaTaiKhoan)
        self.assertEqual(self.client.get(self.url).status_code, 403)


# ---------------------------------------------------------------------
# UC4.4 Chấp nhận Booking
# ---------------------------------------------------------------------
# ===== NHÓM TEST UC4.4: CHẤP NHẬN BOOKING =====
class UC44ChapNhan(TiepNhanBase):
    # Kiểm tra: chấp nhận xong -> Booking 'Chờ đặt cọc', hạn cọc = bây giờ + 1 ngày, khung giờ vẫn 'Đang giữ chỗ', có ghi lịch sử.
    def test_chap_nhan_thanh_cong(self):
        bk = self.tao_booking()
        truoc = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(self.url_chap_nhan(bk))
        self.assertRedirects(res, reverse('manage_bookings'))
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)                    # hậu điều kiện 1
        self.assertAlmostEqual(                                           # BR4.4-1/BR4.4-3: hạn cọc = lúc chấp nhận + 1 ngày
            (bk.HanDatCoc - truoc).total_seconds(), 86400, delta=60)
        bk.MaLich.refresh_from_db()
        self.assertEqual(bk.MaLich.TrangThai, SL.DANG_GIU)                # slot vẫn giữ cho tới khi Chốt Booking
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk)
        self.assertEqual((ls.TrangThaiCu, ls.TrangThaiMoi, ls.BenThucHien),
                         (BK.CHO_XAC_NHAN, BK.CHO_DAT_COC, BenThucHien.NHIEP_ANH_GIA))

    # Kiểm tra: Khách nhận thông báo web và 1 Email nêu số tiền cọc 40% (600.000 trên 1.500.000); Nhiếp ảnh gia không bị báo nhầm.
    def test_thong_bao_web_va_email_cho_khach(self):                      # bước 4-5
        bk = self.tao_booking()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url_chap_nhan(bk))
        tb = ThongBao.objects.get(MaNguoiNhan=self.khach, MaBooking=bk)
        self.assertIn('1 ngày', tb.NoiDung)
        self.assertIn('600.000', tb.NoiDung)                              # 40% của 1.500.000
        self.assertEqual(tb.TrangThaiGuiEmail, TrangThaiGuiEmail.THANH_CONG)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.khach.email])
        self.assertIn('600.000', mail.outbox[0].body)
        self.assertFalse(ThongBao.objects.filter(MaNguoiNhan=self.nag.MaTaiKhoan).exists())

    # Kiểm tra: số tiền cọc trong thông báo web + Email, và trên trang chi tiết, đúng bằng kết quả của tinh_so_tien
    # (cùng hàm Thanh toán dùng để thu tiền thật) -> không lệch nhau. Dùng giá lẻ 1.234.567 để lộ lỗi làm tròn.
    def test_so_tien_coc_khop_tinh_so_tien(self):
        bk = self.tao_booking(TongGiaTri=1234567)
        bk.refresh_from_db()
        dung = uc._tien(tinh_so_tien(bk.TongGiaTri, LoaiThanhToan.TIEN_COC))
        self.assertEqual(dung, '493.827')                                 # 40% của 1.234.567 = 493.826,8 -> làm tròn lên
        self.assertContains(self.client.get(self.url_chi_tiet(bk)), dung)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url_chap_nhan(bk))
        tb = ThongBao.objects.get(MaNguoiNhan=self.khach, MaBooking=bk)
        self.assertIn(f'{dung} VNĐ', tb.NoiDung)
        self.assertIn(f'{dung} VNĐ', mail.outbox[0].body)


    # Kiểm tra: giả vờ gửi mail bị lỗi -> Booking vẫn chấp nhận bình thường, thông báo chỉ bị đánh dấu 'Gửi thất bại'.
    def test_loi_gui_email_khong_lam_hong_viec_chap_nhan(self):
        bk = self.tao_booking()
        with mock.patch.object(services, 'send_mail', side_effect=OSError('SMTP down')):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.url_chap_nhan(bk))
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)
        tb = ThongBao.objects.get(MaNguoiNhan=self.khach)
        self.assertEqual(tb.TrangThaiGuiEmail, TrangThaiGuiEmail.THAT_BAI)

    # Kiểm tra: mở nút chấp nhận bằng đường link thường (GET) bị từ chối (405), Booking không đổi.
    def test_chi_nhan_post(self):
        bk = self.tao_booking()
        self.assertEqual(self.client.get(self.url_chap_nhan(bk)).status_code, 405)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)

    # Kiểm tra: không chấp nhận được Booking của Nhiếp ảnh gia khác (404), không đổi gì, không gửi thông báo.
    def test_khong_chap_nhan_booking_nguoi_khac(self):                    # BR4.3-1
        bk = self.tao_booking(nag=self.nag_khac)
        self.assertEqual(self.client.post(self.url_chap_nhan(bk)).status_code, 404)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)
        self.assertFalse(ThongBao.objects.exists())

    # Kiểm tra: bấm chấp nhận 2 lần chỉ có tác dụng 1 lần (1 thông báo, 1 dòng lịch sử, 1 Email); lần 2 báo 'không còn ở trạng thái'.
    def test_chap_nhan_hai_lan_chi_co_hieu_luc_mot_lan(self):
        bk = self.tao_booking()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url_chap_nhan(bk))
            res = self.client.post(self.url_chap_nhan(bk), follow=True)
        self.assertContains(res, 'không còn ở trạng thái')
        self.assertEqual(ThongBao.objects.filter(MaBooking=bk).count(), 1)
        self.assertEqual(LichSuTrangThaiBooking.objects.filter(MaBooking=bk).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    # Kiểm tra: Booking đã quá giờ chụp -> ẩn nút Chấp nhận, gõ tay lệnh chấp nhận cũng bị chặn, không đổi gì.
    def test_khong_chap_nhan_booking_da_qua_gio_chup(self):
        bk = self.tao_booking()
        # Dời giờ chụp về quá khứ (đúng thứ tự DB: NgayTao phải trước NgayGioChup).
        Booking.objects.filter(pk=bk.pk).update(NgayTao=timezone.now() - timedelta(days=2),
                                                NgayGioChup=timezone.now() - timedelta(hours=1))
        res = self.client.get(self.url_chi_tiet(bk))
        self.assertNotContains(res, 'Chấp nhận Booking')                  # ẩn nút Chấp nhận
        self.assertContains(res, 'Từ chối Booking')                       # vẫn từ chối được
        res = self.client.post(self.url_chap_nhan(bk), follow=True)       # gõ tay POST cũng bị chặn
        self.assertContains(res, uc.TB_QUA_GIO_CHUP)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)
        self.assertFalse(ThongBao.objects.exists())
        self.assertFalse(LichSuTrangThaiBooking.objects.filter(MaBooking=bk).exists())

    # Kiểm tra: Booking quá giờ chụp vẫn TỪ CHỐI được và khung giờ được trả về trống.
    def test_van_tu_choi_duoc_booking_da_qua_gio_chup(self):
        bk = self.tao_booking()
        Booking.objects.filter(pk=bk.pk).update(NgayTao=timezone.now() - timedelta(days=2),
                                                NgayGioChup=timezone.now() - timedelta(hours=1))
        self.client.post(self.url_tu_choi(bk), {'ly_do': 'Đã quá giờ chụp'})
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_TU_CHOI)
        bk.MaLich.refresh_from_db()
        self.assertEqual(bk.MaLich.TrangThai, SL.TRONG)                   # slot được trả lại

    # Kiểm tra: tài khoản Khách hàng không được chấp nhận Booking (403).
    def test_khach_hang_khong_chap_nhan_duoc(self):
        bk = self.tao_booking()
        self.client.force_login(self.khach)
        self.assertEqual(self.client.post(self.url_chap_nhan(bk)).status_code, 403)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)


# ---------------------------------------------------------------------
# UC4.5 Từ chối Booking
# ---------------------------------------------------------------------
# ===== NHÓM TEST UC4.5: TỪ CHỐI BOOKING =====
class UC45TuChoi(TiepNhanBase):
    # Kiểm tra: mở trang từ chối thì hiện ô nhập lý do, và CHƯA từ chối gì cả (UC4.5 bước 3).
    def test_get_hien_form_nhap_ly_do(self):                              # bước 3
        bk = self.tao_booking()
        res = self.client.get(self.url_tu_choi(bk))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Lý do từ chối')
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)                   # chỉ mở form, chưa từ chối

    # Kiểm tra: nhập lý do và xác nhận -> Booking 'Đã từ chối', lưu lý do, khung giờ về 'Lịch trống', có ghi lịch sử.
    def test_tu_choi_thanh_cong(self):
        bk = self.tao_booking()
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(self.url_tu_choi(bk), {'ly_do': 'Trùng lịch cá nhân'})
        self.assertRedirects(res, reverse('manage_bookings'))
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_TU_CHOI)                     # hậu điều kiện 1
        self.assertEqual(bk.LyDoTuChoi, 'Trùng lịch cá nhân')
        bk.MaLich.refresh_from_db()
        self.assertEqual(bk.MaLich.TrangThai, SL.TRONG)                   # hậu điều kiện 2, BR4.5-2
        ls = LichSuTrangThaiBooking.objects.get(MaBooking=bk)
        self.assertEqual((ls.TrangThaiMoi, ls.BenThucHien, ls.LyDo),
                         (BK.DA_TU_CHOI, BenThucHien.NHIEP_ANH_GIA, 'Trùng lịch cá nhân'))

    # Kiểm tra: Khách nhận thông báo web và Email có kèm lý do từ chối.
    def test_thong_bao_web_va_email_kem_ly_do(self):                      # bước 7-8, hậu điều kiện 3
        bk = self.tao_booking()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url_tu_choi(bk), {'ly_do': 'Trùng lịch cá nhân'})
        tb = ThongBao.objects.get(MaNguoiNhan=self.khach, MaBooking=bk)
        self.assertIn('Trùng lịch cá nhân', tb.NoiDung)
        self.assertEqual(tb.TrangThaiGuiEmail, TrangThaiGuiEmail.THANH_CONG)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.khach.email])
        self.assertIn('Trùng lịch cá nhân', mail.outbox[0].body)

    # Kiểm tra: để trống / chỉ nhập dấu cách / xuống dòng -> hiện 'Vui lòng nhập lý do từ chối', Booking và khung giờ giữ nguyên, không gửi thông báo (BR4.5-1).
    def test_khong_nhap_ly_do(self):                                      # ngoại lệ 4a, BR4.5-1
        bk = self.tao_booking()
        for ly_do in ('', '    ', '\n\t'):                                # rỗng hoặc toàn khoảng trắng đều không được
            with self.subTest(ly_do=ly_do):
                res = self.client.post(self.url_tu_choi(bk), {'ly_do': ly_do})
                self.assertEqual(res.status_code, 200)                    # ở lại bước 4
                self.assertContains(res, uc.TB_THIEU_LY_DO)
                bk.refresh_from_db()
                self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)
                bk.MaLich.refresh_from_db()
                self.assertEqual(bk.MaLich.TrangThai, SL.DANG_GIU)        # slot chưa bị nhả
        self.assertFalse(ThongBao.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    # Kiểm tra: lý do 256 ký tự bị từ chối, đúng 255 ký tự thì được.
    def test_ly_do_qua_dai(self):                                         # LichSu.LyDo chỉ chứa 255 ký tự
        bk = self.tao_booking()
        res = self.client.post(self.url_tu_choi(bk), {'ly_do': 'a' * 256})
        self.assertContains(res, 'Lý do tối đa 255 ký tự')
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)
        self.client.post(self.url_tu_choi(bk), {'ly_do': 'a' * 255})      # đúng 255 thì được
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.DA_TU_CHOI)

    # Kiểm tra: sau khi từ chối, khách khác giữ chỗ được ngay khung giờ đó (BR4.5-2).
    def test_slot_duoc_khach_khac_dat_ngay(self):                         # BR4.5-2
        bk = self.tao_booking()
        self.client.post(self.url_tu_choi(bk), {'ly_do': 'Bận'})
        giu = uc41.giu_cho_slot(self.khach_b, bk.MaLich_id)               # Khách khác giữ chỗ được luôn
        self.assertEqual(giu.MaLich_id, bk.MaLich_id)

    # Kiểm tra: không mở/từ chối được Booking của Nhiếp ảnh gia khác (404).
    def test_khong_tu_choi_booking_nguoi_khac(self):                      # BR4.3-1
        bk = self.tao_booking(nag=self.nag_khac)
        self.assertEqual(self.client.get(self.url_tu_choi(bk)).status_code, 404)
        self.assertEqual(self.client.post(self.url_tu_choi(bk), {'ly_do': 'x'}).status_code, 404)
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_XAC_NHAN)

    # Kiểm tra: Booking đã chấp nhận rồi thì không từ chối được nữa (chỉ xử lý được khi đang 'Chờ xác nhận').
    def test_khong_tu_choi_booking_da_chap_nhan(self):                    # tiền điều kiện: đang "Chờ xác nhận"
        bk = self.tao_booking(trang_thai=BK.CHO_DAT_COC, HanDatCoc=timezone.now() + timedelta(days=1))
        res = self.client.post(self.url_tu_choi(bk), {'ly_do': 'Đổi ý'}, follow=True)
        self.assertContains(res, 'không còn ở trạng thái')
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, BK.CHO_DAT_COC)

    # Kiểm tra trực tiếp hàm nghiệp vụ tu_choi_booking: lý do chỉ toàn dấu cách -> báo lỗi đúng câu quy định.
    def test_service_tu_choi_thieu_ly_do(self):
        bk = self.tao_booking()
        with self.assertRaises(uc.XuLyBookingLoi) as ctx:
            uc.tu_choi_booking(self.nag.MaTaiKhoan, bk.pk, '   ')
        self.assertEqual(ctx.exception.thong_bao, uc.TB_THIEU_LY_DO)
# notifications/tests.py - kiểm tra P2 (gửi thông báo) và P8 (xem, đánh dấu thông báo). Chạy: python manage.py test notifications
from types import SimpleNamespace  # tạo "thông báo giả" để thử hàm url_booking mà không cần dựng cả Booking
from unittest.mock import patch  # giả lập lỗi (DB hỏng, ghi thất bại)

from django.contrib.auth import get_user_model  # lấy model User của project (accounts.User)
from django.contrib.auth.models import Group  # nhóm quyền, dùng để cho người dùng thành Nhiếp ảnh gia khi thử link
from django.contrib.messages import get_messages  # đọc các hộp thông báo đã xếp hàng cho trang kế tiếp
from django.db import DatabaseError  # kiểu lỗi cơ sở dữ liệu để giả lập
from django.test import TestCase  # lớp test của Django: tự dùng DB tạm, không đụng db.sqlite3 thật
from django.urls import reverse  # đổi tên URL thành địa chỉ

from core.constants import DanhDauSao, TrangThaiDoc, VaiTro  # hằng số trạng thái đọc, sao và tên vai trò
from notifications import services  # các hàm P8 cần thử
from notifications.models import ThongBao  # model thông báo để kiểm tra dữ liệu đã lưu
from notifications.services import dem_chua_doc, gui_thong_bao, gui_thong_bao_nhieu_nguoi  # 3 hàm P2 cần test

User = get_user_model()  # gán tên User để tạo người dùng thử


class GuiThongBaoTestCase(TestCase):  # nhóm các test của hàm gửi thông báo
    @classmethod  # chạy một lần trước cả nhóm test
    def setUpTestData(cls):  # tạo dữ liệu mẫu dùng chung
        cls.a = User.objects.create_user('a', 'a@example.com', 'Matkhau@123', so_dien_thoai='0900000001')  # người dùng A
        cls.b = User.objects.create_user('b', 'b@example.com', 'Matkhau@123', so_dien_thoai='0900000002')  # người dùng B

    def test_tao_thong_bao_chua_doc(self):  # thông báo mới phải ở trạng thái Chưa đọc
        tb = gui_thong_bao(self.a, 'Booking mới', 'Bạn có Booking mới')  # gửi cho A, không gắn Booking
        self.assertIsNotNone(tb)  # phải tạo được
        self.assertEqual(tb.MaNguoiNhan, self.a)  # đúng người nhận
        self.assertEqual(tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # đúng trạng thái Chưa đọc
        self.assertIsNone(tb.MaBooking)  # không gắn Booking nên để trống

    def test_dem_chua_doc(self):  # đếm đúng số chưa đọc
        gui_thong_bao(self.a, 'Một', 'nội dung')  # A nhận thông báo 1
        gui_thong_bao(self.a, 'Hai', 'nội dung')  # A nhận thông báo 2
        gui_thong_bao(self.b, 'Ba', 'nội dung')  # B nhận thông báo, không tính cho A
        self.assertEqual(dem_chua_doc(self.a), 2)  # A có 2 chưa đọc
        ThongBao.objects.filter(MaNguoiNhan=self.a).update(TrangThaiDoc=TrangThaiDoc.DA_DOC)  # giả lập A đã đọc hết
        self.assertEqual(dem_chua_doc(self.a), 0)  # còn 0 chưa đọc

    def test_thieu_nguoi_nhan_khong_loi(self):  # thiếu người nhận thì không ném lỗi
        self.assertIsNone(gui_thong_bao(None, 'x', 'y'))  # trả về None
        self.assertEqual(ThongBao.objects.count(), 0)  # không có dòng nào được tạo

    def test_thieu_noi_dung_khong_loi(self):  # thiếu tiêu đề/nội dung thì không tạo
        self.assertIsNone(gui_thong_bao(self.a, '', 'y'))  # tiêu đề rỗng
        self.assertIsNone(gui_thong_bao(self.a, 'x', '   '))  # nội dung chỉ có khoảng trắng

    def test_tieu_de_qua_dai_bi_cat(self):  # tiêu đề dài hơn 255 ký tự bị cắt
        tb = gui_thong_bao(self.a, 'x' * 300, 'y')  # tiêu đề 300 ký tự
        self.assertEqual(len(tb.TieuDe), 255)  # chỉ còn 255

    def test_nhieu_nguoi_bo_trung(self):  # gửi nhiều người, người trùng chỉ nhận một lần
        ds = gui_thong_bao_nhieu_nguoi([self.a, self.b, self.a], 'Hồ sơ mới', 'Có hồ sơ chờ duyệt')  # A xuất hiện 2 lần
        self.assertEqual(len(ds), 2)  # chỉ tạo 2 thông báo
        self.assertEqual(ThongBao.objects.count(), 2)  # trong DB cũng đúng 2 dòng


# =====================================================================
# P8 (UC9.1, UC9.2): test xem và đánh dấu thông báo. Chạy: python manage.py test notifications
# =====================================================================



class DichVuThongBaoTestCase(TestCase):  # nhóm test của các hàm trong services.py (chưa qua giao diện)
    @classmethod  # chạy một lần trước cả nhóm
    def setUpTestData(cls):  # dữ liệu mẫu dùng chung
        cls.a = User.objects.create_user('a', 'a@example.com', 'Matkhau@123', so_dien_thoai='0900000001')  # người dùng A
        cls.b = User.objects.create_user('b', 'b@example.com', 'Matkhau@123', so_dien_thoai='0900000002')  # người dùng B
        cls.tb1 = gui_thong_bao(cls.a, 'Booking mới', 'Có yêu cầu đặt lịch chụp ảnh cưới')  # A: thông báo 1
        cls.tb2 = gui_thong_bao(cls.a, 'Thanh toán cọc', 'Cọc 40% đã được xác nhận')  # A: thông báo 2
        cls.tb3 = gui_thong_bao(cls.a, 'Ảnh hậu kỳ', 'Ảnh đã tải lên')  # A: thông báo 3
        cls.tb_b = gui_thong_bao(cls.b, 'Của B', 'Không được lộ cho A')  # thông báo của B
        ThongBao.objects.filter(pk=cls.tb3.pk).update(TrangThaiDoc=TrangThaiDoc.DA_DOC, DanhDauSao=DanhDauSao.DA_DANH_DAU)  # tb3: đã đọc và có sao

    def test_danh_sach_chi_cua_chu(self):  # A không thấy thông báo của B
        ma = {tb.pk for tb in services.lay_danh_sach(self.a)}  # mã các thông báo A thấy
        self.assertEqual(ma, {self.tb1.pk, self.tb2.pk, self.tb3.pk})  # đúng 3 cái của A
        self.assertNotIn(self.tb_b.pk, ma)  # không có của B

    def test_loc_nhom(self):  # lọc Chưa đọc và Đã đánh dấu sao
        chua_doc = {tb.pk for tb in services.lay_danh_sach(self.a, services.LOC_CHUA_DOC)}  # nhóm Chưa đọc
        self.assertEqual(chua_doc, {self.tb1.pk, self.tb2.pk})  # chỉ 2 cái chưa đọc
        sao = {tb.pk for tb in services.lay_danh_sach(self.a, services.LOC_SAO)}  # nhóm Đã đánh dấu sao
        self.assertEqual(sao, {self.tb3.pk})  # chỉ tb3
        self.assertEqual(services.chuan_hoa_loc('linh_tinh'), services.LOC_TAT_CA)  # giá trị lạ về "Tất cả"

    def test_tim_kiem(self):  # tìm theo tiêu đề và nội dung
        tieu_de = list(services.lay_danh_sach(self.a, tu_khoa='cọc'))  # từ khóa nằm ở tiêu đề tb2 và nội dung tb2
        self.assertEqual([tb.pk for tb in tieu_de], [self.tb2.pk])  # chỉ tb2
        noi_dung = list(services.lay_danh_sach(self.a, tu_khoa='ảnh cưới'))  # từ khóa nằm ở nội dung tb1
        self.assertEqual([tb.pk for tb in noi_dung], [self.tb1.pk])  # chỉ tb1
        self.assertEqual(services.lay_danh_sach(self.a, tu_khoa='   ').count(), 3)  # từ khóa toàn dấu cách = không lọc

    def test_dem_theo_nhom_mot_truy_van(self):  # đếm 3 nhóm tốn đúng 1 câu truy vấn
        with self.assertNumQueries(1):  # chỉ cho phép 1 câu SQL
            so = services.dem_theo_nhom(self.a)  # đếm
        self.assertEqual(so, {'tat_ca': 3, 'chua_doc': 2, 'sao': 1})  # đúng số liệu

    def test_dat_trang_thai_doc_va_idempotent(self):  # đổi đọc/chưa đọc, bấm hai lần vẫn đúng
        self.assertTrue(services.dat_trang_thai_doc(self.a, self.tb1.pk, True))  # đánh dấu đã đọc
        self.assertTrue(services.dat_trang_thai_doc(self.a, self.tb1.pk, True))  # bấm lần hai vẫn thành công
        self.tb1.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(self.tb1.TrangThaiDoc, TrangThaiDoc.DA_DOC)  # đã là Đã đọc
        self.assertTrue(services.dat_trang_thai_doc(self.a, self.tb1.pk, False))  # đánh dấu lại chưa đọc
        self.tb1.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb1.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # về Chưa đọc

    def test_dat_dau_sao(self):  # gắn và bỏ sao
        self.assertTrue(services.dat_dau_sao(self.a, self.tb1.pk, True))  # gắn sao
        self.tb1.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb1.DanhDauSao, DanhDauSao.DA_DANH_DAU)  # đã gắn
        self.assertTrue(services.dat_dau_sao(self.a, self.tb1.pk, False))  # bỏ sao
        self.tb1.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb1.DanhDauSao, DanhDauSao.CHUA_DANH_DAU)  # đã bỏ

    def test_khong_sua_duoc_thong_bao_cua_nguoi_khac(self):  # B không đổi được thông báo của A
        self.assertFalse(services.dat_trang_thai_doc(self.b, self.tb1.pk, True))  # thất bại
        self.assertFalse(services.dat_dau_sao(self.b, self.tb1.pk, True))  # thất bại
        self.tb1.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb1.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # không đổi
        self.assertEqual(self.tb1.DanhDauSao, DanhDauSao.CHUA_DANH_DAU)  # không đổi

    def test_tu_dong_danh_dau_da_doc(self):  # mở xem thì tự chuyển Đã đọc
        tb = ThongBao.objects.get(pk=self.tb1.pk)  # lấy bản mới từ DB
        self.assertTrue(services.tu_dong_danh_dau_da_doc(self.a, tb))  # tự đánh dấu
        self.assertEqual(tb.TrangThaiDoc, TrangThaiDoc.DA_DOC)  # bản đang cầm đã đổi
        self.assertEqual(ThongBao.objects.get(pk=self.tb1.pk).TrangThaiDoc, TrangThaiDoc.DA_DOC)  # DB cũng đổi

    def test_url_booking(self):  # link Booking theo vai trò
        khong_booking = SimpleNamespace(MaBooking_id=None)  # thông báo không gắn Booking
        self.assertIsNone(services.url_booking(khong_booking, self.a))  # không có link
        co_booking = SimpleNamespace(MaBooking_id=7)  # thông báo gắn Booking số 7
        from django.urls import reverse  # thêm dòng này lên đầu file tests.py nếu chưa có (đổi tên URL thành địa chỉ)

        # dòng 134: thay '#' bằng link thật, vì Tuyền đã tạo trang chi_tiet_booking
        self.assertEqual(services.url_booking(co_booking, self.a), reverse('chi_tiet_booking', kwargs={'ma_booking': co_booking.MaBooking_id}))  # A là Khách hàng, trang đã có nên phải ra link thật
        nhom, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)  # nhóm Nhiếp ảnh gia
        self.a.groups.add(nhom)  # cho A vào nhóm đó
        self.assertEqual(services.url_booking(co_booking, self.a), reverse('chi_tiet_yeu_cau_booking', args=[7]))  # link thật của Tuyền


class GiaoDienThongBaoTestCase(TestCase):  # nhóm test của các trang (qua trình duyệt giả)
    @classmethod  # chạy một lần trước cả nhóm
    def setUpTestData(cls):  # dữ liệu mẫu
        cls.a = User.objects.create_user('a', 'a@example.com', 'Matkhau@123', so_dien_thoai='0900000001')  # người dùng A
        cls.b = User.objects.create_user('b', 'b@example.com', 'Matkhau@123', so_dien_thoai='0900000002')  # người dùng B
        cls.tb = gui_thong_bao(cls.a, 'Booking mới', 'Nội dung <b>thử</b>\nDòng hai')  # thông báo của A (có thẻ HTML để thử thoát ký tự)
        cls.tb_b = gui_thong_bao(cls.b, 'Của B', 'Bí mật của B')  # thông báo của B

    def test_chua_dang_nhap_bi_chuyen_ve_dang_nhap(self):  # khách vãng lai không xem được
        for ten, tham_so in (('notifications', []), ('chi_tiet_thong_bao', [self.tb.pk])):  # cả trang danh sách và chi tiết
            res = self.client.get(reverse(ten, args=tham_so))  # mở khi chưa đăng nhập
            self.assertEqual(res.status_code, 302)  # bị chuyển hướng
            self.assertIn('/dang-nhap/', res['Location'])  # tới trang đăng nhập

    def test_danh_sach_chi_hien_cua_minh(self):  # trang danh sách đúng nội dung
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('notifications'))  # mở danh sách
        self.assertEqual(res.status_code, 200)  # thành công
        self.assertContains(res, 'Booking mới')  # có thông báo của A
        self.assertNotContains(res, 'Của B')  # không có của B

    def test_trang_rong(self):  # người chưa có thông báo
        nguoi_moi = User.objects.create_user('c', 'c@example.com', 'Matkhau@123', so_dien_thoai='0900000003')  # người dùng C chưa có gì
        self.client.force_login(nguoi_moi)  # đăng nhập C
        res = self.client.get(reverse('notifications'))  # mở danh sách
        self.assertContains(res, 'Chưa có thông báo')  # hiện màn hình Rỗng

    def test_phan_trang(self):  # 12 thông báo thì trang 1 có 10, trang 2 có 2
        for i in range(11):  # tạo thêm 11 (đã có 1) = 12
            gui_thong_bao(self.a, f'Mục {i}', 'nội dung')  # gửi thêm
        self.client.force_login(self.a)  # đăng nhập A
        r1 = self.client.get(reverse('notifications'))  # trang 1
        self.assertEqual(len(r1.context['page_obj']), 10)  # 10 dòng
        r2 = self.client.get(reverse('notifications') + '?page=2')  # trang 2
        self.assertEqual(len(r2.context['page_obj']), 2)  # 2 dòng

    def test_chi_tiet_tu_dong_da_doc_va_thoat_html(self):  # xem chi tiết thì thành Đã đọc, nội dung được thoát ký tự
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('chi_tiet_thong_bao', args=[self.tb.pk]))  # mở chi tiết
        self.assertEqual(res.status_code, 200)  # thành công
        self.assertContains(res, '&lt;b&gt;thử&lt;/b&gt;')  # thẻ <b> bị thoát, không chạy HTML
        self.tb.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.DA_DOC)  # đã chuyển Đã đọc

    def test_chi_tiet_cua_nguoi_khac_la_404(self):  # B mở thông báo của A
        self.client.force_login(self.b)  # đăng nhập B
        res = self.client.get(reverse('chi_tiet_thong_bao', args=[self.tb.pk]))  # mở thông báo của A
        self.assertEqual(res.status_code, 404)  # 404, không lộ nội dung
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # và không bị đổi trạng thái

    def test_so_chua_doc_tren_header_giam_sau_khi_xem(self):  # số trên chuông cập nhật ngay sau khi mở chi tiết
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('chi_tiet_thong_bao', args=[self.tb.pk]))  # mở chi tiết
        self.assertEqual(res.context['unread_count'], 0)  # header đã tính lại là 0

    def test_doi_trang_thai_chi_nhan_post(self):  # GET vào địa chỉ đổi trạng thái bị từ chối
        self.client.force_login(self.a)  # đăng nhập A
        for ten in ('doi_trang_thai_doc', 'doi_dau_sao'):  # cả hai địa chỉ POST
            res = self.client.get(reverse(ten, args=[self.tb.pk]))  # mở bằng GET
            self.assertEqual(res.status_code, 405)  # 405 Method Not Allowed

    def test_post_doi_da_doc_roi_chua_doc(self):  # bấm "Đánh dấu chưa đọc" sau khi đã đọc
        self.client.force_login(self.a)  # đăng nhập A
        self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'da_doc'})  # đánh dấu đã đọc
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.DA_DOC)  # đã đọc
        res = self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'chua_doc', 'next': '/thong-bao/?loc=chua_doc'})  # đánh dấu lại chưa đọc
        self.assertRedirects(res, '/thong-bao/?loc=chua_doc', fetch_redirect_response=False)  # quay về đúng trang kèm bộ lọc
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # về Chưa đọc

    def test_post_doi_sao(self):  # gắn sao qua POST
        self.client.force_login(self.a)  # đăng nhập A
        self.client.post(reverse('doi_dau_sao', args=[self.tb.pk]), {'gia_tri': 'co'})  # gắn sao
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.DanhDauSao, DanhDauSao.DA_DANH_DAU)  # đã gắn

    def test_post_vao_thong_bao_nguoi_khac_la_404(self):  # B không POST được vào thông báo của A
        self.client.force_login(self.b)  # đăng nhập B
        res = self.client.post(reverse('doi_dau_sao', args=[self.tb.pk]), {'gia_tri': 'co'})  # thử gắn sao
        self.assertEqual(res.status_code, 404)  # 404
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.DanhDauSao, DanhDauSao.CHUA_DANH_DAU)  # không đổi

    def test_gia_tri_la_bi_tu_choi(self):  # gia_tri bị sửa tay thành giá trị lạ
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'abc'}, follow=True)  # gửi giá trị lạ, đi theo cả lần chuyển trang như người dùng thật
        self.assertContains(res, 'Không thể cập nhật trạng thái thông báo')  # hiện hộp lỗi trên trang kế tiếp
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # không đổi

    def test_next_sang_trang_la_bi_chan(self):  # chống chuyển hướng sang website lạ
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(reverse('doi_dau_sao', args=[self.tb.pk]), {'gia_tri': 'co', 'next': 'https://trang-la.example.com/'})  # next là trang ngoài
        self.assertRedirects(res, reverse('chi_tiet_thong_bao', args=[self.tb.pk]) + '?giu=1', fetch_redirect_response=False)  # bị bỏ qua, về trang chi tiết (kèm giu=1)

    def test_khung_chuong_toi_da_4_dong(self):  # khung chuông chỉ hiện 4 thông báo mới nhất
        for i in range(6):  # tạo thêm 6 (đã có 1) = 7
            gui_thong_bao(self.a, f'Mục {i}', 'nội dung')  # gửi thêm
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('khung_thong_bao'))  # gọi mảnh HTML
        self.assertEqual(res.status_code, 200)  # thành công
        self.assertEqual(len(res.context['ds']), 4)  # đúng 4 dòng
        self.assertContains(res, 'Xem tất cả thông báo')  # có link sang trang danh sách
        self.assertNotContains(res, 'Bí mật của B')  # không lẫn thông báo người khác

    def test_khung_chuong_sao_len_dau(self):  # thông báo có sao phải đứng đầu khung chuông dù cũ hơn
        cu = ThongBao.objects.filter(MaNguoiNhan=self.a).order_by('NgayTao').first()  # thông báo cũ nhất của A
        for i in range(5):  # thêm 5 thông báo mới hơn để cái cũ rớt khỏi 4 dòng mới nhất
            gui_thong_bao(self.a, f'Mới {i}', 'nội dung')  # gửi thêm
        services.dat_dau_sao(self.a, cu.pk, True)  # gắn sao cái cũ
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('khung_thong_bao'))  # gọi mảnh HTML
        self.assertEqual(res.context['ds'][0].pk, cu.pk)  # có sao nên đứng đầu

    def test_post_sao_ajax_tra_204(self):  # khung chuông gọi ngầm: không chuyển trang
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(reverse('doi_dau_sao', args=[self.tb.pk]), {'gia_tri': 'co'}, headers={'X-Requested-With': 'XMLHttpRequest'})  # gọi kiểu fetch
        self.assertEqual(res.status_code, 204)  # xong, không redirect

    def test_khung_chuong_chua_dang_nhap_la_401(self):  # khách vãng lai gọi mảnh chuông
        self.assertEqual(self.client.get(reverse('khung_thong_bao')).status_code, 401)  # 401, không chuyển trang

    def test_header_co_chuong_tha_xuong(self):  # header có khối chuông và địa chỉ nạp khung
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('notifications'))  # mở danh sách
        self.assertContains(res, 'data-bell')  # có khối chuông
        self.assertContains(res, reverse('khung_thong_bao'))  # có địa chỉ nạp khung

    def test_loi_tai_danh_sach(self):  # DB lỗi khi tải danh sách thì hiện màn hình Lỗi tải, không sập
        self.client.force_login(self.a)  # đăng nhập A
        with patch('notifications.views.services.dem_theo_nhom', side_effect=DatabaseError('hỏng')):  # giả lập DB lỗi
            res = self.client.get(reverse('notifications'))  # mở danh sách
        self.assertEqual(res.status_code, 200)  # trang vẫn dựng được
        self.assertContains(res, 'Không thể tải danh sách thông báo')  # hiện khung Lỗi tải
        self.assertContains(res, 'Thử lại')  # có nút Thử lại

    def test_loi_cap_nhat_da_doc_o_trang_chi_tiet(self):  # không ghi được Đã đọc thì vẫn xem được nội dung
        self.client.force_login(self.a)  # đăng nhập A
        with patch('notifications.services.dat_trang_thai_doc', return_value=False):  # giả lập ghi thất bại
            res = self.client.get(reverse('chi_tiet_thong_bao', args=[self.tb.pk]))  # mở chi tiết
        self.assertEqual(res.status_code, 200)  # vẫn xem được
        self.assertContains(res, 'Không thể cập nhật trạng thái Đã đọc')  # hiện hộp Lỗi cập nhật đã đọc
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # vẫn Chưa đọc (đúng wireframe)



class LoiDaDuocBaoTestCase(TestCase):  # test tái hiện 2 lỗi người kiểm tra nêu (viết TRƯỚC khi sửa)
    def setUp(self):  # dữ liệu mẫu
        self.a = User.objects.create_user('a', 'a@example.com', 'Matkhau@123', so_dien_thoai='0900000001')  # người dùng A
        self.tb = gui_thong_bao(self.a, 'Booking mới', 'Nội dung')  # thông báo của A
        self.client.force_login(self.a)  # đăng nhập A

    def test_loi1_danh_dau_chua_doc_o_chi_tiet_phai_giu_chua_doc(self):  # lỗi 1
        url = reverse('chi_tiet_thong_bao', args=[self.tb.pk])  # trang chi tiết
        self.client.get(url)  # mở xem: tự thành Đã đọc
        trang = self.client.get(url)  # mở lại để lấy form
        res = self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'chua_doc', 'next': trang.context['quay_lai']}, follow=True)  # bấm "Đánh dấu chưa đọc"
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # phải còn Chưa đọc sau khi quay về trang chi tiết
        self.assertContains(res, 'Đánh dấu đã đọc')  # nhãn nút đổi theo trạng thái mới

    def test_loi2_thong_bao_gan_sao_phai_len_dau(self):  # lỗi 2
        cu = ThongBao.objects.get(pk=self.tb.pk)  # thông báo cũ nhất
        moi = gui_thong_bao(self.a, 'Mới hơn', 'nội dung')  # thông báo mới hơn
        services.dat_dau_sao(self.a, cu.pk, True)  # gắn sao thông báo cũ
        thu_tu = [tb.pk for tb in services.lay_danh_sach(self.a)]  # thứ tự hiển thị
        self.assertEqual(thu_tu[0], cu.pk)  # thông báo có sao đứng đầu dù cũ hơn

    def test_loi1_sao_o_chi_tiet_cung_giu_chua_doc(self):  # (b) sau khi đánh dấu chưa đọc, bấm sao vẫn Chưa đọc
        url = reverse('chi_tiet_thong_bao', args=[self.tb.pk])  # trang chi tiết
        self.client.get(url)  # mở xem: tự thành Đã đọc
        quay_lai = self.client.get(url).context['quay_lai']  # địa chỉ mà form ở trang chi tiết gửi kèm
        self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'chua_doc', 'next': quay_lai}, follow=True)  # đánh dấu chưa đọc
        res = self.client.post(reverse('doi_dau_sao', args=[self.tb.pk]), {'gia_tri': 'co', 'next': quay_lai}, follow=True)  # rồi bấm sao
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.CHUA_DOC)  # vẫn Chưa đọc
        self.assertEqual(self.tb.DanhDauSao, DanhDauSao.DA_DANH_DAU)  # và đã có sao
        self.assertContains(res, 'Bỏ đánh dấu sao')  # nhãn nút sao đổi theo

    def test_mo_tu_danh_sach_van_tu_dong_da_doc(self):  # không có giu=1 thì vẫn tự chuyển Đã đọc (không làm hỏng UC9.2 bước 6)
        self.client.get(reverse('chi_tiet_thong_bao', args=[self.tb.pk]))  # mở như bấm từ danh sách
        self.tb.refresh_from_db()  # đọc lại
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.DA_DOC)  # đã Đã đọc

    def test_loi2_bo_sao_ve_lai_dung_cho(self):  # bỏ sao thì thông báo về lại vị trí theo thời gian
        cu = ThongBao.objects.get(pk=self.tb.pk)  # thông báo cũ nhất
        moi = gui_thong_bao(self.a, 'Mới hơn', 'nội dung')  # thông báo mới hơn
        services.dat_dau_sao(self.a, cu.pk, True)  # gắn sao thông báo cũ
        services.dat_dau_sao(self.a, cu.pk, False)  # rồi bỏ sao
        thu_tu = [tb.pk for tb in services.lay_danh_sach(self.a)]  # thứ tự hiển thị
        self.assertEqual(thu_tu, [moi.pk, cu.pk])  # mới hơn đứng trước như cũ

    def test_post_doc_ajax_tra_204(self):  # JS gọi ngầm đổi đã đọc: không chuyển trang
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'da_doc'}, headers={'X-Requested-With': 'XMLHttpRequest'})  # gọi kiểu fetch
        self.assertEqual(res.status_code, 204)  # xong, không redirect
        self.tb.refresh_from_db()  # đọc lại từ DB
        self.assertEqual(self.tb.TrangThaiDoc, TrangThaiDoc.DA_DOC)  # đã chuyển Đã đọc

    def test_post_doc_ajax_gia_tri_la_tra_400(self):  # giá trị lạ qua fetch: báo 400
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(reverse('doi_trang_thai_doc', args=[self.tb.pk]), {'gia_tri': 'abc'}, headers={'X-Requested-With': 'XMLHttpRequest'})  # gửi giá trị lạ
        self.assertEqual(res.status_code, 400)  # JS sẽ tự chuyển sang gửi form thường
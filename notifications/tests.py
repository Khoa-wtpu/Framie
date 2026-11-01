# notifications/tests.py - kiểm tra hàm P2. Chạy: python manage.py test notifications
from django.contrib.auth import get_user_model  # lấy model User của project (accounts.User)
from django.test import TestCase  # lớp test của Django: tự dùng DB tạm, không đụng db.sqlite3 thật

from core.constants import TrangThaiDoc  # hằng số trạng thái đọc
from notifications.models import ThongBao  # model thông báo để kiểm tra dữ liệu đã lưu
from notifications.services import dem_chua_doc, gui_thong_bao, gui_thong_bao_nhieu_nguoi  # 3 hàm cần test

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

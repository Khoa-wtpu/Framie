# core/test_trang_chu.py - B8: kiểm tra Trang chủ. Chạy: python manage.py test core.test_trang_chu
# ▸ ===== CHÚ THÍCH TỔNG QUAN (dành cho sếp) =====
# ▸ Đây là file KIỂM THỬ TỰ ĐỘNG: máy tự "đóng vai khách" mở Trang chủ rồi kiểm tra kết quả có đúng như thiết kế không.
# ▸ Mỗi hàm bắt đầu bằng "test_" là MỘT tình huống kiểm tra. Nếu ai đó sửa code làm hỏng Trang chủ, test sẽ báo đỏ ngay.
# ▸ Cách hiểu nhanh các lệnh: self.client.get('/') = "mở trang chủ"; assertContains = "trang phải CÓ chữ này";
# ▸ assertNotContains = "trang KHÔNG được có chữ này"; assertEqual = "hai giá trị phải bằng nhau".
# ▸ Lưu ý: các dòng bắt đầu bằng "# ▸" là chú thích được thêm vào; code gốc giữ nguyên.

# ▸ SimpleNamespace: tạo nhanh một đối tượng "giả" có các thuộc tính tùy ý, dùng để dựng dữ liệu mẫu.
from types import SimpleNamespace
# ▸ mock: công cụ "thay thế tạm" một hàm thật bằng hàm giả trong lúc test (để không cần dữ liệu thật).
from unittest import mock

# ▸ get_user_model: lấy lớp "Tài khoản người dùng" mà dự án đang dùng.
from django.contrib.auth import get_user_model
# ▸ Group: nhóm quyền của Django (dùng để gán vai trò Khách hàng / Nhiếp ảnh gia cho tài khoản).
from django.contrib.auth.models import Group
# ▸ TestCase: lớp nền cho bài test; mỗi test chạy trên một cơ sở dữ liệu tạm, xong là xóa, không ảnh hưởng dữ liệu thật.
from django.test import TestCase
# ▸ reverse: đổi tên trang thành địa chỉ URL.
from django.urls import reverse

# ▸ Nạp các hằng số dùng chung: TrangThaiHoSo (Đã duyệt / Chờ duyệt...) và VaiTro (Khách hàng, Nhiếp ảnh gia...).
from core.constants import TrangThaiHoSo, VaiTro
# ▸ Nạp các bảng dữ liệu cần dùng. "LoaiHinhChup as LoaiHinhChup_" = đặt tên thay thế có thêm dấu _ để tránh trùng tên với tên khác.
from profiles.models import LoaiHinhChup as LoaiHinhChup_, NhiepAnhGia, NhiepAnhGia_LoaiHinhChup

# ▸ User = lớp tài khoản người dùng của dự án, dùng để tạo tài khoản mẫu trong test.
User = get_user_model()
# ▸ Đường dẫn tới hàm của Khoa MÀ view đang dùng. Test sẽ thay hàm này bằng dữ liệu giả cho dễ kiểm soát.
HAM_NOI_BAT = 'core.views_trang_chu.nhiep_anh_gia_noi_bat'   # hàm của Khoa, thay bằng dữ liệu giả cho dễ kiểm tra


# ▸ Hàm trợ giúp: tạo "ảnh giả" từ tên file.
def _anh(ten_file):
    # giống ImageField: có .url khi có file, rỗng (False) khi chưa có
    # ▸ Nếu có tên file thì trả đối tượng giả có thuộc tính .url = '/media/<tên file>'; nếu không có tên thì trả None (không có ảnh).
    return SimpleNamespace(url=f'/media/{ten_file}') if ten_file else None


# ▸ Hàm trợ giúp: tạo MỘT nhiếp ảnh gia giả với dữ liệu mẫu. Các tham số có giá trị mặc định, test nào cần khác thì truyền giá trị riêng.
def _nag_gia(pk=7, ten='Lê Minh', portfolio='p.jpg', avatar='a.jpg', khung_gio=4):
    # ▸ Trả về từ điển có đúng các trường như hàm thật của Khoa: đối tượng nhiếp ảnh gia (mã pk), tên, ảnh đại diện, ảnh portfolio,
    # ▸ loại hình chụp, khu vực, điểm trung bình 4.8, số đánh giá 23 và số khung giờ trống trong 7 ngày tới.
    return {'nhiep_anh_gia': SimpleNamespace(pk=pk), 'ten': ten, 'anh_dai_dien': _anh(avatar),
            'anh_portfolio': _anh(portfolio), 'loai_hinh': 'Cưới, Chân dung', 'khu_vuc': 'Đà Nẵng',
            'diem_trung_binh': 4.8, 'so_danh_gia': 23, 'so_khung_gio_trong': khung_gio}


# ▸ NHÓM 1: các kiểm tra cơ bản của Trang chủ.
class TrangChuCoBan(TestCase):
    # ▸ Test 1: khách chưa đăng nhập vẫn vào được Trang chủ và đúng trang.
    def test_vao_duoc_khong_can_dang_nhap(self):
        # ▸ Giả lập khách mở địa chỉ gốc "/" và lưu phản hồi vào biến res.
        res = self.client.get('/')
        # ▸ Mã 200 = "thành công". (Nếu bắt đăng nhập thì sẽ là 302 chuyển hướng.)
        self.assertEqual(res.status_code, 200)
        # ▸ Địa chỉ "/" phải đúng là trang có tên nội bộ "home".
        self.assertEqual(res.resolver_match.url_name, 'home')
        # ▸ Trang phải được dựng từ file giao diện core/trang_chu.html.
        self.assertTemplateUsed(res, 'core/trang_chu.html')
        # ▸ Chiều ngược lại: tên "home" phải đổi ra đúng địa chỉ "/".
        self.assertEqual(reverse('home'), '/')

    # ▸ Test 2: đủ các khối nội dung chính.
    def test_du_cac_khoi(self):
        # ▸ Mở trang chủ, lấy toàn bộ mã HTML dạng chữ (decode đổi dữ liệu thô sang chữ tiếng Việt).
        html = self.client.get('/').content.decode()
        # ▸ Danh sách 4 câu tiêu đề đặc trưng: banner, khối nổi bật, khối 5 bước, khối mời đăng ký.
        for noi_dung in ['Từ tìm kiếm đến nhận ảnh', 'Nhiếp ảnh gia nổi bật', 'Đặt lịch trên FRAMIE qua 5 bước',
                         'Tạo tài khoản để bắt đầu đặt lịch']:
            # ▸ Với từng câu: bắt buộc phải xuất hiện trong trang, thiếu câu nào là test báo lỗi.
            self.assertIn(noi_dung, html)

    # ▸ Test 3: ô tìm kiếm nhanh gửi đúng sang trang Tìm kiếm.
    def test_o_tim_nhanh_gui_len_trang_tim_kiem(self):
        # ▸ Mở trang chủ, lấy mã HTML.
        html = self.client.get('/').content.decode()
        # ▸ Form tìm kiếm phải có thuộc tính action trỏ đúng tới địa chỉ trang "search".
        self.assertIn(f'action="{reverse("search")}"', html)
        # ▸ Ô nhập phải có tên "q" (tham số từ khóa mà trang tìm kiếm đọc).
        self.assertIn('name="q"', html)

    # ▸ Test 4: 5 bước đặt lịch hiện đúng thứ tự 1 -> 5.
    def test_cac_buoc_dat_lich_dung_thu_tu(self):
        # ▸ Mở trang chủ, lấy mã HTML.
        html = self.client.get('/').content.decode()
        # ▸ Với mỗi tiêu đề bước (theo thứ tự đúng), tìm vị trí xuất hiện đầu tiên trong HTML => được danh sách 5 vị trí.
        vi_tri = [html.index(t) for t in ['Tìm nhiếp ảnh gia', 'Chọn lịch và giữ chỗ', 'Gửi yêu cầu Booking',
                                          'Xác nhận và đặt cọc', 'Chụp và nhận ảnh']]
        # ▸ Nếu các bước đứng đúng thứ tự thì danh sách vị trí đã tăng dần, tức bằng chính nó sau khi sắp xếp.
        self.assertEqual(vi_tri, sorted(vi_tri))


# ▸ NHÓM 2: kiểm tra khối "Nhiếp ảnh gia nổi bật".
class NhiepAnhGiaNoiBat(TestCase):
    # ▸ Test 5: không có nhiếp ảnh gia nào thì phải hiện thông báo trống.
    def test_khong_co_du_lieu_hien_thong_bao_rong(self):
        # ▸ Trong khối with, hàm của Khoa bị thay bằng hàm giả luôn trả danh sách rỗng [].
        with mock.patch(HAM_NOI_BAT, return_value=[]):
            # ▸ Mở trang chủ trong điều kiện "không có ai nổi bật".
            res = self.client.get('/')
        # ▸ Trang phải có câu thông báo "Chưa có nhiếp ảnh gia nổi bật".
        self.assertContains(res, 'Chưa có nhiếp ảnh gia nổi bật')
        # ▸ Dữ liệu 'noi_bat' mà view giao cho giao diện phải là danh sách rỗng.
        self.assertEqual(res.context['noi_bat'], [])

    # ▸ Test 6: view phải gọi hàm của Khoa đúng 1 lần và xin đúng 3 người.
    def test_goi_ham_cua_khoa_voi_so_luong_3(self):
        # ▸ Thay hàm của Khoa bằng hàm giả và đặt tên "ham" để theo dõi xem nó được gọi thế nào.
        with mock.patch(HAM_NOI_BAT, return_value=[]) as ham:
            # ▸ Mở trang chủ.
            self.client.get('/')
        # ▸ Kiểm tra: hàm được gọi đúng 1 lần, với tham số so_luong=3.
        ham.assert_called_once_with(so_luong=3)

    # ▸ Test 7: thẻ nhiếp ảnh gia hiện đủ thông tin.
    def test_hien_the_day_du_thong_tin(self):
        # ▸ Cho hàm của Khoa trả về 1 nhiếp ảnh gia giả với dữ liệu mặc định.
        with mock.patch(HAM_NOI_BAT, return_value=[_nag_gia()]):
            # ▸ Mở trang chủ.
            res = self.client.get('/')
        # ▸ Phải thấy tên "Lê Minh".
        self.assertContains(res, 'Lê Minh')
        # ▸ Phải thấy điểm "4.8" (dấu chấm, không phải dấu phẩy).
        self.assertContains(res, '4.8')                       # dấu chấm, giống trang tìm kiếm
        # ▸ Phải thấy số lượt đánh giá "23 đánh giá".
        self.assertContains(res, '23 đánh giá')
        # ▸ Phải thấy loại hình chụp.
        self.assertContains(res, 'Cưới, Chân dung')
        # ▸ Phải thấy khu vực.
        self.assertContains(res, 'Đà Nẵng')
        # ▸ Phải thấy nhãn số khung giờ còn trống.
        self.assertContains(res, '4 khung giờ trống trong 7 ngày tới')
        # ▸ Địa chỉ ảnh Portfolio phải nằm trong trang.
        self.assertContains(res, '/media/p.jpg')              # ảnh Portfolio
        # ▸ Địa chỉ ảnh đại diện phải nằm trong trang.
        self.assertContains(res, '/media/a.jpg')              # ảnh đại diện

    # ▸ Test 8: nhiếp ảnh gia không còn khung giờ trống.
    def test_khong_co_khung_gio_trong(self):
        # ▸ Dựng nhiếp ảnh gia giả với 0 khung giờ trống.
        with mock.patch(HAM_NOI_BAT, return_value=[_nag_gia(khung_gio=0)]):
            # ▸ Mở trang chủ.
            res = self.client.get('/')
        # ▸ Trang phải hiện câu "Chưa có khung giờ trống..." thay vì con số.
        self.assertContains(res, 'Chưa có khung giờ trống trong 7 ngày tới')

    # ▸ Test 9: thiếu ảnh thì trang vẫn chạy, không lỗi.
    def test_thieu_anh_van_hien_the_khong_loi(self):
        # ▸ Dựng nhiếp ảnh gia giả KHÔNG có ảnh portfolio lẫn ảnh đại diện.
        with mock.patch(HAM_NOI_BAT, return_value=[_nag_gia(portfolio=None, avatar=None)]):
            # ▸ Mở trang chủ.
            res = self.client.get('/')
        # ▸ Trang vẫn phải thành công (mã 200), không bị lỗi 500.
        self.assertEqual(res.status_code, 200)
        # ▸ Và vẫn hiện tên nhiếp ảnh gia.
        self.assertContains(res, 'Lê Minh')

    # ▸ Test 10: thẻ chỉ bấm được khi đã có trang hồ sơ.
    def test_the_bam_duoc_khi_co_trang_ho_so(self):
        # K9 (photographer_detail) chưa có: thẻ không có link. Khi K9 có thì thẻ trỏ đúng hồ sơ.
        # ▸ Dựng 1 nhiếp ảnh gia giả có mã 7.
        with mock.patch(HAM_NOI_BAT, return_value=[_nag_gia(pk=7)]):
            # ▸ Lúc này trang hồ sơ K9 chưa tồn tại => thẻ KHÔNG được có lớp "card--link" (kiểu thẻ bấm được).
            self.assertNotContains(self.client.get('/'), 'card--link')
            # ▸ Giả lập "K9 đã làm xong": thay hàm reverse bằng hàm giả. Với tên 'photographer_detail' trả '/nhiep-anh-gia/<mã>/',
            # ▸ còn các tên khác thì dùng reverse thật như bình thường.
            with mock.patch('core.views_trang_chu.reverse', side_effect=lambda ten, args=None: f'/nhiep-anh-gia/{args[0]}/'
                            if ten == 'photographer_detail' else reverse(ten, args=args)):
                # ▸ Bây giờ thẻ phải có liên kết trỏ đúng tới hồ sơ số 7.
                self.assertContains(self.client.get('/'), 'href="/nhiep-anh-gia/7/"')


# ▸ NHÓM 3: kiểm tra khối "Loại hình chụp".
class LoaiHinhChupTrangChu(TestCase):
    # ▸ Test 11: mỗi loại hình có link lọc đúng sang trang tìm kiếm.
    def test_co_link_loc_theo_loai_hinh(self):
        # ▸ Tạo vào CSDL tạm một loại hình tên "Cưới".
        lh = LoaiHinhChup_.objects.create(TenLoaiHinh='Cưới')
        # ▸ Mở trang chủ, lấy HTML.
        html = self.client.get('/').content.decode()
        # ▸ Phải có link dạng "<địa chỉ tìm kiếm>?loai_hinh=<mã>".
        self.assertIn(f'{reverse("search")}?loai_hinh={lh.pk}', html)
        # ▸ Phải có tiêu đề khối loại hình.
        self.assertIn('Bạn muốn chụp loại hình nào?', html)

    # ▸ Test 12: chưa có loại hình nào thì ẩn cả khối.
    def test_chua_co_loai_hinh_thi_an_khoi(self):
        # ▸ CSDL tạm đang trống loại hình => tiêu đề khối KHÔNG được xuất hiện.
        self.assertNotContains(self.client.get('/'), 'Bạn muốn chụp loại hình nào?')

    # ▸ Test 13: số đếm chỉ tính nhiếp ảnh gia công khai (đã duyệt).
    def test_dem_so_nhiep_anh_gia_cong_khai(self):
        # ▸ Tạo loại hình "Cưới".
        lh = LoaiHinhChup_.objects.create(TenLoaiHinh='Cưới')
        # ▸ Tạo 2 nhiếp ảnh gia: 'a' có hồ sơ ĐÃ DUYỆT, 'b' có hồ sơ CHỜ DUYỆT.
        for ten, trang_thai in (('a', TrangThaiHoSo.DA_DUYET), ('b', TrangThaiHoSo.CHO_DUYET)):
            # ▸ Tạo tài khoản mẫu (tên, email, mật khẩu, số điện thoại riêng cho mỗi người; ord(ten) đổi chữ thành số để số điện thoại không trùng).
            u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                         so_dien_thoai=f'09000000{ord(ten)}', trang_thai_ho_so=trang_thai)
            # ▸ Tạo hồ sơ nhiếp ảnh gia gắn với tài khoản đó, điền các trường bắt buộc bằng dữ liệu giả (ảnh, giới thiệu, ngân hàng, số tài khoản, QR).
            nag = NhiepAnhGia.objects.create(MaTaiKhoan=u, AnhDaiDien='a.jpg', GioiThieu='g', NganHang='b',
                                             SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')
            # ▸ Cho người đó nhận chụp loại hình "Cưới".
            NhiepAnhGia_LoaiHinhChup.objects.create(MaNhiepAnhGia=nag, MaLoaiHinh=lh)
        # ▸ Mở trang chủ.
        res = self.client.get('/')
        # ▸ Kết quả phải là: loại hình Cưới có đúng 1 người (chỉ người đã duyệt được tính, người chờ duyệt bị loại).
        self.assertEqual(res.context['loai_hinh_ds'], [{'ma': lh.pk, 'ten': 'Cưới', 'so_nguoi': 1}])   # chỉ tính hồ sơ Đã duyệt
        # ▸ Và chữ "1 nhiếp ảnh gia" phải hiện trên trang.
        self.assertContains(res, '1 nhiếp ảnh gia')


# ▸ NHÓM 4: kiểm tra khối "Lời mời đăng ký" (cuối trang).
class LoiMoiDangKy(TestCase):
    # ▸ Test 14: khách chưa đăng nhập thấy lời mời đăng ký.
    def test_khach_chua_dang_nhap_thay_loi_moi(self):
        # ▸ Mở trang chủ khi chưa đăng nhập.
        res = self.client.get('/')
        # ▸ Phải có link tới trang đăng ký.
        self.assertContains(res, reverse('register'))
        # ▸ Phải có nút "Đăng ký ngay".
        self.assertContains(res, 'Đăng ký ngay')

    # ▸ Test 15: khách đã đăng nhập thì thấy nút "Tìm nhiếp ảnh gia" thay cho đăng ký.
    def test_da_dang_nhap_thay_nut_tim_nhiep_anh_gia(self):
        # ▸ Tạo một tài khoản khách hàng mẫu.
        u = User.objects.create_user(username='kh', email='kh@x.vn', password='x', so_dien_thoai='0900000001')
        # ▸ Gán tài khoản vào nhóm vai trò "Khách hàng" (tạo nhóm nếu chưa có; [0] lấy đối tượng nhóm).
        u.groups.add(Group.objects.get_or_create(name=VaiTro.KHACH_HANG)[0])
        # ▸ Đăng nhập thẳng bằng tài khoản này (bỏ qua bước nhập mật khẩu).
        self.client.force_login(u)
        # ▸ Mở trang chủ khi đã đăng nhập.
        res = self.client.get('/')
        # ▸ Nút "Đăng ký ngay" không được xuất hiện nữa.
        self.assertNotContains(res, 'Đăng ký ngay')
        # ▸ Thay vào đó phải hiện tiêu đề "Sẵn sàng cho buổi chụp tiếp theo?".
        self.assertContains(res, 'Sẵn sàng cho buổi chụp tiếp theo?')

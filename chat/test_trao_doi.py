# chat/test_trao_doi.py - P11 (UC8.2, UC8.3). Chạy: python manage.py test chat
import itertools  # bộ đếm để mỗi User có số điện thoại khác nhau
import re  # cắt đúng vùng HTML cần kiểm tra (cột trái, token CSRF)
from unittest import mock  # patch để ép lỗi 5a và 2a

from django.contrib.auth import get_user_model  # model User của dự án (accounts.User)
from django.contrib.auth.models import Group  # nhóm quyền = vai trò
from django.contrib.messages import get_messages  # đọc thông báo đã gửi
from django.db import DatabaseError  # lỗi DB giả
from django.test import TestCase  # lớp test của Django
from django.urls import reverse  # đổi name thành đường dẫn

from chat import services  # hằng số và hàm nghiệp vụ
from chat.models import CuocTroChuyen, TinNhan  # hai bảng của Module 8
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò, trạng thái hồ sơ
from profiles.models import NhiepAnhGia  # hồ sơ Nhiếp ảnh gia

User = get_user_model()  # model User
_DEM = itertools.count(500)  # bắt đầu từ 500 để không trùng số điện thoại với tests.py của P10
AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}  # tiêu đề chat.js gửi kèm mọi yêu cầu ngầm


def _cot_trai(html):  # chỉ lấy danh sách cuộc ở cột trái, bỏ qua header (header cũng có aria-current)
    m = re.search(r'<ul class="hop-thu".*?</ul>', html, re.S)  # khối <ul class="hop-thu">...</ul>
    return m.group(0) if m else ''  # không có thì trả chuỗi rỗng


def _bo_csrf(html):  # token CSRF đổi mỗi lần nên bỏ đi trước khi so sánh hai trang
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken" value=""', html)


def _tao_user(ten, vai_tro, trang_thai=None):  # tạo User thuộc một nhóm
    u = User.objects.create_user(username=ten, password='Xk9#mQ2vLp', email=f'{ten}@x.vn',
                                 so_dien_thoai='0' + str(next(_DEM)).zfill(9), trang_thai_ho_so=trang_thai)  # số điện thoại hợp lệ
    u.groups.add(Group.objects.get_or_create(name=vai_tro)[0])  # gán vai trò
    return u  # trả về User


def _tao_nag(ten, trang_thai=TrangThaiHoSo.DA_DUYET):  # tạo Nhiếp ảnh gia kèm hồ sơ
    u = _tao_user(ten, VaiTro.NHIEP_ANH_GIA, trang_thai)  # tài khoản
    return NhiepAnhGia.objects.create(MaTaiKhoan=u, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',
                                      SoTaiKhoan='123', ChuTaiKhoan='C', AnhMaQR='q.png')  # hồ sơ


class CoSoTest(TestCase):  # lớp cha: dựng sẵn 1 Khách hàng, 1 Nhiếp ảnh gia, 1 cuộc trò chuyện
    def setUp(self):  # chạy trước mỗi test
        self.khach = _tao_user('khach1', VaiTro.KHACH_HANG)  # Khách hàng
        self.nag = _tao_nag('nag1')  # Nhiếp ảnh gia đã duyệt
        self.cuoc = CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=self.nag)  # cuộc trò chuyện
        self.url_trang = reverse('chi_tiet_cuoc_tro_chuyen', args=[self.cuoc.pk])  # trang chat
        self.url_gui = reverse('gui_tin_nhan', args=[self.cuoc.pk])  # gửi tin
        self.url_moi = reverse('tin_nhan_moi', args=[self.cuoc.pk])  # polling

    def tin(self, nguoi, noi_dung):  # tạo nhanh một tin trong cuộc trò chuyện
        return TinNhan.objects.create(MaCuocTroChuyen=self.cuoc, MaNguoiGui=nguoi, NoiDung=noi_dung)  # INSERT


class XemLichSuTests(CoSoTest):  # UC8.3
    def test_hai_ben_thay_lich_su_theo_thu_tu(self):  # luồng chính
        self.tin(self.khach, 'Chào anh')  # tin 1
        self.tin(self.nag.MaTaiKhoan, 'Chào em')  # tin 2
        for u in (self.khach, self.nag.MaTaiKhoan):  # cả hai bên
            self.client.force_login(u)  # đăng nhập
            r = self.client.get(self.url_trang)  # mở cuộc trò chuyện
            self.assertEqual(r.status_code, 200)  # mở được
            html = r.content.decode()  # nội dung trang
            html = html[html.index('data-chat-list'):]  # chỉ xét khung tin nhắn, bỏ cột trái (xem trước tin cuối)
            self.assertLess(html.index('Chào anh'), html.index('Chào em'))  # cũ trước, mới sau

    def test_tin_cua_minh_va_cua_doi_phuong_khac_class(self):  # tin của mình nằm bên phải
        self.tin(self.khach, 'cua khach')  # tin của Khách
        self.client.force_login(self.khach)  # Khách xem
        self.assertContains(self.client.get(self.url_trang), 'tn--cua-toi')  # có bong bóng "của tôi"
        self.client.force_login(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia xem
        self.assertContains(self.client.get(self.url_trang), 'tn--doi-phuong')  # cùng tin nhưng là của đối phương

    def test_nguoi_ngoai_bi_404(self):  # chỉ hai người trong cuộc
        ngoai = _tao_user('khach2', VaiTro.KHACH_HANG)  # Khách hàng khác
        self.client.force_login(ngoai)  # đăng nhập
        self.assertEqual(self.client.get(self.url_trang).status_code, 404)  # không xem được trang
        self.assertEqual(self.client.get(self.url_moi + '?sau=0').status_code, 404)  # không polling được

    def test_nag_khac_va_quan_tri_vien_bi_404(self):  # Nhiếp ảnh gia khác, Quản trị viên cũng là người ngoài
        for u in (_tao_nag('nag2').MaTaiKhoan, _tao_user('qtv', VaiTro.QUAN_TRI_VIEN)):  # hai người ngoài
            self.client.force_login(u)  # đăng nhập
            self.assertEqual(self.client.get(self.url_trang).status_code, 404)  # đều bị chặn

    def test_chua_dang_nhap_chuyen_sang_dang_nhap(self):  # trang HTML
        r = self.client.get(self.url_trang)  # chưa đăng nhập
        self.assertEqual(r.status_code, 302)  # chuyển hướng
        self.assertTrue(r['Location'].startswith(reverse('login') + '?next='))  # kèm next

    def test_nag_chua_duyet_bi_404(self):  # README: chưa duyệt chỉ dùng "Hồ sơ của tôi"
        u = self.nag.MaTaiKhoan  # tài khoản Nhiếp ảnh gia
        u.trang_thai_ho_so = TrangThaiHoSo.CHO_DUYET  # chuyển về chờ duyệt
        u.save()  # lưu
        self.client.force_login(u)  # đăng nhập
        self.assertEqual(self.client.get(self.url_trang).status_code, 404)  # không vào được

    def test_chi_hien_30_tin_gan_nhat_va_tai_them(self):  # kéo lên tải tin cũ như Messenger
        ids = [self.tin(self.khach, f'tin so {i}').pk for i in range(35)]  # 35 tin
        self.client.force_login(self.khach)  # đăng nhập
        html = self.client.get(self.url_trang).content.decode()  # mở trang
        self.assertIn('data-con-cu="1"', html)  # còn tin cũ
        self.assertIn('tin so 34', html)  # có tin mới nhất
        self.assertNotIn('>tin so 4</p>', html)  # tin thứ 5 (cũ) chưa hiện
        r = self.client.get(self.url_moi, {'truoc': ids[5]}, **AJAX)  # tải tin cũ hơn tin thứ 6 trong danh sách (id ids[5])
        d = r.json()  # đọc JSON
        self.assertEqual([t['id'] for t in d['tin_nhan']], ids[0:5])  # đủ 5 tin cũ, cũ trước mới sau
        self.assertFalse(d['con_cu'])  # hết tin cũ

    def test_loi_tai_lich_su_hien_thong_bao_2a(self):  # luồng ngoại lệ 2a
        self.client.force_login(self.khach)  # đăng nhập
        with mock.patch('chat.views.services.lay_tin_gan_nhat', side_effect=DatabaseError('hỏng')):  # ép lỗi DB
            r = self.client.get(self.url_trang)  # mở trang
        self.assertEqual(r.status_code, 200)  # không phải trang 500
        self.assertContains(r, 'Không thể tải lịch sử trao đổi')  # tiêu đề theo wireframe
        self.assertContains(r, 'Vui lòng thực hiện lại.')  # mô tả theo đặc tả (template tách thành 2 phần)

    def test_noi_dung_duoc_escape_chong_xss(self):  # chèn thẻ script
        self.tin(self.khach, '<script>alert(1)</script>')  # tin độc hại
        self.client.force_login(self.nag.MaTaiKhoan)  # đối phương xem
        html = self.client.get(self.url_trang).content.decode()  # mở trang
        self.assertNotIn('<script>alert(1)</script>', html)  # không còn nguyên thẻ
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)  # đã bị escape
        d = self.client.get(self.url_moi + '?sau=0', **AJAX).json()  # qua JSON polling
        self.assertNotIn('<script>', d['tin_nhan'][0]['html'])  # HTML trong JSON cũng đã escape


class GuiTinTests(CoSoTest):  # UC8.2
    def test_khach_gui_tin_luu_vao_lich_su(self):  # luồng chính (yêu cầu ngầm)
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_gui, {'noi_dung': '  Xin chào  '}, **AJAX)  # gửi tin
        self.assertEqual(r.status_code, 200)  # thành công
        tin = TinNhan.objects.get()  # đã lưu đúng 1 tin
        self.assertEqual((tin.NoiDung, tin.MaNguoiGui, tin.MaCuocTroChuyen), ('Xin chào', self.khach, self.cuoc))  # nội dung đã strip, đúng người gửi
        self.assertEqual(r.json(), {'ok': True, 'id': tin.pk})  # trả mã tin

    def test_nag_tra_loi_va_khach_thay_qua_polling(self):  # hai chiều
        self.client.force_login(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia
        self.client.post(self.url_gui, {'noi_dung': 'Em nhận lịch ạ'}, **AJAX)  # gửi tin
        self.client.force_login(self.khach)  # Khách hàng
        d = self.client.get(self.url_moi + '?sau=0', **AJAX).json()  # polling
        self.assertEqual(len(d['tin_nhan']), 1)  # thấy 1 tin
        self.assertIn('Em nhận lịch ạ', d['tin_nhan'][0]['html'])  # đúng nội dung

    def test_tin_rong_hoac_chi_khoang_trang_bi_tu_choi(self):  # kiểm tra đầu vào
        self.client.force_login(self.khach)  # đăng nhập
        for nd in ('', '   ', '\n\n'):  # ba kiểu rỗng
            r = self.client.post(self.url_gui, {'noi_dung': nd}, **AJAX)  # gửi
            self.assertEqual(r.status_code, 400)  # bị từ chối
        self.assertEqual(TinNhan.objects.count(), 0)  # không lưu gì

    def test_tin_qua_dai_bi_tu_choi(self):  # vượt 2000 ký tự
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_gui, {'noi_dung': 'a' * (services.GIOI_HAN_NOI_DUNG + 1)}, **AJAX)  # gửi tin dài
        self.assertEqual(r.status_code, 400)  # bị từ chối
        r = self.client.post(self.url_gui, {'noi_dung': 'a' * services.GIOI_HAN_NOI_DUNG}, **AJAX)  # đúng giới hạn
        self.assertEqual(r.status_code, 200)  # được chấp nhận

    def test_nguoi_ngoai_khong_gui_duoc(self):  # chặn ghi
        self.client.force_login(_tao_user('khach2', VaiTro.KHACH_HANG))  # người ngoài
        self.assertEqual(self.client.post(self.url_gui, {'noi_dung': 'hack'}, **AJAX).status_code, 404)  # 404
        self.assertEqual(TinNhan.objects.count(), 0)  # không lưu gì

    def test_chua_dang_nhap_ajax_tra_401_form_thuong_chuyen_dang_nhap(self):  # hết phiên
        self.assertEqual(self.client.post(self.url_gui, {'noi_dung': 'x'}, **AJAX).status_code, 401)  # yêu cầu ngầm: 401 JSON
        r = self.client.post(self.url_gui, {'noi_dung': 'x'})  # form thường
        self.assertEqual(r.status_code, 302)  # chuyển sang đăng nhập
        self.assertTrue(r['Location'].startswith(reverse('login')))  # đúng trang đăng nhập
        self.assertEqual(TinNhan.objects.count(), 0)  # không lưu gì

    def test_get_vao_url_gui_bi_405(self):  # chỉ POST
        self.client.force_login(self.khach)  # đăng nhập
        self.assertEqual(self.client.get(self.url_gui).status_code, 405)  # từ chối GET

    def test_form_thuong_khong_co_javascript_van_gui_duoc(self):  # dự phòng không JS
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(self.url_gui, {'noi_dung': 'Không JS'})  # form thường
        self.assertRedirects(r, self.url_trang, fetch_redirect_response=False)  # quay lại cuộc trò chuyện
        self.assertEqual(TinNhan.objects.get().NoiDung, 'Không JS')  # đã lưu

    def test_loi_luu_hien_thong_bao_5a(self):  # luồng ngoại lệ 5a
        self.client.force_login(self.khach)  # đăng nhập
        with mock.patch('chat.views.services.gui_tin_nhan', side_effect=DatabaseError('hỏng')):  # ép lỗi DB
            r = self.client.post(self.url_gui, {'noi_dung': 'x'}, **AJAX)  # gửi ngầm
        self.assertEqual(r.status_code, 500)  # lỗi máy chủ có kiểm soát
        self.assertEqual(r.json()['loi'], services.LOI_GUI_TIN)  # thông báo theo đặc tả
        with mock.patch('chat.views.services.gui_tin_nhan', side_effect=DatabaseError('hỏng')):  # ép lỗi lần nữa
            r = self.client.post(self.url_gui, {'noi_dung': 'x'})  # form thường
        self.assertEqual(r.status_code, 302)  # quay về trang chat
        self.assertIn(services.LOI_GUI_TIN, [str(m) for m in get_messages(r.wsgi_request)])  # hộp đỏ trên đầu trang
        self.assertEqual(TinNhan.objects.count(), 0)  # không lưu gì


class PollingTests(CoSoTest):  # tự làm mới tin mỗi vài giây
    def test_chi_tra_tin_sau_moc(self):  # lấy phần mới
        a, b, c = (self.tin(self.khach, t).pk for t in ('a', 'b', 'c'))  # ba tin
        self.client.force_login(self.nag.MaTaiKhoan)  # đăng nhập
        d = self.client.get(self.url_moi, {'sau': a}, **AJAX).json()  # xin tin sau tin a
        self.assertEqual([t['id'] for t in d['tin_nhan']], [b, c])  # đúng b, c theo thứ tự
        self.assertEqual(self.client.get(self.url_moi, {'sau': c}, **AJAX).json()['tin_nhan'], [])  # không còn tin mới

    def test_tham_so_sai_bi_400(self):  # kiểm tra tham số
        self.client.force_login(self.khach)  # đăng nhập
        for q in ({}, {'sau': 'abc'}, {'sau': '1', 'truoc': '2'}):  # thiếu, không phải số, đủ cả hai
            self.assertEqual(self.client.get(self.url_moi, q, **AJAX).status_code, 400)  # đều 400

    def test_chua_dang_nhap_tra_401(self):  # chat.js dừng polling khi gặp 401
        self.assertEqual(self.client.get(self.url_moi + '?sau=0', **AJAX).status_code, 401)  # 401

    def test_khong_cho_trinh_duyet_luu_dem(self):  # tránh thấy tin cũ
        self.client.force_login(self.khach)  # đăng nhập
        self.assertIn('no-cache', self.client.get(self.url_moi + '?sau=0', **AJAX)['Cache-Control'])  # có tiêu đề chống lưu đệm


class HopThuTests(CoSoTest):  # menu "Tin nhắn" (url name inbox)
    def test_url_inbox_ton_tai(self):  # core/navigation.py dùng name này
        self.assertEqual(reverse('inbox'), '/tin-nhan/')  # đúng đường dẫn

    def test_khach_thay_cuoc_cua_minh_cuoc_moi_nhat_len_dau(self):  # sắp xếp theo tin cuối
        nag2 = _tao_nag('nag2')  # Nhiếp ảnh gia thứ hai
        cuoc2 = CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=nag2)  # cuộc thứ hai
        self.tin(self.khach, 'tin cu o cuoc 1')  # tin ở cuộc 1
        TinNhan.objects.create(MaCuocTroChuyen=cuoc2, MaNguoiGui=nag2.MaTaiKhoan, NoiDung='tin moi o cuoc 2')  # tin mới hơn ở cuộc 2
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.get(reverse('inbox'))  # mở danh sách
        self.assertEqual([c['ma'] for c in r.context['cac_cuoc']], [cuoc2.pk, self.cuoc.pk])  # cuộc 2 lên đầu
        self.assertContains(r, 'tin moi o cuoc 2')  # có xem trước tin cuối
        self.assertContains(r, 'Bạn: tin cu o cuoc 1')  # tin cuối do mình gửi thì có "Bạn:"

    def test_nag_chi_thay_cuoc_cua_minh(self):  # không lẫn cuộc của người khác
        nag2 = _tao_nag('nag2')  # Nhiếp ảnh gia khác
        CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=nag2)  # cuộc không liên quan
        self.client.force_login(self.nag.MaTaiKhoan)  # đăng nhập
        r = self.client.get(reverse('inbox'))  # mở danh sách
        self.assertEqual([c['ma'] for c in r.context['cac_cuoc']], [self.cuoc.pk])  # chỉ cuộc của mình

    def test_quan_tri_vien_va_nag_chua_duyet_bi_403(self):  # không có mục Tin nhắn trong menu của họ
        self.client.force_login(_tao_user('qtv', VaiTro.QUAN_TRI_VIEN))  # Quản trị viên
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 403)  # bị chặn
        self.client.force_login(_tao_nag('nag3', TrangThaiHoSo.CHO_DUYET).MaTaiKhoan)  # Nhiếp ảnh gia chờ duyệt
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 403)  # bị chặn

    def test_chua_dang_nhap_chuyen_sang_dang_nhap(self):  # chặn người lạ
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 302)  # chuyển hướng

    def test_danh_sach_trong_hien_cau_huong_dan(self):  # chưa có cuộc nào
        CuocTroChuyen.objects.all().delete()  # xóa cuộc trò chuyện
        self.client.force_login(self.khach)  # đăng nhập
        self.assertContains(self.client.get(reverse('inbox')), 'Chưa có cuộc trò chuyện nào')  # tiêu đề ở cột phải


# ---------------------------------------------------------------------------------------------
# Bổ sung checkpoint 4: kiểm thử theo bảng trường hợp (tách Khách hàng / Nhiếp ảnh gia)
# ---------------------------------------------------------------------------------------------

class CotTraiVaVaiTroTests(CoSoTest):  # lỗi gốc: trang chi tiết bị rỗng cột trái, nhãn/câu chữ không theo vai trò
    def setUp(self):  # thêm một cuộc trò chuyện thứ hai để kiểm tra danh sách có nhiều dòng
        super().setUp()  # dựng cuộc 1 (khach1 - nag1)
        self.khach2 = _tao_user('khach2', VaiTro.KHACH_HANG)  # Khách hàng thứ hai
        self.nag2 = _tao_nag('nag2')  # Nhiếp ảnh gia thứ hai
        self.cuoc_khach = CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=self.nag2)  # khach1 - nag2
        self.cuoc_nag = CuocTroChuyen.objects.create(MaKhachHang=self.khach2, MaNhiepAnhGia=self.nag)  # khach2 - nag1

    # ---- trường hợp 8: mở một cuộc thì cột trái vẫn đủ danh sách ----
    def test_khach_mo_chi_tiet_cot_trai_van_day_du(self):  # lỗi ảnh 3 của khách hàng
        self.client.force_login(self.khach)  # Khách hàng
        r = self.client.get(self.url_trang)  # mở cuộc 1
        self.assertEqual(r.status_code, 200)  # mở được
        self.assertEqual({c['ma'] for c in r.context['cac_cuoc']}, {self.cuoc.pk, self.cuoc_khach.pk})  # đủ 2 cuộc của mình
        self.assertContains(r, 'nag2')  # tên đối phương của cuộc còn lại hiện ở cột trái
        self.assertNotContains(r, 'Bạn chưa có cuộc trò chuyện nào')  # không hiện câu "trống"

    def test_nag_mo_chi_tiet_cot_trai_van_day_du(self):  # lỗi ảnh 1 của nhiếp ảnh gia
        self.client.force_login(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia
        r = self.client.get(self.url_trang)  # mở cuộc 1
        self.assertEqual(r.status_code, 200)  # mở được
        self.assertEqual({c['ma'] for c in r.context['cac_cuoc']}, {self.cuoc.pk, self.cuoc_nag.pk})  # đủ 2 cuộc của mình
        self.assertContains(r, 'khach2')  # tên Khách hàng của cuộc còn lại hiện ở cột trái
        self.assertNotContains(r, 'Chưa có khách hàng nào nhắn tin cho bạn')  # không hiện câu "trống"

    def test_cuoc_dang_mo_duoc_lam_noi_bat_dung_mot_dong(self):  # nổi bật cuộc đang mở
        for u in (self.khach, self.nag.MaTaiKhoan):  # cả hai vai trò
            self.client.force_login(u)  # đăng nhập
            ds = _cot_trai(self.client.get(self.url_trang).content.decode())  # chỉ xét cột trái (header cũng có aria-current)
            self.assertEqual(ds.count('aria-current="page"'), 1)  # chỉ một dòng được đánh dấu
            self.assertEqual(ds.count('is-active'), 1)  # và chỉ một dòng có class nổi bật
            self.assertIn(f'href="{self.url_trang}" aria-current="page"', ds)  # đúng là dòng của cuộc đang mở

    def test_tran_chi_tiet_va_hop_thu_dung_chung_ngu_canh_cot_trai(self):  # tránh quên truyền biến lần nữa
        for u in (self.khach, self.nag.MaTaiKhoan):  # cả hai vai trò
            self.client.force_login(u)  # đăng nhập
            ds_hop_thu = self.client.get(reverse('inbox')).context['cac_cuoc']  # danh sách ở hộp thư
            ds_chi_tiet = self.client.get(self.url_trang).context['cac_cuoc']  # danh sách ở trang chi tiết
            self.assertEqual([c['ma'] for c in ds_hop_thu], [c['ma'] for c in ds_chi_tiet])  # giống hệt nhau

    # ---- nhãn vai trò, nút Xem hồ sơ (trường hợp 19) ----
    def test_khach_thay_doi_phuong_la_nhiep_anh_gia(self):  # lỗi nhãn ảnh 1
        self.client.force_login(self.khach)  # Khách hàng
        r = self.client.get(self.url_trang)  # mở cuộc 1
        self.assertEqual(r.context['doi_phuong']['vai_tro'], 'Nhiếp ảnh gia')  # nhãn đúng
        self.assertContains(r, '<p class="chat__vai-tro">Nhiếp ảnh gia</p>')  # hiện ở đầu cột giữa và cột phải
        self.assertNotContains(r, '<p class="chat__vai-tro">Khách hàng</p>')  # không còn nhãn sai
        self.assertContains(r, '>Xem hồ sơ</a>')  # Khách hàng có nút Xem hồ sơ

    def test_nag_thay_doi_phuong_la_khach_hang_khong_co_xem_ho_so(self):  # trường hợp 19
        self.client.force_login(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia
        r = self.client.get(self.url_trang)  # mở cuộc 1
        self.assertEqual(r.context['doi_phuong']['vai_tro'], 'Khách hàng')  # nhãn đúng
        self.assertEqual(r.context['doi_phuong']['ho_so'], '')  # Khách hàng không có trang hồ sơ công khai
        self.assertContains(r, '<p class="chat__vai-tro">Khách hàng</p>')  # nhãn hiện đúng
        self.assertNotContains(r, '<p class="chat__vai-tro">Nhiếp ảnh gia</p>')  # không lẫn nhãn
        self.assertNotContains(r, 'Xem hồ sơ')  # không nút Xem hồ sơ (cột phải và menu ···)

    # ---- trường hợp 6: hộp thư trống theo vai trò ----
    def test_hop_thu_trong_cau_chu_theo_vai_tro(self):  # câu chữ khác nhau
        CuocTroChuyen.objects.all().delete()  # xóa hết cuộc trò chuyện
        self.client.force_login(self.khach)  # Khách hàng
        r = self.client.get(reverse('inbox'))  # hộp thư
        self.assertContains(r, 'Chưa có cuộc trò chuyện nào')  # tiêu đề dành cho Khách (cột phải)
        self.assertContains(r, 'Hãy tìm nhiếp ảnh gia để bắt đầu.')  # mô tả (cột phải)
        self.assertContains(r, 'Bạn chưa nhắn tin cho nhiếp ảnh gia nào.')  # mô tả (cột trái)
        self.assertNotContains(r, 'Chưa có khách hàng nào nhắn tin cho bạn')  # không lẫn câu của Nhiếp ảnh gia
        self.client.force_login(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia
        r = self.client.get(reverse('inbox'))  # hộp thư
        self.assertContains(r, 'Chưa có khách hàng nào nhắn tin cho bạn.')  # câu dành cho Nhiếp ảnh gia
        self.assertNotContains(r, 'Hãy tìm nhiếp ảnh gia')  # không lẫn câu của Khách
        self.assertNotContains(r, '>Tìm kiếm</a>')  # Nhiếp ảnh gia không có nút Tìm kiếm

    # ---- trường hợp 7 ----
    def test_hop_thu_chua_chon_cuoc_nao(self):  # cột giữa nhắc chọn cuộc
        for u in (self.khach, self.nag.MaTaiKhoan):  # cả hai vai trò
            self.client.force_login(u)  # đăng nhập
            r = self.client.get(reverse('inbox'))  # hộp thư
            self.assertContains(r, 'Chọn một cuộc trò chuyện')  # lời nhắc
            self.assertNotIn('aria-current="page"', _cot_trai(r.content.decode()))  # chưa dòng nào ở cột trái nổi bật (header vẫn có)

    # ---- trường hợp 9: cuộc mới chưa có tin ----
    def test_cuoc_chua_co_tin_cau_chao_theo_vai_tro(self):  # câu chữ khác nhau
        self.client.force_login(self.khach)  # Khách hàng
        r = self.client.get(self.url_trang)  # mở cuộc 1 (chưa có tin)
        self.assertContains(r, 'Hãy gửi lời chào đến nhiếp ảnh gia.')  # câu của Khách
        self.assertNotContains(r, 'Hãy gửi lời chào đến khách hàng.')  # không lẫn
        self.client.force_login(self.nag.MaTaiKhoan)  # Nhiếp ảnh gia
        r = self.client.get(self.url_trang)  # mở cuộc 1
        self.assertContains(r, 'Hãy gửi lời chào đến khách hàng.')  # câu của Nhiếp ảnh gia
        self.assertNotContains(r, 'Khách hàng chưa nhắn gì')  # không dùng câu cũ
        self.assertNotContains(r, 'Hãy gửi lời chào đến nhiếp ảnh gia.')  # không lẫn

    # ---- trường hợp 12, 14 ----
    def test_loi_gui_tin_dung_chu_wireframe(self):  # luồng 5a
        self.assertEqual(services.LOI_GUI_TIN, 'Không thể gửi tin nhắn. Vui lòng thử lại.')  # đúng wireframe Lỗi gửi tin

    def test_loi_tai_lich_su_khoa_o_nhap_va_co_thu_lai(self):  # luồng 2a UC8.3, cả hai vai trò
        for u in (self.khach, self.nag.MaTaiKhoan):  # đăng nhập lần lượt
            self.client.force_login(u)  # đăng nhập
            with mock.patch('chat.views.services.lay_tin_gan_nhat', side_effect=DatabaseError('hỏng')):  # ép lỗi DB
                r = self.client.get(self.url_trang)  # mở trang
            self.assertEqual(r.status_code, 200)  # không phải trang 500
            self.assertContains(r, 'Không thể tải lịch sử trao đổi')  # tiêu đề lỗi
            self.assertContains(r, '>Thử lại</a>')  # nút Thử lại
            self.assertContains(r, '>Quay lại danh sách</a>')  # nút Quay lại
            self.assertContains(r, 'chat__soan--khoa')  # ô nhập bị khóa theo wireframe
            self.assertContains(r, 'disabled')  # nút Gửi và ô nhập bị vô hiệu
            self.assertEqual(len(r.context['cac_cuoc']), 2)  # cột trái vẫn đủ danh sách

    def test_khong_tai_duoc_danh_sach_bao_loi_khong_noi_trong(self):  # lỗi cột trái
        for u in (self.khach, self.nag.MaTaiKhoan):  # cả hai vai trò
            self.client.force_login(u)  # đăng nhập
            with mock.patch('chat.services.danh_sach_cuoc', side_effect=DatabaseError('hỏng')):  # ép lỗi DB
                r = self.client.get(reverse('inbox'))  # hộp thư
            self.assertEqual(r.status_code, 200)  # trang vẫn hiện
            self.assertContains(r, services.LOI_TAI_LICH_SU)  # báo lỗi
            self.assertNotContains(r, 'chưa có cuộc trò chuyện nào')  # không nhầm với trường hợp trống
            self.assertNotContains(r, 'Chưa có khách hàng nào nhắn tin cho bạn')  # không nhầm với trường hợp trống

    # ---- trường hợp 16, 17 ----
    def test_cuoc_khong_ton_tai_va_cuoc_cua_nguoi_khac_cung_trang_404(self):  # không lộ cuộc có tồn tại
        self.client.force_login(self.khach)  # Khách hàng
        r_khong_co = self.client.get(reverse('chi_tiet_cuoc_tro_chuyen', args=[99999]))  # không tồn tại
        r_cua_nguoi = self.client.get(reverse('chi_tiet_cuoc_tro_chuyen', args=[self.cuoc_nag.pk]))  # của khach2 - nag1
        for r in (r_khong_co, r_cua_nguoi):  # cả hai
            self.assertEqual(r.status_code, 404)  # 404
            self.assertContains(r, 'Không tìm thấy cuộc trò chuyện', status_code=404)  # trang riêng của chat
            self.assertContains(r, 'Quay lại danh sách', status_code=404)  # có nút về hộp thư
        self.assertEqual(_bo_csrf(r_khong_co.content.decode()), _bo_csrf(r_cua_nguoi.content.decode()))  # giống hệt nhau (bỏ token CSRF)

    # ---- trường hợp 18 ----
    def test_co_san_cau_khong_tim_thay_khi_loc(self):  # chat.js hiện câu này khi lọc không ra
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.get(reverse('inbox'))  # hộp thư
        self.assertContains(r, 'data-chat-ds-trong')  # phần tử dành cho câu thông báo
        self.assertContains(r, 'Không tìm thấy cuộc trò chuyện phù hợp.')  # câu theo bảng trường hợp

    # ---- chỗ đặt hộp lỗi và dấu hiệu cho chat.js (nhóm tin, dòng ngày) ----
    def test_hop_loi_nam_tren_khung_chat_dung_wireframe(self):  # Lỗi gửi tin: hộp nét đứt ngay dưới đầu cuộc trò chuyện
        self.client.force_login(self.khach)  # đăng nhập
        html = self.client.get(self.url_trang).content.decode()  # mở trang
        self.assertLess(html.index('data-chat-loi'), html.index('class="chat__khung"'))  # hộp lỗi nằm trên khung tin
        self.assertIn('data-hom-nay="', html)  # ngày hôm nay để chat.js dựng dòng "Hôm nay"
        self.assertIn('data-chat-gui', html)  # nút Gửi để chat.js khóa khi ô trống

    def test_tin_nhan_co_du_data_cho_chat_js(self):  # chat.js nhóm tin theo người/ngày/phút
        self.tin(self.khach, 'a')  # tin của khách
        self.client.force_login(self.nag.MaTaiKhoan)  # nhiếp ảnh gia xem
        html = self.client.get(self.url_trang).content.decode()  # mở trang
        for dau_hieu in ('data-nguoi="doi"', 'data-ngay="', 'data-ts="'):  # các thuộc tính cần có
            self.assertIn(dau_hieu, html)  # có đủ
        d = self.client.get(self.url_moi + '?sau=0', **AJAX).json()  # qua JSON polling
        self.assertIn('data-ts="', d['tin_nhan'][0]['html'])  # tin polling cũng có đủ


class GioDanhSachTests(TestCase):  # filter gio_ds: 12:30 / Hôm qua / Thứ Hai / dd/mm/yyyy (wireframe cột trái)
    def test_cac_moc_thoi_gian(self):  # đủ 4 kiểu hiển thị
        import datetime  # tính lùi ngày
        from django.utils import timezone  # giờ địa phương
        from chat.templatetags.chat_tags import THU, gio_ds  # filter cần thử
        bay_gio = timezone.localtime()  # hiện tại
        self.assertEqual(gio_ds(bay_gio), bay_gio.strftime('%H:%M'))  # hôm nay: chỉ giờ
        self.assertEqual(gio_ds(bay_gio - datetime.timedelta(days=1)), 'Hôm qua')  # hôm qua
        ba_ngay = bay_gio - datetime.timedelta(days=3)  # 3 ngày trước
        self.assertEqual(gio_ds(ba_ngay), THU[ba_ngay.weekday()])  # trong tuần: tên thứ
        muoi_ngay = bay_gio - datetime.timedelta(days=10)  # 10 ngày trước
        self.assertEqual(gio_ds(muoi_ngay), muoi_ngay.strftime('%d/%m/%Y'))  # xa hơn: ngày đầy đủ
        self.assertEqual(gio_ds(None), '')  # không có giờ thì để trống

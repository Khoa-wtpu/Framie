# chat/test_trao_doi.py - P11 (UC8.2, UC8.3). Chạy: python manage.py test chat
import itertools  # bộ đếm để mỗi User có số điện thoại khác nhau
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
        self.assertContains(r, services.LOI_TAI_LICH_SU)  # hiện thông báo theo đặc tả

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
        self.assertContains(self.client.get(reverse('inbox')), 'Bạn chưa có cuộc trò chuyện nào')  # câu hướng dẫn
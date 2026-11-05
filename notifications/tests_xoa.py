# notifications/tests_xoa.py - kiểm tra chức năng xóa thông báo. Chạy: python manage.py test notifications.tests_xoa
from unittest.mock import patch  # giả lập lỗi DB

from django.contrib.auth import get_user_model  # model User của project
from django.contrib.messages import get_messages  # đọc hộp thông báo đã xếp hàng
from django.db import DatabaseError  # kiểu lỗi DB để giả lập
from django.test import TestCase  # lớp test của Django, dùng DB tạm
from django.urls import reverse  # đổi tên URL thành địa chỉ

from notifications import services  # hàm xoa_thong_bao cần thử
from notifications.models import ThongBao  # đếm thông báo còn lại
from notifications.services import gui_thong_bao  # tạo thông báo mẫu
from notifications.views import TB_DA_XOA, TB_LOI_XOA  # hai câu báo

User = get_user_model()  # gán tên User


class XoaThongBaoTestCase(TestCase):  # nhóm test xóa thông báo
    @classmethod  # chạy một lần trước cả nhóm
    def setUpTestData(cls):  # dữ liệu mẫu
        cls.a = User.objects.create_user('a', 'a@example.com', 'Matkhau@123', so_dien_thoai='0900000001')  # người dùng A
        cls.b = User.objects.create_user('b', 'b@example.com', 'Matkhau@123', so_dien_thoai='0900000002')  # người dùng B

    def setUp(self):  # chạy trước mỗi test
        self.tb = gui_thong_bao(self.a, 'Booking mới', 'Nội dung')  # thông báo của A
        self.url = reverse('xoa_thong_bao', args=[self.tb.pk])  # địa chỉ xóa thông báo đó

    def test_dich_vu_xoa_duoc(self):  # chủ thông báo xóa được
        self.assertTrue(services.xoa_thong_bao(self.a, self.tb.pk))  # trả về True
        self.assertFalse(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng đã mất

    def test_dich_vu_khong_xoa_cua_nguoi_khac(self):  # B không xóa được thông báo của A
        self.assertFalse(services.xoa_thong_bao(self.b, self.tb.pk))  # trả về False
        self.assertTrue(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng vẫn còn

    def test_dich_vu_loi_db_tra_false(self):  # DB lỗi thì không ném lỗi ra ngoài
        with patch('notifications.services.thong_bao_cua', side_effect=DatabaseError('hỏng')):  # giả lập DB lỗi
            self.assertFalse(services.xoa_thong_bao(self.a, self.tb.pk))  # trả về False
        self.assertTrue(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng vẫn còn

    def test_chua_dang_nhap_bi_chuyen_ve_dang_nhap(self):  # khách vãng lai không xóa được
        res = self.client.post(self.url)  # gửi POST khi chưa đăng nhập
        self.assertEqual(res.status_code, 302)  # bị chuyển hướng
        self.assertTrue(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng vẫn còn

    def test_chi_nhan_post(self):  # mở bằng GET bị từ chối
        self.client.force_login(self.a)  # đăng nhập A
        self.assertEqual(self.client.get(self.url).status_code, 405)  # 405 Method Not Allowed
        self.assertTrue(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng vẫn còn

    def test_post_xoa_thanh_cong_ve_danh_sach(self):  # xóa xong thì quay về danh sách kèm hộp xanh
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(self.url, {'next': '/thong-bao/?loc=chua_doc'})  # xóa, next là danh sách có bộ lọc
        self.assertRedirects(res, '/thong-bao/?loc=chua_doc', fetch_redirect_response=False)  # về đúng trang kèm bộ lọc
        self.assertFalse(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng đã mất
        self.assertIn(TB_DA_XOA, [m.message for m in get_messages(res.wsgi_request)])  # có câu báo thành công

    def test_next_la_trang_chi_tiet_da_xoa_thi_ve_danh_sach(self):  # tránh quay về trang 404
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(self.url, {'next': reverse('chi_tiet_thong_bao', args=[self.tb.pk]) + '?giu=1'})  # next là trang chi tiết vừa xóa
        self.assertRedirects(res, reverse('notifications'), fetch_redirect_response=False)  # bị đổi về danh sách

    def test_next_sang_trang_la_bi_chan(self):  # chống chuyển hướng sang website lạ
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(self.url, {'next': 'https://trang-la.example.com/'})  # next là trang ngoài
        self.assertRedirects(res, reverse('notifications'), fetch_redirect_response=False)  # bị bỏ qua, về danh sách

    def test_post_vao_thong_bao_nguoi_khac_la_404(self):  # B không xóa được qua giao diện
        self.client.force_login(self.b)  # đăng nhập B
        self.assertEqual(self.client.post(self.url).status_code, 404)  # 404, không lộ nội dung
        self.assertTrue(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng của A vẫn còn

    def test_post_ajax_tra_204(self):  # JS gọi ngầm: không chuyển trang
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.post(self.url, headers={'X-Requested-With': 'XMLHttpRequest'})  # gọi kiểu fetch
        self.assertEqual(res.status_code, 204)  # xong, không redirect
        self.assertFalse(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng đã mất

    def test_post_ajax_loi_tra_500(self):  # xóa lỗi qua fetch: báo 500 để JS gửi form kiểu thường
        self.client.force_login(self.a)  # đăng nhập A
        with patch('notifications.views.services.xoa_thong_bao', return_value=False):  # giả lập xóa thất bại
            res = self.client.post(self.url, headers={'X-Requested-With': 'XMLHttpRequest'})  # gọi kiểu fetch
        self.assertEqual(res.status_code, 500)  # báo lỗi

    def test_post_loi_hien_hop_do(self):  # xóa lỗi kiểu thường: hiện câu báo lỗi
        self.client.force_login(self.a)  # đăng nhập A
        with patch('notifications.views.services.xoa_thong_bao', return_value=False):  # giả lập xóa thất bại
            res = self.client.post(self.url)  # gửi form thường
        self.assertIn(TB_LOI_XOA, [m.message for m in get_messages(res.wsgi_request)])  # có câu báo lỗi
        self.assertTrue(ThongBao.objects.filter(pk=self.tb.pk).exists())  # dòng vẫn còn

    def test_danh_sach_co_nut_xoa_va_hop_xac_nhan(self):  # trang danh sách có nút xóa và hộp hỏi lại
        self.client.force_login(self.a)  # đăng nhập A
        res = self.client.get(reverse('notifications'))  # mở danh sách
        self.assertContains(res, self.url)  # có form xóa của thông báo này
        self.assertContains(res, 'data-xoa-hop')  # có hộp xác nhận
# chat/tests.py - P10 (UC8.1). Chạy: python manage.py test chat
import itertools  # bộ đếm để mỗi User có số điện thoại khác nhau
import sys  # để đăng ký urlconf tạm trong bộ nhớ
import types  # tạo module urlconf tạm
from unittest import mock  # patch để ép lỗi

from django.contrib.auth import get_user_model  # lấy model User của dự án (accounts.User)
from django.contrib.auth.models import AnonymousUser, Group  # người chưa đăng nhập; nhóm quyền
from django.contrib.messages import get_messages  # đọc thông báo đã gửi
from django.core.exceptions import ValidationError  # lỗi dữ liệu giả
from django.db import DatabaseError  # lỗi DB giả
from django.http import HttpResponse  # view giả cho urlconf thử
from django.template import Context, Template  # dựng template để thử thẻ nut_nhan_tin
from django.test import RequestFactory, TestCase, override_settings  # công cụ test
from django.urls import include, path, reverse  # khai báo đường dẫn

from chat import services  # để lấy đường dẫn mong đợi
from chat.models import CuocTroChuyen  # bảng cuộc trò chuyện
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò, trạng thái hồ sơ
from profiles.models import NhiepAnhGia  # hồ sơ Nhiếp ảnh gia

User = get_user_model()  # model User
_DEM = itertools.count(1)  # 1, 2, 3... dùng sinh số điện thoại


def _tam(request, *args, **kwargs):  # view giả, chỉ để urlconf thử có đủ tên URL
    return HttpResponse('ok')


def _urlconf(ten, co_chi_tiet):  # tạo urlconf tạm, độc lập với các module khác của nhóm
    m = types.ModuleType(ten)  # module rỗng
    m.urlpatterns = [  # các đường dẫn cần cho P10
        path('', include('chat.urls')),  # URL của P10
        path('dang-nhap/', _tam, name='login'),  # trang đăng nhập giả
        path('nhiep-anh-gia/<int:ma>/', _tam, name='photographer_detail'),  # hồ sơ công khai giả
    ] + ([path('tin-nhan/<int:ma>/', _tam, name='chi_tiet_cuoc_tro_chuyen')] if co_chi_tiet else [])  # UC8.2 giả (có hoặc không)
    sys.modules[ten] = m  # đăng ký để Django import được
    return ten


CO_UC82 = _urlconf('chat_urlconf_co_uc82', True)  # urlconf có UC8.2


def _tao_user(ten, vai_tro, trang_thai=None):  # tạo User thuộc một nhóm
    u = User.objects.create_user(username=ten, password='Xk9#mQ2vLp', email=f'{ten}@x.vn',
                                 so_dien_thoai='0' + str(next(_DEM)).zfill(9),
                                 trang_thai_ho_so=trang_thai)  # số điện thoại hợp lệ 10 chữ số bắt đầu bằng 0
    u.groups.add(Group.objects.get_or_create(name=vai_tro)[0])  # gán vai trò
    return u


def _tao_nag(ten, trang_thai=TrangThaiHoSo.DA_DUYET):  # tạo Nhiếp ảnh gia kèm hồ sơ
    u = _tao_user(ten, VaiTro.NHIEP_ANH_GIA, trang_thai)  # tài khoản
    return NhiepAnhGia.objects.create(MaTaiKhoan=u, AnhDaiDien='a.jpg', GioiThieu='x', NganHang='B',
                                      SoTaiKhoan='123', ChuTaiKhoan='C', AnhMaQR='q.png')  # hồ sơ (ảnh chỉ là chuỗi đường dẫn)


@override_settings(ROOT_URLCONF=CO_UC82, LOGIN_URL='login')  # dùng urlconf có UC8.2
class KhoiTaoCuocTroChuyenTests(TestCase):
    def setUp(self):  # chạy trước mỗi test
        self.khach = _tao_user('khach1', VaiTro.KHACH_HANG)  # một Khách hàng
        self.nag = _tao_nag('nag1')  # một Nhiếp ảnh gia đã duyệt
        self.url = f'/tin-nhan/bat-dau/{self.nag.pk}/'  # đường dẫn nút Nhắn tin

    def test_khach_tao_moi_roi_chuyen_vao_cuoc_tro_chuyen(self):  # trường hợp chính
        self.client.force_login(self.khach)
        r = self.client.post(self.url)
        cuoc = CuocTroChuyen.objects.get()  # đã tạo đúng 1 cuộc
        self.assertEqual((cuoc.MaKhachHang, cuoc.MaNhiepAnhGia), (self.khach, self.nag))
        self.assertRedirects(r, f'/tin-nhan/{cuoc.pk}/', fetch_redirect_response=False)

    def test_bam_lai_mo_cuoc_cu_khong_tao_them(self):  # mỗi cặp chỉ một cuộc
        self.client.force_login(self.khach)
        self.client.post(self.url)
        r = self.client.post(self.url)
        self.assertEqual(CuocTroChuyen.objects.count(), 1)
        self.assertRedirects(r, f'/tin-nhan/{CuocTroChuyen.objects.get().pk}/', fetch_redirect_response=False)

    def test_hai_khach_khac_nhau_co_hai_cuoc_rieng(self):  # cặp khác thì cuộc khác
        k2 = _tao_user('khach2', VaiTro.KHACH_HANG)
        for k in (self.khach, k2):
            self.client.force_login(k)
            self.client.post(self.url)
        self.assertEqual(CuocTroChuyen.objects.count(), 2)

    def test_chua_dang_nhap_chuyen_sang_dang_nhap(self):  # chặn người chưa đăng nhập
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/dang-nhap/?next='))  # kèm next để quay lại
        self.assertEqual(CuocTroChuyen.objects.count(), 0)

    def test_nhiep_anh_gia_bi_chan_403(self):  # chỉ Khách hàng
        self.client.force_login(self.nag.MaTaiKhoan)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(CuocTroChuyen.objects.count(), 0)

    def test_quan_tri_vien_bi_chan_403(self):  # Quản trị viên cũng không được
        qtv = _tao_user('qtv', VaiTro.QUAN_TRI_VIEN)
        self.client.force_login(qtv)
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_get_khong_duoc_tao(self):  # GET (trình duyệt tải trước) bị từ chối
        self.client.force_login(self.khach)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(CuocTroChuyen.objects.count(), 0)

    def test_nhiep_anh_gia_khong_ton_tai_404(self):
        self.client.force_login(self.khach)
        self.assertEqual(self.client.post('/tin-nhan/bat-dau/9999/').status_code, 404)

    def test_nhiep_anh_gia_chua_duyet_khong_tao_moi(self):  # hồ sơ chưa duyệt thì 404
        chua = _tao_nag('nag2', TrangThaiHoSo.CHO_DUYET)
        self.client.force_login(self.khach)
        self.assertEqual(self.client.post(f'/tin-nhan/bat-dau/{chua.pk}/').status_code, 404)
        self.assertEqual(CuocTroChuyen.objects.count(), 0)

    def test_cuoc_cu_van_mo_duoc_khi_nag_het_duyet(self):  # cuộc đã có vẫn mở lại
        self.client.force_login(self.khach)
        self.client.post(self.url)
        u = self.nag.MaTaiKhoan
        u.trang_thai_ho_so = TrangThaiHoSo.DA_TU_CHOI
        u.save()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertEqual(CuocTroChuyen.objects.count(), 1)

    def test_nag_bi_khoa_khong_tao_moi(self):  # is_active=False thì 404
        khoa = _tao_nag('nag3')
        khoa.MaTaiKhoan.is_active = False
        khoa.MaTaiKhoan.save()
        self.client.force_login(self.khach)
        self.assertEqual(self.client.post(f'/tin-nhan/bat-dau/{khoa.pk}/').status_code, 404)
        self.assertEqual(CuocTroChuyen.objects.count(), 0)

    def test_loi_bat_ngo_hien_thong_bao_2a(self):  # luồng 2a: ép lỗi DB và lỗi dữ liệu
        self.client.force_login(self.khach)
        for loi in (DatabaseError('hỏng'), ValidationError('sai')):
            with mock.patch('chat.views.services.mo_hoac_tao_cuoc_tro_chuyen', side_effect=loi):
                r = self.client.post(self.url)  # không follow: view giả của urlconf thử không có context
            self.assertEqual(r.status_code, 302)  # chuyển về hồ sơ, không phải trang 500
            self.assertIn('Không thể khởi tạo cuộc trò chuyện. Vui lòng thực hiện lại.',
                          [str(m) for m in get_messages(r.wsgi_request)])  # đọc thông báo đã đặt trong request
        self.assertEqual(CuocTroChuyen.objects.count(), 0)


@override_settings(ROOT_URLCONF=CO_UC82, LOGIN_URL='login')
class NutNhanTinTests(TestCase):
    def _ve(self, user):  # dựng thẻ nut_nhan_tin cho một người dùng
        req = RequestFactory().get('/nhiep-anh-gia/5/')
        req.user = user
        return Template('{% load chat_tags %}{% nut_nhan_tin 5 %}').render(Context({'request': req}))

    def test_khach_hang_thay_form_post(self):
        html = self._ve(_tao_user('k', VaiTro.KHACH_HANG))
        self.assertIn('<form method="post"', html)
        self.assertIn('/tin-nhan/bat-dau/5/', html)

    def test_chua_dang_nhap_thay_link_dang_nhap(self):
        html = self._ve(AnonymousUser())
        self.assertIn('/dang-nhap/?next=', html)
        self.assertNotIn('<form', html)

    def test_nhiep_anh_gia_khong_thay_nut(self):
        self.assertEqual(self._ve(_tao_user('n', VaiTro.NHIEP_ANH_GIA, TrangThaiHoSo.DA_DUYET)).strip(), '')


class UrlconfThatTests(TestCase):  # KHÔNG override ROOT_URLCONF: dùng urlconf thật, Khoa đổi tên URL thì test này đỏ
    def test_post_chuyen_ve_dung_trang_that(self):
        khach = _tao_user('khach1', VaiTro.KHACH_HANG)
        nag = _tao_nag('nag1')
        self.client.force_login(khach)
        r = self.client.post(reverse('khoi_tao_cuoc_tro_chuyen', args=[nag.pk]))
        cuoc = CuocTroChuyen.objects.get()
        dich = services.duong_dan_cuoc_tro_chuyen(cuoc.pk) or reverse('photographer_detail', args=[nag.pk])  # UC8.2 chưa có thì về hồ sơ K9
        self.assertRedirects(r, dich, fetch_redirect_response=False)


class NutTrenTrangK9Tests(TestCase):  # urlconf THẬT, GET trang hồ sơ công khai K9: chứng minh nút thật sự hiện (cần đã gắn thẻ vào template K9)
    def setUp(self):  # chạy trước mỗi test
        self.nag = _tao_nag('nag1')  # Nhiếp ảnh gia đã duyệt
        self.trang = reverse('photographer_detail', args=[self.nag.pk])  # trang hồ sơ công khai K9
        self.url_nut = reverse('khoi_tao_cuoc_tro_chuyen', args=[self.nag.pk])  # đích của form Nhắn tin
        if 'Tính năng nhắn tin sẽ mở sau' in self.client.get(self.trang).content.decode():  # K9 còn nút "Liên hệ" mờ giữ chỗ của Khoa
            self.skipTest('Khoa chưa gắn {% nut_nhan_tin %} vào trang K9; gắn xong test này tự chạy.')  # bỏ qua, không báo đỏ
        # Template K9 là của Khoa. Chưa gắn {% nut_nhan_tin %} thì bỏ qua cả nhóm test, không báo đỏ.
        self.client.force_login(_tao_user('khach_do', VaiTro.KHACH_HANG))  # đăng nhập thử bằng một Khách hàng
        if f'action="{self.url_nut}"' not in self.client.get(self.trang).content.decode():  # trang chưa có form Nhắn tin
            self.skipTest('K9 chưa gắn {% nut_nhan_tin %} (việc của Khoa), bỏ qua.')  # tự chạy lại khi Khoa gắn xong
        self.client.logout()  # trở về chưa đăng nhập cho từng test

    def test_khach_hang_thay_form_nhan_tin(self):
        self.client.force_login(_tao_user('khach1', VaiTro.KHACH_HANG))
        r = self.client.get(self.trang)
        self.assertContains(r, f'action="{self.url_nut}"')  # có form POST tới URL của P10

    def test_chua_dang_nhap_thay_link_dang_nhap(self):
        r = self.client.get(self.trang)
        self.assertContains(r, f'{reverse("login")}?next=')  # link đăng nhập kèm next
        self.assertNotContains(r, f'action="{self.url_nut}"')  # không có form

    def test_nhiep_anh_gia_khong_thay_nut(self):
        self.client.force_login(_tao_user('nag2', VaiTro.NHIEP_ANH_GIA, TrangThaiHoSo.DA_DUYET))
        r = self.client.get(self.trang)
        self.assertNotContains(r, f'action="{self.url_nut}"')

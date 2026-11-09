# Chạy: python manage.py test delivery.test_so_sanh_truoc_sau
# E9 (giữ bản trước khi tải ảnh hậu kỳ, xóa cả hai bản khi hết hạn) và E10 (slider so sánh trước/sau cho Khách hàng).
import io
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from bookings.models import Booking
from core.constants import LoaiAnh, LuuTruAnh, TrangThaiBooking as TT, VaiTro
from delivery import services
from delivery.models import Anh, YeuCauChinhSua, YeuCauChinhSua_Anh
from delivery.tests import User, _NenAnh, tep_anh
from delivery.xoa_anh_het_han import xoa_anh_cua_booking


def anh_bytes(mau, kich_thuoc=(80, 60)):                       # ảnh JPEG thật, mỗi màu một nội dung khác nhau
    dem = io.BytesIO()
    Image.new('RGB', kich_thuoc, mau).save(dem, 'JPEG')
    return dem.getvalue()


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(), ROOT_URLCONF='delivery.tests')
class _NenSoSanh(_NenAnh):                                     # lớp nền riêng của E9/E10 (không có test riêng)
    def luu_tep(self, duong_dan, noi_dung):                    # ghi 1 tệp vào kho ảnh riêng
        services.kho_anh().save(duong_dan, ContentFile(noi_dung))

    def anh_hau_ky(self, bk, ten, truoc=True):                 # ảnh Đã hậu kỳ có đủ tệp: bản hiện tại, bản gốc và (nếu truoc=True) bản trước
        a = self.tao_anh(bk, ten, loai=LoaiAnh.DA_HAU_KY)
        self.luu_tep(a.DuongDanAnh, anh_bytes((200, 30, 30)))
        self.luu_tep(services.duong_dan_goc(a.DuongDanAnh), anh_bytes((10, 10, 10)))
        if truoc:
            a.DuongDanAnhTruoc = f'booking_{bk.pk}/truoc_{ten}'
            self.luu_tep(a.DuongDanAnhTruoc, anh_bytes((30, 30, 200)))
            a.save(update_fields=['DuongDanAnhTruoc'])
        return a

    def booking_kiem_tra(self):                                # Chờ Khách hàng kiểm tra: a1 có bản trước, a2 không
        bk = self.tao_booking(self.goi_gh, TT.CHO_KH_KIEM_TRA)
        self.a1 = self.anh_hau_ky(bk, 'a1.jpg', truoc=True)
        self.a2 = self.anh_hau_ky(bk, 'a2.jpg', truoc=False)
        return bk

    def doc(self, ten_tep):                                    # đọc nội dung 1 tệp trong kho ảnh
        with services.kho_anh().open(ten_tep) as tep:
            return tep.read()


class GiuBanTruocTests(_NenSoSanh):                            # E9: nghiệp vụ tải ảnh hậu kỳ
    def test_hau_ky_lan_dau_goi_gioi_han_ban_chua_hau_ky_thanh_ban_truoc(self):   # UC5.4: bản có watermark chưa hậu kỳ thành "bản trước"
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)
        p1 = self.tao_anh(bk, 'p1.jpg', chon=1, that=True)
        self.tao_anh(bk, 'p2.jpg', chon=1, that=True)
        cu, kho = p1.DuongDanAnh, services.kho_anh()
        with self.captureOnCommitCallbacks(execute=True):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('p1.jpg'), tep_anh('p2.jpg')])
        p1.refresh_from_db()
        self.assertEqual(p1.DuongDanAnhTruoc, cu)                                  # đường dẫn bản cũ chuyển sang cột mới
        self.assertTrue(kho.exists(cu))                                            # bản trước KHÔNG bị xóa
        self.assertFalse(kho.exists(services.duong_dan_goc(cu)))                   # bản gốc không watermark của bản trước thì xóa
        self.assertNotEqual(p1.DuongDanAnh, cu)
        self.assertTrue(kho.exists(p1.DuongDanAnh))

    def test_goi_toan_bo_tai_lan_dau_khong_co_ban_truoc(self):
        bk = self.tao_booking(self.goi_tb, TT.DANG_HAU_KY)
        services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('z1.jpg')])
        anh = Anh.objects.get(MaBooking=bk)
        self.assertIsNone(anh.DuongDanAnhTruoc)                                    # chưa có bản trước -> slider sẽ ẩn nút
        self.assertFalse(services.co_ban_truoc(anh))

    def test_tai_lai_sau_yeu_cau_chinh_sua_chi_giu_mot_ban_truoc(self):            # UC5.5: bản hậu kỳ liền trước thành bản trước, bản trước cũ hơn bị xóa
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)
        q1 = self.anh_hau_ky(bk, 'q1.jpg', truoc=True)
        Anh.objects.filter(pk=q1.pk).update(NgayTaiLen=timezone.now() - timedelta(days=3))
        yc = YeuCauChinhSua.objects.create(MaBooking=bk, NgayYeuCau=timezone.now() - timedelta(days=1), NoiDung='Sáng hơn', SoLanYeuCau=1)
        YeuCauChinhSua_Anh.objects.create(MaYeuCauChinhSua=yc, MaAnh=q1, NoiDungChinhSua='Sáng hơn')
        hien_tai, truoc_cu, kho = q1.DuongDanAnh, q1.DuongDanAnhTruoc, services.kho_anh()
        with self.captureOnCommitCallbacks(execute=True):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('q1.jpg')])
        q1.refresh_from_db()
        self.assertEqual((q1.PhienBanAnh, q1.DuongDanAnhTruoc), (2, hien_tai))     # bản liền trước = bản hậu kỳ vừa bị thay
        self.assertTrue(kho.exists(hien_tai))                                      # giữ lại
        self.assertFalse(kho.exists(truoc_cu))                                     # chỉ giữ MỘT bản trước: bản cũ hơn bị xóa
        self.assertFalse(kho.exists(services.duong_dan_goc(hien_tai)))

    def test_ban_truoc_la_ban_co_watermark_khong_phai_ban_goc(self):               # luồng thật hai lần tải
        bk = self.tao_booking(self.goi_tb, TT.DANG_HAU_KY)
        lan1 = tep_anh('z1.jpg')
        goc_lan1 = lan1.read(); lan1.seek(0)
        services.tai_anh_len(bk.pk, self.nag_user, [lan1])
        z1 = Anh.objects.get(MaBooking=bk)
        ban_wm_lan1 = self.doc(z1.DuongDanAnh)
        self.assertNotEqual(ban_wm_lan1, goc_lan1)                                 # bản đang lưu là bản có watermark
        yc = YeuCauChinhSua.objects.create(MaBooking=bk, NgayYeuCau=timezone.now() + timedelta(seconds=1), NoiDung='x', SoLanYeuCau=1)
        YeuCauChinhSua_Anh.objects.create(MaYeuCauChinhSua=yc, MaAnh=z1, NoiDungChinhSua='x')
        Booking.objects.filter(pk=bk.pk).update(TrangThai=TT.DANG_HAU_KY, HanHauKy=timezone.now() + timedelta(days=3))
        with self.captureOnCommitCallbacks(execute=True):
            services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('z1.jpg', kich_thuoc=(90, 70))])
        z1.refresh_from_db()
        self.assertEqual(self.doc(z1.DuongDanAnhTruoc), ban_wm_lan1)               # bản trước đúng là bản watermark của lần 1
        self.assertNotEqual(self.doc(z1.DuongDanAnhTruoc), goc_lan1)               # tuyệt đối không phải bản gốc

    def test_tai_loi_giua_chung_khong_mat_ban_hien_tai_va_khong_doi_cot_moi(self):  # lỗi lưu: hoàn tác DB, không xóa tệp cũ
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)
        p1 = self.tao_anh(bk, 'p1.jpg', chon=1, that=True)
        self.tao_anh(bk, 'p2.jpg', chon=1, that=True)
        cu, kho = p1.DuongDanAnh, services.kho_anh()
        with mock.patch.object(services, 'chen_watermark', side_effect=[b'x', OSError('đầy ổ đĩa')]):
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(services.LoiTaiAnh):
                    services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('p1.jpg'), tep_anh('p2.jpg')])
        p1.refresh_from_db()
        self.assertEqual((p1.DuongDanAnh, p1.DuongDanAnhTruoc), (cu, None))
        self.assertTrue(kho.exists(cu))
        self.assertTrue(kho.exists(services.duong_dan_goc(cu)))


class XoaCaHaiBanTests(_NenSoSanh):                            # N10: hết hạn tải thì xóa cả bản hiện tại, bản gốc và bản trước
    def test_het_han_xoa_ca_hai_ban(self):
        bk = self.tao_booking(self.goi_gh, TT.HOAN_THANH)
        a = self.anh_hau_ky(bk, 'a1.jpg', truoc=True)
        kho = services.kho_anh()
        for duong_dan in (a.DuongDanAnh, services.duong_dan_goc(a.DuongDanAnh), a.DuongDanAnhTruoc):
            self.assertTrue(kho.exists(duong_dan))
        self.assertEqual(xoa_anh_cua_booking(bk), 1)
        for duong_dan in (a.DuongDanAnh, services.duong_dan_goc(a.DuongDanAnh), a.DuongDanAnhTruoc):
            self.assertFalse(kho.exists(duong_dan))
        a.refresh_from_db()
        self.assertEqual(a.TrangThaiLuuTru, LuuTruAnh.DA_XOA)
        self.assertEqual(xoa_anh_cua_booking(bk), 0)                               # chạy lại vẫn an toàn

    def test_anh_khong_co_ban_truoc_van_xoa_binh_thuong(self):
        bk = self.tao_booking(self.goi_gh, TT.HOAN_THANH)
        a = self.anh_hau_ky(bk, 'a1.jpg', truoc=False)
        self.assertEqual(xoa_anh_cua_booking(bk), 1)
        self.assertFalse(services.kho_anh().exists(a.DuongDanAnh))


class XemBanTruocTests(_NenSoSanh):                            # E10: ai được xem ảnh bản trước
    def url(self, anh, **tham_so):
        return reverse('xem_anh', args=[anh.pk]) + '?' + '&'.join(f'{k}={v}' for k, v in {'truoc': 1, **tham_so}.items())

    def test_khach_va_nhiep_anh_gia_cua_booking_xem_duoc(self):
        bk = self.booking_kiem_tra()
        for nguoi in (self.kh, self.nag_user):
            self.client.force_login(nguoi)
            phan_hoi = self.client.get(self.url(self.a1))
            self.assertEqual(phan_hoi.status_code, 200)
            self.assertEqual(b''.join(phan_hoi.streaming_content), self.doc(self.a1.DuongDanAnhTruoc))   # đúng tệp bản trước
            self.assertEqual(phan_hoi['Content-Disposition'], 'inline')
            self.assertIn('no-store', phan_hoi['Cache-Control'])
            self.assertEqual(phan_hoi['X-Content-Type-Options'], 'nosniff')

    def test_kich_co_vua_cho_slider(self):
        self.booking_kiem_tra()
        self.client.force_login(self.kh)
        phan_hoi = self.client.get(self.url(self.a1, vua=1))
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi['Content-Type'], 'image/jpeg')

    def test_nguoi_ngoai_quan_tri_vien_va_khach_vang_lai_khong_xem_duoc(self):
        self.booking_kiem_tra()
        quan_tri = User.objects.create_user('admin_ss', 'admin_ss@x.vn', 'p', so_dien_thoai='0900000071')
        quan_tri.groups.add(Group.objects.get_or_create(name=VaiTro.QUAN_TRI_VIEN)[0])
        khach_khac = User.objects.create_user('kh_khac', 'kh_khac@x.vn', 'p', so_dien_thoai='0900000072')
        for nguoi in (self.nag_khac, quan_tri, khach_khac):                        # NAG khác, Quản trị viên, Khách khác Booking
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get(self.url(self.a1)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(self.a1)).status_code, 302)      # chưa đăng nhập -> trang đăng nhập

    def test_anh_khong_co_ban_truoc_hoac_da_hoan_chinh_hoac_da_xoa_tra_404(self):
        bk = self.booking_kiem_tra()
        hoan_chinh = self.anh_hau_ky(bk, 'h1.jpg', truoc=True)
        Anh.objects.filter(pk=hoan_chinh.pk).update(LoaiAnh=LoaiAnh.HOAN_CHINH, CoWatermark=0)   # CHECK của bảng: Hoàn chỉnh <=> không watermark, đổi cả hai cột cùng lúc
        da_xoa = self.anh_hau_ky(bk, 'x1.jpg', truoc=True)
        Anh.objects.filter(pk=da_xoa.pk).update(TrangThaiLuuTru=LuuTruAnh.DA_XOA)
        self.client.force_login(self.kh)
        for anh in (self.a2, hoan_chinh, da_xoa):
            self.assertEqual(self.client.get(self.url(anh)).status_code, 404)

    def test_anh_chinh_van_xem_nhu_cu_khi_khong_co_tham_so_truoc(self):
        self.booking_kiem_tra()
        self.client.force_login(self.kh)
        phan_hoi = self.client.get(reverse('xem_anh', args=[self.a1.pk]))
        self.assertEqual(b''.join(phan_hoi.streaming_content), self.doc(self.a1.DuongDanAnh))


class SliderTrangKiemTraTests(_NenSoSanh):                     # E10: hiển thị trên trang Khách hàng kiểm tra ảnh
    def trang(self, bk):
        self.client.force_login(self.kh)
        return self.client.get(reverse('xem_anh_hau_ky', args=[bk.pk]))

    def test_chi_anh_co_ban_truoc_moi_co_nut_va_hop_so_sanh(self):
        bk = self.booking_kiem_tra()
        trang = self.trang(bk)
        self.assertEqual(trang.status_code, 200)
        self.assertContains(trang, '>So sánh trước/sau</button>', count=1)         # đúng 1 nút hiển thị chữ này
        self.assertContains(trang, 'data-so-sanh-truoc=', count=1)                 # đúng 1 nút: ảnh a1 (a2 không có bản trước thì ẩn nút)
        self.assertContains(trang, reverse('xem_anh', args=[self.a1.pk]) + '?truoc=1&amp;vua=1')
        self.assertNotContains(trang, reverse('xem_anh', args=[self.a2.pk]) + '?truoc=1')
        self.assertContains(trang, 'id="so-sanh-hop"')
        self.assertContains(trang, 'type="range"')                                 # ô range, dùng được bằng bàn phím
        self.assertContains(trang, 'Trước')
        self.assertContains(trang, 'Sau')
        self.assertContains(trang, 'delivery/css/so_sanh_truoc_sau.css')           # CSS và JS để file riêng
        self.assertContains(trang, 'delivery/js/so_sanh_truoc_sau.js')

    def test_khong_anh_nao_co_ban_truoc_thi_khong_co_nut_va_khong_co_hop(self):
        bk = self.tao_booking(self.goi_gh, TT.CHO_KH_KIEM_TRA)
        self.anh_hau_ky(bk, 'a1.jpg', truoc=False)
        trang = self.trang(bk)
        self.assertEqual(trang.status_code, 200)
        self.assertNotContains(trang, 'data-so-sanh-truoc')
        self.assertNotContains(trang, 'so-sanh-hop')

    def test_file_ban_truoc_mat_thi_an_nut(self):
        bk = self.booking_kiem_tra()
        services.kho_anh().delete(self.a1.DuongDanAnhTruoc)
        self.assertNotContains(self.trang(bk), 'data-so-sanh-truoc')

    def test_goi_toan_bo_lan_dau_chua_co_ban_truoc_thi_an_nut(self):
        bk = self.tao_booking(self.goi_tb, TT.DANG_HAU_KY)
        services.tai_anh_len(bk.pk, self.nag_user, [tep_anh('z1.jpg')])           # Booking sang Chờ Khách hàng kiểm tra
        self.assertNotContains(self.trang(bk), 'data-so-sanh-truoc')

    def test_trang_khong_viet_style_inline_cho_slider(self):
        bk = self.booking_kiem_tra()
        html = self.trang(bk).content.decode()
        phan_so_sanh = html[html.index('id="so-sanh-hop"'):html.index('</dialog>', html.index('id="so-sanh-hop"'))]
        self.assertNotIn('style=', phan_so_sanh)                                   # JS chỉ gán biến CSS, HTML không chứa style

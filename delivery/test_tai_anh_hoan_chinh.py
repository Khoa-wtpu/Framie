# Chạy: python manage.py test delivery.test_tai_anh_hoan_chinh      (N10: UC5.8 Khách hàng tải về thiết bị ảnh hoàn chỉnh)
import io
import zipfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone

from core.constants import KetQuaTaiAnh, LoaiAnh, LuuTruAnh, TrangThaiBooking as TT
from delivery import services
from delivery import services_tai_anh as dich_vu
from delivery.models import Anh, BanGiao, LichSuTaiAnh
from delivery.tests import _NenAnh, urlpatterns                  # noqa: F401  (urlpatterns: bảng URL test của delivery)


class _NenTaiHoanChinh(_NenAnh):                               # Booking Hoàn thành + ảnh Hoàn chỉnh có tệp thật
    def booking_hoan_thanh(self, con_han=True, co_ban_giao=True):
        bk = self.tao_booking(self.goi_tb, TT.HOAN_THANH)
        if co_ban_giao:
            BanGiao.objects.create(
                MaBooking=bk, NgayXacNhan=timezone.now() - timedelta(days=4),
                ThoiHanTaiAnh=timezone.now() + timedelta(days=2) if con_han else timezone.now() - timedelta(hours=1))
        return bk

    def anh_hoan_chinh(self, bk, ten, noi_dung=None):          # ảnh Hoàn chỉnh: DuongDanAnh trỏ vào bản không watermark (thư mục goc)
        duong_dan = services.duong_dan_goc(f'booking_{bk.pk}/{ten}')
        noi_dung = noi_dung or f'day-du-{ten}'.encode()
        services.kho_anh().save(duong_dan, ContentFile(noi_dung))
        return Anh.objects.create(MaBooking=bk, TenAnh=ten, DuongDanAnh=duong_dan, DinhDangAnh='JPG', KichThuocAnh=len(noi_dung),
                                  LoaiAnh=LoaiAnh.HOAN_CHINH, CoWatermark=0)


class TaiHoanChinhServiceTests(_NenTaiHoanChinh):              # nghiệp vụ UC5.8
    def test_tai_mot_anh_tra_thang_tep_va_ghi_lich_su_thanh_cong(self):
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        kq = dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])
        with kq['tep']:
            self.assertEqual(kq['tep'].read(), b'day-du-a1.jpg')   # đúng bản không watermark
        self.assertEqual((kq['ten_tep'], kq['content_type'], kq['so_anh']), ('a1.jpg', 'image/jpeg', 1))
        ls = LichSuTaiAnh.objects.get()
        self.assertEqual((ls.MaAnh, ls.MaKhachHang, ls.KetQuaTaiAnh), (a, self.kh, KetQuaTaiAnh.THANH_CONG))

    def test_tai_nhieu_anh_thanh_mot_tep_zip_moi_anh_mot_dong_lich_su(self):
        bk = self.booking_hoan_thanh()
        a1, a2 = self.anh_hoan_chinh(bk, 'a1.jpg'), self.anh_hoan_chinh(bk, 'a2.jpg')
        kq = dich_vu.chuan_bi_tai(bk.pk, self.kh, [a1.pk, a2.pk])
        with kq['tep']:
            zf = zipfile.ZipFile(io.BytesIO(kq['tep'].read()))
        self.assertEqual((kq['content_type'], sorted(zf.namelist())), ('application/zip', ['a1.jpg', 'a2.jpg']))
        self.assertEqual(zf.read('a2.jpg'), b'day-du-a2.jpg')
        self.assertEqual(LichSuTaiAnh.objects.filter(KetQuaTaiAnh=KetQuaTaiAnh.THANH_CONG).count(), 2)

    def test_tai_tat_ca(self):
        bk = self.booking_hoan_thanh()
        for ten in ('a1.jpg', 'a2.jpg', 'a3.jpg'):
            self.anh_hoan_chinh(bk, ten)
        kq = dich_vu.chuan_bi_tai(bk.pk, self.kh, None)
        kq['tep'].close()
        self.assertEqual((kq['so_anh'], LichSuTaiAnh.objects.count()), (3, 3))

    def test_ten_trung_trong_zip_khong_de_len_nhau(self):
        bk = self.booking_hoan_thanh()
        a1 = self.anh_hoan_chinh(bk, 'a.jpg')
        a2 = Anh.objects.create(MaBooking=bk, TenAnh='a.jpg', DuongDanAnh=services.duong_dan_goc(f'booking_{bk.pk}/a_khac.jpg'),
                                DinhDangAnh='JPG', KichThuocAnh=5, LoaiAnh=LoaiAnh.HOAN_CHINH, CoWatermark=0)
        services.kho_anh().save(a2.DuongDanAnh, ContentFile(b'khac'))
        kq = dich_vu.chuan_bi_tai(bk.pk, self.kh, [a1.pk, a2.pk])
        with kq['tep']:
            self.assertEqual(len(zipfile.ZipFile(io.BytesIO(kq['tep'].read())).namelist()), 2)

    def test_chua_hoan_thanh_bi_chan(self):
        bk = self.tao_booking(self.goi_tb, TT.CHO_XAC_NHAN_THANH_TOAN)
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'Chỉ Booking đã hoàn thành'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])
        self.assertFalse(LichSuTaiAnh.objects.exists())

    def test_chua_mo_quyen_tai_bi_chan(self):
        bk = self.booking_hoan_thanh(co_ban_giao=False)
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'chưa được mở quyền tải'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])

    def test_qua_han_luu_tru_4a(self):                         # quá 3 ngày, dù file chưa kịp bị xóa
        bk = self.booking_hoan_thanh(con_han=False)
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'hết thời hạn lưu trữ'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])
        self.assertFalse(LichSuTaiAnh.objects.exists())

    def test_anh_da_bi_xoa_4a_va_lich_su_van_con(self):
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])['tep'].close()
        Anh.objects.filter(pk=a.pk).update(TrangThaiLuuTru=LuuTruAnh.DA_XOA)   # việc quá hạn đã xóa file
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'hết thời hạn lưu trữ'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])
        self.assertEqual(LichSuTaiAnh.objects.count(), 1)      # lịch sử được giữ

    def test_khach_khac_bi_chan(self):
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'không thuộc về bạn'):
            dich_vu.chuan_bi_tai(bk.pk, self.nag_user, [a.pk])

    def test_ma_anh_khong_hop_le_va_chua_chon_anh_nao(self):
        bk = self.booking_hoan_thanh()
        self.anh_hoan_chinh(bk, 'a1.jpg')
        hau_ky = self.tao_anh(bk, 'h.jpg', loai=LoaiAnh.DA_HAU_KY, that=True)   # ảnh còn watermark không được tải ở đây
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'không hợp lệ'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [hau_ky.pk])
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'ít nhất một ảnh'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [])

    def test_mat_tep_thi_ghi_that_bai_roi_tai_lai_duoc(self):   # ngoại lệ 5a
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        services.kho_anh().delete(a.DuongDanAnh)               # giả lập mất tệp / lỗi ổ đĩa
        with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'thử tải lại'):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])
        self.assertEqual(LichSuTaiAnh.objects.get().KetQuaTaiAnh, KetQuaTaiAnh.THAT_BAI)
        services.kho_anh().save(a.DuongDanAnh, ContentFile(b'da-khoi-phuc'))   # sự cố hết, Khách bấm tải lại
        dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])['tep'].close()
        self.assertEqual(sorted(LichSuTaiAnh.objects.values_list('KetQuaTaiAnh', flat=True)),
                         sorted([KetQuaTaiAnh.THAT_BAI, KetQuaTaiAnh.THANH_CONG]))

    def test_zip_thieu_mot_tep_thi_ca_lan_that_bai(self):
        bk = self.booking_hoan_thanh()
        a1, a2 = self.anh_hoan_chinh(bk, 'a1.jpg'), self.anh_hoan_chinh(bk, 'a2.jpg')
        services.kho_anh().delete(a2.DuongDanAnh)
        with self.assertRaises(dich_vu.LoiTaiHoanChinh):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a1.pk, a2.pk])
        self.assertEqual(LichSuTaiAnh.objects.filter(KetQuaTaiAnh=KetQuaTaiAnh.THAT_BAI).count(), 2)

    def test_duong_dan_ngoai_kho_anh_bi_chan(self):
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        Anh.objects.filter(pk=a.pk).update(DuongDanAnh='../ngoai_kho.txt')
        with self.assertRaises(dich_vu.LoiTaiHoanChinh):
            dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])
        self.assertEqual(LichSuTaiAnh.objects.get().KetQuaTaiAnh, KetQuaTaiAnh.THAT_BAI)

    def test_khong_ghi_duoc_lich_su_thi_khong_cho_tai(self):
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        with mock.patch.object(LichSuTaiAnh.objects, 'bulk_create', side_effect=DatabaseError('hỏng')):
            with self.assertRaisesMessage(dich_vu.LoiTaiHoanChinh, 'thử tải lại'):
                dich_vu.chuan_bi_tai(bk.pk, self.kh, [a.pk])


class TaiHoanChinhViewTests(_NenTaiHoanChinh):                 # view UC5.8
    def url(self, bk):
        return reverse('tai_anh_hoan_chinh', args=[bk.pk])

    def test_get_hien_danh_sach_anh_han_tai_va_nut_tai(self):
        bk = self.booking_hoan_thanh()
        self.anh_hoan_chinh(bk, 'a1.jpg')
        self.client.force_login(self.kh)
        r = self.client.get(self.url(bk))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Tải ảnh hoàn chỉnh')
        self.assertContains(r, 'a1.jpg')
        self.assertContains(r, 'Tải tất cả')
        self.assertContains(r, 'không có watermark')

    def test_get_het_han_hien_thong_bao_va_khong_co_nut_tai(self):   # ngoại lệ 4a
        bk = self.booking_hoan_thanh(con_han=False)
        self.anh_hoan_chinh(bk, 'a1.jpg')
        self.client.force_login(self.kh)
        r = self.client.get(self.url(bk))
        self.assertContains(r, 'hết thời hạn lưu trữ')
        self.assertNotContains(r, 'Tải tất cả')

    def test_get_chua_hoan_thanh(self):
        bk = self.tao_booking(self.goi_tb, TT.CHO_XAC_NHAN_THANH_TOAN)
        self.client.force_login(self.kh)
        r = self.client.get(self.url(bk))
        self.assertContains(r, 'Chỉ Booking đã hoàn thành')
        self.assertNotContains(r, 'Tải tất cả')

    def test_phan_quyen(self):
        bk = self.booking_hoan_thanh()
        self.client.force_login(self.nag_user)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 403)       # Nhiếp ảnh gia không vào được
        self.client.logout()
        r = self.client.get(self.url(bk))
        self.assertEqual(r.status_code, 302)                                   # chưa đăng nhập
        self.assertIn('/dang-nhap/', r['Location'])

    def test_post_tai_mot_anh_tra_tep_dinh_kem(self):
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'tai_mot': a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('a1.jpg', r['Content-Disposition'])
        self.assertEqual(b''.join(r.streaming_content), b'day-du-a1.jpg')
        self.assertIn('no-store', r['Cache-Control'])
        self.assertEqual(LichSuTaiAnh.objects.filter(KetQuaTaiAnh=KetQuaTaiAnh.THANH_CONG).count(), 1)

    def test_post_tai_chon_nhieu_anh_tra_zip(self):
        bk = self.booking_hoan_thanh()
        a1, a2 = self.anh_hoan_chinh(bk, 'a1.jpg'), self.anh_hoan_chinh(bk, 'a2.jpg')
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'tai_chon': '1', 'anh': [a1.pk, a2.pk]})
        self.assertEqual(r['Content-Type'], 'application/zip')
        self.assertEqual(len(zipfile.ZipFile(io.BytesIO(b''.join(r.streaming_content))).namelist()), 2)

    def test_post_tai_tat_ca(self):
        bk = self.booking_hoan_thanh()
        self.anh_hoan_chinh(bk, 'a1.jpg')
        self.anh_hoan_chinh(bk, 'a2.jpg')
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'tai_tat_ca': '1'})
        self.assertEqual(r['Content-Type'], 'application/zip')

    def test_post_khong_chon_anh_o_lai_trang_va_bao_loi(self):
        bk = self.booking_hoan_thanh()
        self.anh_hoan_chinh(bk, 'a1.jpg')
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'tai_chon': '1'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vui lòng chọn ít nhất một ảnh')
        self.assertFalse(LichSuTaiAnh.objects.exists())

    def test_post_loi_tai_hien_thong_bao_lich_su_that_bai_va_cho_tai_lai(self):   # ngoại lệ 5a
        bk = self.booking_hoan_thanh()
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        services.kho_anh().delete(a.DuongDanAnh)
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'tai_mot': a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vui lòng thử tải lại.')
        self.assertContains(r, 'Tải ảnh thất bại')              # hiện trong "Lịch sử tải gần đây"
        self.assertContains(r, 'Tải tất cả')                    # vẫn còn nút để tải lại

    def test_post_het_han_bi_chan_khong_tra_tep(self):
        bk = self.booking_hoan_thanh(con_han=False)
        a = self.anh_hoan_chinh(bk, 'a1.jpg')
        self.client.force_login(self.kh)
        r = self.client.post(self.url(bk), {'tai_mot': a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'hết thời hạn lưu trữ')
        self.assertFalse(LichSuTaiAnh.objects.exists())

    def test_post_thao_tac_la_va_ma_anh_sai_kieu(self):
        bk = self.booking_hoan_thanh()
        self.anh_hoan_chinh(bk, 'a1.jpg')
        self.client.force_login(self.kh)
        self.assertContains(self.client.post(self.url(bk), {'xoa_het': '1'}), 'Thao tác không hợp lệ.')
        self.assertContains(self.client.post(self.url(bk), {'tai_mot': 'abc'}), 'Thao tác không hợp lệ.')

    def test_booking_cua_nguoi_khac_la_404(self):
        bk = self.booking_hoan_thanh()
        khac = get_user_model().objects.create_user('kh9', 'kh9@x.vn', 'p', so_dien_thoai='0900000099')
        self.client.force_login(khac)
        self.assertEqual(self.client.get(self.url(bk)).status_code, 404)

# Chạy: python manage.py test delivery.test_ghep_anh
# Ghép ảnh hậu kỳ với ảnh cần sửa THEO HÌNH ẢNH (delivery/ghep_anh.py) + chọn tay ảnh chưa ghép được.
# Phần 1 (GhepAnhThuanTests) không cần Django, có thể chạy riêng: python -m unittest delivery.test_ghep_anh.GhepAnhThuanTests
import io
import json
import random
import unittest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from core.constants import LoaiAnh, TrangThaiBooking as TT
from delivery import ghep_anh, services
from delivery.models import Anh
from delivery.tests import _NenAnh


def canh(seed, kich_thuoc=(600, 400)):                         # "cảnh chụp" giả: nhiều hình màu mờ, mỗi seed một cảnh khác nhau
    r = random.Random(seed)
    hinh = Image.new('RGB', kich_thuoc, tuple(r.randint(0, 255) for _ in range(3)))
    ve = ImageDraw.Draw(hinh)
    for _ in range(25):
        x, y, w, h = r.randint(0, kich_thuoc[0]), r.randint(0, kich_thuoc[1]), r.randint(30, 250), r.randint(30, 200)
        (ve.ellipse if r.random() < .5 else ve.rectangle)([x, y, x + w, y + h], fill=tuple(r.randint(0, 255) for _ in range(3)))
    return hinh.filter(ImageFilter.GaussianBlur(4))


def sua(hinh, kieu):                                           # giả lập Nhiếp ảnh gia hậu kỳ
    if kieu == 'sang':
        return ImageEnhance.Brightness(hinh).enhance(1.4)
    if kieu == 'den_trang':
        return ImageOps.grayscale(hinh).convert('RGB')
    if kieu == 'min_da':
        return hinh.filter(ImageFilter.GaussianBlur(2))
    return ImageEnhance.Color(ImageEnhance.Brightness(hinh).enhance(0.8)).enhance(1.8)   # đổi tông màu mạnh


def jpeg(hinh):                                                # ảnh -> bytes JPEG
    dem = io.BytesIO()
    hinh.convert('RGB').save(dem, 'JPEG', quality=90)
    return dem.getvalue()


def dau(hinh):
    return ghep_anh.tao_dau_van_tay(io.BytesIO(jpeg(hinh)))


class GhepAnhThuanTests(unittest.TestCase):                    # thuật toán thuần, không đụng database
    def test_ghep_dung_du_bi_chinh_sang_mau_va_xao_tron(self):
        for lan in range(10):
            r = random.Random(lan)
            n = r.randint(2, 8)
            goc = [canh(lan * 100 + i) for i in range(n)]
            moi_hinh = [sua(h, r.choice(['sang', 'den_trang', 'min_da', 'mau'])) for h in goc]
            hoan_vi = list(range(n))
            r.shuffle(hoan_vi)
            cap, chua, _ = ghep_anh.ghep([dau(moi_hinh[p]) for p in hoan_vi], [dau(h) for h in goc])
            self.assertEqual(chua, [], f'lần {lan}: còn ảnh chưa ghép')
            self.assertEqual(cap, {i: hoan_vi[i] for i in range(n)}, f'lần {lan}: ghép sai')

    def test_anh_chup_lien_tiep_gan_giong_nhau_khong_ghep_bua(self):
        goc = canh(999)
        loat = [goc.transform(goc.size, Image.AFFINE, (1, 0, dx, 0, 1, 0)) for dx in (0, 6, 12)]
        cap, chua, ung_vien = ghep_anh.ghep([dau(ImageEnhance.Brightness(h).enhance(1.3)) for h in reversed(loat)],
                                            [dau(h) for h in loat])
        self.assertEqual(cap, {})                              # không đủ chắc chắn -> để Nhiếp ảnh gia chọn tay
        self.assertEqual(chua, [0, 1, 2])
        self.assertEqual(sorted(ung_vien[0]), [0, 1, 2])       # vẫn có gợi ý để đổ vào danh sách thả xuống

    def test_lech_ti_le_khung_bi_loai(self):
        a, b = canh(1, (600, 400)), canh(1, (400, 600))
        self.assertIsNone(ghep_anh.khoang_cach(dau(a), dau(b)))
        cap, chua, _ = ghep_anh.ghep([dau(b)], [dau(a)])
        self.assertEqual((cap, chua), ({}, [0]))

    def test_cap_cuoi_ghep_bang_loai_tru(self):
        goc = canh(5)
        cap, chua, _ = ghep_anh.ghep([dau(sua(goc, 'mau'))], [dau(goc)])
        self.assertEqual((cap, chua), ({0: 0}, []))

    def test_chon_tay_duoc_tin_tuyet_doi_va_phan_con_lai_ghep_tu_dong(self):
        goc = [canh(10 + i) for i in range(3)]
        moi = [dau(sua(goc[2], 'sang')), dau(sua(goc[0], 'sang')), dau(sua(goc[1], 'sang'))]
        cap, chua, _ = ghep_anh.ghep_co_tay(moi, [dau(h) for h in goc], {0: 0})   # NAG ép tệp 0 -> ảnh 0 (khác với hình)
        self.assertEqual(cap[0], 0)                            # cặp chọn tay giữ nguyên
        self.assertEqual(len(cap) + len(chua), 3)

    def test_chon_tay_sai_nem_value_error(self):
        d = [dau(canh(1)), dau(canh(2))]
        with self.assertRaises(ValueError):
            ghep_anh.ghep_co_tay(d, d, {0: 1, 1: 1})           # hai tệp cùng chọn một ảnh
        with self.assertRaises(ValueError):
            ghep_anh.ghep_co_tay(d, d, {5: 0})                 # vị trí tệp lạ

    def test_anh_khong_doc_duoc_la_none_khong_gay_loi(self):
        cap, chua, _ = ghep_anh.ghep([None, dau(canh(1))], [dau(canh(1)), None])
        self.assertEqual(cap, {1: 0})
        self.assertEqual(chua, [0])


class GhepAnhDichVuTests(_NenAnh):                             # dịch vụ tải ảnh hậu kỳ dùng ghép theo hình (không dùng hàm ghép theo tên của test cũ)
    GHEP_THEO_TEN = False

    def booking_hau_ky(self, ds_canh):                         # Booking Đang hậu kỳ; Khách đã chọn các ảnh p1, p2, ... (mỗi ảnh một cảnh), có tệp thật
        bk = self.tao_booking(self.goi_gh, TT.DANG_HAU_KY)
        kho, ds = services.kho_anh(), []
        for i, hinh in enumerate(ds_canh, 1):
            a = self.tao_anh(bk, f'p{i}.jpg', chon=1)
            kho.save(a.DuongDanAnh, io.BytesIO(jpeg(hinh)))    # bản có watermark (ở đây dùng tạm ảnh thật)
            kho.save(services.duong_dan_goc(a.DuongDanAnh), io.BytesIO(jpeg(hinh)))   # bản gốc: dùng để so hình
            ds.append(a)
        return bk, ds

    def tep(self, ten, hinh):
        return SimpleUploadedFile(ten, jpeg(hinh))

    def goc_cua(self, anh):                                    # nội dung bản gốc (không watermark) của ảnh sau khi tải: chính là tệp Nhiếp ảnh gia đã tải
        anh.refresh_from_db()
        with services.kho_anh().open(services.duong_dan_goc(anh.DuongDanAnh)) as tep:
            return tep.read()

    def test_ghep_theo_hinh_bat_ke_ten_tep(self):
        goc = [canh(21), canh(22), canh(23)]
        bk, (p1, p2, p3) = self.booking_hau_ky(goc)
        # Tên tệp cố tình đảo: nếu ghép theo thứ tự tên (cách cũ) sẽ ghép sai cả ba ảnh.
        tep_c, tep_a, tep_b = (self.tep('a_cuoi.jpg', sua(goc[2], 'sang')), self.tep('b_x.jpg', sua(goc[0], 'den_trang')),
                               self.tep('c_y.jpg', sua(goc[1], 'min_da')))
        noi_dung = {t.name: t.read() for t in (tep_c, tep_a, tep_b)}
        for t in (tep_c, tep_a, tep_b):
            t.seek(0)
        kq = services.tai_anh_len(bk.pk, self.nag_user, [tep_c, tep_a, tep_b])
        self.assertEqual(kq['trang_thai_moi'], TT.CHO_KH_KIEM_TRA)
        self.assertEqual(self.goc_cua(p1), noi_dung['b_x.jpg'])   # cảnh 1 <- tệp b_x
        self.assertEqual(self.goc_cua(p2), noi_dung['c_y.jpg'])   # cảnh 2 <- tệp c_y
        self.assertEqual(self.goc_cua(p3), noi_dung['a_cuoi.jpg'])   # cảnh 3 <- tệp a_cuoi
        self.assertTrue(all(Anh.objects.get(pk=a.pk).DuongDanAnhTruoc for a in (p1, p2, p3)))   # có bản trước để slider so sánh

    def anh_chup_lien_tiep(self):                              # hai cảnh gần giống nhau tới mức không tự ghép được
        nen = canh(77)
        return [nen, nen.transform(nen.size, Image.AFFINE, (1, 0, 4, 0, 1, 0))]

    def test_chua_ghep_duoc_bao_loi_kem_goi_y_va_khong_luu_gi(self):
        hai = self.anh_chup_lien_tiep()
        bk, (p1, p2) = self.booking_hau_ky(hai)
        kho = services.kho_anh()
        truoc = sorted(kho.listdir(f'booking_{bk.pk}')[1])
        with self.assertRaises(services.LoiChuaGhep) as ctx:
            services.tai_anh_len(bk.pk, self.nag_user,
                                 [self.tep('m1.jpg', sua(hai[1], 'sang')), self.tep('m2.jpg', sua(hai[0], 'sang'))])
        loi = ctx.exception
        self.assertEqual(sorted(c['chi_so'] for c in loi.chua_ghep), [0, 1])
        self.assertEqual(sorted(a['ma'] for a in loi.ds_anh_can), sorted([p1.pk, p2.pk]))
        self.assertTrue(all(set(c['ung_vien']) == {p1.pk, p2.pk} for c in loi.chua_ghep))
        self.assertEqual(sorted(kho.listdir(f'booking_{bk.pk}')[1]), truoc)   # chưa ghi thêm tệp nào
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)
        self.assertIsNone(Anh.objects.get(pk=p1.pk).DuongDanAnhTruoc)         # DB không đổi

    def test_chon_tay_roi_tai_lai_thanh_cong(self):
        hai = self.anh_chup_lien_tiep()
        bk, (p1, p2) = self.booking_hau_ky(hai)
        tep_1, tep_2 = self.tep('m1.jpg', sua(hai[1], 'sang')), self.tep('m2.jpg', sua(hai[0], 'sang'))
        b1, b2 = tep_1.read(), tep_2.read()
        tep_1.seek(0), tep_2.seek(0)
        kq = services.tai_anh_len(bk.pk, self.nag_user, [tep_1, tep_2], {0: p2.pk, 1: p1.pk})   # NAG chọn: tệp 0 là bản sửa của ảnh 2, tệp 1 của ảnh 1
        self.assertEqual(kq['trang_thai_moi'], TT.CHO_KH_KIEM_TRA)
        self.assertEqual(self.goc_cua(p1), b2)
        self.assertEqual(self.goc_cua(p2), b1)

    def test_chon_tay_sai_bi_chan(self):
        hai = self.anh_chup_lien_tiep()
        bk, (p1, p2) = self.booking_hau_ky(hai)
        tep_hai = lambda: [self.tep('m1.jpg', sua(hai[1], 'sang')), self.tep('m2.jpg', sua(hai[0], 'sang'))]
        with self.assertRaises(services.LoiTaiAnh):            # mã ảnh không thuộc danh sách cần sửa
            services.tai_anh_len(bk.pk, self.nag_user, tep_hai(), {0: 999999})
        with self.assertRaises(services.LoiTaiAnh):            # hai tệp cùng chọn một ảnh
            services.tai_anh_len(bk.pk, self.nag_user, tep_hai(), {0: p1.pk, 1: p1.pk})
        bk.refresh_from_db()
        self.assertEqual(bk.TrangThai, TT.DANG_HAU_KY)

    def test_view_ajax_tra_danh_sach_chua_ghep_roi_nhan_ghep_tay(self):
        hai = self.anh_chup_lien_tiep()
        bk, (p1, p2) = self.booking_hau_ky(hai)
        self.client.force_login(self.nag_user)
        url = reverse('tai_anh_len', args=[bk.pk])
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        cho = self.client.post(url, {'anh': [self.tep('m1.jpg', sua(hai[1], 'sang')), self.tep('m2.jpg', sua(hai[0], 'sang'))]}, **ajax)
        self.assertEqual(cho.status_code, 400)
        du_lieu = cho.json()
        self.assertFalse(du_lieu['ok'])
        self.assertEqual(len(du_lieu['chua_ghep']), 2)
        self.assertEqual(len(du_lieu['ds_anh']), 2)
        self.assertTrue(all('/xem/' in a['url'] and a['url'].endswith('?nho=1') for a in du_lieu['ds_anh']))
        ok = self.client.post(url, {'anh': [self.tep('m1.jpg', sua(hai[1], 'sang')), self.tep('m2.jpg', sua(hai[0], 'sang'))],
                                    'ghep_tay': json.dumps({'0': p2.pk, '1': p1.pk})}, **ajax)
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()['ok'])

    def test_view_ghep_tay_sai_dinh_dang_bi_tu_choi(self):
        bk, _ = self.booking_hau_ky([canh(31), canh(32)])
        self.client.force_login(self.nag_user)
        phan_hoi = self.client.post(reverse('tai_anh_len', args=[bk.pk]),
                                    {'anh': [self.tep('a.jpg', canh(31)), self.tep('b.jpg', canh(32))], 'ghep_tay': 'khong-phai-json'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertFalse(phan_hoi.json()['ok'])

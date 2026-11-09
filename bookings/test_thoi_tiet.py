# =====================================================================
# bookings/test_thoi_tiet.py - Test cho bookings/thoi_tiet.py (E7: dịch vụ lấy dự báo thời tiết)
# Chạy:  python manage.py test bookings.test_thoi_tiet
# Toàn bộ test dùng dữ liệu GIẢ (giả lập urlopen), KHÔNG gọi mạng thật, không đụng database.
# =====================================================================
import json  # đổi dict sang chữ JSON để giả làm nội dung API trả về
import urllib.error  # các loại lỗi mạng (URLError, HTTPError)
from datetime import datetime, timedelta  # ngày giờ và khoảng thời gian
from unittest import mock  # mock: giả lập tạm một hàm trong lúc test
from zoneinfo import ZoneInfo  # múi giờ

from django.core.cache import cache  # bộ nhớ tạm của Django (cần xóa trước mỗi test)
from django.test import SimpleTestCase  # lớp test nhẹ, không cần database
from django.utils import timezone  # lấy giờ hiện tại có múi giờ

from bookings import thoi_tiet as dv  # file đang được test (dv = dịch vụ)

MUI_GIO = ZoneInfo('Asia/Ho_Chi_Minh')  # múi giờ Việt Nam


class PhanHoiGia:  # giả làm "phản hồi" của urlopen (dùng được với lệnh with ... as ...)
    def __init__(self, du_lieu):  # nhận dict dữ liệu muốn giả
        self.noi_dung = json.dumps(du_lieu).encode('utf-8')  # đổi sang byte giống dữ liệu thật

    def read(self):  # code thật gọi .read() để lấy nội dung
        return self.noi_dung  # trả nội dung giả

    def __enter__(self):  # bắt đầu khối with
        return self  # trả chính nó

    def __exit__(self, *args):  # kết thúc khối with
        return False  # không nuốt lỗi


def dau_ngay_nay():  # 0 giờ sáng hôm nay theo giờ Việt Nam (API bắt đầu dự báo từ mốc này)
    return timezone.localtime(timezone.now(), MUI_GIO).replace(hour=0, minute=0, second=0, microsecond=0)  # lấy giờ hiện tại rồi về 0 giờ


def du_lieu_gia(ma_thoi_tiet=61, gia_tri_null_o=None):  # tạo bảng dự báo giả 16 ngày x 24 giờ = 384 giờ giống API thật
    moc = dau_ngay_nay()  # giờ đầu tiên của bảng
    gio = [(moc + timedelta(hours=i)).strftime('%Y-%m-%dT%H:00') for i in range(384)]  # danh sách 384 chuỗi giờ
    nhiet_do = [20.0 + i / 100 for i in range(384)]  # nhiệt độ giả: mỗi giờ một số khác nhau để biết có tra đúng giờ không
    xac_suat = [i % 101 for i in range(384)]  # % mưa giả: cũng khác nhau theo giờ
    ma = [ma_thoi_tiet] * 384  # mã thời tiết giả: giờ nào cũng giống nhau
    if gia_tri_null_o is not None:  # nếu test muốn giả lập "giờ này API trả null"
        nhiet_do[gia_tri_null_o] = None  # đặt nhiệt độ ở giờ đó thành null
    return {'hourly': {'time': gio, 'temperature_2m': nhiet_do, 'precipitation_probability': xac_suat, 'weather_code': ma}}  # đúng khuôn của API thật


def chi_so_gio(gio_chup):  # đổi giờ chụp thành số thứ tự giờ trong bảng giả (để biết kết quả đúng phải là bao nhiêu)
    return int((gio_chup.replace(minute=0, second=0, microsecond=0) - dau_ngay_nay()).total_seconds() // 3600)  # số giờ tính từ 0 giờ hôm nay


class ThoiTietTest(SimpleTestCase):  # nhóm test E7
    def setUp(self):  # chạy TRƯỚC mỗi test
        cache.clear()  # xóa bộ nhớ tạm để test này không bị ảnh hưởng bởi test trước
        self.gio_chup = timezone.localtime(timezone.now(), MUI_GIO).replace(minute=30, second=0, microsecond=0) + timedelta(days=2)  # giờ chụp mẫu: 2 ngày nữa, phút 30

    def test_thanh_cong_tra_dung_gio(self):  # tình huống 1: gọi thành công, kết quả đúng giờ chụp
        i = chi_so_gio(self.gio_chup)  # số thứ tự giờ chụp trong bảng giả
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia(ma_thoi_tiet=80))):  # giả lập API trả bảng giả (mã 80 = mưa rào nhẹ)
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm cần test
        self.assertEqual(kq, {'nhiet_do': round(20.0 + i / 100, 1), 'xac_suat_mua': i % 101, 'mo_ta': 'Mưa rào nhẹ'})  # kết quả phải đúng giờ, đúng mô tả

    def test_goi_dung_toa_do_va_gioi_han_thoi_gian(self):  # tình huống 2: gọi API đúng tọa độ, đúng múi giờ, đúng giới hạn 3 giây
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia())) as gia:  # giả lập và giữ lại để soi cách gọi
            dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm
        url = gia.call_args.args[0]  # địa chỉ đã gọi
        self.assertIn('latitude=16.0544', url)  # đúng vĩ độ Đà Nẵng
        self.assertIn('longitude=108.2022', url)  # đúng kinh độ Đà Nẵng
        self.assertIn('Asia%2FHo_Chi_Minh', url)  # đúng múi giờ
        self.assertEqual(gia.call_args.kwargs['timeout'], 3)  # chờ tối đa 3 giây

    def test_nho_ket_qua_khong_goi_lai(self):  # tình huống 3: gọi lần 2 (cùng khu vực) dùng bộ nhớ tạm, không gọi mạng nữa
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia())) as gia:  # giả lập API
            dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # lần 1: phải gọi API
            dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup + timedelta(hours=3))  # lần 2: giờ khác nhưng cùng khu vực
        self.assertEqual(gia.call_count, 1)  # tổng cộng chỉ gọi API đúng 1 lần

    def test_cac_cach_viet_tp_hcm_dung_chung_toa_do(self):  # tình huống 4: 'TP.HCM' và 'TP. Hồ Chí Minh' là cùng một nơi
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia())):  # giả lập API
            kq1 = dv.lay_du_bao_thoi_tiet('TP.HCM', self.gio_chup)  # cách viết tắt
            kq2 = dv.lay_du_bao_thoi_tiet('TP. Hồ Chí Minh', self.gio_chup)  # cách viết đầy đủ
        self.assertTrue(kq1)  # có kết quả
        self.assertEqual(kq1, kq2)  # hai cách viết cho cùng kết quả

    def test_nhan_doi_tuong_khu_vuc(self):  # tình huống 5: truyền thẳng đối tượng có thuộc tính TenKhuVuc
        khu_vuc = mock.Mock(TenKhuVuc='Đà Lạt')  # giả một đối tượng KhuVuc
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia())):  # giả lập API
            kq = dv.lay_du_bao_thoi_tiet(khu_vuc, self.gio_chup)  # gọi hàm
        self.assertEqual(set(kq), {'nhiet_do', 'xac_suat_mua', 'mo_ta'})  # có đủ 3 mục

    def test_gio_chup_chua_gan_mui_gio(self):  # tình huống 6: giờ chụp dạng "naive" vẫn chạy, không làm hỏng trang
        gio_naive = self.gio_chup.replace(tzinfo=None)  # bỏ múi giờ đi
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia())):  # giả lập API
            kq = dv.lay_du_bao_thoi_tiet('Hà Nội', gio_naive)  # gọi hàm
        self.assertTrue(kq)  # vẫn có kết quả

    def test_khu_vuc_la_hoac_thieu_thi_tra_rong_khong_goi_mang(self):  # tình huống 7: khu vực lạ / trống / thiếu giờ -> rỗng, không gọi mạng
        with mock.patch('urllib.request.urlopen') as gia:  # giả lập; nếu bị gọi thì đếm được
            self.assertEqual(dv.lay_du_bao_thoi_tiet('Sao Hỏa', self.gio_chup), {})  # khu vực không có trong bảng tọa độ
            self.assertEqual(dv.lay_du_bao_thoi_tiet('', self.gio_chup), {})  # khu vực trống
            self.assertEqual(dv.lay_du_bao_thoi_tiet(None, self.gio_chup), {})  # không có khu vực
            self.assertEqual(dv.lay_du_bao_thoi_tiet('Đà Nẵng', None), {})  # không có giờ chụp
        gia.assert_not_called()  # không lần nào gọi mạng

    def test_qua_xa_ngay_du_bao_tra_rong_khong_goi_mang(self):  # tình huống 8: buổi chụp cách hôm nay hơn 16 ngày
        with mock.patch('urllib.request.urlopen') as gia:  # giả lập; nếu bị gọi thì đếm được
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup + timedelta(days=20))  # giờ chụp 22 ngày nữa
        self.assertEqual(kq, {})  # rỗng
        gia.assert_not_called()  # không gọi mạng

    def test_buoi_chup_da_qua_tra_rong(self):  # tình huống 9: buổi chụp đã qua
        with mock.patch('urllib.request.urlopen') as gia:  # giả lập
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup - timedelta(days=3))  # giờ chụp 3 ngày trước (còn trước hôm nay)
        self.assertEqual(kq, {})  # rỗng
        gia.assert_not_called()  # không gọi mạng

    def test_loi_mang_tra_rong_va_nho_loi_ngan_han(self):  # tình huống 10: mất mạng/hết giờ -> rỗng; lần sau không phải chờ lại
        with mock.patch('urllib.request.urlopen', side_effect=urllib.error.URLError('mất mạng')) as gia:  # giả lập lỗi mạng
            kq1 = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # lần 1: gọi và lỗi
            kq2 = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # lần 2: dùng "bộ nhớ lỗi", khỏi gọi lại
        self.assertEqual((kq1, kq2), ({}, {}))  # cả hai đều rỗng, không ném lỗi
        self.assertEqual(gia.call_count, 1)  # chỉ gọi 1 lần

    def test_het_gio_cho_tra_rong(self):  # tình huống 11: API chậm quá 3 giây (TimeoutError)
        with mock.patch('urllib.request.urlopen', side_effect=TimeoutError('quá 3 giây')):  # giả lập hết giờ chờ
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm
        self.assertEqual(kq, {})  # rỗng

    def test_api_tra_loi_http_tra_rong(self):  # tình huống 12: API báo lỗi 429 (gọi quá nhiều) hoặc 500
        loi = urllib.error.HTTPError('http://x', 429, 'Too Many Requests', {}, None)  # giả lỗi HTTP 429
        with mock.patch('urllib.request.urlopen', side_effect=loi):  # giả lập
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm
        self.assertEqual(kq, {})  # rỗng

    def test_du_lieu_hong_tra_rong(self):  # tình huống 13: API trả JSON sai khuôn (thiếu mục hourly)
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia({'error': True})):  # giả lập dữ liệu sai khuôn
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm
        self.assertEqual(kq, {})  # rỗng

    def test_gio_chup_bi_null_tra_rong(self):  # tình huống 14: đúng giờ chụp API trả null
        i = chi_so_gio(self.gio_chup)  # số thứ tự giờ chụp trong bảng giả
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia(gia_tri_null_o=i))):  # giả lập: giờ đó có nhiệt độ null
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm
        self.assertEqual(kq, {})  # rỗng

    def test_ma_thoi_tiet_la_dung_mo_ta_mac_dinh(self):  # tình huống 15: mã thời tiết chưa có trong bảng mô tả
        with mock.patch('urllib.request.urlopen', return_value=PhanHoiGia(du_lieu_gia(ma_thoi_tiet=777))):  # giả lập mã lạ 777
            kq = dv.lay_du_bao_thoi_tiet('Đà Nẵng', self.gio_chup)  # gọi hàm
        self.assertEqual(kq['mo_ta'], dv.MO_TA_MAC_DINH)  # dùng câu mô tả mặc định

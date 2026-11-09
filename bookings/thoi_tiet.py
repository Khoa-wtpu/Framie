# =====================================================================
# bookings/thoi_tiet.py  -  E7 (Nguyên)
#   Dịch vụ lấy dự báo thời tiết buổi chụp (Module 4 - API thời tiết)
#
# Yêu cầu (task E7):
#   - Chỉ có MỘT hàm công khai: lay_du_bao_thoi_tiet(khu_vuc, ngay_gio_chup).
#   - Trả về nhiệt độ, khả năng mưa, mô tả ngắn. Mọi lỗi (mạng, API, quá xa ngày dự báo...) đều trả rỗng {}.
#   - Tọa độ lấy theo KHU VỰC của Nhiếp ảnh gia (bảng khai báo sẵn bên dưới), không đoán từ địa chỉ gõ tay.
#   - Chờ tối đa 3 giây; nhớ kết quả trong bộ nhớ tạm của Django 45 phút.
#   - Chỉ dùng thư viện chuẩn của Python (urllib) nên KHÔNG cần thêm gói mới vào requirements.txt.
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ
# ---------------------------------------------------------------------
import json  # đọc dữ liệu JSON mà API trả về
import logging  # thư viện ghi log của Python (để lỗi vẫn có dấu vết mà không làm hỏng trang)
import unicodedata  # tách dấu tiếng Việt, để so tên khu vực không phân biệt dấu
import urllib.parse  # ghép các tham số vào địa chỉ URL
import urllib.request  # gọi API qua mạng (thư viện có sẵn của Python)
from datetime import timedelta  # một khoảng thời gian (ví dụ 1 giờ, 16 ngày)
from zoneinfo import ZoneInfo  # múi giờ (tzdata đã có trong requirements.txt)

from django.core.cache import cache  # bộ nhớ tạm của Django (mặc định nằm trong RAM)
from django.utils import timezone  # xử lý giờ có múi giờ

logger = logging.getLogger(__name__)  # "cây bút ghi log" mang tên file này

URL_API = 'https://api.open-meteo.com/v1/forecast'  # địa chỉ API dự báo của Open-Meteo (E6: miễn phí, không cần khóa)
MUI_GIO = 'Asia/Ho_Chi_Minh'  # múi giờ Việt Nam; nếu E6 báo API không nhận thì đổi thành 'Asia/Bangkok'
GIAY_CHO_TOI_DA = 3  # chờ API tối đa 3 giây, quá thì bỏ cuộc (theo yêu cầu E7)
SO_NGAY_DU_BAO = 16  # API dự báo theo giờ tối đa 16 ngày (kết quả E6)
CAC_BIEN_THEO_GIO = 'temperature_2m,precipitation_probability,weather_code'  # 3 thứ cần lấy: nhiệt độ, % mưa, mã thời tiết
GIAY_NHO_KET_QUA = 45 * 60  # nhớ kết quả 45 phút (yêu cầu: 30-60 phút)
GIAY_NHO_KHI_LOI = 60  # khi API lỗi, nhớ "đang lỗi" 1 phút để các lần xem trang sau khỏi phải chờ 3 giây nữa

# Bảng tọa độ (vĩ độ, kinh độ) theo khu vực. Khóa là tên đã bỏ dấu, bỏ khoảng trắng, viết thường (xem _chuan_hoa).
# 5 khu vực của dữ liệu mẫu + vài cách viết khác của TP.HCM (trong test của nhóm có dùng 'TP.HCM').
TOA_DO_KHU_VUC = {
   'tphochiminh': (10.8231, 106.6297),  # TP. Hồ Chí Minh
   'tphcm': (10.8231, 106.6297),  # TP.HCM (cách viết tắt)
   'hochiminh': (10.8231, 106.6297),  # Hồ Chí Minh (không có "TP.")
   'hanoi': (21.0285, 105.8542),  # Hà Nội
   'danang': (16.0544, 108.2022),  # Đà Nẵng
   'dalat': (11.9404, 108.4583),  # Đà Lạt
   'nhatrang': (12.2388, 109.1967),  # Nha Trang
}

# Mã thời tiết quốc tế (WMO) mà API trả về -> mô tả ngắn tiếng Việt.
MO_TA_THEO_MA = {
   0: 'Trời quang', 1: 'Ít mây', 2: 'Có mây', 3: 'Nhiều mây',  # nhóm trời không mưa
   45: 'Sương mù', 48: 'Sương mù đóng băng',  # nhóm sương mù
   51: 'Mưa phùn nhẹ', 53: 'Mưa phùn', 55: 'Mưa phùn dày',  # nhóm mưa phùn
   56: 'Mưa phùn lạnh', 57: 'Mưa phùn lạnh dày',  # mưa phùn lạnh (hiếm ở Việt Nam)
   61: 'Mưa nhẹ', 63: 'Mưa vừa', 65: 'Mưa to',  # nhóm mưa thường
   66: 'Mưa lạnh nhẹ', 67: 'Mưa lạnh to',  # mưa lạnh (hiếm ở Việt Nam)
   80: 'Mưa rào nhẹ', 81: 'Mưa rào', 82: 'Mưa rào rất to',  # nhóm mưa rào
   95: 'Dông', 96: 'Dông kèm mưa đá nhẹ', 99: 'Dông kèm mưa đá lớn',  # nhóm dông
}
MO_TA_MAC_DINH = 'Chưa rõ thời tiết'  # dùng khi gặp mã lạ chưa có trong bảng trên


# ---------------------------------------------------------------------
# PHẦN 2: HÀM PHỤ (chỉ dùng nội bộ trong file này, tên bắt đầu bằng dấu _)
# ---------------------------------------------------------------------
def _chuan_hoa(ten):  # đổi tên khu vực về dạng so sánh được: 'TP. Hồ Chí Minh' -> 'tphochiminh'
   ten = str(ten).lower().replace('đ', 'd')  # viết thường; chữ đ không tự tách dấu được nên đổi riêng sang d
   ten = unicodedata.normalize('NFD', ten)  # tách dấu ra khỏi chữ (ồ -> o + dấu mũ + dấu huyền)
   return ''.join(c for c in ten if c.isalnum() and not unicodedata.combining(c))  # giữ chữ và số, bỏ dấu, khoảng trắng, dấu chấm


def _goi_api(vi_do, kinh_do):  # gọi API thật, trả về {'2026-11-12T09:00': (nhiệt độ, % mưa, mã), ...}; lỗi thì ném ngoại lệ
   tham_so = urllib.parse.urlencode({  # ghép các tham số thành chuỗi "latitude=...&longitude=..."
       'latitude': vi_do,  # vĩ độ
       'longitude': kinh_do,  # kinh độ
       'hourly': CAC_BIEN_THEO_GIO,  # lấy dự báo theo từng giờ
       'forecast_days': SO_NGAY_DU_BAO,  # lấy 16 ngày
       'timezone': MUI_GIO,  # giờ trả về tính theo giờ Việt Nam
   })
   with urllib.request.urlopen(f'{URL_API}?{tham_so}', timeout=GIAY_CHO_TOI_DA) as phan_hoi:  # gọi API, chờ tối đa 3 giây; mã lỗi HTTP (429...) sẽ tự ném ngoại lệ
       du_lieu = json.loads(phan_hoi.read().decode('utf-8'))  # đọc nội dung trả về rồi đổi từ chữ JSON sang dict
   theo_gio = du_lieu['hourly']  # phần dự báo theo giờ
   return dict(zip(  # ghép 4 danh sách song song thành một bảng tra theo giờ
       theo_gio['time'],  # khóa: chuỗi giờ, ví dụ '2026-11-12T09:00'
       zip(theo_gio['temperature_2m'], theo_gio['precipitation_probability'], theo_gio['weather_code']),  # giá trị: (nhiệt độ, % mưa, mã thời tiết)
   ))


# ---------------------------------------------------------------------
# PHẦN 3: HÀM CÔNG KHAI DUY NHẤT (E8 gọi hàm này để vẽ thẻ "Dự báo thời tiết buổi chụp")
# ---------------------------------------------------------------------
def lay_du_bao_thoi_tiet(khu_vuc, ngay_gio_chup):  # nhận khu vực + giờ chụp, trả dict dự báo hoặc {}
   """Trả {'nhiet_do': 29.5, 'xac_suat_mua': 40, 'mo_ta': 'Mưa rào nhẹ'}; mọi lỗi / không có dự báo thì trả {}."""
   try:  # bọc TOÀN BỘ hàm: bất kể lỗi gì cũng không được làm hỏng trang
       ten = getattr(khu_vuc, 'TenKhuVuc', khu_vuc)  # nhận được cả đối tượng KhuVuc lẫn chuỗi tên khu vực
       if not ten or ngay_gio_chup is None:  # thiếu khu vực hoặc thiếu giờ chụp
           return {}  # không có gì để tra -> rỗng
       toa_do = TOA_DO_KHU_VUC.get(_chuan_hoa(ten))  # tra tọa độ theo tên khu vực
       if toa_do is None:  # khu vực chưa có trong bảng tọa độ
           return {}  # không đoán bừa -> rỗng

       mui_gio = ZoneInfo(MUI_GIO)  # múi giờ Việt Nam
       if timezone.is_naive(ngay_gio_chup):  # nếu giờ chụp chưa gắn múi giờ
           ngay_gio_chup = timezone.make_aware(ngay_gio_chup, mui_gio)  # coi đó là giờ Việt Nam
       gio_chup = timezone.localtime(ngay_gio_chup, mui_gio)  # đổi giờ chụp sang giờ Việt Nam (khớp với giờ API trả về)
       bay_gio = timezone.localtime(timezone.now(), mui_gio)  # giờ hiện tại theo giờ Việt Nam
       dau_ngay_nay = bay_gio.replace(hour=0, minute=0, second=0, microsecond=0)  # 0 giờ sáng hôm nay (API bắt đầu dự báo từ mốc này)
       if gio_chup < bay_gio - timedelta(hours=1):  # buổi chụp đã qua hơn 1 giờ
           return {}  # dự báo cho quá khứ vô nghĩa -> rỗng
       if gio_chup >= dau_ngay_nay + timedelta(days=SO_NGAY_DU_BAO):  # buổi chụp xa hơn 16 ngày
           return {}  # quá xa ngày dự báo -> rỗng

       khoa_cache = f'thoi_tiet:{toa_do[0]}:{toa_do[1]}'  # mỗi tọa độ một ô nhớ (cả bảng 16 ngày, nên nhiều Booking cùng khu vực dùng chung)
       bang_du_bao = cache.get(khoa_cache)  # xem trong bộ nhớ tạm đã có chưa
       if bang_du_bao is None:  # chưa có (hoặc đã hết hạn)
           try:  # thử gọi API thật
               bang_du_bao = _goi_api(*toa_do)  # gọi API, chờ tối đa 3 giây
               cache.set(khoa_cache, bang_du_bao, GIAY_NHO_KET_QUA)  # thành công: nhớ 45 phút
           except Exception as loi:  # lỗi mạng, hết giờ, bị chặn, JSON hỏng, thiếu trường...
               logger.warning('Không lấy được dự báo thời tiết (%s): %s', ten, loi)  # chỉ ghi log, không báo lỗi lên trang
               cache.set(khoa_cache, {}, GIAY_NHO_KHI_LOI)  # nhớ "đang lỗi" 1 phút để khỏi gọi lại liên tục
               return {}  # trả rỗng

       mot_gio = bang_du_bao.get(gio_chup.strftime('%Y-%m-%dT%H:00'))  # tra đúng giờ chụp (làm tròn xuống đầu giờ)
       if mot_gio is None:  # không có giờ đó trong bảng (hoặc bảng rỗng vì đang lỗi)
           return {}  # trả rỗng
       nhiet_do, xac_suat_mua, ma_thoi_tiet = mot_gio  # tách 3 giá trị
       if nhiet_do is None or xac_suat_mua is None or ma_thoi_tiet is None:  # API đôi khi trả null cho giờ chưa có số liệu
           return {}  # thiếu số liệu thì không hiện nửa vời -> rỗng
       return {  # kết quả trả cho E8
           'nhiet_do': round(float(nhiet_do), 1),  # nhiệt độ (°C), làm tròn 1 chữ số thập phân
           'xac_suat_mua': int(round(xac_suat_mua)),  # khả năng mưa (%), số nguyên
           'mo_ta': MO_TA_THEO_MA.get(int(ma_thoi_tiet), MO_TA_MAC_DINH),  # mô tả ngắn tiếng Việt
       }
   except Exception:  # lưới an toàn cuối cùng cho mọi lỗi bất ngờ khác
       logger.exception('Lỗi bất ngờ khi lấy dự báo thời tiết')  # ghi log đầy đủ để Nguyên còn biết đường sửa
       return {}  # vẫn trả rỗng, trang không bị hỏng

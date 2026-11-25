# =====================================================================
# bookings/thoi_tiet.py  -  E7 (Nguyên)
#   Dịch vụ lấy dự báo thời tiết buổi chụp (Module 4 - API thời tiết)
#
# Yêu cầu (task E7):
#   - Chỉ có MỘT hàm công khai: lay_du_bao_thoi_tiet(khu_vuc, ngay_gio_chup, thoi_luong_phut=None).
#   - Trả về nhiệt độ, khả năng mưa, mô tả ngắn. Mọi lỗi (mạng, API, quá xa ngày dự báo...) đều trả rỗng {}.
#   - Tọa độ lấy theo KHU VỰC của Nhiếp ảnh gia (bảng khai báo sẵn bên dưới), không đoán từ địa chỉ gõ tay.
#   - Chờ tối đa 3 giây; nhớ kết quả trong bộ nhớ tạm của Django 30 phút (E1).
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
MUI_GIO = 'Asia/Ho_Chi_Minh'  # múi giờ Việt Nam (E6: API nhận tên này)
GIAY_CHO_TOI_DA = 3  # chờ API tối đa 3 giây, quá thì bỏ cuộc (theo yêu cầu E7)
SO_NGAY_DU_BAO = 16  # API dự báo theo giờ tối đa 16 ngày (kết quả E6)
CAC_BIEN_THEO_GIO = 'temperature_2m,precipitation_probability,weather_code'  # 3 thứ cần lấy: nhiệt độ, % mưa, mã thời tiết
GIAY_NHO_KET_QUA = 30 * 60  # nhớ kết quả 30 phút (E1 ghi 30 phút; Task 6 cho phép 30-60 phút)
GIAY_NHO_KHI_LOI = 60  # khi API lỗi, nhớ "đang lỗi" 1 phút để các lần xem trang sau khỏi phải chờ 3 giây nữa

# Bảng tọa độ (vĩ độ, kinh độ) theo khu vực. Khóa là tên đã bỏ dấu, bỏ khoảng trắng, viết thường (xem _chuan_hoa).
# F2: đủ 34 tỉnh thành theo core/du_lieu_khu_vuc.py (Quyết định 19/2025/QĐ-TTg). Mỗi tỉnh dùng tọa độ của một thành phố/đô thị
# đại diện (thường là nơi đặt trụ sở tỉnh hoặc nơi khách hay chụp nhất), vì API dự báo theo điểm, không theo ranh giới tỉnh.
TOA_DO_KHU_VUC = {
    # --- 34 tỉnh thành (khóa = core.du_lieu_khu_vuc.chuan_hoa(tên), theo thứ tự mã số Phụ lục I) ---
    'hanoi': (21.0285, 105.8542),  # 01 Hà Nội
    'caobang': (22.6657, 106.2579),  # 04 Cao Bằng (TP. Cao Bằng)
    'tuyenquang': (21.8233, 105.2181),  # 08 Tuyên Quang (TP. Tuyên Quang)
    'dienbien': (21.3860, 103.0230),  # 11 Điện Biên (TP. Điện Biên Phủ)
    'laichau': (22.3964, 103.4580),  # 12 Lai Châu (TP. Lai Châu)
    'sonla': (21.3256, 103.9188),  # 14 Sơn La (TP. Sơn La)
    'laocai': (22.4809, 103.9755),  # 15 Lào Cai (TP. Lào Cai)
    'thainguyen': (21.5942, 105.8482),  # 19 Thái Nguyên (TP. Thái Nguyên)
    'langson': (21.8537, 106.7615),  # 20 Lạng Sơn (TP. Lạng Sơn)
    'quangninh': (20.9712, 107.0448),  # 22 Quảng Ninh (TP. Hạ Long)
    'bacninh': (21.1861, 106.0763),  # 24 Bắc Ninh (TP. Bắc Ninh)
    'phutho': (21.3227, 105.4020),  # 25 Phú Thọ (TP. Việt Trì)
    'haiphong': (20.8449, 106.6881),  # 31 Hải Phòng
    'hungyen': (20.6464, 106.0511),  # 33 Hưng Yên (TP. Hưng Yên)
    'ninhbinh': (20.2506, 105.9745),  # 37 Ninh Bình (TP. Ninh Bình)
    'thanhhoa': (19.8067, 105.7852),  # 38 Thanh Hóa (TP. Thanh Hóa)
    'nghean': (18.6796, 105.6813),  # 40 Nghệ An (TP. Vinh)
    'hatinh': (18.3428, 105.9057),  # 42 Hà Tĩnh (TP. Hà Tĩnh)
    'quangtri': (17.4689, 106.6223),  # 44 Quảng Trị (TP. Đồng Hới, nơi đặt trụ sở tỉnh sau sáp nhập)
    'hue': (16.4637, 107.5909),  # 46 Huế
    'danang': (16.0544, 108.2022),  # 48 Đà Nẵng
    'quangngai': (15.1205, 108.7923),  # 51 Quảng Ngãi (TP. Quảng Ngãi)
    'gialai': (13.7765, 109.2237),  # 52 Gia Lai (TP. Quy Nhơn, nơi đặt trụ sở tỉnh sau sáp nhập)
    'khanhhoa': (12.2388, 109.1967),  # 56 Khánh Hòa (TP. Nha Trang)
    'daklak': (12.6667, 108.0383),  # 66 Đắk Lắk (TP. Buôn Ma Thuột)
    'lamdong': (11.9404, 108.4583),  # 68 Lâm Đồng (TP. Đà Lạt)
    'dongnai': (10.9574, 106.8426),  # 75 Đồng Nai (TP. Biên Hòa)
    'hochiminh': (10.8231, 106.6297),  # 79 Hồ Chí Minh
    'tayninh': (11.3100, 106.0983),  # 80 Tây Ninh (TP. Tây Ninh)
    'dongthap': (10.4600, 105.6330),  # 82 Đồng Tháp (TP. Cao Lãnh)
    'vinhlong': (10.2537, 105.9722),  # 86 Vĩnh Long (TP. Vĩnh Long)
    'angiang': (10.3711, 105.4328),  # 91 An Giang (TP. Long Xuyên)
    'cantho': (10.0452, 105.7469),  # 92 Cần Thơ
    'camau': (9.1769, 105.1524),  # 96 Cà Mau (TP. Cà Mau)
    # --- Khóa CŨ giữ lại để dữ liệu/booking cũ chưa đổi tên vẫn có dự báo ---
    'tphochiminh': (10.8231, 106.6297),  # TP. Hồ Chí Minh
    'tphcm': (10.8231, 106.6297),  # TP.HCM (cách viết tắt)
    'dalat': (11.9404, 108.4583),  # Đà Lạt (nay thuộc Lâm Đồng)
    'nhatrang': (12.2388, 109.1967),  # Nha Trang (nay thuộc Khánh Hòa)
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


def _cac_gio_cua_buoi_chup(gio_chup, thoi_luong_phut):  # danh sách các giờ tròn mà buổi chụp đi qua (giờ Việt Nam)
    dau = gio_chup.replace(minute=0, second=0, microsecond=0)  # giờ bắt đầu, làm tròn xuống đầu giờ
    try:  # thời lượng có thể là None hoặc giá trị lạ
        so_phut = int(thoi_luong_phut or 0)
    except (TypeError, ValueError):
        so_phut = 0
    if so_phut <= 0:  # không biết thời lượng: chỉ xét giờ bắt đầu
        return [dau]
    cuoi = (gio_chup + timedelta(minutes=so_phut) - timedelta(seconds=1)).replace(minute=0, second=0, microsecond=0)  # giờ chứa khoảnh khắc cuối của buổi chụp (kết thúc đúng giờ tròn thì không tính giờ đó)
    ds = [dau]
    while ds[-1] < cuoi:
        ds.append(ds[-1] + timedelta(hours=1))
    return ds


# ---------------------------------------------------------------------
# PHẦN 3: HÀM CÔNG KHAI DUY NHẤT (E8 gọi hàm này để vẽ thẻ "Dự báo thời tiết buổi chụp")
# ---------------------------------------------------------------------
def lay_du_bao_thoi_tiet(khu_vuc, ngay_gio_chup, thoi_luong_phut=None):
    # tra toạ độ khu vực + giờ chụp (+ thời lượng buổi chụp), trả dict dự báo hoặc {}
    """Trả {'nhiet_do': 29.5, 'xac_suat_mua': 40, 'mo_ta': 'Mưa rào nhẹ'}; mọi lỗi / không có dự báo thì trả {}.

    Buổi chụp bắt đầu ở ngay_gio_chup và kéo dài thoi_luong_phut phút (ThoiLuongChup của gói), nên xét MỌI giờ mà buổi chụp
    đi qua (chụp 8h30 đến 11h30 thì xét các giờ 8, 9, 10, 11; chụp 8h30 đến 11h00 thì chỉ 8, 9, 10):
      - nhiet_do: nhiệt độ ở giờ bắt đầu;
      - xac_suat_mua: xác suất mưa LỚN NHẤT trong các giờ đó;
      - mo_ta: mô tả theo giờ có xác suất mưa lớn nhất (bằng nhau thì giờ sớm hơn) để chữ khớp với số hiển thị.
    thoi_luong_phut không có (None / 0) thì chỉ xét giờ bắt đầu."""
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
        if gio_chup >= dau_ngay_nay + timedelta(days=SO_NGAY_DU_BAO):  # buổi chụp xa hơn 16 ngày so với ngày booking
            return {}  # quá xa ngày dự báo -> rỗng
#1 Hàm lay_du_bao_thoi_tiet tra tọa độ khu vực và kiểm tra cache.
        # Nếu đã có dữ liệu trong cache thì sử dụng lại,
        # nếu chưa có thì gọi hàm _goi_api để lấy dữ liệu từ Open-Meteo (175-176)
        khoa_cache = f'thoi_tiet:{toa_do[0]}:{toa_do[1]}'  # mỗi tọa độ một ô nhớ (cả bảng 16 ngày, nên nhiều Booking cùng khu vực dùng chung)
        bang_du_bao = cache.get(khoa_cache)  # xem trong bộ nhớ tạm đã có chưa
        if bang_du_bao is None:  # chưa có (hoặc đã hết hạn)
            try:  # thử gọi API thật
                bang_du_bao = _goi_api(*toa_do)  # gọi API, chờ tối đa 3 giây
                cache.set(khoa_cache, bang_du_bao, GIAY_NHO_KET_QUA)  # thành công: nhớ 30 phút
            except Exception as loi:  # lỗi mạng, hết giờ, bị chặn, JSON hỏng, thiếu trường...
                logger.warning('Không lấy được dự báo thời tiết (%s): %s', ten, loi)  # chỉ ghi log, không báo lỗi lên trang
                cache.set(khoa_cache, {}, GIAY_NHO_KHI_LOI)  # nhớ "đang lỗi" 1 phút để khỏi gọi lại liên tục
                return {}  # trả rỗng
#2 Sau đó, hệ thống lấy nhiệt độ, xác suất mưa lớn nhất trong khung giờ chụp (192) và
        # mô tả thời tiết bằng tiếng Việt. (197-201)
        # Dữ liệu được trả về hàm lay_the_thoi_tiet.
        cac_gio = _cac_gio_cua_buoi_chup(gio_chup, thoi_luong_phut)
        #Hệ thống xác định các khung giờ mà buổi chụp diễn ra.
        mot_gio = bang_du_bao.get(cac_gio[0].strftime('%Y-%m-%dT%H:00'))
        #Hệ thống lấy nhiệt độ, xác suất mưa và mã thời tiết tại giờ bắt đầu buổi chụp.
        if mot_gio is None:  # không có giờ đó trong bảng (hoặc bảng rỗng vì đang lỗi)
            return {}  # trả rỗng
        nhiet_do, xac_suat_mua, ma_thoi_tiet = mot_gio
        #2.1 Hệ thống lấy nhiệt độ, xác suất mưa và mã thời tiết tại giờ bắt đầu buổi chụp.
        if nhiet_do is None or xac_suat_mua is None or ma_thoi_tiet is None:  # API đôi khi trả null cho giờ chưa có số liệu
            return {}  # giờ bắt đầu thiếu số liệu thì không hiện nửa vời -> rỗng
        #2.2 Sau đó, hệ thống duyệt qua các giờ còn lại của buổi chụp để tìm xác suất mưa lớn nhất.
        for gio in cac_gio[1:]:  # các giờ sau trong buổi chụp: lấy xác suất mưa lớn nhất
            gio_sau = bang_du_bao.get(gio.strftime('%Y-%m-%dT%H:00'))

            if gio_sau is None or gio_sau[1] is None or gio_sau[2] is None:  # giờ ngoài bảng hoặc bị null: bỏ qua giờ đó
                continue
    # 2.3 Nếu xác suất mưa của giờ sau lớn hơn xác suất mưa đang lưu,
    # hệ thống cập nhật lại xác suất mưa và mã thời tiết tương ứng.
            if gio_sau[1] > xac_suat_mua:  # CHỈ khi lớn hơn hẳn: bằng nhau thì giữ giờ sớm hơn
                xac_suat_mua, ma_thoi_tiet = gio_sau[1], gio_sau[2]
        return {  #3 Cuối cùng, hệ thống trả về dữ liệu dự báo thời tiết.
            'nhiet_do': round(float(nhiet_do), 1),  # nhiệt độ (°C) ở giờ bắt đầu, làm tròn 1 chữ số thập phân
            'xac_suat_mua': int(round(xac_suat_mua)),  # khả năng mưa cao nhất trong buổi chụp (%), số nguyên
            'mo_ta': MO_TA_THEO_MA.get(int(ma_thoi_tiet), MO_TA_MAC_DINH),  # mô tả ngắn tiếng Việt theo giờ mưa cao nhất
        }
    except Exception:  # lưới an toàn cuối cùng cho mọi lỗi bất ngờ khác
        logger.exception('Lỗi bất ngờ khi lấy dự báo thời tiết')  # ghi log đầy đủ để Nguyên còn biết đường sửa
        return {}  # vẫn trả rỗng, trang không bị hỏng
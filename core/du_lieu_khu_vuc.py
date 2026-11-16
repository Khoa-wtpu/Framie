# =====================================================================
# core/du_lieu_khu_vuc.py   (task F1)
# DANH MỤC 34 ĐƠN VỊ HÀNH CHÍNH CẤP TỈNH dùng làm bảng KHUVUC.
#
# Nguồn: Quyết định 19/2025/QĐ-TTg ngày 30/6/2025 (hiệu lực 01/7/2025), Phụ lục I,
#        sắp theo mã số trong Phụ lục (28 tỉnh + 6 thành phố).
# Quy ước đặt tên: KHÔNG kèm chữ "Tỉnh" hay "Thành phố", chỉ giữ tên riêng, ví dụ
#        'Hồ Chí Minh', 'Hà Nội', 'Lâm Đồng'. Làm vậy để khớp bảng tọa độ thời tiết
#        (bookings/thoi_tiet.py, khóa là tên đã bỏ dấu, bỏ khoảng trắng, viết thường).
#
# File này là Python THUẦN (không import Django, không ghi database) để Tuyền (F2),
# trang Tìm kiếm, Trợ lý và form hồ sơ (F3) dùng lại cùng một danh sách.
# Lệnh nạp vào database: python manage.py nap_khu_vuc
# Kiểm tra riêng:        python core/du_lieu_khu_vuc.py
# =====================================================================
import unicodedata

# (mã số theo Phụ lục I, tên khu vực dùng trong hệ thống, loại đơn vị theo Quyết định)
DANH_SACH_34 = [
    ('01', 'Hà Nội', 'Thành phố'),
    ('04', 'Cao Bằng', 'Tỉnh'),
    ('08', 'Tuyên Quang', 'Tỉnh'),
    ('11', 'Điện Biên', 'Tỉnh'),
    ('12', 'Lai Châu', 'Tỉnh'),
    ('14', 'Sơn La', 'Tỉnh'),
    ('15', 'Lào Cai', 'Tỉnh'),
    ('19', 'Thái Nguyên', 'Tỉnh'),
    ('20', 'Lạng Sơn', 'Tỉnh'),
    ('22', 'Quảng Ninh', 'Tỉnh'),
    ('24', 'Bắc Ninh', 'Tỉnh'),
    ('25', 'Phú Thọ', 'Tỉnh'),
    ('31', 'Hải Phòng', 'Thành phố'),
    ('33', 'Hưng Yên', 'Tỉnh'),
    ('37', 'Ninh Bình', 'Tỉnh'),
    ('38', 'Thanh Hóa', 'Tỉnh'),
    ('40', 'Nghệ An', 'Tỉnh'),
    ('42', 'Hà Tĩnh', 'Tỉnh'),
    ('44', 'Quảng Trị', 'Tỉnh'),
    ('46', 'Huế', 'Thành phố'),
    ('48', 'Đà Nẵng', 'Thành phố'),
    ('51', 'Quảng Ngãi', 'Tỉnh'),
    ('52', 'Gia Lai', 'Tỉnh'),
    ('56', 'Khánh Hòa', 'Tỉnh'),
    ('66', 'Đắk Lắk', 'Tỉnh'),
    ('68', 'Lâm Đồng', 'Tỉnh'),
    ('75', 'Đồng Nai', 'Tỉnh'),
    ('79', 'Hồ Chí Minh', 'Thành phố'),
    ('80', 'Tây Ninh', 'Tỉnh'),
    ('82', 'Đồng Tháp', 'Tỉnh'),
    ('86', 'Vĩnh Long', 'Tỉnh'),
    ('91', 'An Giang', 'Tỉnh'),
    ('92', 'Cần Thơ', 'Thành phố'),
    ('96', 'Cà Mau', 'Tỉnh'),
]

TEN_34 = [ten for _, ten, _ in DANH_SACH_34]

# Tên CŨ (dữ liệu mẫu 5 khu vực của các giai đoạn trước, hoặc cách viết khác) -> tên mới.
# Lệnh nap_khu_vuc dùng bảng này để ĐỔI TÊN bản ghi đã có (giữ nguyên các liên kết với
# hồ sơ Nhiếp ảnh gia), chứ không xóa rồi tạo lại.
TEN_CU_SANG_MOI = {
    'TP. Hồ Chí Minh': 'Hồ Chí Minh',
    'TP.HCM': 'Hồ Chí Minh',
    'TP HCM': 'Hồ Chí Minh',
    'Thành phố Hồ Chí Minh': 'Hồ Chí Minh',
    'Đà Lạt': 'Lâm Đồng',        # Đà Lạt thuộc tỉnh Lâm Đồng
    'Nha Trang': 'Khánh Hòa',    # Nha Trang thuộc tỉnh Khánh Hòa
}


def chuan_hoa(ten):
    """Cùng cách chuẩn hóa với bookings.thoi_tiet._chuan_hoa: 'Hồ Chí Minh' -> 'hochiminh'.
    F2 dùng kết quả này làm khóa của TOA_DO_KHU_VUC."""
    ten = str(ten).lower().replace('đ', 'd')
    ten = unicodedata.normalize('NFD', ten)
    return ''.join(c for c in ten if c.isalnum() and not unicodedata.combining(c))


def kiem_tra():
    """Trả về danh sách lỗi (rỗng là đạt)."""
    loi = []
    if len(DANH_SACH_34) != 34:
        loi.append(f'Cần 34 đơn vị, hiện có {len(DANH_SACH_34)}')
    ma = [m for m, _, _ in DANH_SACH_34]
    if len(set(ma)) != len(ma):
        loi.append('Mã số bị trùng')
    if ma != sorted(ma):
        loi.append('Chưa sắp theo mã số Phụ lục I')
    if len(set(TEN_34)) != len(TEN_34):
        loi.append('Tên bị trùng')
    khoa = {}
    for ten in TEN_34:
        if ten != ten.strip() or '  ' in ten:
            loi.append(f'Khoảng trắng thừa: {ten!r}')
        if ten.startswith(('Tỉnh', 'Thành phố', 'TP')):
            loi.append(f'Tên không được kèm chữ Tỉnh/Thành phố: {ten}')
        k = chuan_hoa(ten)
        if k in khoa:
            loi.append(f'Khóa chuẩn hóa trùng: {ten} và {khoa[k]}')
        khoa[k] = ten
    if sum(1 for _, _, loai in DANH_SACH_34 if loai == 'Thành phố') != 6:
        loi.append('Phải có đúng 6 thành phố')
    for cu, moi in TEN_CU_SANG_MOI.items():
        if moi not in TEN_34:
            loi.append(f'Tên mới {moi!r} (của {cu!r}) không nằm trong 34')
    return loi


if __name__ == '__main__':
    loi = kiem_tra()
    for x in loi:
        print('LỖI:', x)
    print('Số đơn vị:', len(DANH_SACH_34), '| lỗi:', len(loi))
    for ma, ten, loai in DANH_SACH_34:
        print(f'{ma}  {ten:<12} {chuan_hoa(ten):<12} ({loai})')

# =====================================================================
# core/management/commands/_du_lieu_mau.py
# DỮ LIỆU và LỊCH THỜI GIAN của dữ liệu mẫu FRAMIE (Kế hoạch mục 6).
#
# File này là Python THUẦN: không import Django, không ghi database.
# Việc ghi vào database do nap_du_lieu_mau.py làm. Tách ra như vậy để
# kiểm tra riêng các ràng buộc ngày giờ (ví dụ: hạn đặt cọc phải sau
# ngày tạo Booking) mà không cần chạy server.
# Dấu _ ở đầu tên file = Django không coi đây là một lệnh.
#
# Cách kiểm tra riêng:  python core/management/commands/_du_lieu_mau.py
# =====================================================================
import os
from datetime import timedelta
from zoneinfo import ZoneInfo

from core.constants import (BenThucHien as BEN, LoaiAnh, LoaiHauKy,
                            TrangThaiBooking as TT, TrangThaiSlot,
                            TrangThaiThanhToan as TTT)

MUI_GIO = ZoneInfo('Asia/Ho_Chi_Minh')
MAT_KHAU_MAU = 'Framie@2026'
DUOI_EMAIL = '@example.com'          # mọi tài khoản mẫu có đuôi này => lệnh biết đường xóa

# ---------------------------------------------------------------------
# 1. DANH MỤC
# ---------------------------------------------------------------------
LOAI_HINH = ['Chân dung', 'Cưới', 'Gia đình', 'Sự kiện', 'Sản phẩm', 'Thời trang']
PHONG_CACH = ['Tối giản', 'Điện ảnh', 'Hoài niệm', 'Tự nhiên', 'Editorial', 'Đen trắng']
# Tên khu vực không kèm chữ Tỉnh/Thành phố (F1). Chỉ số 0..4 được dùng ở trường kv bên dưới.
KHU_VUC = ['Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Lâm Đồng', 'Khánh Hòa']

# ---------------------------------------------------------------------
# 2. NGƯỜI DÙNG (toàn thông tin giả)
# ---------------------------------------------------------------------
# ho, ten, user, sdt, ngân hàng, số TK, loại hình (chỉ số), phong cách, khu vực, trạng thái hồ sơ
NHIEP_ANH_GIA = [
    # --- 7 hồ sơ ĐÃ DUYỆT (chỉ số 0..6) ---
    dict(ho='Lê', ten='Minh Khôi', user='nag01', sdt='0900000001', nh='Vietcombank',
         stk='9704000000000001', loai=[0, 2], pc=[0, 3], kv=[0, 2], hs='Đã duyệt'),
    dict(ho='Trần', ten='Bảo Ngọc', user='nag02', sdt='0900000002', nh='Techcombank',
         stk='9704000000000002', loai=[1, 2], pc=[1, 5], kv=[0, 3, 2], hs='Đã duyệt'),
    dict(ho='Phạm', ten='Gia Huy', user='nag03', sdt='0900000003', nh='MB Bank',
         stk='9704000000000003', loai=[3, 0], pc=[2, 4], kv=[1, 2], hs='Đã duyệt'),
    dict(ho='Võ', ten='Thanh Trúc', user='nag04', sdt='0900000004', nh='ACB',
         stk='9704000000000004', loai=[5, 0], pc=[4, 0], kv=[0, 1, 2], hs='Đã duyệt'),
    # nag05 là NAG CHÍNH của buổi demo (F4): ở Đà Nẵng, 3 loại hình, ảnh Portfolio thật, QR thật, Booking thời tiết và Slider
    dict(ho='Đặng', ten='Quốc Anh', user='nag05', sdt='0900000005', nh='MB Bank',
         stk='9704000000000005', loai=[0, 1, 2], pc=[3, 1, 4], kv=[2], hs='Đã duyệt'),
    dict(ho='Hoàng', ten='Mỹ Linh', user='nag06', sdt='0900000006', nh='VPBank',
         stk='9704000000000006', loai=[1, 3], pc=[3, 1], kv=[4, 2], hs='Đã duyệt'),
    dict(ho='Bùi', ten='Đức Long', user='nag07', sdt='0900000007', nh='Sacombank',
         stk='9704000000000007', loai=[2, 1], pc=[5, 2], kv=[3, 2], hs='Đã duyệt'),
    # --- 2 hồ sơ CHỜ DUYỆT (chỉ số 7, 8) ---
    dict(ho='Ngô', ten='Khánh Vy', user='nag08', sdt='0900000008', nh='TPBank',
         stk='9704000000000008', loai=[0], pc=[3], kv=[0], hs='Chờ duyệt'),
    dict(ho='Đỗ', ten='Hải Đăng', user='nag09', sdt='0900000009', nh='VIB',
         stk='9704000000000009', loai=[3], pc=[1], kv=[1], hs='Chờ duyệt'),
    # --- 1 hồ sơ ĐÃ TỪ CHỐI (chỉ số 9) ---
    dict(ho='Vũ', ten='Tuấn Kiệt', user='nag10', sdt='0900000010', nh='Agribank',
         stk='9704000000000010', loai=[4], pc=[0], kv=[0], hs='Đã từ chối'),
]
SO_NAG_DA_DUYET = 7

KHACH_HANG = [
    dict(ho='Nguyễn', ten='Thảo My', user='kh01', sdt='0910000001'),
    dict(ho='Lý', ten='Hoàng Nam', user='kh02', sdt='0910000002'),
    dict(ho='Phan', ten='Ngọc Hân', user='kh03', sdt='0910000003'),
    dict(ho='Trương', ten='Anh Tuấn', user='kh04', sdt='0910000004'),
    dict(ho='Huỳnh', ten='Bích Phượng', user='kh05', sdt='0910000005'),
    dict(ho='Mai', ten='Đình Phúc', user='kh06', sdt='0910000006'),
    dict(ho='Dương', ten='Khả Hân', user='kh07', sdt='0910000007'),
    dict(ho='Cao', ten='Thế Vinh', user='kh08', sdt='0910000008'),
]
QUAN_TRI_VIEN = dict(ho='Quản trị', ten='Mẫu', user='admin_mau', sdt='0920000001')


def email_that():
    """{username: email thật} của các tài khoản mẫu đã được đặt email thật.
    Đặt trong file .env (không đưa lên GitHub), ví dụ:  DEMO_EMAIL_NAG05=ten+nag05@gmail.com  và  DEMO_EMAIL_KH01=ten+kh01@gmail.com
    Quy tắc tên biến: DEMO_EMAIL_ + username viết HOA. Mỗi email phải khác nhau (email là duy nhất và dùng để đăng nhập)."""
    ket_qua = {}
    for p in NHIEP_ANH_GIA + KHACH_HANG + [QUAN_TRI_VIEN]:
        gia_tri = os.environ.get(f"DEMO_EMAIL_{p['user'].upper()}", '').strip()
        if gia_tri:
            ket_qua[p['user']] = gia_tri
    return ket_qua


def email_cua(user):
    """Email của tài khoản mẫu: mặc định user@example.com (email giả, hệ thống không gửi tới được); có đặt DEMO_EMAIL_<USER> thì dùng email thật đó."""
    return email_that().get(user) or f'{user}{DUOI_EMAIL}'


GIOI_THIEU = {
    0: 'Chuyên chụp chân dung tự nhiên, ưu tiên ánh sáng sẵn có và cảm xúc thật của người được chụp.',
    1: 'Chụp ảnh cưới và gia đình theo phong cách điện ảnh, nhẹ nhàng, tôn trọng khoảnh khắc.',
    2: 'Nhiếp ảnh sự kiện và chân dung báo chí, làm việc nhanh gọn và đúng hẹn.',
    3: 'Thời trang và chân dung phong cách editorial, có sẵn ekip trang điểm khi cần.',
    4: 'Chân dung, ảnh cưới ngoại cảnh và ảnh gia đình tại Đà Nẵng, Hội An. Phong cách tự nhiên, điện ảnh, giữ trọn khoảnh khắc.',
    5: 'Ảnh cưới ngoại cảnh và sự kiện, thích bắt khoảnh khắc đời thường giữa thiên nhiên.',
    6: 'Ảnh gia đình, trẻ em và kỷ niệm, phong cách đen trắng hoài niệm.',
    7: 'Mới bắt đầu nhận khách chụp chân dung, mong được góp ý để hoàn thiện hồ sơ.',
    8: 'Nhiếp ảnh sự kiện, có kinh nghiệm chụp hội thảo và tiệc công ty.',
    9: 'Chụp ảnh sản phẩm tại nhà, đang hoàn thiện danh mục ảnh.',
}

# ---------------------------------------------------------------------
# 3. GÓI DỊCH VỤ, PROJECT
# ---------------------------------------------------------------------
TEN_GOI = {  # theo chỉ số loại hình: (gói giới hạn, gói toàn bộ, gói thứ ba)
    0: ('Chân dung cơ bản', 'Chân dung nâng cao', 'Chân dung ngoại cảnh (cũ)'),
    1: ('Cưới - lễ gia tiên', 'Cưới - trọn ngày', 'Cưới - album mini (cũ)'),
    2: ('Gia đình nhỏ', 'Gia đình trọn gói', 'Gia đình - ngày lễ (cũ)'),
    3: ('Sự kiện nửa ngày', 'Sự kiện cả ngày', 'Sự kiện - gói tiết kiệm (cũ)'),
    4: ('Sản phẩm 10 mẫu', 'Sản phẩm trọn bộ', 'Sản phẩm - lookbook (cũ)'),
    5: ('Thời trang 1 look', 'Thời trang lookbook', 'Thời trang - capsule (cũ)'),
}
TEN_PROJECT = ['Ánh sáng buổi sớm', 'Sắc xám thành phố', 'Khoảnh khắc đời thường', 'Một ngày dài']
# Địa điểm chụp theo đúng định dạng của form đặt lịch: "<Khu vực> - <Địa chỉ>". Thẻ thời tiết (E8) lấy phần đầu làm khu vực.
DIA_DIEM_THEO_KV = {      # chỉ số khu vực (KHU_VUC) -> các địa điểm
    0: ['Hồ Chí Minh - Công viên Gia Định', 'Hồ Chí Minh - Studio Framie, Quận 3', 'Hồ Chí Minh - Nhà thờ Đức Bà'],
    1: ['Hà Nội - Hồ Gươm', 'Hà Nội - Hồ Tây', 'Hà Nội - Phố cổ'],
    2: ['Đà Nẵng - Bãi Xép', 'Đà Nẵng - Phố cổ Hội An', 'Đà Nẵng - Cầu Rồng', 'Đà Nẵng - Bán đảo Sơn Trà'],
    3: ['Lâm Đồng - Đồi chè Cầu Đất', 'Lâm Đồng - Hồ Xuân Hương'],
    4: ['Khánh Hòa - Bãi Dài, Nha Trang', 'Khánh Hòa - Tháp Bà Ponagar'],
}


def dia_diem_cua(nag, khach):
    """Địa điểm của một Booking: luôn nằm trong khu vực Nhiếp ảnh gia nhận chụp."""
    kv = NHIEP_ANH_GIA[nag]['kv']
    ds = DIA_DIEM_THEO_KV[kv[khach % len(kv)]]
    return ds[(nag + khach) % len(ds)]


CONCEPT = ['Tối giản, tông trắng và xám', 'Phong cách điện ảnh, ánh sáng ấm',
           'Tự nhiên, nhiều khoảnh khắc đời thường', 'Đen trắng hoài niệm']


# Giá nền theo loại hình (đồng) cho các loại hình THỨ HAI, THỨ BA của một NAG: (gói giới hạn ảnh, gói toàn bộ)
GIA_THEO_LOAI = {0: (1500000, 3000000), 1: (4500000, 9000000), 2: (2000000, 4000000),
                 3: (3500000, 7000000), 4: (2500000, 5000000), 5: (3000000, 6000000)}


def goi_cua(chi_so_nag):
    """Các gói của một nhiếp ảnh gia ĐÃ DUYỆT (F4: mỗi loại hình của NAG có 2 gói, khác giá, thời lượng, số ảnh).
    Loại hình ĐẦU TIÊN là loại 'chính': các Booking mẫu dùng gói của loại này (khóa 'chinh'), và nếu chỉ số NAG chẵn
    thì loại này có thêm gói thứ ba đã ngừng/ẩn."""
    i = chi_so_nag
    ds = []
    for k, loai in enumerate(NHIEP_ANH_GIA[i]['loai'][:3]):
        ten = TEN_GOI[loai]
        if k == 0:
            gia_gh, gia_tb = 1500000 + 100000 * (i % 4), 3000000 + 200000 * (i % 3)
            tl_gh, so_anh = 60 + 30 * (i % 3), 6 + 2 * (i % 3)
        else:
            nen_gh, nen_tb = GIA_THEO_LOAI[loai]
            gia_gh, gia_tb = nen_gh + 100000 * ((i + k) % 4), nen_tb + 200000 * ((i + k) % 3)
            tl_gh, so_anh = 90 + 30 * ((i + k) % 3), 8 + 2 * ((i + k) % 3)
        ds.append(dict(ten=ten[0], loai_hinh=loai, gia=gia_gh, thoi_luong=tl_gh, hau_ky=LoaiHauKy.GIOI_HAN,
                       so_anh=so_anh, trang_thai='Đang áp dụng', chinh=(k == 0)))
        ds.append(dict(ten=ten[1], loai_hinh=loai, gia=gia_tb, thoi_luong=180 + 60 * k, hau_ky=LoaiHauKy.TOAN_BO,
                       so_anh=None, trang_thai='Đang áp dụng', chinh=(k == 0)))
        if k == 0 and i % 2 == 0:  # NAG số 0, 2, 4, 6 có thêm gói thứ ba đã ngừng/ẩn
            ds.append(dict(ten=ten[2], loai_hinh=loai, gia=2000000, thoi_luong=120, hau_ky=LoaiHauKy.GIOI_HAN,
                           so_anh=10, trang_thai='Ngừng áp dụng' if i % 4 == 0 else 'Đã ẩn', chinh=True))
    return ds


# Project THẬT của nag05 (F4). 'thu_muc' là thư mục con của du_lieu_mau/anh/nag05 chứa ảnh 01.jpg, 02.jpg... và bia.jpg
PROJECT_NAG_CHINH = [
    dict(ten='Cưới - Khởi đầu mới', loai_hinh=1, thu_muc='cuoi', so_anh=8, ngay=34,
         concept='Ngoại cảnh, phong cách điện ảnh, cỏ xanh và bầu trời rộng'),
    dict(ten='Gia đình - Khoảnh khắc lưu mãi', loai_hinh=2, thu_muc='gia_dinh', so_anh=8, ngay=64,
         concept='Tự nhiên, công viên lúc nắng dịu, bóng bay và nụ cười của trẻ nhỏ'),
    dict(ten='Chân dung', loai_hinh=0, thu_muc='chan_dung', so_anh=7, ngay=94,
         concept='Editorial, nền trắng, sơ mi xanh sọc và đồ vật cổ điển'),
]
CHI_SO_NAG_CHINH = 4   # nag05
# 2 NAG còn lại trong top 3 "Nhiếp ảnh gia nổi bật" ở Trang chủ (điểm trung bình cao nhất trong dữ liệu mẫu): nag02, nag06.
# Thẻ nổi bật lấy ảnh bìa của project MỚI NHẤT, nên hai người này cũng phải có ảnh Portfolio thật (xem nguon_project trong nap_du_lieu_mau.py).
CHI_SO_NAG_NOI_BAT = (1, 5)
THU_MUC_THEO_LOAI = {0: 'chan_dung', 1: 'cuoi', 2: 'gia_dinh'}   # chỉ số loại hình (LOAI_HINH) -> thư mục ảnh của nag05; loại khác dùng 'cuoi'
# Ảnh dùng làm BÌA cho NAG khác (nổi bật ở Trang chủ): chỉ chọn ảnh không dính logo/watermark/số trang của bên khác (xem NGUON_ANH.md)
ANH_BIA_SACH = {'cuoi': ['02.jpg', '04.jpg', '05.jpg', '07.jpg'], 'gia_dinh': ['05.jpg'],
                'chan_dung': ['01.jpg', '02.jpg', '03.jpg', '04.jpg', '05.jpg', '06.jpg', '07.jpg']}


def project_cua(chi_so_nag, now):
    """3-4 project, mỗi project 5-8 ảnh. NAG chính (nag05) có 3 project thật theo PROJECT_NAG_CHINH."""
    i = chi_so_nag
    if i == CHI_SO_NAG_CHINH:
        return [dict(ten=p['ten'], loai_hinh=p['loai_hinh'], concept=p['concept'], so_anh=p['so_anh'],
                     ngay_chup=(now - timedelta(days=p['ngay'])).date(), thu_muc=p['thu_muc'])
                for p in PROJECT_NAG_CHINH]
    loai_ds = NHIEP_ANH_GIA[i]['loai']
    ds = []
    for j in range(3 + (i % 2)):
        ds.append(dict(ten=f'{TEN_PROJECT[j]}', loai_hinh=loai_ds[j % len(loai_ds)],
                       concept=CONCEPT[(i + j) % len(CONCEPT)],
                       ngay_chup=(now - timedelta(days=30 * (j + 1) + i)).date(),
                       so_anh=5 + ((i + j) % 4), thu_muc=None))
    return ds


# ---------------------------------------------------------------------
# 4. LỊCH THỜI GIAN CỦA BOOKING
# ---------------------------------------------------------------------
def _chup_luc(now, so_ngay, gio):
    """Thời điểm chụp = (hôm nay + so_ngay) lúc `gio` giờ, theo giờ Việt Nam."""
    n = now.astimezone(MUI_GIO)
    return (n + timedelta(days=so_ngay)).replace(hour=gio, minute=0, second=0, microsecond=0)


def _chuoi_buoc(goi_gioi_han):
    ds = [TT.CHO_XAC_NHAN, TT.CHO_DAT_COC, TT.CHOT_BOOKING, TT.DA_CHUP]
    if goi_gioi_han:
        ds.append(TT.CHO_KH_CHON_ANH)
    return ds + [TT.CHO_HAU_KY, TT.DANG_HAU_KY, TT.CHO_KH_KIEM_TRA,
                 TT.CHO_XAC_NHAN_THANH_TOAN, TT.HOAN_THANH]


_NOI_DUNG = {
    TT.CHO_DAT_COC: (BEN.NHIEP_ANH_GIA, 'Nhiếp ảnh gia chấp nhận Booking'),
    TT.CHOT_BOOKING: (BEN.NHIEP_ANH_GIA, 'Nhiếp ảnh gia xác nhận đã nhận đủ tiền cọc'),
    TT.DA_CHUP: (BEN.NHIEP_ANH_GIA, 'Buổi chụp đã hoàn tất'),
    TT.CHO_KH_CHON_ANH: (BEN.NHIEP_ANH_GIA, 'Nhiếp ảnh gia tải ảnh chưa hậu kỳ'),
    TT.CHO_HAU_KY: (BEN.NHIEP_ANH_GIA, ''),
    TT.DANG_HAU_KY: (BEN.NHIEP_ANH_GIA, 'Nhiếp ảnh gia bắt đầu hậu kỳ'),
    TT.CHO_KH_KIEM_TRA: (BEN.NHIEP_ANH_GIA, 'Nhiếp ảnh gia tải ảnh đã hậu kỳ'),
    TT.CHO_XAC_NHAN_THANH_TOAN: (BEN.KHACH_HANG, 'Khách hàng xác nhận hoàn tất bàn giao'),
    TT.HOAN_THANH: (BEN.NHIEP_ANH_GIA, 'Nhiếp ảnh gia xác nhận đã nhận đủ 60%'),
}


def lich_su_tu_moc(cuoi, gioi_han, t, lap_chinh_sua=(), ben_huy=None, ly_do_huy=None,
                   ly_do_tu_choi=None):
    """Sinh danh sách dòng LichSuTrangThaiBooking.
    t = {trạng thái: thời điểm vào trạng thái đó}. Mỗi dòng: (cũ, mới, thời điểm, bên, lý do)."""
    hang = [(None, TT.CHO_XAC_NHAN, t[TT.CHO_XAC_NHAN], BEN.KHACH_HANG, 'Khách hàng gửi yêu cầu đặt lịch')]
    chuoi = _chuoi_buoc(gioi_han)
    if cuoi in chuoi:
        dung_o = chuoi.index(cuoi)
        di = chuoi[1:dung_o + 1]
        truoc = TT.CHO_XAC_NHAN
    else:
        # nhánh kết thúc không thành công: đi tới bước "điểm rẽ" rồi rẽ
        diem_re = {TT.DA_TU_CHOI: TT.CHO_XAC_NHAN, TT.HET_THOI_HAN_DAT_COC: TT.CHO_DAT_COC,
                   TT.DA_HUY: TT.CHOT_BOOKING}[cuoi]
        di = chuoi[1:chuoi.index(diem_re) + 1]
        truoc = TT.CHO_XAC_NHAN
    for s in di:
        ben, ly_do = _NOI_DUNG[s]
        if s == TT.CHO_HAU_KY:
            ben = BEN.KHACH_HANG if gioi_han else BEN.NHIEP_ANH_GIA
            ly_do = 'Khách hàng chọn xong ảnh' if gioi_han else 'Gói hậu kỳ toàn bộ, chuyển thẳng sang chờ hậu kỳ'
        hang.append((truoc, s, t[s], ben, ly_do))
        truoc = s
        if s == TT.CHO_KH_KIEM_TRA:
            for (t_yc, t_nop_lai) in lap_chinh_sua:
                hang.append((TT.CHO_KH_KIEM_TRA, TT.DANG_HAU_KY, t_yc, BEN.KHACH_HANG,
                             'Khách hàng yêu cầu chỉnh sửa'))
                hang.append((TT.DANG_HAU_KY, TT.CHO_KH_KIEM_TRA, t_nop_lai, BEN.NHIEP_ANH_GIA,
                             'Nhiếp ảnh gia tải ảnh đã chỉnh sửa'))
    if cuoi == TT.DA_TU_CHOI:
        hang.append((truoc, cuoi, t[cuoi], BEN.NHIEP_ANH_GIA, ly_do_tu_choi))
    elif cuoi == TT.HET_THOI_HAN_DAT_COC:
        hang.append((truoc, cuoi, t[cuoi], BEN.HE_THONG, 'Quá 1 ngày chưa đặt cọc'))
    elif cuoi == TT.DA_HUY:
        hang.append((truoc, cuoi, t[cuoi], ben_huy, ly_do_huy))
    return hang


def _bk(ma, nag, khach, gioi_han, cuoi, tao, chup, t, **kw):
    """Dựng một Booking mẫu. t = thời điểm vào từng trạng thái (đã tính sẵn)."""
    s = dict(ma=ma, nag=nag, khach=khach, gioi_han=gioi_han, trang_thai=cuoi, tao=tao, chup=chup,
             dia_diem=dia_diem_cua(nag, khach), so_nguoi=1 + (khach % 4),
             concept=CONCEPT[(nag + khach) % len(CONCEPT)],
             yeu_cau='Mong nhiếp ảnh gia liên hệ trước buổi chụp 1 ngày.' if khach % 2 == 0 else None,
             ly_do_tu_choi=None, han_coc=None, han_chon=None, han_hau_ky=None, han_tt=None,
             slot_trang_thai=TrangThaiSlot.DA_DAT, coc=None, con_lai=None, ban_giao=None,
             anh=None, chinh_sua=[], huy=None, danh_gia=None, tai_anh=[], co_giu_cho=True)
    s.update(kw)
    if TT.CHO_DAT_COC in t:
        s['han_coc'] = t[TT.CHO_DAT_COC] + timedelta(days=1)
    # han_chon luôn None: Khách chọn ảnh hậu kỳ không còn hạn 2 ngày
    if TT.DANG_HAU_KY in t:
        s['han_hau_ky'] = t[TT.DANG_HAU_KY] + timedelta(days=3)
    if TT.CHO_XAC_NHAN_THANH_TOAN in t:
        s['han_tt'] = t[TT.CHO_XAC_NHAN_THANH_TOAN] + timedelta(days=2)
    s['t'] = t
    if 'lich_su' not in s:
        s['lich_su'] = lich_su_tu_moc(cuoi, gioi_han, t, s.pop('lap_chinh_sua', ()),
                                      s['huy']['ben'] if s['huy'] else None,
                                      s['huy']['ly_do'] if s['huy'] else None,
                                      s['ly_do_tu_choi'])
    return s


def _chuoi_moc(tao, **moc):
    d = {TT.CHO_XAC_NHAN: tao}
    d.update(moc)
    return d


def lich_booking(now):
    """19 Booking mẫu BK01..BK19 (mục 6.2 và F4). Mọi mốc thời gian tính từ `now`."""
    h = timedelta
    N = now
    ds = []

    # BK01 Chờ xác nhận
    tao = N - h(hours=3)
    ds.append(_bk('BK01', 0, 0, False, TT.CHO_XAC_NHAN, tao, _chup_luc(N, 5, 9), _chuoi_moc(tao),
                  slot_trang_thai=TrangThaiSlot.DANG_GIU))
    # BK02 Chờ đặt cọc (còn hạn)
    tao = N - h(hours=6)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: N - h(hours=5)})
    ds.append(_bk('BK02', 1, 1, False, TT.CHO_DAT_COC, tao, _chup_luc(N, 7, 14), t,
                  slot_trang_thai=TrangThaiSlot.DANG_GIU))
    # BK03 Chờ đặt cọc (đã có minh chứng)
    tao = N - h(hours=22)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: N - h(hours=21)})
    ds.append(_bk('BK03', 2, 2, False, TT.CHO_DAT_COC, tao, _chup_luc(N, 6, 9), t,
                  slot_trang_thai=TrangThaiSlot.DANG_GIU,
                  coc=dict(trang_thai=TTT.CHO_XAC_NHAN_COC, ngay_tt=N - h(hours=2), ngay_xn=None, minh_chung=True)))
    # BK04 Chốt Booking
    tao = N - h(days=4)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=3)})
    ds.append(_bk('BK04', 3, 3, False, TT.CHOT_BOOKING, tao, _chup_luc(N, 4, 10), t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=3, hours=3),
                           ngay_xn=N - h(days=3), minh_chung=True)))
    # BK05 Đã chụp, gói giới hạn (chưa có ảnh)
    tao = N - h(days=9)
    chup = _chup_luc(N, -1, 9)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=8),
                           TT.DA_CHUP: chup + h(hours=3)})
    ds.append(_bk('BK05', 4, 4, True, TT.DA_CHUP, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=8, hours=2),
                           ngay_xn=N - h(days=8), minh_chung=True)))
    # BK06 Chờ Khách hàng lựa chọn ảnh (gói giới hạn, 14 ảnh chưa hậu kỳ)
    tao = N - h(days=10)
    chup = _chup_luc(N, -2, 9)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=9),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_KH_CHON_ANH: N - h(days=1)})
    ds.append(_bk('BK06', 5, 5, True, TT.CHO_KH_CHON_ANH, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=9, hours=2),
                           ngay_xn=N - h(days=9), minh_chung=True),
                  anh=dict(so_luong=14, loai=LoaiAnh.CHUA_HAU_KY, chon=0, ngay=t[TT.CHO_KH_CHON_ANH])))
    # BK07 Chờ hậu kỳ (gói hậu kỳ toàn bộ, 8 ảnh)
    tao = N - h(days=11)
    chup = _chup_luc(N, -3, 9)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=10),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: N - h(days=2)})
    ds.append(_bk('BK07', 6, 6, False, TT.CHO_HAU_KY, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=10, hours=2),
                           ngay_xn=N - h(days=10), minh_chung=True),
                  anh=dict(so_luong=8, loai=LoaiAnh.CHUA_HAU_KY, chon=8, ngay=t[TT.CHO_HAU_KY])))
    # BK08 Đang hậu kỳ (gói giới hạn: 14 ảnh, khách đã chọn đủ số ảnh tối đa của gói)
    tao = N - h(days=14)
    chup = _chup_luc(N, -6, 14)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=12),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_KH_CHON_ANH: N - h(days=5),
                           TT.CHO_HAU_KY: N - h(days=4), TT.DANG_HAU_KY: N - h(days=1)})
    ds.append(_bk('BK08', 0, 7, True, TT.DANG_HAU_KY, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=12, hours=2),
                           ngay_xn=N - h(days=12), minh_chung=True),
                  anh=dict(so_luong=14, loai=LoaiAnh.CHUA_HAU_KY, chon='toi_da', ngay=t[TT.CHO_KH_CHON_ANH])))
    # BK09 Chờ Khách hàng kiểm tra (đã dùng 2 lần chỉnh sửa). F4: của NAG chính (nag05) và Khách kh01, dùng cho Slider trước/sau:
    # 3 ảnh đầu có bản trước (màu), bản hiện tại là bản hậu kỳ đen trắng.
    tao = N - h(days=20)
    chup = _chup_luc(N, -14, 9)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=18),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: N - h(days=13),
                           TT.DANG_HAU_KY: N - h(days=12), TT.CHO_KH_KIEM_TRA: N - h(days=9)})
    lap = [(N - h(days=8), N - h(days=6)), (N - h(days=5), N - h(days=3))]
    ds.append(_bk('BK09', CHI_SO_NAG_CHINH, 0, False, TT.CHO_KH_KIEM_TRA, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=18, hours=2),
                           ngay_xn=N - h(days=18), minh_chung=True),
                  anh=dict(so_luong=7, loai=LoaiAnh.DA_HAU_KY, chon=7, ngay=t[TT.CHO_KH_KIEM_TRA],
                           phien_ban={0: 2, 1: 3, 2: 2}),
                  chinh_sua=[
                      dict(so_lan=1, ngay=lap[0][0], noi_dung='Ảnh hơi tối, mong chỉnh sáng lại một chút.',
                           anh=[(0, 'Tăng sáng khuôn mặt'), (1, 'Giảm độ tương phản')]),
                      dict(so_lan=2, ngay=lap[1][0], noi_dung='Chỉnh lại màu da cho tự nhiên hơn.',
                           anh=[(1, 'Màu da tự nhiên hơn'), (2, 'Cắt lại khung dọc')]),
                  ],
                  lap_chinh_sua=lap))
    # BK10 Chờ xác nhận thanh toán (còn hạn 2 ngày, khách chưa tải minh chứng 60%)
    tao = N - h(days=15)
    chup = _chup_luc(N, -9, 9)
    xn_bg = N - h(minutes=10)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=13),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: N - h(days=8),
                           TT.DANG_HAU_KY: N - h(days=7), TT.CHO_KH_KIEM_TRA: N - h(days=4),
                           TT.CHO_XAC_NHAN_THANH_TOAN: xn_bg})
    ds.append(_bk('BK10', 2, 1, False, TT.CHO_XAC_NHAN_THANH_TOAN, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=13, hours=2),
                           ngay_xn=N - h(days=13), minh_chung=True),
                  con_lai=dict(trang_thai=TTT.CHO_XAC_NHAN_60, ngay_tt=None, ngay_xn=None, minh_chung=False),
                  ban_giao=dict(ngay_xn=xn_bg, thoi_han=None),
                  anh=dict(so_luong=8, loai=LoaiAnh.DA_HAU_KY, chon=8, ngay=t[TT.CHO_KH_KIEM_TRA])))
    # BK11 Chờ xác nhận thanh toán (Quá hạn thanh toán)
    tao = N - h(days=26)
    chup = _chup_luc(N, -20, 9)
    xn_bg = N - h(days=3)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=24),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: N - h(days=19),
                           TT.DANG_HAU_KY: N - h(days=18), TT.CHO_KH_KIEM_TRA: N - h(days=14),
                           TT.CHO_XAC_NHAN_THANH_TOAN: xn_bg})
    ds.append(_bk('BK11', 3, 2, False, TT.CHO_XAC_NHAN_THANH_TOAN, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=24, hours=2),
                           ngay_xn=N - h(days=24), minh_chung=True),
                  con_lai=dict(trang_thai=TTT.QUA_HAN, ngay_tt=None, ngay_xn=None, minh_chung=False),
                  ban_giao=dict(ngay_xn=xn_bg, thoi_han=None),
                  anh=dict(so_luong=8, loai=LoaiAnh.DA_HAU_KY, chon=8, ngay=t[TT.CHO_KH_KIEM_TRA])))
    # BK12 Hoàn thành, còn hạn tải, chưa đánh giá
    tao = N - h(days=22)
    chup = _chup_luc(N, -15, 9)
    xn_bg = N - h(days=6)
    ht = N - h(days=1)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=20),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: N - h(days=14),
                           TT.DANG_HAU_KY: N - h(days=13), TT.CHO_KH_KIEM_TRA: N - h(days=9),
                           TT.CHO_XAC_NHAN_THANH_TOAN: xn_bg, TT.HOAN_THANH: ht})
    ds.append(_bk('BK12', 4, 3, False, TT.HOAN_THANH, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=20, hours=2),
                           ngay_xn=N - h(days=20), minh_chung=True),
                  con_lai=dict(trang_thai=TTT.DA_THANH_TOAN, ngay_tt=ht - h(hours=2), ngay_xn=ht, minh_chung=True),
                  ban_giao=dict(ngay_xn=xn_bg, thoi_han=ht + h(days=3)),
                  anh=dict(so_luong=8, loai=LoaiAnh.HOAN_CHINH, chon=8, ngay=t[TT.CHO_KH_KIEM_TRA])))
    # BK13 Hoàn thành, ảnh đã xóa, đã đánh giá
    tao = N - h(days=52)
    chup = _chup_luc(N, -45, 9)
    xn_bg = N - h(days=34)
    ht = N - h(days=32)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=50),
                           TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: N - h(days=43),
                           TT.DANG_HAU_KY: N - h(days=42), TT.CHO_KH_KIEM_TRA: N - h(days=38),
                           TT.CHO_XAC_NHAN_THANH_TOAN: xn_bg, TT.HOAN_THANH: ht})
    ds.append(_bk('BK13', 5, 4, False, TT.HOAN_THANH, tao, chup, t,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=50, hours=2),
                           ngay_xn=N - h(days=50), minh_chung=True),
                  con_lai=dict(trang_thai=TTT.DA_THANH_TOAN, ngay_tt=ht - h(hours=2), ngay_xn=ht, minh_chung=True),
                  ban_giao=dict(ngay_xn=xn_bg, thoi_han=ht + h(days=3)),
                  anh=dict(so_luong=8, loai=LoaiAnh.HOAN_CHINH, chon=8, ngay=t[TT.CHO_KH_KIEM_TRA],
                           luu_tru='Đã xóa'),
                  tai_anh=[(ht + h(hours=5), True), (ht + h(hours=5, minutes=2), True),
                           (ht + h(days=1), True), (ht + h(days=1, hours=1), False)],
                  danh_gia=dict(diem=5, nhan_xet='Ảnh đẹp, nhiếp ảnh gia nhiệt tình và đúng hẹn.',
                                ngay=ht + h(days=1))))
    # BK14 Đã từ chối
    tao = N - h(days=2)
    ly = 'Nhiếp ảnh gia đã có lịch riêng vào ngày này.'
    t = _chuoi_moc(tao, **{TT.DA_TU_CHOI: tao + h(hours=5)})
    ds.append(_bk('BK14', 6, 5, False, TT.DA_TU_CHOI, tao, _chup_luc(N, 6, 9), t,
                  ly_do_tu_choi=ly, slot_trang_thai=TrangThaiSlot.TRONG))
    # BK15 Hết thời hạn đặt cọc
    tao = N - h(days=4)
    cdc = tao + h(hours=1)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: cdc, TT.HET_THOI_HAN_DAT_COC: cdc + h(days=1, minutes=1)})
    ds.append(_bk('BK15', 0, 6, False, TT.HET_THOI_HAN_DAT_COC, tao, _chup_luc(N, 4, 9), t,
                  slot_trang_thai=TrangThaiSlot.TRONG))
    # BK16 Đã hủy (Khách hủy sau khi cọc => Mất cọc)
    tao = N - h(days=7)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=6),
                           TT.DA_HUY: N - h(days=1)})
    ds.append(_bk('BK16', 1, 7, False, TT.DA_HUY, tao, _chup_luc(N, 3, 9), t,
                  slot_trang_thai=TrangThaiSlot.TRONG,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=6, hours=2),
                           ngay_xn=N - h(days=6), minh_chung=True),
                  huy=dict(ben='Khách hàng', ly_do='Khách thay đổi kế hoạch, không thể đi chụp.',
                           trang_thai_luc_huy=TT.CHOT_BOOKING, xu_ly='Mất cọc',
                           hoan_tien=None, ngay=N - h(days=1), ngay_xn_hoan=None)))
    # BK17 Đã hủy (Nhiếp ảnh gia hủy sau khi cọc => Hoàn cọc, Chờ hoàn tiền)
    tao = N - h(days=8)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=7),
                           TT.DA_HUY: N - h(days=2)})
    ds.append(_bk('BK17', 2, 0, False, TT.DA_HUY, tao, _chup_luc(N, 5, 9), t,
                  slot_trang_thai=TrangThaiSlot.TRONG,
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=7, hours=2),
                           ngay_xn=N - h(days=7), minh_chung=True),
                  huy=dict(ben='Nhiếp ảnh gia', ly_do='Nhiếp ảnh gia bị ốm, không thể thực hiện buổi chụp.',
                           trang_thai_luc_huy=TT.CHOT_BOOKING, xu_ly='Hoàn cọc',
                           hoan_tien='Chờ hoàn tiền', ngay=N - h(days=2), ngay_xn_hoan=None)))
    # BK18 (F4) Chốt Booking của NAG chính, buổi chụp 3 ngày nữa ở Đà Nẵng: thẻ dự báo thời tiết hiện cho Khách kh01 và nag05
    tao = N - h(days=3)
    t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: N - h(days=2)})
    ds.append(_bk('BK18', CHI_SO_NAG_CHINH, 0, False, TT.CHOT_BOOKING, tao, _chup_luc(N, 3, 9), t,
                  dia_diem='Đà Nẵng - Bãi Xép',
                  coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=N - h(days=2, hours=3),
                           ngay_xn=N - h(days=2), minh_chung=True)))
    # BK19 (F4) Chờ xác nhận của NAG chính, buổi chụp 9 ngày nữa ở Hội An: nag05 đăng nhập sẽ thấy yêu cầu mới để chấp nhận
    tao = N - h(hours=5)
    ds.append(_bk('BK19', CHI_SO_NAG_CHINH, 2, False, TT.CHO_XAC_NHAN, tao, _chup_luc(N, 9, 14), _chuoi_moc(tao),
                  dia_diem='Đà Nẵng - Phố cổ Hội An', slot_trang_thai=TrangThaiSlot.DANG_GIU))
    return ds


DIEM_NEN = [(5, 4), (5, 5), (4, 5), (4, 4), (5, 5), (5, 4), (4, 5)]
NHAN_XET_NEN = ['Buổi chụp rất thoải mái, ảnh đẹp hơn mong đợi.', 'Giao ảnh đúng hạn, màu ảnh dễ nhìn.',
                'Nhiếp ảnh gia chu đáo, hướng dẫn tạo dáng tự nhiên.', 'Sẽ tiếp tục đặt lịch lần sau.']


def lich_nen(now):
    """Mỗi nhiếp ảnh gia đã duyệt thêm 2 Booking 'Hoàn thành' đã đánh giá (đã trả hết),
    để trang hồ sơ có điểm trung bình thật và hàm nhiep_anh_gia_noi_bat có dữ liệu."""
    h = timedelta
    ds = []
    for nag in range(SO_NAG_DA_DUYET):
        for k in range(2):
            day = 60 + 17 * nag + 40 * k           # lệch ngày để không trùng khung giờ
            chup = _chup_luc(now, -day, 9 + 2 * k)
            tao = chup - h(days=7)
            xn_bg = chup + h(days=8)
            ht = chup + h(days=9)
            t = _chuoi_moc(tao, **{TT.CHO_DAT_COC: tao + h(hours=1), TT.CHOT_BOOKING: tao + h(days=1),
                                   TT.DA_CHUP: chup + h(hours=3), TT.CHO_HAU_KY: chup + h(days=1),
                                   TT.DANG_HAU_KY: chup + h(days=2), TT.CHO_KH_KIEM_TRA: chup + h(days=6),
                                   TT.CHO_XAC_NHAN_THANH_TOAN: xn_bg, TT.HOAN_THANH: ht})
            diem = DIEM_NEN[nag][k]
            ds.append(_bk(f'BKN{nag + 1:02d}{k + 1}', nag, (nag + 3 * k + 1) % len(KHACH_HANG), False,
                          TT.HOAN_THANH, tao, chup, t, co_giu_cho=False,
                          coc=dict(trang_thai=TTT.DA_DAT_COC, ngay_tt=tao + h(days=1) - h(hours=2),
                                   ngay_xn=tao + h(days=1), minh_chung=False),
                          con_lai=dict(trang_thai=TTT.DA_THANH_TOAN, ngay_tt=ht - h(hours=2), ngay_xn=ht,
                                       minh_chung=False),
                          ban_giao=dict(ngay_xn=xn_bg, thoi_han=ht + h(days=3)),
                          danh_gia=dict(diem=diem, nhan_xet=NHAN_XET_NEN[(nag + k) % len(NHAN_XET_NEN)],
                                        ngay=ht + h(days=1))))
    return ds


# ---------------------------------------------------------------------
# 5. KHUNG GIỜ (LichKhaDung)
# ---------------------------------------------------------------------
KHOI_GIO = [(8, 10), (13, 15), (16, 18)]


def _khoang_cua(b):
    bd = b['chup']
    kt = bd + timedelta(hours=2)
    return bd.date(), bd.time().replace(tzinfo=None), kt.time().replace(tzinfo=None)


SO_NGAY_LICH = 45          # F4: lịch trống 45 ngày tới (còn hạn khi nạp sát ngày báo cáo)


def lich_khung_gio(bookings, nen, now):
    """Trả về danh sách khung giờ cho từng NAG đã duyệt:
    [{'nag', 'ngay', 'bat_dau', 'ket_thuc', 'trang_thai', 'ma_booking'}, ...].
    Khung giờ của Booking mẫu lấy theo giờ chụp. Ngoài ra mỗi NAG có lịch trống rải đều SO_NGAY_LICH ngày tới
    (mỗi ngày làm việc 2 khung, vài ngày nghỉ rải rác, lệch giữa các NAG), trong đó có 1 'Đang giữ chỗ' và
    1 'Đã đặt lịch' không gắn Booking để xem giao diện lịch."""
    from datetime import time
    ket_qua = []
    homnay = now.astimezone(MUI_GIO).date()
    for nag in range(SO_NAG_DA_DUYET):
        slots = []
        for b in bookings + nen:
            if b['nag'] != nag:
                continue
            ngay, bd, kt = _khoang_cua(b)
            slots.append(dict(nag=nag, ngay=ngay, bat_dau=bd, ket_thuc=kt,
                              trang_thai=b['slot_trang_thai'], ma_booking=b['ma']))
        ung_vien = []
        for so_ngay in range(1, SO_NGAY_LICH + 1):
            if (so_ngay + nag) % 4 == 0:            # ngày nghỉ của NAG này
                continue
            ngay = homnay + timedelta(days=so_ngay)
            for lech in (0, 1):
                a, z = KHOI_GIO[(so_ngay + nag + lech) % len(KHOI_GIO)]
                bd, kt = time(a), time(z)
                trung = any(s['ngay'] == ngay and bd < s['ket_thuc'] and s['bat_dau'] < kt for s in slots)
                if not trung and (ngay, bd, kt) not in [(u[0], u[1], u[2]) for u in ung_vien]:
                    ung_vien.append((ngay, bd, kt))
        mau_giu, mau_dat = len(ung_vien) // 4, len(ung_vien) // 4 + 1     # khoảng ngày 11-12: một khung 'Đang giữ chỗ', một 'Đã đặt lịch'
        for idx, (ngay, bd, kt) in enumerate(ung_vien):
            tt = (TrangThaiSlot.DANG_GIU if idx == mau_giu else
                  TrangThaiSlot.DA_DAT if idx == mau_dat else TrangThaiSlot.TRONG)
            slots.append(dict(nag=nag, ngay=ngay, bat_dau=bd, ket_thuc=kt, trang_thai=tt, ma_booking=None))
        slots.sort(key=lambda s: (s['ngay'], s['bat_dau']))
        ket_qua.extend(slots)
    return ket_qua


# ---------------------------------------------------------------------
# 6. TỰ KIỂM TRA (chạy: python _du_lieu_mau.py) - mô phỏng các CHECK của database
# ---------------------------------------------------------------------
def kiem_tra(now):
    bk = lich_booking(now)
    nen = lich_nen(now)
    loi = []
    assert [b['ma'] for b in bk] == [f'BK{i:02d}' for i in range(1, 20)]
    for b in bk + nen:
        m = b['ma']
        if not b['chup'] > b['tao']:
            loi.append(f'{m}: NgayGioChup phải sau NgayTao')
        for k in ('han_coc', 'han_chon', 'han_hau_ky', 'han_tt'):
            if b[k] is not None and not b[k] > b['tao']:
                loi.append(f'{m}: {k} phải sau NgayTao')
        if b['tao'] > now:
            loi.append(f'{m}: NgayTao nằm trong tương lai')
        # lịch sử: thời điểm tăng dần, nối tiếp nhau, kết thúc đúng trạng thái
        ls = b['lich_su']
        for a, c in zip(ls, ls[1:]):
            if c[2] < a[2]:
                loi.append(f'{m}: lịch sử đi lùi {a[1]} -> {c[1]}')
            if c[0] != a[1]:
                loi.append(f'{m}: lịch sử đứt {a[1]} / {c[0]}')
        if ls[-1][1] != b['trang_thai']:
            loi.append(f'{m}: lịch sử kết thúc ở {ls[-1][1]}, Booking là {b["trang_thai"]}')
        if ls[0][2] < b['tao']:
            loi.append(f'{m}: lịch sử bắt đầu trước NgayTao')
        for row in ls:
            if row[2] > now:
                loi.append(f'{m}: lịch sử ở tương lai ({row[1]})')
        if b['trang_thai'] == TT.DA_TU_CHOI and not b['ly_do_tu_choi']:
            loi.append(f'{m}: thiếu lý do từ chối')
        if b['trang_thai'] != TT.DA_TU_CHOI and b['ly_do_tu_choi']:
            loi.append(f'{m}: có lý do từ chối nhưng không bị từ chối')
        # thanh toán và các mốc con
        for ten in ('coc', 'con_lai'):
            p = b[ten]
            if p and p['ngay_tt'] and p['ngay_xn'] and p['ngay_xn'] < p['ngay_tt']:
                loi.append(f'{m}: {ten} xác nhận trước khi thanh toán')
            if p and p['ngay_tt'] and p['ngay_tt'] < b['tao']:
                loi.append(f'{m}: {ten} thanh toán trước NgayTao')
        if b['ban_giao'] and b['ban_giao']['thoi_han'] and not b['ban_giao']['thoi_han'] > b['ban_giao']['ngay_xn']:
            loi.append(f'{m}: ThoiHanTaiAnh phải sau NgayXacNhan')
        if b['huy']:
            hy = b['huy']
            if hy['xu_ly'] == 'Hoàn cọc' and not hy['hoan_tien']:
                loi.append(f'{m}: Hoàn cọc cần TrangThaiHoanTien')
            if hy['xu_ly'] != 'Hoàn cọc' and hy['hoan_tien']:
                loi.append(f'{m}: TrangThaiHoanTien chỉ dùng khi Hoàn cọc')
            if hy['ngay'] < b['tao']:
                loi.append(f'{m}: hủy trước NgayTao')
    # trạng thái -> điều kiện thanh toán / ảnh
    tt_coc = {b['ma']: b['coc'] for b in bk}
    for ma in ('BK01', 'BK02', 'BK14', 'BK15', 'BK19'):
        if tt_coc[ma] is not None:
            loi.append(f'{ma}: chưa nên có khoản cọc')
    for ma in [f'BK{i:02d}' for i in range(4, 14)] + ['BK16', 'BK17']:
        if tt_coc[ma] is None:
            loi.append(f'{ma}: thiếu khoản cọc')
    # khung giờ
    slots = lich_khung_gio(bk, nen, now)
    khoa = set()
    for s in slots:
        k = (s['nag'], s['ngay'], s['bat_dau'])
        if k in khoa:
            loi.append(f'khung giờ trùng {k}')
        khoa.add(k)
        if not s['ket_thuc'] > s['bat_dau']:
            loi.append(f'khung giờ {k} kết thúc không sau bắt đầu')
    theo_nag = {}
    for s in slots:
        theo_nag.setdefault(s['nag'], []).append(s)
    for nag, ds in theo_nag.items():
        ds.sort(key=lambda s: (s['ngay'], s['bat_dau']))
        for a, c in zip(ds, ds[1:]):
            if a['ngay'] == c['ngay'] and c['bat_dau'] < a['ket_thuc']:
                loi.append(f'NAG {nag}: khung giờ chồng nhau ngày {a["ngay"]}')
        if len(ds) < 40:
            loi.append(f'NAG {nag}: chỉ có {len(ds)} khung giờ (cần từ 40 để phủ {SO_NGAY_LICH} ngày)')
        ngay_cuoi = max(s['ngay'] for s in ds if s['trang_thai'] == TrangThaiSlot.TRONG)
        if (ngay_cuoi - now.astimezone(MUI_GIO).date()).days < SO_NGAY_LICH - 4:
            loi.append(f'NAG {nag}: lịch trống chưa phủ tới {SO_NGAY_LICH} ngày')
        tt = {s['trang_thai'] for s in ds}
        if len(tt) != 3:
            loi.append(f'NAG {nag}: chưa đủ 3 trạng thái khung giờ')
    # NgayGioChup nằm trong khung giờ của slot (Booking.clean)
    for b in bk + nen:
        ngay, bd, kt = _khoang_cua(b)
        c = [s for s in slots if s['ma_booking'] == b['ma']]
        if len(c) != 1 or not (c[0]['ngay'] == b['chup'].date() and c[0]['bat_dau'] <= b['chup'].time().replace(tzinfo=None) <= c[0]['ket_thuc']):
            loi.append(f'{b["ma"]}: giờ chụp không nằm trong khung giờ')
    # gói giới hạn cho BK05, BK06, BK08
    for ma in ('BK05', 'BK06', 'BK08'):
        if not next(b for b in bk if b['ma'] == ma)['gioi_han']:
            loi.append(f'{ma} phải là gói giới hạn')
    return loi, bk, nen, slots


if __name__ == '__main__':
    from datetime import datetime
    # thử ở nhiều thời điểm trong ngày để chắc chắn không phụ thuộc giờ chạy lệnh
    tong = 0
    for gio in (0, 1, 6, 9, 12, 15, 23):
        for ngay in (1, 15, 28):
            now = datetime(2026, 10, ngay, gio, 37, tzinfo=MUI_GIO)
            loi, bk, nen, slots = kiem_tra(now)
            for x in loi:
                print(now.isoformat(), x)
            tong += len(loi)
    print('TỔNG LỖI:', tong)
    print('Số Booking:', len(bk), '+ nền', len(nen), '| số khung giờ:', len(slots))

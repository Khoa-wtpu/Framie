# delivery/ghep_anh.py - Slider trước/sau: ghép ảnh hậu kỳ mới với ảnh cũ THEO HÌNH ẢNH (không theo tên tệp)
# Chỉ dùng Pillow, không cần Django, không cần thư viện thêm. Có thể chạy thử độc lập.
#
# Ý tưởng:
#   1. Mỗi ảnh -> "dấu vân tay": ảnh xám 16x16 đã cân bằng sáng + tỉ lệ khung hình.
#   2. Khoảng cách giữa 2 ảnh = trộn của (1 - tương quan chuẩn hóa) và khoảng cách dHash.
#      Cả hai chịu được việc chỉnh sáng, tương phản, màu, làm mịn da, watermark.
#   3. Loại trước các cặp lệch tỉ lệ khung quá nhiều (khả năng cao là bị crop).
#   4. Ghép TOÀN CỤC: sắp mọi cặp theo khoảng cách tăng dần, chọn tham lam, mỗi ảnh chỉ ghép một lần.
#      Chỉ nhận cặp khi đủ gần (ngưỡng) VÀ cách xa ứng viên tốt thứ hai (độ chênh).
#   5. Cặp không đạt -> trả về trong danh sách "chưa ghép" để Nhiếp ảnh gia chọn tay.
#
# HAI GIỚI HẠN CẦN BIẾT (đưa vào báo cáo):
#   - Ảnh hậu kỳ bị cắt làm đổi tỉ lệ khung hình quá 5% (ví dụ cắt sang 4:5) thì bị loại ở bước 3,
#     nên toàn bộ các ảnh đó chuyển sang cho Nhiếp ảnh gia chọn tay (không ghép nhầm).
#   - Ảnh quá giống nhau (chụp liên tiếp cùng một cảnh) khó phân biệt, không đạt điều kiện "hơn hẳn ứng viên thứ hai"
#     ở bước 4, nên có thể phải chọn tay (hệ thống thà không ghép còn hơn ghép sai).
from PIL import Image, ImageOps

KICH_THUOC = 16                      # ảnh xám thu nhỏ KICH_THUOC x KICH_THUOC để so sánh tương quan
KICH_THUOC_HASH = 9                  # dHash dùng lưới 9x8 (so pixel kề nhau theo hàng) -> 64 bit
LECH_TI_LE_TOI_DA = 0.05             # lệch tỉ lệ khung hình quá 5% -> loại luôn (bị crop / xoay)
NGUONG_KHOANG_CACH = 0.30            # khoảng cách tối đa để nhận một cặp (0 = giống hệt, 1 = khác hẳn)
NGUONG_LOAI_TRU = 0.50              # ngưỡng nới rộng cho cặp cuối cùng còn lại (ghép bằng phép loại trừ)
DO_CHENH_TOI_THIEU = 0.04            # cặp tốt nhất phải tốt hơn ứng viên thứ hai ít nhất chừng này (khi có >= 2 ứng viên)
TRONG_SO_TUONG_QUAN = 0.6            # khoảng cách = 0.6 * (1 - tương quan) / 2 + 0.4 * (dHash / 64)


class DauVanTay:                     # thông tin rút gọn của một ảnh, đủ để so sánh mà không phải mở lại ảnh
    __slots__ = ('ti_le', 'diem', 'bit')

    def __init__(self, ti_le, diem, bit):
        self.ti_le = ti_le           # rộng / cao sau khi xoay theo EXIF
        self.diem = diem             # danh sách KICH_THUOC^2 giá trị xám (0-255) sau autocontrast
        self.bit = bit               # dHash: số nguyên 64 bit


def _dua_ve_xam(hinh):               # xoay theo EXIF, bỏ kênh trong suốt, đổi sang xám
    hinh = ImageOps.exif_transpose(hinh)
    if hinh.mode in ('RGBA', 'LA', 'P'):                       # ảnh trong suốt -> nền xám trung tính để không lệch hash
        hinh = hinh.convert('RGBA')
        nen = Image.new('RGBA', hinh.size, (128, 128, 128, 255))
        nen.alpha_composite(hinh)
        hinh = nen
    return hinh.convert('L')


def _tinh_dhash(xam):                # so pixel kề nhau theo hàng trên ảnh 9x8 -> 64 bit
    nho = xam.resize((KICH_THUOC_HASH, KICH_THUOC_HASH - 1), Image.LANCZOS)
    px = list(nho.getdata())
    rong = KICH_THUOC_HASH
    bit = 0
    for hang in range(KICH_THUOC_HASH - 1):
        for cot in range(rong - 1):
            bit = (bit << 1) | (1 if px[hang * rong + cot] > px[hang * rong + cot + 1] else 0)
    return bit


def tao_dau_van_tay(tep):            # tep: đường dẫn hoặc file-like; trả về DauVanTay
    with Image.open(tep) as goc:
        goc.draft('L', (256, 256))                             # JPEG: giải mã nhanh ở kích thước nhỏ (bỏ qua nếu không hỗ trợ)
        xam = _dua_ve_xam(goc)
        rong, cao = xam.size
        ti_le = rong / cao if cao else 1.0
        xam.thumbnail((256, 256))                              # thu nhỏ bớt trước cho nhanh
        xam = ImageOps.autocontrast(xam, cutoff=1)             # kéo giãn sáng tối -> triệt tiêu chênh lệch độ sáng, tương phản
        diem = list(xam.resize((KICH_THUOC, KICH_THUOC), Image.LANCZOS).getdata())
        bit = _tinh_dhash(xam)
    return DauVanTay(ti_le, diem, bit)


def _tuong_quan(a, b):               # hệ số tương quan Pearson giữa hai vector pixel, -1..1
    n = len(a)
    ta, tb = sum(a) / n, sum(b) / n
    sa = sum((x - ta) ** 2 for x in a)
    sb = sum((y - tb) ** 2 for y in b)
    if sa < 1e-9 or sb < 1e-9:                                 # ảnh phẳng (một màu): không có hình để so
        return 1.0 if (sa < 1e-9 and sb < 1e-9) else 0.0
    return sum((x - ta) * (y - tb) for x, y in zip(a, b)) / ((sa * sb) ** 0.5)


def khoang_cach(a, b):               # 0 = giống hệt, 1 = khác hẳn; None nếu không so được (thiếu ảnh) hoặc lệch tỉ lệ quá nhiều
    if a is None or b is None:
        return None
    if abs(a.ti_le - b.ti_le) / max(a.ti_le, b.ti_le) > LECH_TI_LE_TOI_DA:
        return None
    tq = (1 - _tuong_quan(a.diem, b.diem)) / 2                 # 0..1
    dh = bin(a.bit ^ b.bit).count('1') / 64                    # khoảng cách Hamming chuẩn hóa 0..1
    return TRONG_SO_TUONG_QUAN * tq + (1 - TRONG_SO_TUONG_QUAN) * dh


def ghep(moi, cu, thuong=None):
    """Ghép toàn cục ảnh mới (moi) với ảnh cũ (cu); phần tử có thể là None (ảnh không đọc được -> không ghép tự động).
    thuong: tuỳ chọn, dict {(i, j): điểm} trừ vào khoảng cách (ví dụ tên tệp trùng nhau) để phá thế hòa.
    Trả về (cap, chua_ghep, ung_vien):
      cap        = {chỉ số moi: chỉ số cu} các cặp được nhận
      chua_ghep  = danh sách chỉ số moi chưa ghép được
      ung_vien   = {chỉ số moi chưa ghép: [chỉ số cu gần nhất, ...]} sắp từ gần đến xa (gợi ý cho dropdown chọn tay)
    """
    thuong = thuong or {}
    hang, cot = {}, {}                                         # hang[i] = {j: kc}, cot[j] = {i: kc}
    for i, m in enumerate(moi):
        for j, c in enumerate(cu):
            kc = khoang_cach(m, c)
            if kc is not None:
                kc = max(0.0, kc - thuong.get((i, j), 0.0))
                hang.setdefault(i, {})[j] = kc
                cot.setdefault(j, {})[i] = kc

    tat_ca = sorted(((kc, i, j) for i, d in hang.items() for j, kc in d.items()))   # từ cặp gần nhất đến xa nhất
    cap, da_cu = {}, set()
    for kc, i, j in tat_ca:
        if kc > NGUONG_KHOANG_CACH:
            break                                              # các cặp còn lại đều quá xa
        if i in cap or j in da_cu:
            continue                                           # ảnh này đã có cặp
        # độ chênh: so với ứng viên thứ hai CÒN TRỐNG của cả hai phía
        doi_thu = [v for b, v in hang[i].items() if b != j and b not in da_cu]
        doi_thu += [v for a, v in cot[j].items() if a != i and a not in cap]
        if any(v - kc < DO_CHENH_TOI_THIEU for v in doi_thu):
            continue                                           # có ứng viên quá sát -> không tự quyết, để NAG chọn tay
        cap[i] = j
        da_cu.add(j)

    con_moi = [i for i in range(len(moi)) if i not in cap]
    con_cu = [j for j in range(len(cu)) if j not in da_cu]
    if len(con_moi) == 1 and len(con_cu) == 1:                 # chỉ còn đúng một ảnh mỗi phía: ghép bằng phép loại trừ, với ngưỡng nới rộng hơn
        kc = hang.get(con_moi[0], {}).get(con_cu[0])
        if kc is not None and kc <= NGUONG_LOAI_TRU:
            cap[con_moi[0]] = con_cu[0]
            da_cu.add(con_cu[0])
    chua_ghep = [i for i in range(len(moi)) if i not in cap]
    ung_vien = {i: [j for _, j in sorted((v, j) for j, v in hang.get(i, {}).items() if j not in da_cu)]
                for i in chua_ghep}
    return cap, chua_ghep, ung_vien


def ghep_co_tay(moi, cu, ghep_tay=None, thuong=None):
    """Như ghep(), nhưng một số cặp đã do Nhiếp ảnh gia chọn tay (ghep_tay = {chỉ số moi: chỉ số cu}).
    Cặp chọn tay được tin tuyệt đối; phần còn lại ghép tự động trong số ảnh chưa dùng.
    Trả về (cap_day_du, chua_ghep, ung_vien) với chỉ số theo danh sách gốc.
    Ném ValueError nếu ghep_tay sai (chỉ số lạ, hai tệp cùng chọn một ảnh)."""
    ghep_tay = dict(ghep_tay or {})
    if (any(not 0 <= i < len(moi) for i in ghep_tay) or any(not 0 <= j < len(cu) for j in ghep_tay.values())
            or len(set(ghep_tay.values())) != len(ghep_tay)):
        raise ValueError('ghep_tay không hợp lệ')
    ds_moi = [i for i in range(len(moi)) if i not in ghep_tay]
    ds_cu = [j for j in range(len(cu)) if j not in set(ghep_tay.values())]
    thuong_con = {(a, b): v for (i, j), v in (thuong or {}).items()
                  if i in ds_moi and j in ds_cu for a, b in [(ds_moi.index(i), ds_cu.index(j))]}
    cap_con, chua_con, uv_con = ghep([moi[i] for i in ds_moi], [cu[j] for j in ds_cu], thuong_con)
    cap = dict(ghep_tay)
    cap.update({ds_moi[a]: ds_cu[b] for a, b in cap_con.items()})
    chua = [ds_moi[a] for a in chua_con]
    ung_vien = {ds_moi[a]: [ds_cu[b] for b in ds] for a, ds in uv_con.items()}
    return cap, chua, ung_vien

"""Trạng thái -> tông màu. Giá trị lưu trong DB chính là chữ tiếng Việt ở core/constants.py,
nên khóa ở đây lấy thẳng từ constants (không gõ lại chữ). Tông màu khai báo ở static/css/tokens.css.
Tông có sẵn: amber, orange, red, rose, pink, violet, indigo, blue, sky, teal, green, lime, brown, gray."""
from .constants import (KetQuaTaiAnh, LoaiAnh, LuuTruAnh, TrangThaiBooking as B,
                        TrangThaiDatLaiMatKhau as MK, TrangThaiDoc, TrangThaiGiuCho as GC,
                        TrangThaiGoi, TrangThaiGuiEmail, TrangThaiHoanTien, TrangThaiHoSo as HS,
                        TrangThaiSlot as SL, TrangThaiThanhToan as TT, XuLyTienCoc, HOAN_TAT_BAN_GIAO)

TONE_BY_STATUS = {
    # Booking: đi từ ấm (đang chờ) sang lạnh (đang làm) rồi xanh lá (xong); thất bại dùng đỏ/nâu/xám
    B.CHO_XAC_NHAN: "amber", B.CHO_DAT_COC: "orange", B.CHOT_BOOKING: "blue",
    B.DA_CHUP: "indigo", B.CHO_KH_CHON_ANH: "violet", B.CHO_HAU_KY: "sky",
    B.DANG_HAU_KY: "teal", B.CHO_KH_KIEM_TRA: "pink", B.CHO_XAC_NHAN_THANH_TOAN: "lime",
    B.HOAN_THANH: "green", B.DA_TU_CHOI: "red", B.HET_THOI_HAN_DAT_COC: "brown", B.DA_HUY: "gray",
    # Hồ sơ Nhiếp ảnh gia
    HS.CHO_DUYET: "amber", HS.DA_DUYET: "green", HS.DA_TU_CHOI: "red",
    # Slot và lượt giữ chỗ
    SL.TRONG: "sky", SL.DANG_GIU: "amber", SL.DA_DAT: "blue",
    GC.DA_HOAN_TAT: "green", GC.HET_HAN: "gray",
    # Thanh toán
    TT.CHO_XAC_NHAN_COC: "violet", TT.DA_DAT_COC: "teal", TT.CHO_XAC_NHAN_60: "lime",
    TT.QUA_HAN: "red", TT.DA_THANH_TOAN: "green",
    # Gói dịch vụ
    TrangThaiGoi.DANG_AP_DUNG: "green", TrangThaiGoi.NGUNG_AP_DUNG: "gray", TrangThaiGoi.DA_AN: "brown",
    # Ảnh, tải ảnh
    LoaiAnh.CHUA_HAU_KY: "gray", LoaiAnh.DA_HAU_KY: "indigo", LoaiAnh.HOAN_CHINH: "green",
    LuuTruAnh.CON_LUU: "green", LuuTruAnh.DA_XOA: "gray",
    KetQuaTaiAnh.THANH_CONG: "green", KetQuaTaiAnh.THAT_BAI: "red",
    # Hoàn cọc
    XuLyTienCoc.KHONG_PHAT_SINH: "gray", XuLyTienCoc.MAT_COC: "red", XuLyTienCoc.HOAN_COC: "teal",
    TrangThaiHoanTien.CHO_HOAN_TIEN: "amber", TrangThaiHoanTien.DA_HOAN_TIEN: "green",
    # Quên mật khẩu
    MK.CHO_XAC_THUC: "amber", MK.DA_XAC_THUC: "blue", MK.DA_DAT_LAI: "green",
    # Thông báo, email, bàn giao
    TrangThaiDoc.CHUA_DOC: "blue", TrangThaiDoc.DA_DOC: "gray",
    TrangThaiGuiEmail.THANH_CONG: "green", TrangThaiGuiEmail.THAT_BAI: "red",
    HOAN_TAT_BAN_GIAO: "green",
}
# Lưu ý: 'Đang giữ chỗ' (Slot và Giữ chỗ), 'Hết hạn' (Giữ chỗ và Mật khẩu), 'Đã từ chối' (Hồ sơ và Booking)
# trùng chữ nên dùng chung một màu, khớp quy ước "chữ trùng từng chữ" của constants.py.


def tone_of(value):
    return TONE_BY_STATUS.get(value, "gray")

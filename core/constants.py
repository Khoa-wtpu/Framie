# =====================================================================
# core/constants.py
# Nơi DUY NHẤT khai báo tên trạng thái của hệ thống FRAMIE.
# Các app khác chỉ import từ đây, KHÔNG tự gõ chữ tiếng Việt.
# Chữ trong dấu nháy phải trùng từng chữ (cả dấu, hoa/thường) với
# Bảng quy ước trạng thái và Data Dictionary (Quy ước 7).
# Cách dùng:  from core.constants import TrangThaiBooking
#             TrangThaiBooking.DA_HUY   ->  'Đã hủy'
# =====================================================================


def _choices(values):
    # Biến danh sách tên thành danh sách cặp (giá trị lưu DB, nhãn hiển thị)
    # để gắn vào cột có choices= của model. Dấu _ = hàm dùng nội bộ file này.
    return [(v, v) for v in values]


class VaiTro:
    # Vai trò chính của tài khoản. Sẽ là tên 3 nhóm quyền (Group) của Django.
    KHACH_HANG = 'Khách hàng'
    NHIEP_ANH_GIA = 'Nhiếp ảnh gia'
    QUAN_TRI_VIEN = 'Quản trị viên'


class TrangThaiHoSo:
    # Trạng thái hồ sơ Nhiếp ảnh gia (cột trang_thai_ho_so trong User).
    CHO_DUYET = 'Chờ duyệt'      # mới nộp hoặc vừa cập nhật, chờ Quản trị viên xem
    DA_DUYET = 'Đã duyệt'        # hiển thị công khai, được nhận Booking
    DA_TU_CHOI = 'Đã từ chối'    # Quản trị viên từ chối, có lý do
    CHOICES = _choices([CHO_DUYET, DA_DUYET, DA_TU_CHOI])


class TrangThaiBooking:
    # Trạng thái của Booking: 13 trạng thái, đi theo thứ tự quy trình TO-BE.
    CHO_XAC_NHAN = 'Chờ xác nhận'                 # Khách vừa gửi, chờ Nhiếp ảnh gia chấp nhận
    CHO_DAT_COC = 'Chờ đặt cọc'                   # đã chấp nhận, Khách có 1 ngày để đặt cọc 40%
    CHOT_BOOKING = 'Chốt Booking'                 # Nhiếp ảnh gia xác nhận đủ cọc, chờ buổi chụp
    DA_CHUP = 'Đã chụp'                           # buổi chụp xong (từ đây không hủy được nữa)
    CHO_KH_CHON_ANH = 'Chờ Khách hàng lựa chọn ảnh'   # chỉ gói giới hạn số ảnh, hạn 2 ngày
    CHO_HAU_KY = 'Chờ hậu kỳ'                     # chờ Nhiếp ảnh gia bắt đầu hậu kỳ
    DANG_HAU_KY = 'Đang hậu kỳ'                   # đang hậu kỳ, hạn 3 ngày
    CHO_KH_KIEM_TRA = 'Chờ Khách hàng kiểm tra'   # Khách xem ảnh đã hậu kỳ
    CHO_XAC_NHAN_THANH_TOAN = 'Chờ xác nhận thanh toán'  # chờ thanh toán 60% còn lại
    HOAN_THANH = 'Hoàn thành'                     # kết thúc thành công
    # --- 3 trạng thái kết thúc không thành công ---
    DA_TU_CHOI = 'Đã từ chối'                     # Nhiếp ảnh gia từ chối
    HET_THOI_HAN_DAT_COC = 'Hết thời hạn đặt cọc' # Khách không đặt cọc trong 1 ngày
    DA_HUY = 'Đã hủy'                             # hủy ở Chờ đặt cọc hoặc Chốt Booking
    ALL = [CHO_XAC_NHAN, CHO_DAT_COC, CHOT_BOOKING, DA_CHUP, CHO_KH_CHON_ANH,
           CHO_HAU_KY, DANG_HAU_KY, CHO_KH_KIEM_TRA, CHO_XAC_NHAN_THANH_TOAN,
           HOAN_THANH, DA_TU_CHOI, HET_THOI_HAN_DAT_COC, DA_HUY]   # cả 13
    CHOICES = _choices(ALL)


class TrangThaiSlot:
    # Trạng thái khung giờ (slot) trong Lịch khả dụng.
    TRONG = 'Lịch trống'          # ai cũng chọn được
    DANG_GIU = 'Đang giữ chỗ'     # có Khách đang giữ (5 phút) hoặc đã gửi Booking chưa chốt
    DA_DAT = 'Đã đặt lịch'        # Nhiếp ảnh gia đã xác nhận đủ cọc
    CHOICES = _choices([TRONG, DANG_GIU, DA_DAT])


class TrangThaiGiuCho:
    # Trạng thái của MỘT LƯỢT giữ chỗ (khác với trạng thái của slot ở trên).
    DANG_GIU = 'Đang giữ chỗ'              # Khách mới chọn slot, còn trong 5 phút
    DA_HOAN_TAT = 'Đã hoàn tất Booking'    # Khách gửi Booking kịp 5 phút
    HET_HAN = 'Hết hạn'                    # quá 5 phút chưa gửi, slot về Lịch trống
    CHOICES = _choices([DANG_GIU, DA_HOAN_TAT, HET_HAN])


class TrangThaiThanhToan:
    # Trạng thái của MỘT khoản thanh toán (cọc 40% hoặc phần còn lại 60%).
    CHO_XAC_NHAN_COC = 'Chờ xác nhận thanh toán cọc'  # Khách đã tải minh chứng cọc
    DA_DAT_COC = 'Đã đặt cọc'                               # Nhiếp ảnh gia xác nhận cọc
    CHO_XAC_NHAN_60 = 'Chờ xác nhận thanh toán'        # khoản còn lại, chờ xác nhận
    QUA_HAN = 'Quá hạn thanh toán'                          # quá 2 ngày chưa trả 60%
    DA_THANH_TOAN = 'Đã thanh toán'                         # đã nhận đủ 60%
    CHOICES = _choices([CHO_XAC_NHAN_COC, DA_DAT_COC, CHO_XAC_NHAN_60,
                        QUA_HAN, DA_THANH_TOAN])


class LoaiThanhToan:
    TIEN_COC = 'Tiền cọc'            # 40% giá trị Booking
    PHAN_CON_LAI = 'Phần còn lại'    # 60% giá trị Booking
    CHOICES = _choices([TIEN_COC, PHAN_CON_LAI])


class TrangThaiGoi:
    # Trạng thái Gói dịch vụ. Chỉ gói 'Đang áp dụng' cho Khách chọn khi đặt Booking.
    DANG_AP_DUNG = 'Đang áp dụng'
    NGUNG_AP_DUNG = 'Ngừng áp dụng'   # không cho đặt mới, vẫn giữ lịch sử Booking cũ
    DA_AN = 'Đã ẩn'
    CHOICES = _choices([DANG_AP_DUNG, NGUNG_AP_DUNG, DA_AN])


class LoaiHauKy:
    # Cách hậu kỳ của gói dịch vụ.
    GIOI_HAN = 'Giới hạn số lượng ảnh'   # Khách chọn ảnh trong giới hạn của gói
    TOAN_BO = 'Hậu kỳ toàn bộ ảnh'       # bỏ qua bước Khách chọn ảnh
    CHOICES = _choices([GIOI_HAN, TOAN_BO])


class LoaiAnh:
    # Giai đoạn của một ảnh (mỗi ảnh chỉ một bản ghi, đổi loại khi sang giai đoạn mới).
    CHUA_HAU_KY = 'Chưa hậu kỳ'   # ảnh gốc Nhiếp ảnh gia tải lên, có watermark
    DA_HAU_KY = 'Đã hậu kỳ'       # ảnh đã chỉnh sửa, có watermark
    HOAN_CHINH = 'Hoàn chỉnh'     # ảnh cuối, không watermark, Khách tải được
    CHOICES = _choices([CHUA_HAU_KY, DA_HAU_KY, HOAN_CHINH])


class LuuTruAnh:
    CON_LUU = 'Còn lưu'
    DA_XOA = 'Đã xóa'      # hệ thống tự xóa file ảnh sau 3 ngày kể từ khi mở quyền tải
    CHOICES = _choices([CON_LUU, DA_XOA])


class KetQuaTaiAnh:
    # Kết quả mỗi lần Khách tải ảnh hoàn chỉnh (ghi vào Lịch sử tải ảnh).
    THANH_CONG = 'Tải ảnh thành công'
    THAT_BAI = 'Tải ảnh thất bại'
    CHOICES = _choices([THANH_CONG, THAT_BAI])


class XuLyTienCoc:
    # Hệ quả tiền cọc khi hủy Booking (ghi vào Yêu cầu hủy).
    KHONG_PHAT_SINH = 'Không phát sinh'   # hủy ở Chờ đặt cọc, chưa có tiền cọc
    MAT_COC = 'Mất cọc'                   # Khách hủy sau khi đã cọc
    HOAN_COC = 'Hoàn cọc'                 # Nhiếp ảnh gia hủy sau khi Khách đã cọc
    CHOICES = _choices([KHONG_PHAT_SINH, MAT_COC, HOAN_COC])


class TrangThaiHoanTien:
    # Chỉ dùng khi XuLyTienCoc là 'Hoàn cọc'. FRAMIE chỉ theo dõi, không hoàn tiền.
    CHO_HOAN_TIEN = 'Chờ hoàn tiền'
    DA_HOAN_TIEN = 'Đã hoàn tiền'         # Khách xác nhận đã nhận lại tiền
    CHOICES = _choices([CHO_HOAN_TIEN, DA_HOAN_TIEN])


class TrangThaiDatLaiMatKhau:
    # Trạng thái một lượt "Quên mật khẩu" (mã 6 số, hiệu lực tối đa 10 phút).
    CHO_XAC_THUC = 'Chờ xác thực'         # đã gửi mã, chờ người dùng nhập
    DA_XAC_THUC = 'Đã xác thực'           # nhập đúng mã
    DA_DAT_LAI = 'Đã đặt lại mật khẩu'    # đã đổi mật khẩu xong
    HET_HAN = 'Hết hạn'                   # mã quá 10 phút
    CHOICES = _choices([CHO_XAC_THUC, DA_XAC_THUC, DA_DAT_LAI, HET_HAN])


class TrangThaiDoc:
    # Thông báo: đã đọc hay chưa.
    CHUA_DOC = 'Chưa đọc'
    DA_DOC = 'Đã đọc'
    CHOICES = _choices([CHUA_DOC, DA_DOC])


class DanhDauSao:
    # Thông báo: người dùng có đánh dấu sao không.
    DA_DANH_DAU = 'Đã đánh dấu sao'
    CHUA_DANH_DAU = 'Chưa đánh dấu sao'
    CHOICES = _choices([DA_DANH_DAU, CHUA_DANH_DAU])


class TrangThaiGuiEmail:
    # Thông báo: kết quả gửi email đi kèm.
    THANH_CONG = 'Gửi thành công'
    THAT_BAI = 'Gửi thất bại'
    CHOICES = _choices([THANH_CONG, THAT_BAI])


class BenThucHien:
    # Ai thực hiện một lần đổi trạng thái Booking (ghi vào Lịch sử trạng thái).
    KHACH_HANG = 'Khách hàng'
    NHIEP_ANH_GIA = 'Nhiếp ảnh gia'
    HE_THONG = 'Hệ thống'     # các thay đổi tự động (quá hạn đặt cọc, hết giữ chỗ...)
    CHOICES = _choices([KHACH_HANG, NHIEP_ANH_GIA, HE_THONG])


# Bàn giao chỉ có một trạng thái nên không cần lớp.
HOAN_TAT_BAN_GIAO = 'Hoàn tất bàn giao'

class KetQuaDuyetHoSo:
    DA_DUYET = TrangThaiHoSo.DA_DUYET            # 'Đã duyệt'
    YEU_CAU_CHINH_SUA = 'Yêu cầu chỉnh sửa'
    DA_TU_CHOI = TrangThaiHoSo.DA_TU_CHOI        # 'Đã từ chối'
    CHOICES = _choices([DA_DUYET, YEU_CAU_CHINH_SUA, DA_TU_CHOI])

class DinhDangTep:
    # Định dạng tệp ảnh được phép (minh chứng thanh toán, ảnh bàn giao).
    JPG = 'JPG'
    PNG = 'PNG'
    JPEG = 'JPEG'
    CHOICES = _choices([JPG, PNG, JPEG])
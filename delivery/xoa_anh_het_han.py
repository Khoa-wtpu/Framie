# =====================================================================
# delivery/xoa_anh_het_han.py  -  T10: xóa file ảnh khi hết thời hạn tải (3 ngày sau khi mở quyền tải)
# File RIÊNG để không đụng delivery/services.py của Nguyên. Dùng lại đúng hàm của Nguyên:
#   kho_anh()        : kho ảnh riêng (PRIVATE_MEDIA_ROOT), không công khai
#   duong_dan_goc()  : đường dẫn bản GỐC (không watermark) đi kèm mỗi ảnh
# Mỗi ảnh có 2 file (bản đang dùng + bản gốc trong thư mục "goc") nên xóa cả hai.
# =====================================================================
import logging

from django.core.exceptions import SuspiciousOperation

from core.constants import LuuTruAnh
from delivery.models import Anh

logger = logging.getLogger(__name__)


def xoa_anh_cua_booking(booking):
    """Xóa file của mọi ảnh còn lưu của Booking rồi đổi TrangThaiLuuTru sang 'Đã xóa'.
    Giữ bản ghi ảnh và Lịch sử tải ảnh. Chạy lại nhiều lần vẫn an toàn.
    Ảnh nào xóa file lỗi thì để nguyên 'Còn lưu' để lần quét sau thử lại. Trả về số ảnh vừa đánh dấu 'Đã xóa'."""
    from delivery.services import duong_dan_goc, kho_anh      # import trong hàm: tránh import vòng khi nạp ứng dụng
    kho = kho_anh()
    so_anh = 0
    for anh in Anh.objects.filter(MaBooking=booking, TrangThaiLuuTru=LuuTruAnh.CON_LUU):
        ds_tep = [anh.DuongDanAnh]
        if '/' in anh.DuongDanAnh:
            ds_tep.append(duong_dan_goc(anh.DuongDanAnh))     # bản gốc không watermark
        try:
            for duong_dan in ds_tep:
                kho.delete(duong_dan)                          # file không tồn tại thì storage bỏ qua, không lỗi
        except (OSError, SuspiciousOperation):                 # lỗi ổ đĩa, hoặc đường dẫn trỏ ra ngoài kho ảnh
            logger.exception('xoa_anh_het_han: không xóa được file ảnh %s', anh.pk)
            continue
        Anh.objects.filter(pk=anh.pk, TrangThaiLuuTru=LuuTruAnh.CON_LUU).update(TrangThaiLuuTru=LuuTruAnh.DA_XOA)
        so_anh += 1
    return so_anh

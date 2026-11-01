# notifications/services.py - P2: hàm gửi thông báo dùng chung (Phanh)
# Các bạn khác import hàm ở đây để gửi thông báo khi có sự kiện (Booking mới, duyệt hồ sơ...)
import logging  # thư viện ghi log: để in cảnh báo ra Terminal khi có lỗi, thay vì làm sập web

from django.db import transaction  # transaction.atomic: bọc thao tác lưu để lỗi không lan sang nơi khác

from core.constants import TrangThaiDoc  # hằng số 'Chưa đọc'/'Đã đọc' (README: không tự gõ chữ tiếng Việt)
from notifications.models import ThongBao  # model bảng THONGBAO đã có sẵn trong notifications/models.py

logger = logging.getLogger(__name__)  # tạo bộ ghi log riêng cho file này


def gui_thong_bao(nguoi_nhan, tieu_de, noi_dung, booking=None):  # hàm chính: gửi 1 thông báo cho 1 người
    """Tạo thông báo 'Chưa đọc'. Trả về ThongBao nếu thành công, None nếu lỗi."""  # mô tả hàm
    if nguoi_nhan is None or getattr(nguoi_nhan, 'pk', None) is None:  # không có người nhận, hoặc User chưa lưu vào DB
        logger.warning('gui_thong_bao: thiếu người nhận (%r)', tieu_de)  # ghi cảnh báo để dễ tìm lỗi
        return None  # dừng, không tạo gì

    tieu_de = (tieu_de or '').strip()[:255]  # bỏ khoảng trắng thừa và cắt còn 255 ký tự (cột TieuDe tối đa 255)
    noi_dung = (noi_dung or '').strip()  # bỏ khoảng trắng thừa ở nội dung
    if not tieu_de or not noi_dung:  # tiêu đề hoặc nội dung rỗng thì không có gì để báo
        logger.warning('gui_thong_bao: thiếu tiêu đề hoặc nội dung')  # ghi cảnh báo
        return None  # dừng, không tạo gì

    try:  # thử lưu; nếu lỗi thì bắt lại, không để nghiệp vụ chính của bạn khác bị sập
        with transaction.atomic():  # savepoint riêng: lỗi ở đây không làm hỏng giao dịch của nơi gọi
            thong_bao = ThongBao.objects.create(  # INSERT một dòng mới vào bảng THONGBAO
                MaNguoiNhan=nguoi_nhan,  # người nhận thông báo
                MaBooking=booking,  # Booking liên quan (None nếu không có, cột cho phép NULL)
                TieuDe=tieu_de,  # tiêu đề đã làm sạch
                NoiDung=noi_dung,  # nội dung đã làm sạch
                TrangThaiDoc=TrangThaiDoc.CHUA_DOC,  # luôn bắt đầu ở trạng thái 'Chưa đọc'
            )  # NgayTao do Django tự điền (auto_now_add)
    except Exception:  # noqa: BLE001  # bắt mọi lỗi khi lưu (DB lỗi, dữ liệu sai...)
        logger.exception('gui_thong_bao: lưu thất bại (%s)', tieu_de)  # ghi log đầy đủ lỗi để sửa sau
        return None  # báo không tạo được nhưng không ném lỗi ra ngoài

    return thong_bao  # trả về thông báo vừa tạo để nơi gọi dùng nếu cần


def gui_thong_bao_nhieu_nguoi(ds_nguoi_nhan, tieu_de, noi_dung, booking=None):  # gửi cùng nội dung cho nhiều người
    """Ví dụ: báo cho tất cả Quản trị viên khi có hồ sơ mới. Trả về list ThongBao đã tạo."""  # mô tả hàm
    da_gui = set()  # tập các mã User đã gửi, để không gửi trùng một người hai lần
    ket_qua = []  # danh sách thông báo tạo thành công
    for user in ds_nguoi_nhan:  # duyệt từng người trong danh sách
        if user is None or user.pk in da_gui:  # bỏ qua giá trị rỗng hoặc người đã gửi rồi
            continue  # sang người tiếp theo
        da_gui.add(user.pk)  # ghi nhớ người này đã được xử lý
        thong_bao = gui_thong_bao(user, tieu_de, noi_dung, booking=booking)  # gửi cho từng người bằng hàm chính
        if thong_bao is not None:  # chỉ giữ lại những thông báo tạo thành công
            ket_qua.append(thong_bao)  # thêm vào danh sách kết quả
    return ket_qua  # trả về danh sách


def dem_chua_doc(user):  # đếm số thông báo chưa đọc của một người
    """Dùng cho số đỏ trên chuông ở đầu trang (header)."""  # mô tả hàm
    if user is None or not getattr(user, 'is_authenticated', False):  # chưa đăng nhập hoặc không có user
        return 0  # khách vãng lai không có thông báo
    return ThongBao.objects.filter(  # đếm trong bảng THONGBAO
        MaNguoiNhan=user,  # chỉ thông báo của người này
        TrangThaiDoc=TrangThaiDoc.CHUA_DOC,  # chỉ thông báo còn 'Chưa đọc'
    ).count()  # trả về số lượng
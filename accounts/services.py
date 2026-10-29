# =====================================================================
# accounts/services.py  -  P4: hàm tạo tài khoản và gửi email đăng ký (Phanh)
# P5 (đăng ký Nhiếp ảnh gia) gọi lại chính hàm tao_tai_khoan, chỉ đổi tham số vai_tro.
# =====================================================================
import logging  # ghi cảnh báo ra Terminal khi gửi email lỗi, thay vì làm sập trang đăng ký

from django.contrib.auth.models import Group  # bảng nhóm quyền của Django (vai trò)
from django.core.mail import send_mail  # hàm gửi email; khi làm thử chỉ in ra Terminal (xem MAILERS trong settings.py)
from django.db import transaction  # transaction.atomic: tạo User và gán nhóm là một khối, lỗi thì hoàn tác cả hai

from core.constants import VaiTro  # tên vai trò, không tự gõ chữ tiếng Việt (README)

from .models import User  # model User của FRAMIE

logger = logging.getLogger(__name__)  # bộ ghi log riêng cho file này


def tach_ho_ten(ho_ten):  # tách "Nguyễn Văn An" thành ("An", "Nguyễn Văn") theo Data Dictionary
    phan = ho_ten.rsplit(maxsplit=1)  # cắt tại khoảng trắng CUỐI CÙNG: phần cuối là tên, phần trước là họ và tên đệm
    if len(phan) == 1:  # họ tên chỉ có một chữ
        return phan[0], ''  # chữ đó là tên, họ và tên đệm để rỗng
    return phan[1], phan[0]  # (first_name = tên, last_name = họ và tên đệm)


def tao_tai_khoan(ho_ten, email, so_dien_thoai, mat_khau, vai_tro=VaiTro.KHACH_HANG, **them):  # tạo User và gán nhóm ngay
    email = email.strip().lower()  # luôn lưu email chữ thường, nếu không EmailBackend gặp MultipleObjectsReturned
    ten, ho_dem = tach_ho_ten(ho_ten)  # tách họ tên thành hai cột có sẵn của Django
    with transaction.atomic():  # từ dòng này, lỗi ở đâu thì hoàn tác hết
        user = User.objects.create_user(  # create_user tự băm mật khẩu, không bao giờ lưu mật khẩu thô
            username=email,  # Django bắt buộc có username; ta dùng luôn email (đăng nhập bằng email)
            email=email,  # cột email (đã unique)
            password=mat_khau,  # mật khẩu thô, create_user sẽ băm
            first_name=ten,  # tên (chữ cuối), đúng Data Dictionary
            last_name=ho_dem,  # họ và tên đệm, đúng Data Dictionary
            so_dien_thoai=so_dien_thoai,  # cột bổ sung của FRAMIE
            **them,  # P5 sẽ truyền thêm trang_thai_ho_so ở đây nếu cần
        )  # hết tạo User
        nhom, _ = Group.objects.get_or_create(name=vai_tro)  # lấy nhóm theo vai trò (migration 0003 đã tạo sẵn)
        user.groups.add(nhom)  # gán nhóm NGAY, để lay_vai_tro và get_role luôn trả cùng một vai trò
    return user  # trả User vừa tạo cho view


def gui_email_dang_ky_thanh_cong(user, link_dang_nhap):  # gửi email báo đăng ký thành công
    tieu_de = 'Đăng ký tài khoản FRAMIE thành công'  # tiêu đề email
    noi_dung = (  # nội dung email dạng chữ thường, KHÔNG ghi mật khẩu
        f'Xin chào {user.get_full_name()},\n\n'  # lời chào kèm họ tên
        'Tài khoản Khách hàng của bạn trên FRAMIE đã được tạo thành công.\n'  # nội dung chính
        f'Bạn đăng nhập bằng email {user.email} tại: {link_dang_nhap}\n\n'  # nhắc email đăng nhập và đường dẫn
        'Nếu bạn không thực hiện đăng ký này, vui lòng bỏ qua email.\n\n'  # phòng trường hợp người khác dùng email của bạn
        'FRAMIE'  # chữ ký
    )  # hết nội dung
    try:  # bọc lại vì máy chủ email có thể lỗi, mà tài khoản thì đã tạo xong
        send_mail(tieu_de, noi_dung, None, [user.email])  # None = dùng DEFAULT_FROM_EMAIL; người nhận là email vừa đăng ký
    except Exception:  # noqa: BLE001  # bắt mọi lỗi gửi (mất mạng, sai cấu hình SMTP...)
        logger.exception('Gửi email đăng ký thất bại (%s)', user.email)  # ghi lỗi đầy đủ ra Terminal để sửa
        return False  # báo không gửi được nhưng KHÔNG làm hỏng việc đăng ký
    return True  # gửi thành công

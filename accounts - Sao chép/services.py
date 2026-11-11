# =====================================================================
# accounts/services.py  -  P4: hàm tạo tài khoản và gửi email đăng ký (Phanh)
# P5 (đăng ký Nhiếp ảnh gia) gọi lại chính hàm tao_tai_khoan, chỉ đổi tham số vai_tro.
# =====================================================================
import logging  # ghi cảnh báo ra Terminal khi gửi email lỗi, thay vì làm sập trang đăng ký
import secrets  # sinh số ngẫu nhiên an toàn cho mã xác thực (random thường có thể đoán được)
from datetime import timedelta  # khoảng thời gian, dùng cho hiệu lực 10 phút của mã

from django.core import signing  # ký và kiểm tra chữ ký token (chống sửa link, có hạn dùng)
from django.contrib.auth.models import Group  # bảng nhóm quyền của Django (vai trò)
from django.core.mail import send_mail  # hàm gửi email; khi làm thử chỉ in ra Terminal (xem MAILERS trong settings.py)
from django.db import transaction  # transaction.atomic: tạo User và gán nhóm là một khối, lỗi thì hoàn tác cả hai
from django.utils import timezone  # giờ hiện tại có múi giờ (USE_TZ=True trong settings.py)

from core.constants import TrangThaiDatLaiMatKhau as TT, VaiTro  # tên vai trò và 4 trạng thái lượt yêu cầu; đặt tên ngắn TT cho dễ viết

from .models import User, YeuCauDatLaiMatKhau  # model User và model lượt yêu cầu đặt lại mật khẩu

logger = logging.getLogger(__name__)  # bộ ghi log riêng cho file này


def tach_ho_ten(ho_ten):  # tách "Nguyễn Văn An" thành ("An", "Nguyễn Văn") theo Data Dictionary
    ho_ten = ' '.join(ho_ten.split())  # gộp khoảng trắng thừa, bỏ khoảng trắng hai đầu
    phan = ho_ten.rsplit(maxsplit=1)  # cắt tại khoảng trắng CUỐI CÙNG: phần cuối là tên, phần trước là họ và tên đệm
    if not phan:  # chuỗi rỗng hoặc toàn khoảng trắng
        return '', ''  # không có tên, không có họ
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


# =====================================================================
# P6 (UC7.5 Quên mật khẩu): các hàm xử lý lượt yêu cầu đặt lại mật khẩu
# =====================================================================
HIEU_LUC_MA = timedelta(minutes=10)  # mã có hiệu lực tối đa 10 phút (BR7.5-5)
KQ_DUNG = 'dung'  # kết quả xác thực: mã đúng
KQ_SAI = 'sai'  # kết quả xác thực: mã sai
KQ_HET_HAN = 'het_han'  # kết quả xác thực: mã quá 10 phút
KQ_KHONG_CON_HIEU_LUC = 'khong_con_hieu_luc'  # kết quả xác thực: lượt này không còn ở trạng thái Chờ xác thực


def tao_yeu_cau_dat_lai(user):  # tạo lượt yêu cầu mới kèm mã 6 chữ số
    with transaction.atomic():  # đóng lượt cũ và tạo lượt mới là một khối
        user.yeu_cau_dat_lai_mat_khau.filter(  # các lượt trước của chính User này (related_name khai báo trong models.py)
            TrangThai__in=[TT.CHO_XAC_THUC, TT.DA_XAC_THUC],  # lượt còn dang dở
        ).update(TrangThai=TT.HET_HAN)  # cho hết hạn hết: mỗi lúc chỉ có MỘT mã còn dùng được
        return YeuCauDatLaiMatKhau.objects.create(  # tạo lượt mới (TrangThai mặc định là Chờ xác thực, ThoiDiemGui Django tự điền)
            MaTaiKhoan=user,  # lượt này của User nào
            OtpXacThuc=f'{secrets.randbelow(1_000_000):06d}',  # số ngẫu nhiên từ 0 đến 999999, thêm số 0 phía trước cho đủ 6 chữ số
            ThoiDiemHetHan=timezone.now() + HIEU_LUC_MA,  # hết hạn sau 10 phút
        )  # hết tạo lượt


def danh_dau_het_han(yeu_cau):  # chuyển một lượt sang Hết hạn
    yeu_cau.TrangThai = TT.HET_HAN  # đổi trạng thái
    yeu_cau.save(update_fields=['TrangThai'])  # chỉ lưu đúng cột này


def gui_email_ma_dat_lai(user, ma):  # gửi mã 6 chữ số tới email của User
    tieu_de = 'Mã xác thực đặt lại mật khẩu FRAMIE'  # tiêu đề email
    noi_dung = (  # nội dung email dạng chữ thường
        f'Xin chào {user.get_full_name()},\n\n'  # lời chào kèm họ tên
        f'Mã xác thực để đặt lại mật khẩu FRAMIE của bạn là: {ma}\n'  # mã 6 chữ số
        'Mã có hiệu lực trong 10 phút. Không chia sẻ mã này cho bất kỳ ai.\n\n'  # nhắc hiệu lực và bảo mật
        'Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này, mật khẩu của bạn không thay đổi.\n\n'  # phòng trường hợp người khác nhập nhầm email của bạn
        'FRAMIE'  # chữ ký
    )  # hết nội dung
    try:  # bọc lại vì máy chủ email có thể lỗi
        send_mail(tieu_de, noi_dung, None, [user.email])  # None = dùng DEFAULT_FROM_EMAIL
    except Exception:  # noqa: BLE001  # bắt mọi lỗi gửi (mất mạng, sai cấu hình SMTP...)
        logger.exception('Gửi mã đặt lại mật khẩu thất bại (%s)', user.email)  # ghi lỗi đầy đủ ra Terminal để sửa
        return False  # view sẽ báo lỗi cho người dùng, KHÔNG được báo "đã gửi" vì không có mã thì họ không đi tiếp được
    return True  # gửi thành công


def con_hieu_luc(yeu_cau):  # lượt này đã quá 10 phút chưa
    return timezone.now() <= yeu_cau.ThoiDiemHetHan  # True nếu còn trong hạn


def xac_thuc_ma(yeu_cau, ma_nhap):  # kiểm tra mã người dùng nhập, trả về một trong 4 hằng KQ_...
    bay_gio = timezone.now()  # lấy giờ MỘT lần để các phép so sánh bên dưới nhất quán
    if yeu_cau.TrangThai != TT.CHO_XAC_THUC:  # lượt đã xác thực, đã dùng xong hoặc đã hết hạn
        return KQ_KHONG_CON_HIEU_LUC  # không cho nhập mã nữa
    if bay_gio > yeu_cau.ThoiDiemHetHan:  # quá 10 phút
        danh_dau_het_han(yeu_cau)  # ghi trạng thái Hết hạn
        return KQ_HET_HAN  # báo hết hạn
    if not secrets.compare_digest(ma_nhap.encode(), yeu_cau.OtpXacThuc.encode()):  # so mã theo cách không lộ thông tin qua thời gian xử lý
        return KQ_SAI  # sai mã, giữ nguyên trạng thái Chờ xác thực
    yeu_cau.TrangThai = TT.DA_XAC_THUC  # nhập đúng mã
    yeu_cau.ThoiDiemXacThuc = bay_gio  # ghi giờ xác thực (ràng buộc CSDL: nằm giữa giờ gửi và giờ hết hạn)
    yeu_cau.save(update_fields=['TrangThai', 'ThoiDiemXacThuc'])  # chỉ lưu hai cột này
    return KQ_DUNG  # báo đúng


def dat_lai_mat_khau(yeu_cau, mat_khau_moi):  # đổi mật khẩu; trả True nếu đổi được, False nếu lượt không còn hợp lệ
    with transaction.atomic():  # đổi mật khẩu và ghi trạng thái là một khối
        yeu_cau = YeuCauDatLaiMatKhau.objects.select_for_update().get(pk=yeu_cau.pk)  # đọc lại dòng mới nhất từ CSDL, tránh dùng bản cũ khi bấm hai lần
        if yeu_cau.TrangThai != TT.DA_XAC_THUC:  # chưa xác thực mã, hoặc đã đặt lại rồi
            return False  # không đổi
        if not con_hieu_luc(yeu_cau):  # xác thực xong nhưng để quá hạn mới nhập mật khẩu
            danh_dau_het_han(yeu_cau)  # ghi trạng thái Hết hạn
            return False  # không đổi
        user = yeu_cau.MaTaiKhoan  # User cần đổi mật khẩu
        user.set_password(mat_khau_moi)  # băm mật khẩu mới, mật khẩu cũ không còn đăng nhập được
        user.save(update_fields=['password'])  # chỉ lưu cột password; các phiên đăng nhập cũ của User tự mất hiệu lực vì mã băm đã đổi
        yeu_cau.TrangThai = TT.DA_DAT_LAI  # lượt này đã hoàn tất
        yeu_cau.save(update_fields=['TrangThai'])  # chỉ lưu cột này
    return True  # đổi thành công


# =====================================================================
# Mời Quản trị viên mới: link có chữ ký + hạn dùng, KHÔNG cần model hay migration
# =====================================================================
SALT_LOI_MOI_QTV = 'accounts.loi_moi_quan_tri_vien'  # "muối" riêng: token này không dùng nhầm cho việc khác
HIEU_LUC_LOI_MOI_QTV = timedelta(hours=48)  # link mời có hiệu lực 48 giờ


class LoiMoiQuanTriKhongHopLe(Exception):  # lỗi tự đặt; nội dung là câu tiếng Việt hiện cho người mở link
    pass  # không cần thêm gì, chỉ cần có tên


def tao_token_loi_moi_qtv(email):  # tạo token chứa email người được mời, có chữ ký + giờ tạo
    return signing.dumps({'email': email.strip().lower()}, salt=SALT_LOI_MOI_QTV)  # ký bằng SECRET_KEY; token KHÔNG chứa mật khẩu


def doc_token_loi_moi_qtv(token, hieu_luc=None):  # kiểm tra token, trả về email; sai/hết hạn thì ném LoiMoiQuanTriKhongHopLe
    if hieu_luc is None:  # không truyền thì dùng hạn mặc định (đọc lúc gọi để test thay được)
        hieu_luc = HIEU_LUC_LOI_MOI_QTV  # 48 giờ
    try:  # giải mã và kiểm tra chữ ký + hạn
        du_lieu = signing.loads(token, salt=SALT_LOI_MOI_QTV, max_age=hieu_luc.total_seconds())  # max_age tính bằng giây
    except signing.SignatureExpired:  # chữ ký đúng nhưng quá hạn (phải bắt TRƯỚC BadSignature vì là lớp con)
        raise LoiMoiQuanTriKhongHopLe('Link mời đã hết hạn. Vui lòng nhờ Quản trị viên gửi lại lời mời.')  # báo hết hạn
    except signing.BadSignature:  # link bị sửa, cắt thiếu hoặc không phải token của hệ thống
        raise LoiMoiQuanTriKhongHopLe('Link mời không hợp lệ. Vui lòng mở đúng link trong email mời.')  # báo không hợp lệ
    email = du_lieu.get('email') if isinstance(du_lieu, dict) else None  # lấy email trong token
    if not email:  # token đúng chữ ký nhưng thiếu email (không xảy ra với token do hệ thống tạo)
        raise LoiMoiQuanTriKhongHopLe('Link mời không hợp lệ. Vui lòng mở đúng link trong email mời.')  # báo không hợp lệ
    return email  # email người được mời


def gui_email_loi_moi_qtv(email, link, nguoi_moi):  # gửi mail mời; True nếu gửi được, False nếu lỗi (view sẽ hiện link cho admin gửi tay)
    gio = int(HIEU_LUC_LOI_MOI_QTV.total_seconds() // 3600)  # số giờ hiệu lực, để câu chữ luôn khớp hằng số
    tieu_de = 'Lời mời làm Quản trị viên FRAMIE'  # tiêu đề email
    noi_dung = (  # nội dung dạng chữ thường, KHÔNG ghi mật khẩu
        'Xin chào,\n\n'  # lời chào (chưa có họ tên vì người nhận chưa có tài khoản)
        f'{nguoi_moi.get_full_name() or nguoi_moi.email} mời bạn làm Quản trị viên của FRAMIE.\n'  # ai mời
        f'Mở link sau để tạo tài khoản (link dùng được một lần, có hiệu lực {gio} giờ):\n{link}\n\n'  # link đăng ký
        'Nếu bạn không mong đợi lời mời này, vui lòng bỏ qua email.\n\n'  # phòng trường hợp gửi nhầm
        'FRAMIE'  # chữ ký
    )  # hết nội dung
    try:  # bọc lại vì máy chủ email có thể lỗi
        send_mail(tieu_de, noi_dung, None, [email])  # None = dùng DEFAULT_FROM_EMAIL
    except Exception:  # noqa: BLE001  # bắt mọi lỗi gửi (mất mạng, sai cấu hình SMTP...)
        logger.exception('Gửi email mời Quản trị viên thất bại (%s)', email)  # ghi lỗi đầy đủ ra Terminal
        return False  # view sẽ hiện link để admin copy gửi tay
    return True  # gửi thành công
